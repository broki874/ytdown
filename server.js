const express = require('express');
const fetch = require('node-fetch');
const app = express();

app.use(express.static('public'));
app.use(express.json());

// Important: Add this for Vercel
app.get('/', (req, res) => {
  res.sendFile(__dirname + '/public/index.html');
});
