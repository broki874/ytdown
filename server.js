const express = require('express');
const app = express();

app.use(express.json());
app.use(express.static('public'));

// Root route
app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/index.html');
});

app.post('/info', async (req, res) => {
  const { url } = req.body;
  try {
    const response = await fetch('https://api.cobalt.tools/api/json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await response.json();
    res.json(data);
  } catch (e) {
    res.status(500).json({ error: 'Service unavailable. Try again later.' });
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
    if (data.url) {
      res.redirect(data.url);
    } else {
      res.send('Download not available');
    }
  } catch (e) {
    res.send('Error');
  }
});

module.exports = app;
