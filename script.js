const API_TOKEN = "apify_api_LRRJCsTnevcCF1n774YJprY2ZzD8dg3AUFWR";
const ACTOR = "easyapi/youtube-shorts-downloader";   // Best for Shorts

document.getElementById("downloadBtn").addEventListener("click", async () => {
  const url = document.getElementById("urlInput").value.trim();
  const status = document.getElementById("status");
  const resultDiv = document.getElementById("result");

  if (!url.includes("youtube.com/shorts")) {
    status.textContent = "❌ Please enter a valid YouTube Shorts URL";
    return;
  }

  status.textContent = "🚀 Starting download...";
  resultDiv.innerHTML = "";

  try {
    const response = await fetch(`https://api.apify.com/v2/acts/${ACTOR}/runs?token=${API_TOKEN}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ links: [url] })
    });

    const data = await response.json();
    const runId = data.data.id;

    status.textContent = "⏳ Processing... (this may take 10-30 seconds)";

    // Poll for result
    let attempts = 0;
    const poll = setInterval(async () => {
      attempts++;
      const runRes = await fetch(`https://api.apify.com/v2/acts/${ACTOR}/runs/${runId}?token=${API_TOKEN}`);
      const runData = await runRes.json();

      if (runData.data.status === "SUCCEEDED") {
        clearInterval(poll);
        status.textContent = "✅ Ready!";

        const itemsRes = await fetch(`https://api.apify.com/v2/acts/${ACTOR}/runs/${runId}/dataset/items?token=${API_TOKEN}`);
        const items = await itemsRes.json();

        if (items && items.length > 0) {
          const downloadUrl = items[0].downloadUrl || items[0].directDownloadUrl || "#";
          resultDiv.innerHTML = `
            <p><strong>Title:</strong> ${items[0].title || "YouTube Short"}</p>
            <a href="${downloadUrl}" target="_blank" download>⬇️ Download MP4</a>
          `;
        }
      } else if (runData.data.status === "FAILED" || attempts > 30) {
        clearInterval(poll);
        status.textContent = "❌ Failed. Try again.";
      }
    }, 5000);

  } catch (err) {
    status.textContent = "❌ Error: " + err.message;
  }
});
