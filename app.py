"""
Shorts downloader — a thin, self-hosted wrapper around yt-dlp.

Run:  uvicorn app:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# --- Config ------------------------------------------------------------------

MAX_DURATION_SEC = int(os.getenv("MAX_DURATION_SEC", "600"))
JOB_TTL_SEC = int(os.getenv("JOB_TTL_SEC", "1800"))
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "3"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "10"))
COOKIE_FILE = os.getenv("COOKIE_FILE")  # optional: path to a Netscape cookies.txt

WORK_ROOT = Path(tempfile.gettempdir()) / "shortsdl"
WORK_ROOT.mkdir(exist_ok=True)

VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
YT_HOSTS = {"youtube.com", "youtube-nocookie.com", "youtu.be"}

app = FastAPI(title="Shorts downloader")

# --- URL handling ------------------------------------------------------------


def video_id_from(url: str) -> str | None:
    """Pull the 11-char id out of any YouTube URL shape. Returns None otherwise.

    Rebuilding a canonical URL from the id is what keeps arbitrary user input
    from ever reaching yt-dlp — no query params, no other hosts, no shell.
    """
    try:
        u = urlparse(url.strip())
    except ValueError:
        return None
    if u.scheme not in ("http", "https"):
        return None

    host = u.netloc.lower().split(":")[0]
    for prefix in ("www.", "m.", "music."):
        host = host.removeprefix(prefix)
    if host not in YT_HOSTS:
        return None

    parts = [p for p in u.path.split("/") if p]
    candidate = ""
    if host == "youtu.be":
        candidate = parts[0] if parts else ""
    elif parts and parts[0] in ("shorts", "embed", "v", "live"):
        candidate = parts[1] if len(parts) > 1 else ""
    elif u.path == "/watch":
        candidate = parse_qs(u.query).get("v", [""])[0]

    return candidate if VIDEO_ID.fullmatch(candidate) else None


def canonical(vid: str) -> str:
    return f"https://www.youtube.com/watch?v={vid}"


# --- Rate limiting -----------------------------------------------------------

_hits: dict[str, deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()


def check_rate(ip: str) -> None:
    now = time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT_PER_MIN:
            raise HTTPException(429, "Too many requests. Wait a minute and try again.")
        q.append(now)


# --- Job store ---------------------------------------------------------------


class Job:
    def __init__(self, vid: str, kind: str) -> None:
        self.id = uuid.uuid4().hex
        self.vid = vid
        self.kind = kind
        self.state: Literal["queued", "running", "done", "error"] = "queued"
        self.percent = 0.0
        self.speed: str | None = None
        self.eta: int | None = None
        self.error: str | None = None
        self.path: Path | None = None
        self.created = time.time()
        self.dir = WORK_ROOT / self.id

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "percent": round(self.percent, 1),
            "speed": self.speed,
            "eta": self.eta,
            "error": self.error,
            "filename": self.path.name if self.path else None,
        }


JOBS: dict[str, Job] = {}
_sem = threading.Semaphore(MAX_CONCURRENT)


def base_opts(job_dir: Path) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": False,
        "restrictfilenames": True,
        "outtmpl": str(job_dir / "%(title).80s [%(id)s].%(ext)s"),
        "retries": 3,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 4,
    }
    if COOKIE_FILE:
        opts["cookiefile"] = COOKIE_FILE
    return opts


FORMATS = {
    # Shorts are usually AVC/AAC; prefer a muxable mp4 pair, fall back to whatever exists.
    "video": {
        "format": "bv*[ext=mp4][vcodec^=avc1]+ba[ext=m4a]/bv*+ba/b[ext=mp4]/b",
        "merge_output_format": "mp4",
    },
    "audio": {
        "format": "ba[ext=m4a]/ba/b",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ],
    },
}


def run_job(job: Job) -> None:
    with _sem:
        job.state = "running"
        job.dir.mkdir(parents=True, exist_ok=True)

        def hook(d: dict[str, Any]) -> None:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                if total:
                    job.percent = min(99.0, d.get("downloaded_bytes", 0) / total * 100)
                job.speed = d.get("_speed_str", "").strip() or None
                job.eta = d.get("eta")
            elif d["status"] == "finished":
                job.percent = 99.0
                job.speed = None

        opts = {**base_opts(job.dir), **FORMATS[job.kind], "progress_hooks": [hook]}

        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([canonical(job.vid)])
            files = [p for p in job.dir.iterdir() if p.is_file() and not p.name.endswith(".part")]
            if not files:
                raise RuntimeError("yt-dlp finished but produced no file.")
            job.path = max(files, key=lambda p: p.stat().st_size)
            job.percent = 100.0
            job.state = "done"
        except DownloadError as e:
            job.state, job.error = "error", friendly(str(e))
        except Exception as e:  # noqa: BLE001
            job.state, job.error = "error", f"Unexpected failure: {e}"


def friendly(msg: str) -> str:
    low = msg.lower()
    if "confirm you're not a bot" in low or "sign in to confirm" in low:
        return (
            "YouTube blocked this server's IP. Supply a cookies.txt via COOKIE_FILE, "
            "or run this from a residential connection."
        )
    if "private video" in low:
        return "That video is private."
    if "video unavailable" in low:
        return "That video is unavailable or region-blocked."
    if "age" in low and "restrict" in low:
        return "That video is age-restricted and needs signed-in cookies."
    return re.sub(r"^ERROR:\s*", "", msg.splitlines()[0])[:200]


# --- API ---------------------------------------------------------------------


class UrlIn(BaseModel):
    url: str


class JobIn(UrlIn):
    kind: Literal["video", "audio"] = "video"


@app.post("/api/info")
async def info(body: UrlIn, request: Request) -> dict[str, Any]:
    check_rate(request.client.host if request.client else "?")
    vid = video_id_from(body.url)
    if not vid:
        raise HTTPException(400, "That doesn't look like a YouTube link.")

    def probe() -> dict[str, Any]:
        with YoutubeDL({**base_opts(WORK_ROOT), "skip_download": True}) as ydl:
            return ydl.extract_info(canonical(vid), download=False)

    try:
        meta = await asyncio.to_thread(probe)
    except DownloadError as e:
        raise HTTPException(502, friendly(str(e))) from e

    duration = meta.get("duration") or 0
    if duration > MAX_DURATION_SEC:
        raise HTTPException(413, f"Video is longer than the {MAX_DURATION_SEC // 60} minute limit.")

    width, height = meta.get("width") or 0, meta.get("height") or 0
    return {
        "id": vid,
        "title": meta.get("title"),
        "uploader": meta.get("uploader"),
        "duration": duration,
        "thumbnail": meta.get("thumbnail"),
        "vertical": bool(height and width and height > width),
        "resolution": f"{width}x{height}" if width and height else None,
        "filesize": meta.get("filesize_approx"),
    }


@app.post("/api/jobs")
async def create_job(body: JobIn, request: Request) -> dict[str, Any]:
    check_rate(request.client.host if request.client else "?")
    vid = video_id_from(body.url)
    if not vid:
        raise HTTPException(400, "That doesn't look like a YouTube link.")
    job = Job(vid, body.kind)
    JOBS[job.id] = job
    threading.Thread(target=run_job, args=(job,), daemon=True).start()
    return job.public()


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "No such job — it may have expired.")
    return job.public()


@app.get("/api/jobs/{job_id}/file")
async def job_file(job_id: str) -> FileResponse:
    job = JOBS.get(job_id)
    if not job or job.state != "done" or not job.path or not job.path.exists():
        raise HTTPException(404, "File isn't ready.")
    return FileResponse(job.path, filename=job.path.name, media_type="application/octet-stream")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (Path(__file__).parent / "index.html").read_text(encoding="utf-8")


# --- Housekeeping ------------------------------------------------------------


async def reap() -> None:
    while True:
        await asyncio.sleep(120)
        cutoff = time.time() - JOB_TTL_SEC
        for jid, job in list(JOBS.items()):
            if job.created < cutoff:
                shutil.rmtree(job.dir, ignore_errors=True)
                JOBS.pop(jid, None)


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(reap())
