from flask import Flask, jsonify, request, redirect, send_file, Response
from yt_dlp import YoutubeDL
from flask_cors import CORS
import os
import tempfile
import logging
import time
import uuid
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Temp directory for downloaded files
TEMP_DIR = tempfile.gettempdir()

# Check if ffmpeg is available
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True)
        logger.info("FFmpeg is available")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("FFmpeg is not available, falling back to yt-dlp merging")
        return False

# Global flag for FFmpeg availability
FFMPEG_AVAILABLE = check_ffmpeg()

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
                                "has_audio": True,
                                "has_video": True
                            })
                            seen_qualities.add(quality)
            
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
                            "has_audio": False,
                            "has_video": True
                        })
                        seen_qualities.add(key)
            
            # Finally add audio-only format (mp4 if available)
            for f in info["formats"]:
                if f.get("vcodec") == "none" and f.get("acodec") != "none":
                    if "audio" not in seen_qualities:
                        audio_ext = "m4a" if f["ext"] == "m4a" else f["ext"]
                        formats.append({
                            "itag": f["format_id"],
                            "qualityLabel": "Audio Only",
                            "container": audio_ext,
                            "has_audio": True,
                            "has_video": False
                        })
                        seen_qualities.add("audio")
                        break  # Just take the first good audio format
            
            # Sort formats by quality (higher resolution first)
            formats.sort(key=lambda x: 0 if x["qualityLabel"] == "Audio Only" else 
                         int(x["qualityLabel"].replace("p", "").replace(" (with audio)", "")), 
                         reverse=True)
            
            return jsonify({
                "title": info.get("title", "YouTube Video"),
                "channel": info.get("uploader", "YouTube Channel"),
                "thumbnail": info.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                "formats": formats,
                "ffmpeg_available": FFMPEG_AVAILABLE
            })
    except Exception as e:
        logger.error(f"Error extracting video info: {str(e)}")
        return jsonify({"error": str(e)})

@app.route("/api/download")
def download():
    video_id = request.args.get("videoId")
    itag = request.args.get("itag")
    use_ffmpeg = request.args.get("use_ffmpeg", "false").lower() == "true"
    
    if not video_id or not itag:
        return jsonify({"error": "Missing video ID or format ID"}), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Download request for video ID: {video_id}, format: {itag}, use_ffmpeg: {use_ffmpeg}")
    
    # Create unique filenames for this download
    file_id = str(uuid.uuid4())
    
    # If we have FFmpeg and user requested it, use FFmpeg for merging
    if FFMPEG_AVAILABLE and use_ffmpeg:
        return download_with_ffmpeg(url, video_id, itag, file_id)
    else:
        return download_with_ytdlp(url, video_id, itag, file_id)

def download_with_ytdlp(url, video_id, itag, file_id):
    """Download and process using yt-dlp's built-in merging capability"""
    output_path = os.path.join(TEMP_DIR, f"youtube_{video_id}_{file_id}.mp4")
    
    # Set up options for yt-dlp
    ydl_opts = {
        "format": f"{itag}+bestaudio/best",  # Specified format + best audio, or best combined format
        "merge_output_format": "mp4",        # Force mp4 for compatibility
        "outtmpl": output_path,              # Output filename template
        "quiet": True,                       # Don't print progress
    }
    
    try:
        logger.info(f"Starting download with yt-dlp...")
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Get video info for filename
            title = info.get('title', 'video').replace(' ', '_')
            # Sanitize filename
            title = "".join(c for c in title if c.isalnum() or c in [' ', '_', '-']).rstrip()
            
            # Check if the file was actually created
            if not os.path.exists(output_path):
                logger.error(f"Download failed: File not created")
                return jsonify({"error": "Download failed"}), 500
            
            # Log file size for debugging
            file_size = os.path.getsize(output_path)
            logger.info(f"File size: {file_size} bytes")
            
            # Return the file
            response = send_file(
                output_path,
                as_attachment=True,
                download_name=f"{title}.mp4",
                mimetype="video/mp4"
            )
            
            # Clean up temporary file after response is sent
            @response.call_on_close
            def cleanup():
                try:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                        logger.info(f"Temporary file removed: {output_path}")
                except Exception as e:
                    logger.error(f"Error removing file: {str(e)}")
            
            return response
            
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({"error": str(e)}), 500

def download_with_ffmpeg(url, video_id, itag, file_id):
    """Download video and audio separately and merge with FFmpeg"""
    # Create temporary paths for video, audio, and output
    temp_video = os.path.join(TEMP_DIR, f"video_{video_id}_{file_id}.mp4")
    temp_audio = os.path.join(TEMP_DIR, f"audio_{video_id}_{file_id}.m4a")
    output_path = os.path.join(TEMP_DIR, f"merged_{video_id}_{file_id}.mp4")
    
    try:
        # First get info to get title
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video').replace(' ', '_')
            # Sanitize filename
            title = "".join(c for c in title if c.isalnum() or c in [' ', '_', '-']).rstrip()
        
        # Download video
        video_opts = {
            "format": itag,
            "outtmpl": temp_video,
            "quiet": True,
        }
        logger.info(f"Downloading video stream with format {itag}")
        with YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        
        # Download audio
        audio_opts = {
            "format": "bestaudio[ext=m4a]",
            "outtmpl": temp_audio,
            "quiet": True,
        }
        logger.info("Downloading audio stream")
        with YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        
        # Check if files exist
        if not os.path.exists(temp_video) or not os.path.exists(temp_audio):
            logger.error("Video or audio file not downloaded correctly")
            return jsonify({"error": "Failed to download video or audio streams"}), 500
        
        # Merge with FFmpeg
        logger.info("Merging video and audio with FFmpeg")
        ffmpeg_cmd = [
            'ffmpeg', 
            '-i', temp_video, 
            '-i', temp_audio, 
            '-c:v', 'copy', 
            '-c:a', 'aac', 
            '-strict', 'experimental',
            output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # Check if merged file exists
        if not os.path.exists(output_path):
            logger.error("FFmpeg merging failed")
            return jsonify({"error": "Failed to merge video and audio streams"}), 500
        
        # Log success
        file_size = os.path.getsize(output_path)
        logger.info(f"Merged file created: {output_path}, size: {file_size} bytes")
        
        # Return the merged file
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f"{title}.mp4",
            mimetype="video/mp4"
        )
        
        # Clean up temporary files after response is sent
        @response.call_on_close
        def cleanup():
            try:
                for file_path in [temp_video, temp_audio, output_path]:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Removed temporary file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing files: {str(e)}")
        
        return response
        
    except subprocess.SubprocessError as e:
        logger.error(f"FFmpeg error: {str(e)}")
        return jsonify({"error": f"FFmpeg error: {str(e)}"}), 500
    except Exception as e:
        logger.error(f"Error in FFmpeg workflow: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/")
def hello():
    # Simple static HTML
    ffmpeg_status = "available" if FFMPEG_AVAILABLE else "not available"
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Video Downloader</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0 auto; padding: 20px; max-width: 800px; }}
            h1 {{ color: #c00; text-align: center; }}
            .form-group {{ padding: 15px; background: #f8f8f8; border-radius: 5px; margin-bottom: 20px; }}
            input[type="text"] {{ width: 70%; padding: 8px; }}
            button {{ padding: 8px 15px; background: #c00; color: white; border: none; cursor: pointer; }}
            .video-info {{ text-align: center; }}
            .video-thumbnail {{ max-width: 320px; }}
            .download-btn {{ display: inline-block; margin: 5px; padding: 8px 15px; background: #2a76dd; color: white; 
                           text-decoration: none; border-radius: 4px; }}
            .status {{ padding: 3px 8px; border-radius: 3px; font-weight: bold; }}
            .available {{ background: #d4edda; color: #155724; }}
            .unavailable {{ background: #f8d7da; color: #721c24; }}
        </style>
    </head>
    <body>
        <h1>YouTube Video Downloader</h1>
        
        <div class="form-group">
            <p><strong>System Status:</strong> FFmpeg is <span class="status {("available" if FFMPEG_AVAILABLE else "unavailable")}">{ffmpeg_status}</span></p>
            <p>Enter a YouTube URL or video ID:</p>
            <input type="text" id="videoInput" placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ">
            <button id="testBtn">Fetch Video</button>
            <br>
            <label><input type="checkbox" id="useFFmpeg"> Use FFmpeg for merging (if available locally)</label>
        </div>
        
        <div id="result">
            <p>Enter a YouTube URL above and click "Fetch Video"</p>
        </div>
        
        <script>
        document.getElementById('testBtn').addEventListener('click', async () => {{
            const input = document.getElementById('videoInput').value.trim();
            const resultDiv = document.getElementById('result');
            
            if (!input) {{
                resultDiv.innerHTML = '<p style="color:red">Please enter a YouTube URL</p>';
                return;
            }}
            
            resultDiv.innerHTML = '<p>Loading video information...</p>';
            
            try {{
                // Extract video ID
                let videoId = input;
                if (input.includes('watch?v=')) {{
                    const match = input.match(/[?&]v=([^&#]*)/);
                    if (match && match[1]) {{
                        videoId = match[1];
                    }}
                }} else if (input.includes('youtu.be/')) {{
                    const match = input.match(/youtu\\.be\\/([^?&#]*)/);
                    if (match && match[1]) {{
                        videoId = match[1];
                    }}
                }}
                
                const response = await fetch(`/api/info?videoId=${{encodeURIComponent(videoId)}}`);
                const data = await response.json();
                
                if (data.error) {{
                    resultDiv.innerHTML = `<p style="color:red">Error: ${{data.error}}</p>`;
                    return;
                }}
                
                // Get FFmpeg setting
                const useFFmpeg = document.getElementById('useFFmpeg').checked;
                
                // Create download buttons
                let buttonsHtml = '';
                if (data.formats && data.formats.length > 0) {{
                    data.formats.forEach(format => {{
                        buttonsHtml += `<a class="download-btn" 
                           href="/api/download?videoId=${{encodeURIComponent(videoId)}}&itag=${{format.itag}}&use_ffmpeg=${{useFFmpeg}}"
                           target="_blank">
                           Download ${{format.qualityLabel}} (${{format.container}})
                        </a> `;
                    }});
                }}
                
                // Display video info
                resultDiv.innerHTML = `
                    <div class="video-info">
                        <h2>${{data.title || 'Unknown Title'}}</h2>
                        <p>${{data.channel || 'Unknown Channel'}}</p>
                        <img src="${{data.thumbnail}}" class="video-thumbnail">
                        <h3>Available Download Options:</h3>
                        <div>${{buttonsHtml || 'No formats available'}}</div>
                    </div>
                `;
            }} catch (error) {{
                resultDiv.innerHTML = `<p style="color:red">Error: ${{error.message}}</p>`;
            }}
        }});
        
        // Enter key event listener
        document.getElementById('videoInput').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') {{
                document.getElementById('testBtn').click();
            }}
        }});
        </script>
    </body>
    </html>
    """
    return html

if __name__ == "__main__":
    port = 5000
    print(f"YouTube Downloader API Server running on port {port}")
    app.run(host="0.0.0.0", port=port)