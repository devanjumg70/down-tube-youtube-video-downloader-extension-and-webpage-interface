from flask import Flask, jsonify, request, redirect, send_file, Response
from yt_dlp import YoutubeDL
from flask_cors import CORS
from flask_socketio import SocketIO
import os
import tempfile
import logging
import time
import uuid
import subprocess
import json
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Temp directory for downloaded files
TEMP_DIR = tempfile.gettempdir()

# Track download progress
download_progress = {}

# Define a progress hook for yt-dlp
def progress_hook(d):
    file_id = d.get('info_dict', {}).get('__download_id', '')
    if file_id and file_id in download_progress:
        if d['status'] == 'downloading':
            # Calculate progress percentage
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            if total_bytes > 0:
                progress = (downloaded_bytes / total_bytes) * 100
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                # Update progress info
                download_progress[file_id].update({
                    'progress': round(progress, 2),
                    'speed': speed,
                    'eta': eta,
                    'size': total_bytes,
                    'downloaded': downloaded_bytes,
                    'status': 'downloading'
                })
                
                # Emit progress update
                socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
        
        elif d['status'] == 'finished':
            download_progress[file_id].update({
                'progress': 100,
                'status': 'processing'
            })
            socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
            
        elif d['status'] == 'error':
            download_progress[file_id].update({
                'status': 'error',
                'error': d.get('error', 'Unknown error')
            })
            socketio.emit(f'progress_update_{file_id}', download_progress[file_id])

# Check if ffmpeg is available
def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True)
        logger.info("FFmpeg is available")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("FFmpeg is not available, falling back to yt-dlp merging")
        return False

# Check if aria2c is available
def check_aria2c():
    try:
        subprocess.run(['aria2c', '--version'], check=True, capture_output=True)
        logger.info("aria2c is available")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("aria2c is not available, falling back to default downloader")
        return False

# Global flags for tool availability
FFMPEG_AVAILABLE = check_ffmpeg()
ARIA2C_AVAILABLE = check_aria2c()

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
            
            # Finally add audio-only format (prioritize MP3 or AAC formats for better compatibility)
            audio_format_found = False
            
            # First try to find mp3 format (most compatible)
            for f in info["formats"]:
                if f.get("vcodec") == "none" and f.get("acodec") != "none" and f["ext"] == "mp3":
                    if "audio" not in seen_qualities:
                        formats.append({
                            "itag": f["format_id"],
                            "qualityLabel": "Audio Only (MP3)",
                            "container": "mp3",
                            "has_audio": True,
                            "has_video": False
                        })
                        seen_qualities.add("audio")
                        audio_format_found = True
                        break
            
            # If no MP3, try to find m4a (AAC) - excellent quality and wide compatibility
            if not audio_format_found:
                for f in info["formats"]:
                    if f.get("vcodec") == "none" and f.get("acodec") != "none" and f["ext"] == "m4a":
                        if "audio" not in seen_qualities:
                            formats.append({
                                "itag": f["format_id"],
                                "qualityLabel": "Audio Only (AAC)",
                                "container": "m4a",
                                "has_audio": True,
                                "has_video": False
                            })
                            seen_qualities.add("audio")
                            audio_format_found = True
                            break
            
            # Fallback to any audio format if no MP3 or M4A found
            if not audio_format_found:
                for f in info["formats"]:
                    if f.get("vcodec") == "none" and f.get("acodec") != "none":
                        if "audio" not in seen_qualities:
                            formats.append({
                                "itag": f["format_id"],
                                "qualityLabel": f"Audio Only ({f['ext'].upper()})",
                                "container": f["ext"],
                                "has_audio": True,
                                "has_video": False
                            })
                            seen_qualities.add("audio")
                            break
            
            # Sort formats by quality (higher resolution first)
            def format_sort_key(x):
                if "Audio Only" in x["qualityLabel"]:
                    return 0  # Audio formats at the bottom
                else:
                    # Extract the numerical part from resolution (e.g., "720p" -> 720)
                    return int(x["qualityLabel"].replace("p", "").replace(" (with audio)", ""))
                
            formats.sort(key=format_sort_key, reverse=True)
            
            return jsonify({
                "title": info.get("title", "YouTube Video"),
                "channel": info.get("uploader", "YouTube Channel"),
                "thumbnail": info.get("thumbnail", f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"),
                "formats": formats,
                "ffmpeg_available": FFMPEG_AVAILABLE,
                "aria2c_available": ARIA2C_AVAILABLE
            })
    except Exception as e:
        logger.error(f"Error extracting video info: {str(e)}")
        return jsonify({"error": str(e)})

@app.route("/api/download")
def download():
    video_id = request.args.get("videoId")
    itag = request.args.get("itag")
    
    # Support both parameter names (use_ffmpeg and useFFmpeg) for better compatibility
    use_ffmpeg_param = request.args.get("use_ffmpeg", request.args.get("useFFmpeg", "true"))
    use_ffmpeg = use_ffmpeg_param.lower() == "true"
    
    if not video_id or not itag:
        return jsonify({"error": "Missing video ID or format ID"}), 400
    
    url = f"https://www.youtube.com/watch?v={video_id}"
    logger.info(f"Download request for video ID: {video_id}, format: {itag}, use_ffmpeg: {use_ffmpeg}")
    
    # Create unique filenames for this download
    file_id = str(uuid.uuid4())
    
    # If we have FFmpeg and user requested it, use FFmpeg for merging
    if FFMPEG_AVAILABLE and use_ffmpeg:
        logger.info("Using FFmpeg for download and merging")
        return download_with_ffmpeg(url, video_id, itag, file_id)
    else:
        if not use_ffmpeg:
            logger.info("FFmpeg disabled by user request, using yt-dlp only")
        elif not FFMPEG_AVAILABLE:
            logger.info("FFmpeg not available, falling back to yt-dlp")
        return download_with_ytdlp(url, video_id, itag, file_id)

def download_with_ytdlp(url, video_id, itag, file_id):
    """Download and process using yt-dlp's built-in merging capability"""
    output_path = os.path.join(TEMP_DIR, f"youtube_{video_id}_{file_id}.mp4")
    
    # Initialize progress tracking for this download
    download_progress[file_id] = {
        'progress': 0,
        'speed': 0,
        'eta': 0,
        'status': 'starting',
        'video_id': video_id,
        'file_id': file_id
    }
    
    # Check if a format has both video and audio streams
    has_both_streams = False
    try:
        # Quick info check to identify combined formats
        with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            for f in info["formats"]:
                if f["format_id"] == itag and f.get("vcodec") != "none" and f.get("acodec") != "none":
                    has_both_streams = True
                    logger.info(f"Format {itag} already has both video and audio streams")
                    break
    except Exception as e:
        logger.warning(f"Error checking format streams: {str(e)}")
    
    # Set up options for yt-dlp
    ydl_opts = {
        # If format already has both streams, just use that format directly
        "format": itag if has_both_streams else f"{itag}+bestaudio/best",
        "merge_output_format": "mp4",        # Force mp4 for compatibility
        "outtmpl": output_path,              # Output filename template
        "quiet": True,                       # Don't print progress
    }
    
    # If aria2c is available, use it for faster downloading
    if ARIA2C_AVAILABLE:
        logger.info("Using aria2c for multi-threaded downloading")
        ydl_opts.update({
            "external_downloader": "aria2c",
            "external_downloader_args": ["--max-connection-per-server=16", "--min-split-size=1M", "--max-concurrent-downloads=16"]
        })
    
    try:
        logger.info(f"Starting download with yt-dlp... (using aria2c: {ARIA2C_AVAILABLE})")
        # Check if this is an audio-only format 
        audio_only = False
        audio_format = "mp3"  # Default to MP3 for audio-only
        
        try:
            with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
                info_check = ydl.extract_info(url, download=False)
                for f in info_check["formats"]:
                    if f["format_id"] == itag and f.get("vcodec") == "none" and f.get("acodec") != "none":
                        audio_only = True
                        audio_format = f["ext"]
                        logger.info(f"Identified audio-only format with extension: {audio_format}")
                        break
        except Exception as e:
            logger.warning(f"Error checking audio format: {str(e)}")
            
        # If this is an audio-only format, modify output path and options
        if audio_only:
            # If the original format is not mp3 or m4a, force mp3 output (better compatibility)
            if audio_format not in ["mp3", "m4a"]:
                audio_format = "mp3"
                
            # Update the output path to use the proper extension
            output_path = os.path.join(TEMP_DIR, f"audio_{video_id}_{file_id}.{audio_format}")
            
            # For mp3 output, add postprocessors to ensure proper conversion
            if audio_format == "mp3":
                ydl_opts["postprocessors"] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            
            logger.info(f"Audio-only download with format: {audio_format}")
            
        # Perform the download
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
            
            # Set the correct MIME type and filename extension based on format
            if audio_only:
                if audio_format == "mp3":
                    mimetype = "audio/mpeg"
                    ext = "mp3"
                elif audio_format == "m4a":
                    mimetype = "audio/m4a"
                    ext = "m4a"
                else:
                    mimetype = f"audio/{audio_format}"
                    ext = audio_format
                    
                logger.info(f"Using audio MIME type: {mimetype}")
            else:
                mimetype = "video/mp4"
                ext = "mp4"
            
            # Return the file
            response = send_file(
                output_path,
                as_attachment=True,
                download_name=f"{title}.{ext}",
                mimetype=mimetype
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
    """Download video and audio separately and merge with FFmpeg, or handle audio-only formats"""
    # Initialize progress tracking for this download
    download_progress[file_id] = {
        'progress': 0,
        'speed': 0,
        'eta': 0,
        'status': 'starting',
        'video_id': video_id,
        'file_id': file_id,
        'stage': 'initialization'
    }
    socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
    
    # First check if this is an audio-only format
    audio_only = False
    audio_format = "mp3"  # Default audio format is MP3 for better compatibility
    
    try:
        # Quick info check to identify audio-only or combined formats
        with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            for f in info["formats"]:
                if f["format_id"] == itag:
                    # Check for audio-only format
                    if f.get("vcodec") == "none" and f.get("acodec") != "none":
                        audio_only = True
                        logger.info(f"Identified audio-only format with itag: {itag}")
                        break
                    # Check for combined format
                    elif f.get("vcodec") != "none" and f.get("acodec") != "none":
                        logger.info(f"Format {itag} already has both video and audio streams")
                        # Use direct download for combined formats
                        return download_with_ytdlp(url, video_id, itag, file_id)
    
    except Exception as e:
        logger.warning(f"Error checking format type: {str(e)}")
    
    # If this is an audio-only format, download and convert directly to MP3
    if audio_only:
        logger.info(f"Processing audio-only format")
        output_path = os.path.join(TEMP_DIR, f"audio_{video_id}_{file_id}.mp3")
        
        # Get info for title
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'audio').replace(' ', '_')
            # Sanitize filename
            title = "".join(c for c in title if c.isalnum() or c in [' ', '_', '-']).rstrip()
        
        # Download audio using yt-dlp
        temp_audio = os.path.join(TEMP_DIR, f"temp_audio_{video_id}_{file_id}")
        audio_opts = {
            "quiet": True,
            "format": itag,
            "outtmpl": temp_audio
        }
        
        # Add aria2c if available
        if ARIA2C_AVAILABLE:
            audio_opts.update({
                "external_downloader": "aria2c",
                "external_downloader_args": ["--max-connection-per-server=16", "--min-split-size=1M"]
            })
        
        # Download the audio
        with YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        
        # Get actual filename (with extension) that yt-dlp created
        temp_audio_file = None
        for filename in os.listdir(TEMP_DIR):
            if filename.startswith(f"temp_audio_{video_id}_{file_id}"):
                temp_audio_file = os.path.join(TEMP_DIR, filename)
                break
        
        if not temp_audio_file or not os.path.exists(temp_audio_file):
            logger.error("Audio file not downloaded correctly")
            return jsonify({"error": "Failed to download audio"}), 500
        
        # Convert to MP3 using FFmpeg
        logger.info(f"Converting audio to MP3 format using FFmpeg")
        ffmpeg_cmd = [
            'ffmpeg',
            '-hide_banner', '-nostats',
            '-i', temp_audio_file,
            '-vn',                       # No video
            '-acodec', 'libmp3lame',     # Use MP3 codec
            '-ab', '192k',               # 192k bitrate
            '-metadata', f'title={title}',
            output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # Verify the output file exists
        if not os.path.exists(output_path):
            logger.error("FFmpeg audio conversion failed")
            return jsonify({"error": "Failed to convert audio to MP3"}), 500
        
        # Return the MP3 file
        file_size = os.path.getsize(output_path)
        logger.info(f"Audio file created: {output_path}, size: {file_size} bytes")
        
        response = send_file(
            output_path,
            as_attachment=True,
            download_name=f"{title}.mp3",
            mimetype="audio/mpeg"
        )
        
        # Clean up files after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(temp_audio_file):
                    os.remove(temp_audio_file)
                if os.path.exists(output_path):
                    os.remove(output_path)
                logger.info("Temporary audio files removed")
            except Exception as e:
                logger.error(f"Error removing files: {str(e)}")
        
        return response
    
    # This is a video format that needs audio - proceed with standard FFmpeg flow
    # Create temporary paths for video, audio, and output
    temp_video = os.path.join(TEMP_DIR, f"video_{video_id}_{file_id}.mp4")
    temp_audio = os.path.join(TEMP_DIR, f"audio_{video_id}_{file_id}.m4a")
    output_path = os.path.join(TEMP_DIR, f"merged_{video_id}_{file_id}.mp4")
    
    try:
        # Get video info for title
        with YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'video').replace(' ', '_')
            # Sanitize filename
            title = "".join(c for c in title if c.isalnum() or c in [' ', '_', '-']).rstrip()
        
        # Set up base options
        base_opts = {
            "quiet": True,
        }
        
        # Add aria2c if available
        if ARIA2C_AVAILABLE:
            logger.info("Using aria2c for multi-threaded downloading")
            base_opts.update({
                "external_downloader": "aria2c",
                "external_downloader_args": ["--max-connection-per-server=16", "--min-split-size=1M", "--max-concurrent-downloads=16"]
            })
        
        # Download video
        video_opts = base_opts.copy()
        video_opts.update({
            "format": itag,
            "outtmpl": temp_video,
        })
        logger.info(f"Downloading video stream with format {itag}")
        # Update progress for video download stage
        download_progress[file_id].update({
            'stage': 'downloading_video',
            'progress': 25,
            'status': 'downloading'
        })
        socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
        
        # Add progress hook to the options
        video_opts['progress_hooks'] = [progress_hook]
        # Add download ID to track this specific file
        video_opts['postprocessor_args'] = [{'__download_id': file_id}]
        
        with YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        
        # Update progress for audio download stage
        download_progress[file_id].update({
            'stage': 'downloading_audio',
            'progress': 50,
            'status': 'downloading'
        })
        socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
        
        # Download audio
        audio_opts = base_opts.copy()
        audio_opts.update({
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": temp_audio,
        })
        logger.info("Downloading audio stream")
        
        # Use progress hook for audio too
        audio_opts['progress_hooks'] = [progress_hook]
        audio_opts['postprocessor_args'] = [{'__download_id': file_id}]
        
        with YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        
        # Check if files exist
        if not os.path.exists(temp_video) or not os.path.exists(temp_audio):
            logger.error("Video or audio file not downloaded correctly")
            return jsonify({"error": "Failed to download video or audio streams"}), 500
        
        # Update progress for FFmpeg merging stage
        download_progress[file_id].update({
            'stage': 'merging',
            'progress': 75,
            'status': 'processing'
        })
        socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
        
        # Merge with FFmpeg (optimized parameters)
        logger.info("Merging video and audio with FFmpeg")
        ffmpeg_cmd = [
            'ffmpeg', 
            '-hide_banner', '-nostats',           # Reduce console output
            '-i', temp_video,                     # Video input
            '-i', temp_audio,                     # Audio input
            '-map', '0:v:0',                      # Use first video stream from first input
            '-map', '1:a:0',                      # Use first audio stream from second input
            '-c:v', 'copy',                       # Copy video (no re-encoding)
            '-c:a', 'aac',                        # Use AAC for audio (widely compatible)
            '-b:a', '192k',                       # Good quality audio bitrate
            '-movflags', '+faststart',            # Optimize for web streaming
            '-metadata', f'title={title}',        # Add title metadata
            output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
        
        # Update progress for completion
        download_progress[file_id].update({
            'stage': 'completed',
            'progress': 100,
            'status': 'completed'
        })
        socketio.emit(f'progress_update_{file_id}', download_progress[file_id])
        
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
    # Modern static HTML with improved UI
    ffmpeg_status = "available" if FFMPEG_AVAILABLE else "not available"
    aria2c_status = "available" if ARIA2C_AVAILABLE else "not available"
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YouTube Video Downloader</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            /* YouTube inspired colors */
            :root {{
                --youtube-red: #ff0000;
                --youtube-red-hover: #cc0000;
                --youtube-blue: #065fd4;
                --youtube-blue-hover: #0547a5;
                --youtube-dark: #212121;
                --youtube-white: #ffffff;
                --youtube-light-bg: #f9f9f9;
                --youtube-gray: #909090;
                --youtube-light-gray: #e5e5e5;
                
                /* Theme variables - light mode default */
                --primary-color: var(--youtube-red);
                --primary-hover: var(--youtube-red-hover);
                --secondary-color: var(--youtube-blue);
                --secondary-hover: var(--youtube-blue-hover);
                --text-dark: var(--youtube-dark);
                --text-light: var(--youtube-gray);
                --bg-light: var(--youtube-light-bg);
                --bg-white: var(--youtube-white);
                --bg-card: var(--youtube-white);
                --shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
                --border-radius: 8px;
                --border-color: var(--youtube-light-gray);
                --success-color: #4caf50;
                --error-color: var(--youtube-red);
                
                /* Animation speeds */
                --transition-speed: 0.3s;
            }}
            
            /* Dark mode styles */
            .dark-mode {{
                --primary-color: var(--youtube-red);
                --primary-hover: var(--youtube-red-hover);
                --secondary-color: var(--youtube-blue);
                --secondary-hover: var(--youtube-blue-hover);
                --text-dark: var(--youtube-white);
                --text-light: #aaaaaa;
                --bg-light: #181818;
                --bg-white: #212121;
                --bg-card: #303030;
                --border-color: #383838;
            }}
            
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, Oxygen, Ubuntu, sans-serif;
            }}
            
            body {{
                background-color: var(--bg-light);
                margin: 0 auto;
                padding: 40px 20px;
                max-width: 800px;
                color: var(--text-dark);
                transition: background-color var(--transition-speed), color var(--transition-speed);
                position: relative;
            }}
            
            /* Theme toggle */
            .theme-switch {{
                position: fixed;
                top: 20px;
                right: 20px;
                background-color: var(--bg-card);
                color: var(--text-dark);
                width: 40px;
                height: 40px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                box-shadow: var(--shadow);
                z-index: 1000;
                transition: all var(--transition-speed);
            }}
            
            .theme-switch:hover {{
                transform: rotate(30deg);
                box-shadow: 0 0 15px rgba(0,0,0,0.2);
            }}
            
            .container {{
                background: var(--bg-white);
                border-radius: var(--border-radius);
                box-shadow: var(--shadow);
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(135deg, var(--primary-color), #ff7676);
                color: white;
                padding: 30px 20px;
                text-align: center;
                position: relative;
                overflow: hidden;
            }}
            
            /* Animated background effect */
            .header::before {{
                content: '';
                position: absolute;
                top: -50%;
                left: -50%;
                width: 200%;
                height: 200%;
                background: radial-gradient(circle, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 70%);
                animation: pulse 8s infinite ease-in-out;
                z-index: 1;
            }}
            
            @keyframes pulse {{
                0% {{ transform: scale(1); opacity: 0.5; }}
                50% {{ transform: scale(1.2); opacity: 0.2; }}
                100% {{ transform: scale(1); opacity: 0.5; }}
            }}
            
            .header h1 {{
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 28px;
                margin-bottom: 10px;
            }}
            
            .header h1 i {{
                margin-right: 12px;
                font-size: 32px;
            }}
            
            .header p {{
                font-size: 16px;
                opacity: 0.9;
            }}
            
            .system-status {{
                background-color: var(--bg-light);
                border-radius: var(--border-radius);
                padding: 15px;
                margin-bottom: 20px;
            }}
            
            .status-title {{
                font-weight: 600;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
            }}
            
            .status-title i {{
                margin-right: 8px;
                color: var(--secondary-color);
            }}
            
            .status-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
            }}
            
            .status-item {{
                display: flex;
                align-items: center;
                background: white;
                padding: 12px;
                border-radius: var(--border-radius);
                border-left: 4px solid var(--secondary-color);
            }}
            
            .status-item i {{
                font-size: 20px;
                margin-right: 10px;
            }}
            
            .status-item .status-content {{
                flex: 1;
            }}
            
            .status-item .status-name {{
                font-weight: 600;
                margin-bottom: 3px;
            }}
            
            .status-item .status-note {{
                font-size: 12px;
                color: var(--text-light);
            }}
            
            .status-badge {{
                padding: 3px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
            }}
            
            .available {{
                background: #d4edda;
                color: #155724;
            }}
            
            .unavailable {{
                background: #f8d7da;
                color: #721c24;
            }}
            
            .form-section {{
                padding: 25px;
            }}
            
            .form-group {{
                margin-bottom: 25px;
            }}
            
            .form-label {{
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
                color: var(--text-dark);
            }}
            
            .input-wrapper {{
                display: flex;
                width: 100%;
                position: relative;
            }}
            
            .input-icon {{
                position: absolute;
                left: 12px;
                top: 50%;
                transform: translateY(-50%);
                color: var(--text-light);
            }}
            
            #videoInput {{
                flex: 1;
                padding: 12px 12px 12px 40px;
                border: 1px solid var(--border-color);
                border-radius: var(--border-radius) 0 0 var(--border-radius);
                font-size: 16px;
                transition: all 0.2s;
            }}
            
            #videoInput:focus {{
                outline: none;
                border-color: var(--primary-color);
                box-shadow: 0 0 0 2px rgba(255, 75, 75, 0.25);
            }}
            
            #fetchBtn {{
                background-color: var(--primary-color);
                color: white;
                border: none;
                padding: 0 25px;
                border-radius: 0 var(--border-radius) var(--border-radius) 0;
                font-weight: 600;
                cursor: pointer;
                font-size: 16px;
                transition: background-color 0.2s;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            
            #fetchBtn i {{
                margin-right: 8px;
            }}
            
            #fetchBtn:hover {{
                background-color: var(--primary-hover);
            }}
            
            .toggle-container {{
                margin-top: 15px;
                display: flex;
                align-items: center;
            }}
            
            .toggle-switch {{
                position: relative;
                display: inline-block;
                width: 60px;
                height: 30px;
                margin-right: 12px;
            }}
            
            .toggle-switch input {{
                opacity: 0;
                width: 0;
                height: 0;
            }}
            
            .toggle-slider {{
                position: absolute;
                cursor: pointer;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: #ccc;
                transition: .4s;
                border-radius: 34px;
            }}
            
            .toggle-slider:before {{
                position: absolute;
                content: "";
                height: 22px;
                width: 22px;
                left: 4px;
                bottom: 4px;
                background-color: white;
                transition: .4s;
                border-radius: 50%;
            }}
            
            input:checked + .toggle-slider {{
                background-color: var(--success-color);
            }}
            
            input:checked + .toggle-slider:before {{
                transform: translateX(30px);
            }}
            
            .toggle-label {{
                font-weight: 500;
                font-size: 14px;
                display: flex;
                align-items: center;
            }}
            
            .toggle-label i {{
                margin-right: 8px;
                color: var(--success-color);
            }}
            
            .loader {{
                display: flex;
                justify-content: center;
                align-items: center;
                flex-direction: column;
                padding: 40px 20px;
            }}
            
            .spinner {{
                width: 40px;
                height: 40px;
                border: 4px solid rgba(255, 75, 75, 0.25);
                border-top: 4px solid var(--primary-color);
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin-bottom: 20px;
            }}
            
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            
            .video-info {{
                padding: 20px;
                max-width: 700px;
                margin: 0 auto;
            }}
            
            .video-details {{
                display: flex;
                align-items: flex-start;
                margin-bottom: 30px;
                background: white;
                border-radius: var(--border-radius);
                overflow: hidden;
                box-shadow: var(--shadow);
            }}
            
            .video-thumbnail {{
                width: 240px;
                height: auto;
                object-fit: cover;
                border-right: 1px solid var(--border-color);
            }}
            
            .video-text {{
                padding: 20px;
                flex: 1;
            }}
            
            .video-text h2 {{
                font-size: 18px;
                margin-bottom: 8px;
                line-height: 1.4;
            }}
            
            .video-text p {{
                color: var(--text-light);
                margin-bottom: 15px;
                font-size: 14px;
            }}
            
            .download-section {{
                background: white;
                border-radius: var(--border-radius);
                padding: 20px;
                box-shadow: var(--shadow);
            }}
            
            .download-section h3 {{
                font-size: 18px;
                margin-bottom: 15px;
                padding-bottom: 10px;
                border-bottom: 1px solid var(--border-color);
                display: flex;
                align-items: center;
            }}
            
            .download-section h3 i {{
                margin-right: 10px;
                color: var(--secondary-color);
            }}
            
            .download-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 12px;
            }}
            
            .download-btn {{
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 12px;
                background-color: var(--secondary-color);
                color: white;
                text-decoration: none;
                border-radius: var(--border-radius);
                font-weight: 500;
                transition: all var(--transition-speed);
                border: 1px solid transparent;
                position: relative;
                overflow: hidden;
            }}
            
            /* Button ripple effect */
            .download-btn::after {{
                content: '';
                position: absolute;
                top: 50%;
                left: 50%;
                width: 5px;
                height: 5px;
                background: rgba(255, 255, 255, 0.5);
                opacity: 0;
                border-radius: 100%;
                transform: scale(1, 1) translate(-50%);
                transform-origin: 50% 50%;
            }}
            
            .download-btn:focus:not(:active)::after {{
                animation: ripple 1s ease-out;
            }}
            
            @keyframes ripple {{
                0% {{ transform: scale(0, 0); opacity: 0.5; }}
                20% {{ transform: scale(25, 25); opacity: 0.3; }}
                100% {{ opacity: 0; transform: scale(40, 40); }}
            }}
            
            .download-btn:hover {{
                background-color: var(--secondary-hover);
                transform: translateY(-2px);
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }}
            
            .download-btn i {{
                margin-right: 8px;
            }}
            
            .download-btn.audio {{
                background-color: var(--primary-color);
            }}
            
            .download-btn.audio:hover {{
                background-color: var(--primary-hover);
            }}
            
            .error-msg {{
                background-color: rgba(245, 101, 101, 0.1);
                color: var(--error-color);
                padding: 15px;
                border-radius: var(--border-radius);
                margin: 20px 0;
                display: flex;
                align-items: center;
            }}
            
            .error-msg i {{
                margin-right: 10px;
                font-size: 18px;
            }}
            
            footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                color: var(--text-light);
                font-size: 14px;
            }}
            
            @media (max-width: 768px) {{
                .video-details {{
                    flex-direction: column;
                }}
                
                .video-thumbnail {{
                    width: 100%;
                    border-right: none;
                    border-bottom: 1px solid var(--border-color);
                }}
                
                .download-grid {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="theme-switch" id="theme-toggle">
            <i class="fas fa-moon"></i>
        </div>
        <div class="container">
            <div class="header">
                <h1><i class="fas fa-download"></i> YouTube Video Downloader</h1>
                <p>Download videos and audio in your preferred format</p>
            </div>
            
            <div class="form-section">
                <div class="system-status">
                    <div class="status-title"><i class="fas fa-server"></i> System Status</div>
                    <div class="status-grid">
                        <div class="status-item">
                            <i class="fas fa-film" style="color: #ff4b4b;"></i>
                            <div class="status-content">
                                <div class="status-name">
                                    FFmpeg
                                    <span class="status-badge {("available" if FFMPEG_AVAILABLE else "unavailable")}">
                                        {ffmpeg_status}
                                    </span>
                                </div>
                                <div class="status-note">High-quality video/audio processing</div>
                            </div>
                        </div>
                        <div class="status-item">
                            <i class="fas fa-bolt" style="color: #fbbf24;"></i>
                            <div class="status-content">
                                <div class="status-name">
                                    aria2c
                                    <span class="status-badge {("available" if ARIA2C_AVAILABLE else "unavailable")}">
                                        {aria2c_status}
                                    </span>
                                </div>
                                <div class="status-note">Multi-threaded, faster downloads</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="videoInput">Enter a YouTube URL or video ID:</label>
                    <div class="input-wrapper">
                        <i class="fas fa-link input-icon"></i>
                        <input type="text" id="videoInput" placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ" 
                               autocomplete="off" spellcheck="false">
                        <button id="fetchBtn"><i class="fas fa-search"></i> Fetch</button>
                    </div>
                    
                    <div class="toggle-container">
                        <label class="toggle-switch">
                            <input type="checkbox" id="useFFmpeg" {("checked" if FFMPEG_AVAILABLE else "")}>
                            <span class="toggle-slider"></span>
                        </label>
                        <span class="toggle-label">
                            <i class="fas fa-check-circle"></i> Use FFmpeg for better quality (recommended)
                        </span>
                    </div>
                </div>
                
                <div id="result">
                    <div class="loader" style="display: none;">
                        <div class="spinner"></div>
                        <p>Analyzing video content...</p>
                    </div>
                    <div class="info-message">
                        <p><i class="fas fa-info-circle"></i> Enter a YouTube URL above and click "Fetch" to get download options</p>
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <p>© 2025 YouTube Video Downloader | Powered by yt-dlp & FFmpeg</p>
        </footer>
        
        <script>
        // Theme toggle functionality
        const themeToggle = document.getElementById('theme-toggle');
        const body = document.body;
        
        // Check if dark mode is enabled in localStorage
        const isDarkMode = localStorage.getItem('darkMode') === 'true';
        
        // Apply dark mode if it was previously enabled
        if (isDarkMode) {
            body.classList.add('dark-mode');
            themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        }
        
        // Toggle dark mode when the button is clicked
        themeToggle.addEventListener('click', function() {
            body.classList.toggle('dark-mode');
            
            // Update localStorage with the current theme preference
            const isDark = body.classList.contains('dark-mode');
            localStorage.setItem('darkMode', isDark);
            
            // Change the icon based on the current theme
            themeToggle.innerHTML = isDark ? 
              '<i class="fas fa-sun"></i>' : 
              '<i class="fas fa-moon"></i>';
        });
            
        document.getElementById('fetchBtn').addEventListener('click', async () => {
            const input = document.getElementById('videoInput').value.trim();
            const resultDiv = document.getElementById('result');
            const loader = document.querySelector('.loader');
            const infoMessage = document.querySelector('.info-message');
            
            if (!input) {
                resultDiv.innerHTML = `
                    <div class="error-msg">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>Please enter a YouTube URL</span>
                    </div>
                    <div class="info-message">
                        <p><i class="fas fa-info-circle"></i> Enter a YouTube URL above and click "Fetch" to get download options</p>
                    </div>
                `;
                return;
            }
            
            // Show loader, hide info message
            if (loader) loader.style.display = 'flex';
            if (infoMessage) infoMessage.style.display = 'none';
            
            // Clear previous content
            resultDiv.innerHTML = `
                <div class="loader">
                    <div class="spinner"></div>
                    <p>Analyzing video content...</p>
                </div>
            `;
            
            try {
                // Extract video ID
                let videoId = input;
                if (input.includes('watch?v=')) {
                    const match = input.match(/[?&]v=([^&#]*)/);
                    if (match && match[1]) {
                        videoId = match[1];
                    }
                } else if (input.includes('youtu.be/')) {
                    const match = input.match(/youtu\\.be\\/([^?&#]*)/);
                    if (match && match[1]) {
                        videoId = match[1];
                    }
                }
                
                const response = await fetch(`/api/info?videoId=${encodeURIComponent(videoId)}`);
                const data = await response.json();
                
                if (data.error) {
                    resultDiv.innerHTML = `
                        <div class="error-msg">
                            <i class="fas fa-exclamation-circle"></i>
                            <span>Error: ${data.error}</span>
                        </div>
                    `;
                    return;
                }
                
                // Get FFmpeg setting
                const useFFmpeg = document.getElementById('useFFmpeg').checked;
                
                // Create download buttons
                let buttonsHtml = '';
                if (data.formats && data.formats.length > 0) {
                    data.formats.forEach(format => {
                        // Determine if this is an audio format
                        const isAudioOnly = format.qualityLabel.includes('Audio Only');
                        const buttonClass = isAudioOnly ? 'download-btn audio' : 'download-btn';
                        const icon = isAudioOnly ? 'fa-music' : 'fa-video';
                        
                        // Clean up format label for audio
                        let formatLabel = format.qualityLabel;
                        if (formatLabel.includes('(MP3)')) {
                            formatLabel = 'Audio Only (MP3)';
                        } else if (formatLabel.includes('(AAC)')) {
                            formatLabel = 'Audio Only (AAC)';
                        }
                        
                        buttonsHtml += `
                            <a class="${buttonClass}" 
                               href="/api/download?videoId=${encodeURIComponent(videoId)}&itag=${format.itag}&use_ffmpeg=${useFFmpeg}"
                               target="_blank">
                               <i class="fas ${icon}"></i> ${formatLabel}
                            </a>
                        `;
                    });
                }
                
                // Display video info
                resultDiv.innerHTML = `
                    <div class="video-info">
                        <div class="video-details">
                            <img src="${data.thumbnail}" class="video-thumbnail" alt="${data.title}">
                            <div class="video-text">
                                <h2>${data.title || 'Unknown Title'}</h2>
                                <p><i class="fas fa-user"></i> ${data.channel || 'Unknown Channel'}</p>
                                <p><i class="fas fa-info-circle"></i> Select your preferred format below</p>
                            </div>
                        </div>
                        
                        <div class="download-section">
                            <h3><i class="fas fa-download"></i> Available Download Options</h3>
                            <div class="download-grid">
                                ${buttonsHtml || '<p>No formats available</p>'}
                            </div>
                        </div>
                    </div>
                `;
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="error-msg">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>Error: ${error.message}</span>
                    </div>
                `;
            }
        });
        
        // Auto-fetch on paste
        document.getElementById('videoInput').addEventListener('paste', (e) => {
            // Short delay to let the paste complete
            setTimeout(() => {
                const input = document.getElementById('videoInput').value.trim();
                if (input && (input.includes('youtube.com') || input.includes('youtu.be'))) {
                    document.getElementById('fetchBtn').click();
                }
            }, 100);
        });
        
        // Enter key event listener
        document.getElementById('videoInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.getElementById('fetchBtn').click();
            }
        });
        
        // Disable FFmpeg toggle if not available
        const ffmpegAvailable = """ + ("true" if FFMPEG_AVAILABLE else "false") + """;
        if (!ffmpegAvailable) {
            document.getElementById('useFFmpeg').disabled = true;
            document.querySelector('.toggle-label').innerHTML += ' <span style="color: var(--error-color); font-size: 12px;">(Not available)</span>';
        }
        </script>
    </body>
    </html>
    """
    return html

# Add a route to get progress information for a specific download
@app.route("/api/progress/<file_id>")
def get_progress(file_id):
    if file_id in download_progress:
        return jsonify(download_progress[file_id])
    else:
        return jsonify({"error": "Download not found"}), 404

# SocketIO event for client connections
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected: {request.sid}")

# SocketIO event for client disconnections
@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected: {request.sid}")

# SocketIO event for subscribing to progress updates
@socketio.on('subscribe')
def handle_subscribe(data):
    file_id = data.get('file_id')
    if file_id:
        logger.info(f"Client {request.sid} subscribed to progress updates for {file_id}")
        if file_id in download_progress:
            # Send initial progress data
            socketio.emit(f'progress_update_{file_id}', download_progress[file_id], to=request.sid)

if __name__ == "__main__":
    port = 5000
    print(f"YouTube Downloader API Server running on port {port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)