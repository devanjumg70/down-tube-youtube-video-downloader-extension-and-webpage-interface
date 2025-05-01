from flask import Flask, jsonify, request, redirect, send_file, Response
from yt_dlp import YoutubeDL
from flask_cors import CORS
import os
import tempfile
import logging
import time
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "expose_headers": "*"}})

# Temp directory for downloaded files
TEMP_DIR = tempfile.gettempdir()

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response

def extract_video_id(url):
    """Extract the video ID from a YouTube URL or return the ID if it's already an ID"""
    if "/" in url or "youtu" in url:
        from urllib.parse import urlparse, parse_qs
        
        # Handle youtu.be URLs
        if "youtu.be" in url:
            return url.split("/")[-1].split("?")[0]
        
        # Handle regular youtube.com URLs
        query = parse_qs(urlparse(url).query)
        return query.get("v", [url])[0]
    
    return url  # Already an ID

@app.route("/api/info")
def get_video_info():
    video_id = request.args.get("videoId")
    
    if not video_id:
        return jsonify({"error": "Missing video ID"}), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    logger.info(f"Received info request for video ID: {video_id}")
    logger.info(f"Request headers: {dict(request.headers)}")
    
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "forcejson": True,
        "format": "best", # Request best format with both video and audio
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Extracting info for {url}")
            info = ydl.extract_info(url, download=False)
            
            # Filter formats to include only desired resolutions
            formats = []
            seen_qualities = set()
            
            # Log available formats for debugging
            logger.info(f"Total formats available: {len(info['formats'])}")
            for f in info["formats"]:
                logger.debug(f"Format: {f.get('format_id')} - {f.get('ext')} - {f.get('height')}p - Audio: {'yes' if f.get('acodec') != 'none' else 'no'}")
            
            # First add combined formats that include both video and audio
            for f in info["formats"]:
                # Look for formats that have both video and audio
                if f.get("vcodec") != "none" and f.get("acodec") != "none":
                    if f.get("height") in [360, 480, 720, 1080]:
                        quality = f"{f['height']}p"
                        if quality not in seen_qualities:
                            formats.append({
                                "itag": f["format_id"],
                                "qualityLabel": f"{quality} (with audio)",
                                "container": f["ext"],
                                "url": f.get("url", ""),
                                "has_audio": True,
                                "has_video": True
                            })
                            seen_qualities.add(quality)
                            logger.info(f"Added combined format: {f['format_id']} - {quality}")
            
            # Then add video-only formats for higher quality options
            # (we'll combine with audio when downloading)
            for f in info["formats"]:
                if f["ext"] == "mp4" and f.get("height") in [360, 480, 720, 1080]:
                    quality = f"{f['height']}p"
                    # Only add if we don't already have this quality as a combined format
                    key = f"{quality}_video"
                    if key not in seen_qualities:
                        formats.append({
                            "itag": f["format_id"],
                            "qualityLabel": quality,
                            "container": "mp4",
                            "url": f.get("url", ""),
                            "has_audio": False,
                            "has_video": True
                        })
                        seen_qualities.add(key)
                        logger.info(f"Added video-only format: {f['format_id']} - {quality}")
            
            # Finally add audio-only format
            for f in info["formats"]:
                if f.get("vcodec") == "none" and f.get("acodec") != "none":
                    if "audio" not in seen_qualities:
                        formats.append({
                            "itag": f["format_id"],
                            "qualityLabel": "Audio Only",
                            "container": f["ext"],
                            "url": f.get("url", ""),
                            "has_audio": True,
                            "has_video": False
                        })
                        seen_qualities.add("audio")
                        logger.info(f"Added audio-only format: {f['format_id']}")
                        break  # Just take the first good audio format
            
            # Sort formats by quality (higher resolution first)
            formats.sort(key=lambda x: 0 if x["qualityLabel"] == "Audio Only" else 
                         int(x["qualityLabel"].replace("p", "").replace(" (with audio)", "")), 
                         reverse=True)
            
            logger.info(f"Returning {len(formats)} filtered formats for video: {info.get('title')}")
            
            return jsonify({
                "title": info.get("title", "YouTube Video"),
                "channel": info.get("uploader", "YouTube Channel"),
                "thumbnail": info.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                "formats": formats
            })
    except Exception as e:
        logger.error(f"Error extracting video info: {str(e)}")
        return jsonify({"error": str(e)})

@app.route("/api/download")
def download():
    video_id = request.args.get("videoId")
    itag = request.args.get("itag")
    
    if not video_id or not itag:
        return jsonify({"error": "Missing video ID or format ID"}), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Download request for video ID: {video_id}, format: {itag}")
    
    # Create a unique filename for this download
    file_id = str(uuid.uuid4())
    output_path = os.path.join(TEMP_DIR, f"youtube_{video_id}_{file_id}.mp4")
    
    # Set up options for yt-dlp
    ydl_opts = {
        "format": f"{itag}+bestaudio/best",  # Specified format + best audio, or best combined format
        "merge_output_format": "mp4",        # Force mp4 for compatibility
        "outtmpl": output_path,              # Output filename template
        "quiet": True,                       # Don't print progress
        "no_warnings": True,                 # Don't print warnings
        "progress_hooks": [lambda d: logger.info(f"Download progress: {d.get('status')} - {d.get('_percent_str', 'N/A')}")],
    }
    
    try:
        logger.info(f"Starting download with options: {ydl_opts}")
        with YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading {url}")
            info = ydl.extract_info(url, download=True)
            logger.info(f"Download completed: {output_path}")
            
            # Get video info for filename
            title = info.get('title', 'video').replace(' ', '_')
            # Sanitize filename
            title = "".join(c for c in title if c.isalnum() or c in [' ', '_', '-']).rstrip()
            
            # Check if the file was actually created
            if not os.path.exists(output_path):
                logger.error(f"Download failed: File not created at {output_path}")
                return jsonify({"error": "Download failed"}), 500
            
            # Log file size for debugging
            file_size = os.path.getsize(output_path)
            logger.info(f"File size: {file_size} bytes")
            
            # Stream the file to client and delete after sending
            @app.after_request
            def cleanup(response):
                # Clean up the temporary file after sending
                # Wait briefly to ensure file isn't still being accessed
                if os.path.exists(output_path):
                    try:
                        time.sleep(1)  # Give a small delay before cleanup
                        os.remove(output_path)
                        logger.info(f"Temporary file removed: {output_path}")
                    except Exception as e:
                        logger.error(f"Error removing temporary file: {str(e)}")
                return response
            
            # Return the file
            logger.info(f"Sending file to client: {title}.mp4")
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f"{title}.mp4",
                mimetype="video/mp4"
            )
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
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
            .download-btn { padding: 8px 15px; background: #2a76dd; color: white; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; }
            .download-btn:hover { background: #1c5bb9; }
            .note { background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0; }
        </style>
    </head>
    <body>
        <h1>YouTube Downloader API Test</h1>
        <p>This page allows you to test the YouTube Downloader API directly.</p>
        
        <div class="note">
            <strong>Note:</strong> This version now properly combines video and audio streams.
            Downloads will take slightly longer as the server needs to process the files.
        </div>
        
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
                        const match = input.match(/[\?&]v=([^&#]*)/);
                        if (match && match[1]) {
                            videoId = match[1];
                        }
                    } else if (input.includes('youtu.be/')) {
                        const match = input.match(/youtu\.be\/(.*?)(\?|$)/);
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