const express = require('express');
const fetch = require('node-fetch');
const app = express();

app.use(express.static('public'));
app.use(express.json());

app.post('/info', async (req, res) => {
  try {
    const { url } = req.body;
    const response = await fetch('https://api.cobalt.tools/api/json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: 'Service unavailable' });
  }
});

app.get('/download', async (req, res) => {
  const { url } = req.query;
  try {
    const response = await fetch('https://api.cobalt.tools/api/json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await response.json();
    if (data.url) res.redirect(data.url);
    else res.send('Try again');
  } catch (e) {
    res.send('Download failed');
  }
});

const port = process.env.PORT || 3000;
app.listen(port);