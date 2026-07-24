const express = require('express');
const app = express();

app.use(express.json());
app.use(express.static('public'));

app.get('/', (req, res) => res.sendFile(__dirname + '/public/index.html'));

app.post('/info', async (req, res) => {
  const { url } = req.body;
  try {
    // Use Piped API
    const videoId = url.split('v=')[1] || url.split('/').pop();
    const response = await fetch(`https://pipedapi.kavin.rocks/streams/${videoId}`);
    const data = await response.json();
    
    res.json({
      title: data.title,
      formats: data.streams.filter(s => s.videoOnly === false).map(s => ({
        url: s.url,
        quality: s.quality,
        format: s.format
      }))
    });
  } catch (e) {
    res.status(500).json({ error: 'API Error' });
  }
});

module.exports = app;
