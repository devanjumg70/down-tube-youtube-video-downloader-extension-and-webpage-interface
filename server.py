from flask import Flask, request, jsonify, redirect
from yt_dlp import YoutubeDL
import re
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes to allow the extension to access the API

# Clean input to extract video ID
def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([\w\-]{11})", url)
    return match.group(1) if match else url  # fallback to direct ID

@app.route("/api/info")
def get_video_info():
    video_id = extract_video_id(request.args.get("videoId", ""))
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "forcejson": True,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Filter formats to include only desired resolutions
            formats = []
            seen_qualities = set()
            
            for f in info["formats"]:
                # Skip formats without video or non-MP4 formats unless audio-only
                if f["ext"] != "mp4" and f["ext"] != "m4a":
                    continue
                    
                # Process audio-only formats
                if f["ext"] == "m4a" and f.get("format_note") and "audio" in f.get("format_note").lower():
                    if "audio" not in seen_qualities:
                        formats.append({
                            "itag": f["format_id"],
                            "qualityLabel": "Audio Only",
                            "container": "mp3",  # User-friendly label for audio
                            "url": f["url"]
                        })
                        seen_qualities.add("audio")
                
                # Process video formats
                if f["ext"] == "mp4" and f.get("height") in [360, 480, 720, 1080]:
                    quality = f"{f['height']}p"
                    if quality not in seen_qualities:
                        formats.append({
                            "itag": f["format_id"],
                            "qualityLabel": quality,
                            "container": "mp4",
                            "url": f["url"]
                        })
                        seen_qualities.add(quality)
            
            # Sort formats by quality (higher resolution first)
            formats.sort(key=lambda x: 1080 if x["qualityLabel"] == "Audio Only" else 
                         int(x["qualityLabel"].replace("p", "")), reverse=True)
            
            return jsonify({
                "title": info.get("title", "YouTube Video"),
                "channel": info.get("uploader", "YouTube Channel"),
                "thumbnail": info.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                "formats": formats
            })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/download")
def download():
    video_url = request.args.get("url")
    if video_url:
        return redirect(video_url)
    return "Invalid URL", 400

@app.route("/")
def hello():
    return "YouTube Downloader Backend Running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)