# Vertical — a self-hosted YouTube Shorts downloader

A thin wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp): FastAPI backend,
job queue, single-page frontend. No third-party download service in the path.

## Run it

```bash
pip install -r requirements.txt
# ffmpeg must be on PATH — it merges the separate video and audio streams
uvicorn app:app --port 8000
```

Open http://127.0.0.1:8000

## How it works

| Endpoint | Purpose |
|---|---|
| `POST /api/info` | Metadata only, no download |
| `POST /api/jobs` | Start a job, returns an id. `kind`: `video` \| `audio` |
| `GET /api/jobs/{id}` | `{state, percent, speed, eta, error}` |
| `GET /api/jobs/{id}/file` | The finished file |

Shorts need no special handling — `youtube.com/shorts/<id>` is an ordinary video
as far as yt-dlp is concerned. Only the frontend cares that the output is 9:16.

Downloads run on worker threads with a semaphore cap, so a slow job never blocks
the event loop and ten simultaneous users can't spawn ten yt-dlp processes.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `MAX_DURATION_SEC` | 600 | Reject anything longer |
| `MAX_CONCURRENT` | 3 | Simultaneous yt-dlp processes |
| `RATE_LIMIT_PER_MIN` | 10 | Requests per IP per minute |
| `JOB_TTL_SEC` | 1800 | How long finished files survive on disk |
| `COOKIE_FILE` | unset | Path to a Netscape `cookies.txt` |

## The part that will actually bite you

Locally this works out of the box. On a VPS it will start failing within days
with "Sign in to confirm you're not a bot" — YouTube treats datacenter IP ranges
as hostile. Options, roughly in order of how well they hold up:

1. Run it on a residential connection (a home box, a Raspberry Pi).
2. Export cookies from a signed-in browser and set `COOKIE_FILE`. Use a throwaway
   Google account — those cookies are a live session for whatever account made them.
3. Route through residential proxies (yt-dlp's `proxy` option).

That third item is exactly what hosted services sell. It's the whole business.

Keep yt-dlp on a recent version. Extractors break when YouTube ships changes and
fixes land quickly; a stale pin is the single most common cause of "it worked
last month."

## Security notes

- User input never reaches yt-dlp verbatim. The URL is parsed, the 11-character
  video id extracted, and a canonical URL rebuilt from it. Non-YouTube hosts,
  `file://` schemes, and path traversal are rejected before anything runs.
- yt-dlp is called through its Python API, never a shell.
- Each job writes to its own temp directory, reaped after `JOB_TTL_SEC`.
- If you expose this publicly, put it behind auth. An open downloader is an open
  proxy — it will be found, and it will be used to move things you didn't intend.

## Legality

Downloading is against YouTube's Terms of Service. Personal copies sit in a grey
area that varies by country; redistributing what you download generally does not.
Running a public instance makes you the operator, with whatever that implies
where you are.
