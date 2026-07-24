app.post('/info', async (req, res) => {
  const { url } = req.body;
  try {
    const response = await fetch('https://api.cobalt.tools/api/json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        url: url,
        isAudioOnly: false,
        filenameStyle: "pretty",
        dubLang: false
      })
    });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: 'Service unavailable' });
  }
});
