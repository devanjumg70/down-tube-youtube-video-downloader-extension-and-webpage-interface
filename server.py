from flask import Flask, request, jsonify, redirect
from yt_dlp import YoutubeDL
import re
from flask_cors import CORS

app = Flask(__name__)

# Enable CORS with more specific configuration
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "expose_headers": "*"}})

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response

# Clean input to extract video ID
def extract_video_id(url):
    match = re.search(r"(?:v=|youtu\.be/)([\w\-]{11})", url)
    return match.group(1) if match else url  # fallback to direct ID

@app.route("/api/info")
def get_video_info():
    video_id = extract_video_id(request.args.get("videoId", ""))
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    print(f"Received info request for video ID: {video_id}")
    print(f"Request headers: {dict(request.headers)}")
    
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
    video_id = request.args.get("videoId")
    itag = request.args.get("itag")
    
    if not video_id or not itag:
        return jsonify({"error": "Missing video ID or format ID"}), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        "quiet": True,
        "format": itag,
        "skip_download": True,
        "forcejson": True,
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Find the requested format
            format_url = None
            for f in info.get("formats", []):
                if f.get("format_id") == itag:
                    format_url = f.get("url")
                    break
            
            if format_url:
                return redirect(format_url)
            else:
                return jsonify({"error": "Format not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def hello():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Downloader API Test</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f8f8f8; }
            h1 { color: #c00; text-align: center; }
            .form-group { margin-bottom: 15px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            input[type="text"] { width: 70%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
            button { padding: 10px 20px; background: #c00; color: white; border: none; cursor: pointer; border-radius: 4px; }
            button:hover { background: #a00; }
            #result { margin-top: 20px; padding: 20px; border-radius: 8px; background: white; min-height: 100px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
            pre { white-space: pre-wrap; background: #f5f5f5; padding: 10px; border-radius: 4px; }
            .video-info { display: flex; flex-direction: column; align-items: center; }
            .video-thumbnail { max-width: 320px; margin: 10px 0; border-radius: 4px; }
            .download-buttons { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 15px; }
            .download-btn { padding: 8px 15px; background: #2a76dd; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .download-btn:hover { background: #1c5bb9; }
        </style>
    </head>
    <body>
        <h1>YouTube Downloader API Test</h1>
        <p>This page allows you to test the YouTube Downloader API directly.</p>
        
        <div class="form-group">
            <label>YouTube Video ID or URL:</label><br>
            <input type="text" id="videoInput" placeholder="e.g., dQw4w9WgXcQ or https://www.youtube.com/watch?v=dQw4w9WgXcQ">
            <button id="testBtn">Test API</button>
        </div>
        
        <div id="result">
            <p>Results will appear here...</p>
        </div>
        
        <script>
            document.getElementById('testBtn').addEventListener('click', async () => {
                const input = document.getElementById('videoInput').value.trim();
                const resultDiv = document.getElementById('result');
                
                if (!input) {
                    resultDiv.innerHTML = '<p style="color: red;">Please enter a YouTube Video ID or URL</p>';
                    return;
                }
                
                resultDiv.innerHTML = '<div style="text-align: center; padding: 20px;"><div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid #c00; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div><p>Loading video information...</p></div>';
                
                try {
                    // Simple extraction of video ID from URL
                    let videoId = input;
                    if (input.includes('watch?v=')) {
                        const match = input.match(/[\\?&]v=([^&#]*)/);
                        if (match && match[1]) {
                            videoId = match[1];
                        }
                    } else if (input.includes('youtu.be/')) {
                        const match = input.match(/youtu\\.be\\/(.*?)(?:\\?|$)/);
                        if (match && match[1]) {
                            videoId = match[1];
                        }
                    }
                    
                    const response = await fetch(`/api/info?videoId=${encodeURIComponent(videoId)}`);
                    const data = await response.json();
                    
                    if (data.error) {
                        resultDiv.innerHTML = `
                            <div style="color: red; text-align: center;">
                                <h3>Error</h3>
                                <p>${data.error}</p>
                            </div>
                        `;
                        return;
                    }
                    
                    // Create a nicer display of the video info
                    let formatsHtml = '';
                    if (data.formats && data.formats.length > 0) {
                        formatsHtml = '<div class="download-buttons">';
                        data.formats.forEach(format => {
                            formatsHtml += `
                                <a 
                                    href="/api/download?videoId=${encodeURIComponent(videoId)}&itag=${format.itag}" 
                                    class="download-btn" 
                                    target="_blank"
                                >
                                    Download ${format.qualityLabel} (${format.container})
                                </a>
                            `;
                        });
                        formatsHtml += '</div>';
                    }
                    
                    resultDiv.innerHTML = `
                        <div class="video-info">
                            <h2>${data.title || 'Unknown Title'}</h2>
                            <p>${data.channel || 'Unknown Channel'}</p>
                            <img src="${data.thumbnail}" alt="Video thumbnail" class="video-thumbnail">
                            <h3>Available Download Options:</h3>
                            ${formatsHtml || '<p>No download options available</p>'}
                        </div>
                        <div style="margin-top: 20px;">
                            <details>
                                <summary>Show Raw API Response</summary>
                                <pre>${JSON.stringify(data, null, 2)}</pre>
                            </details>
                        </div>
                    `;
                } catch (error) {
                    resultDiv.innerHTML = `
                        <div style="color: red; text-align: center;">
                            <h3>Error</h3>
                            <p>${error.message}</p>
                        </div>
                    `;
                }
            });
            
            // Add keyboard event listener for Enter key
            document.getElementById('videoInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    document.getElementById('testBtn').click();
                }
            });
            
            // Style for the spinner animation
            const style = document.createElement('style');
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            `;
            document.head.appendChild(style);
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    # Use port 5000 by default (Replit's standard publicly accessible port)
    port = 5000
    print(f"YouTube Downloader API Server running on port {port}")
    app.run(host="0.0.0.0", port=port)