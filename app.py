from flask import Flask, request, send_file, render_template_string
import yt_dlp
import os

app = Flask(__name__)

HTML = '''
<!DOCTYPE html>
<html>
<head>
<title>YouTube Downloader</title>
<style>body{font-family:Arial;text-align:center;padding:50px;} input{width:70%;padding:15px;} button{padding:15px 30px;background:red;color:white;border:none;font-size:18px;}</style>
</head>
<body>
<h1>🎥 YouTube Video Downloader</h1>
<form method="POST">
  <input type="text" name="url" placeholder="Paste YouTube URL" required>
  <button type="submit">Download</button>
</form>
</body>
</html>
'''

@app.route('/', methods=['GET', 'POST'])
def home():
  if request.method == 'POST':
    url = request.form['url']
    try:
      ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s', 'format': 'best'}
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
      return "Download started! Check your downloads folder."
    except Exception as e:
      return f"Error: {str(e)}"
  return render_template_string(HTML)

if __name__ == '__main__':
  os.makedirs('downloads', exist_ok=True)
  app.run(host='0.0.0.0', port=5000)
