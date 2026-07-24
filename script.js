document.getElementById("downloadBtn").addEventListener("click", async () => {
  const urlInput = document.getElementById("urlInput").value.trim();
  const status = document.getElementById("status");
  const resultDiv = document.getElementById("result");

  if (!urlInput.includes("youtube.com/shorts")) {
    status.textContent = "❌ Please enter a valid YouTube Shorts URL";
    return;
  }

  status.textContent = "🚀 Starting...";
  resultDiv.innerHTML = "";

  try {
    const response = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: urlInput })
    });

    const result = await response.json();

    if (result.success && result.data) {
      status.textContent = "✅ Success!";
      const dlUrl = result.data.downloadUrl || result.data.directDownloadUrl || "#";
      resultDiv.innerHTML = `
        <p><strong>${result.data.title || "YouTube Short"}</strong></p>
        <a href="${dlUrl}" target="_blank" download>⬇️ Download Video</a>
      `;
    } else {
      status.textContent = "❌ " + (result.error || "Something went wrong");
    }
  } catch (err) {
    status.textContent = "❌ Network error. Try again.";
    console.error(err);
  }
});
