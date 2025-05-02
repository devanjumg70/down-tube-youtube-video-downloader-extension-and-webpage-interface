from flask import Flask, jsonify, request, redirect, send_file, Response
from yt_dlp import YoutubeDL
from flask_cors import CORS
import os
import tempfile
import logging
import time
import uuid
import subprocess
import threading

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
        # Check ffmpeg version and capabilities
        result = subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True, text=True)
        version_info = result.stdout.split('\n')[0]
        logger.info(f"FFmpeg detected: {version_info}")
        
        # Verify key codecs are available
        codecs = subprocess.run(['ffmpeg', '-codecs'], check=True, capture_output=True, text=True)
        required_codecs = ['h264', 'aac']
        missing_codecs = [codec for codec in required_codecs if codec not in codecs.stdout]
        
        if missing_codecs:
            logger.warning(f"FFmpeg missing required codecs: {missing_codecs}")
            return False
            
        logger.info("FFmpeg is fully available with required codecs")
        return True
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        logger.warning(f"FFmpeg is not available: {str(e)}")
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

# Global dict to track batch download jobs
BATCH_JOBS = {
    # job_id: {
    #    'status': 'processing|completed|failed',
    #    'total': number of videos in playlist,
    #    'completed': number of videos successfully downloaded,
    #    'failed': number of videos that failed,
    #    'playlist_id': playlist ID,
    #    'playlist_title': title of the playlist,
    #    'started_at': timestamp when job started,
    #    'completed_at': timestamp when job completed (if finished)
    # }
}

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

def extract_playlist_id(url):
    """Extract the playlist ID from a YouTube URL"""
    if "/" in url or "youtu" in url:
        from urllib.parse import urlparse, parse_qs
        
        # Handle playlist URLs
        query = parse_qs(urlparse(url).query)
        playlist_id = query.get("list", [None])[0]
        
        if playlist_id:
            return playlist_id
    
    # Check if it's a direct playlist ID
    if url and url.startswith(("PL", "UU", "LL", "FL", "RD", "UL", "TL", "PU", "OLAK")):
        return url
        
    return None

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
            
            # First, track the resolutions we've already seen
            tracked_resolutions = set()
            
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
                            # Track the resolution we've added
                            tracked_resolutions.add(f['height'])
            
            # Then add video-only formats ONLY for resolutions that don't have a combined format
            # We'll combine with audio when downloading, so we don't need two 360p buttons, etc.
            for f in info["formats"]:
                if f["ext"] == "mp4" and f.get("height") in [360, 480, 720, 1080]:
                    # Skip this resolution if we already have a combined format for it
                    if f['height'] in tracked_resolutions:
                        continue
                        
                    quality = f"{f['height']}p"
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
                        # Track this resolution too
                        tracked_resolutions.add(f['height'])
            
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

def download_with_ytdlp(url, video_id, itag, file_id, is_batch=False):
    """Download and process using yt-dlp's built-in merging capability"""
    output_path = os.path.join(TEMP_DIR, f"youtube_{video_id}_{file_id}.mp4")
    
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
            
            # If this is part of a batch download, return the path rather than the file
            if is_batch:
                logger.info(f"Batch download complete for video {video_id}: {output_path}")
                return output_path
            
            # Otherwise, return the file for direct download
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

def download_with_ffmpeg(url, video_id, itag, file_id, is_batch=False):
    """Download video and audio separately and merge with FFmpeg, or handle audio-only formats"""
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
                        return download_with_ytdlp(url, video_id, itag, file_id, is_batch)
    
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
        
        # For batch downloads, return the path without sending the file
        if is_batch:
            # Clean up the temporary audio file but keep the output
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
            return output_path
            
        # For regular downloads, send the file
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
        with YoutubeDL(video_opts) as ydl:
            ydl.download([url])
        
        # Download audio
        audio_opts = base_opts.copy()
        audio_opts.update({
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": temp_audio,
        })
        logger.info("Downloading audio stream")
        with YoutubeDL(audio_opts) as ydl:
            ydl.download([url])
        
        # Check if files exist
        if not os.path.exists(temp_video) or not os.path.exists(temp_audio):
            logger.error("Video or audio file not downloaded correctly")
            return jsonify({"error": "Failed to download video or audio streams"}), 500
        
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
        
        # Check if merged file exists
        if not os.path.exists(output_path):
            logger.error("FFmpeg merging failed")
            return jsonify({"error": "Failed to merge video and audio streams"}), 500
        
        # Log success
        file_size = os.path.getsize(output_path)
        logger.info(f"Merged file created: {output_path}, size: {file_size} bytes")
        
        # If this is a batch download, return the path without sending the file
        if is_batch:
            # Clean up temporary files but keep the output
            for file_path in [temp_video, temp_audio]:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Removed temporary file: {file_path}")
            return output_path
            
        # For regular downloads, return the merged file
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

@app.route("/api/playlist")
def get_playlist_info():
    """Get information about a YouTube playlist"""
    playlist_id = request.args.get("playlistId")
    
    if not playlist_id:
        return jsonify({"error": "Missing playlist ID"}), 400
    
    # Handle both direct IDs and URLs
    if "/" in playlist_id or "youtu" in playlist_id:
        extracted_id = extract_playlist_id(playlist_id)
        if extracted_id:
            playlist_id = extracted_id
    
    # Use full playlist URL
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    logger.info(f"Received playlist info request for playlist ID: {playlist_id}")
    
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,  # Don't extract individual videos to save time
        "skip_download": True,
        "ignoreerrors": True   # Skip unavailable videos
    }
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            # Extract playlist info
            info = ydl.extract_info(url, download=False)
            
            if not info:
                return jsonify({"error": "Could not retrieve playlist information"}), 404
            
            # Process videos in the playlist
            videos = []
            for entry in info.get('entries', []):
                if entry:
                    videos.append({
                        "id": entry.get('id'),
                        "title": entry.get('title', 'Unknown Title'),
                        "thumbnail": entry.get('thumbnail', f"https://i.ytimg.com/vi/{entry.get('id')}/maxresdefault.jpg"),
                        "duration": entry.get('duration'),
                        "channel": entry.get('uploader', 'Unknown Channel')
                    })
            
            return jsonify({
                "id": playlist_id,
                "title": info.get('title', 'YouTube Playlist'),
                "channel": info.get('uploader', 'YouTube Channel'),
                "videoCount": len(videos),
                "videos": videos
            })
    except Exception as e:
        logger.error(f"Error extracting playlist info: {str(e)}")
        return jsonify({"error": str(e)})

@app.route("/api/batch/status")
def batch_status():
    """Get status of a batch download job"""
    job_id = request.args.get("jobId")
    
    if not job_id:
        return jsonify({"error": "Missing job ID"}), 400
    
    if job_id not in BATCH_JOBS:
        return jsonify({"error": "Invalid job ID or job has expired"}), 404
    
    job_info = BATCH_JOBS[job_id]
    
    # Calculate progress percentage if there are videos to process
    progress = 0
    if job_info['total'] > 0:
        progress = int((job_info['completed'] + job_info['failed']) / job_info['total'] * 100)
    
    return jsonify({
        "job_id": job_id,
        "status": job_info['status'],
        "progress": progress,
        "total": job_info['total'],
        "completed": job_info['completed'],
        "failed": job_info['failed'],
        "playlist_id": job_info['playlist_id'],
        "playlist_title": job_info['playlist_title'],
        "started_at": job_info['started_at'],
        "completed_at": job_info['completed_at']
    })

@app.route("/api/batch/download", methods=['GET', 'POST'])
def batch_download():
    """Start a batch download job for multiple videos"""
    # Handle both GET and POST requests
    if request.method == 'POST':
        # For JSON requests
        data = request.get_json(silent=True) or {}
        playlist_id = data.get("playlistId")
        format_id = data.get("format", data.get("formatId", "best"))
        use_ffmpeg_param = str(data.get("useFFmpeg", "true"))
    else:
        # For query parameters
        playlist_id = request.args.get("playlistId")
        format_id = request.args.get("formatId", request.args.get("format", "best"))
        use_ffmpeg_param = request.args.get("useFFmpeg", request.args.get("use_ffmpeg", "true"))
    
    use_ffmpeg = str(use_ffmpeg_param).lower() == "true"
    
    if not playlist_id:
        return jsonify({"error": "Missing playlist ID"}), 400
        
    # Handle both direct IDs and URLs
    if "/" in playlist_id or "youtu" in playlist_id:
        extracted_id = extract_playlist_id(playlist_id)
        if extracted_id:
            playlist_id = extracted_id
    
    # Use full playlist URL
    url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    # Create a unique job ID for this batch download
    job_id = str(uuid.uuid4())
    
    logger.info(f"Starting batch download for playlist ID: {playlist_id}, format: {format_id}, job ID: {job_id}")
    
    # We'll process this in a background thread to avoid blocking the response
    def get_best_format(video_url, target_resolution=None):
        """Get the best available format for a video that matches the target resolution"""
        ydl_opts = {"quiet": True, "listformats": True}
        with YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(video_url, download=False)
                formats = info.get('formats', [])
                
                if not target_resolution or target_resolution == "best":
                    return "best"
                
                # Try to find the exact match for target resolution
                resolution_map = {
                    "1080": 1080,
                    "720": 720,
                    "480": 480,
                    "360": 360,
                    "audio": 0  # Special case for audio
                }
                
                target_height = resolution_map.get(str(target_resolution), None)
                if target_height is None:
                    return "best"  # Default to best if invalid resolution
                
                # For audio only request
                if target_resolution == "audio" or target_height == 0:
                    audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"]
                    if audio_formats:
                        return max(audio_formats, key=lambda x: x.get("quality", 0)).get("format_id", "bestaudio")
                    return "bestaudio"
                
                # For video requests, find closest match
                video_formats = [f for f in formats if 
                                f.get("height") and 
                                f.get("vcodec") != "none" and
                                f.get("height") <= target_height]
                
                if video_formats:
                    # Find format with closest height to target
                    best_video = max(video_formats, key=lambda x: x.get("height", 0))
                    return best_video.get("format_id", "best")
                
                # If no suitable format found, use the default best
                return "best"
            except Exception as e:
                logger.error(f"Error finding best format for {video_url}: {str(e)}")
                return "best"  # Default to best on error
                
    def run_in_app_context(func, *args, **kwargs):
        """Run a function within the Flask application context"""
        with app.app_context():
            return func(*args, **kwargs)
            
    def process_batch():
        try:
            # First, get the list of videos
            ydl_opts_info = {
                "quiet": True,
                "extract_flat": True,
                "skip_download": True,
                "ignoreerrors": True,
                "no_warnings": True
            }
            
            # Track failed videos for retry
            BATCH_JOBS[job_id]['failed_videos'] = []
            BATCH_JOBS[job_id]['completed_videos'] = []
            BATCH_JOBS[job_id]['last_processed_index'] = 0
            
            with YoutubeDL(ydl_opts_info) as ydl:
                playlist_info = ydl.extract_info(url, download=False)
                
                if not playlist_info or 'entries' not in playlist_info:
                    logger.error(f"Could not retrieve playlist information for {playlist_id}")
                    BATCH_JOBS[job_id]['status'] = 'failed'
                    BATCH_JOBS[job_id]['completed_at'] = time.time()
                    return
                
                # Update job info with playlist details
                BATCH_JOBS[job_id]['total'] = len(playlist_info.get('entries', []))
                BATCH_JOBS[job_id]['playlist_title'] = playlist_info.get('title', 'YouTube Playlist')
                
                # Process each video
                success_count = 0
                failed_count = 0
                entries = playlist_info.get('entries', [])
                total_videos = len(entries)
                
                for i, entry in enumerate(entries):
                    if not entry or not entry.get('id'):
                        logger.warning(f"Skipping invalid entry at position {i}")
                        failed_count += 1
                        BATCH_JOBS[job_id]['failed'] = failed_count
                        continue
                    
                    video_id = entry.get('id')
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    
                    try:
                        # For each video, create a unique filename
                        file_id = str(uuid.uuid4())
                        
                        # Get the best available format for this specific video that matches the target
                        actual_format = get_best_format(video_url, format_id)
                        logger.info(f"Selected format {actual_format} for video {video_id} (requested: {format_id})")
                        
                        if FFMPEG_AVAILABLE and use_ffmpeg:
                            logger.info(f"Processing video {i+1}/{total_videos}: {video_id} with FFmpeg")
                            output_path = download_with_ffmpeg(video_url, video_id, actual_format, file_id, is_batch=True)
                        else:
                            logger.info(f"Processing video {i+1}/{total_videos}: {video_id} with yt-dlp")
                            output_path = download_with_ytdlp(video_url, video_id, actual_format, file_id, is_batch=True)
                        
                        if output_path:
                            success_count += 1
                            BATCH_JOBS[job_id]['completed'] = success_count
                            
                            # Cleanup the output file for batch downloads 
                            # (we don't need to keep them since the user would have already downloaded them individually)
                            if os.path.exists(output_path):
                                os.remove(output_path)
                                logger.info(f"Removed temporary batch file: {output_path}")
                        else:
                            failed_count += 1
                            BATCH_JOBS[job_id]['failed'] = failed_count
                            BATCH_JOBS[job_id]['failed_videos'].append({
                                'video_id': video_id,
                                'index': i
                            })
                        
                        # Track progress
                        BATCH_JOBS[job_id]['last_processed_index'] = i
                        BATCH_JOBS[job_id]['completed_videos'].append(video_id) if success_count > 0 else None
                    except Exception as e:
                        logger.error(f"Error downloading video {video_id}: {str(e)}")
                        failed_count += 1
                        BATCH_JOBS[job_id]['failed'] = failed_count
                
                # Update job status to completed
                BATCH_JOBS[job_id]['status'] = 'completed'
                BATCH_JOBS[job_id]['completed_at'] = time.time()
                logger.info(f"Batch download completed. Success: {success_count}, Failed: {failed_count}")
        except Exception as e:
            logger.error(f"Error processing batch download: {str(e)}")
            BATCH_JOBS[job_id]['status'] = 'failed'
            BATCH_JOBS[job_id]['completed_at'] = time.time()
    
    # Initialize job status in the tracking dictionary
    BATCH_JOBS[job_id] = {
        'status': 'processing',
        'total': 0,
        'completed': 0,
        'failed': 0,
        'playlist_id': playlist_id,
        'playlist_title': 'Loading...',
        'started_at': time.time(),
        'completed_at': None
    }
    
    # Start the background thread with Flask app context
    def run_with_app_context():
        with app.app_context():
            process_batch()
            
    thread = threading.Thread(target=run_with_app_context)
    thread.daemon = True
    thread.start()
    
    # Return immediately with the job ID
    return jsonify({
        "job_id": job_id,
        "message": "Batch download job started",
        "status": "processing"
    })

@app.route("/")
def hello():
    # Modern static HTML with improved UI
    ffmpeg_status = "available" if FFMPEG_AVAILABLE else "not available"
    aria2c_status = "available" if ARIA2C_AVAILABLE else "not available"
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YouTube Video Downloader</title>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {{
                /* Light Theme (Default) */
                --primary-color: #ff4b4b;
                --primary-hover: #e63e3e;
                --secondary-color: #4285f4;
                --secondary-hover: #3367d6;
                --text-dark: #2d3748;
                --text-light: #718096;
                --bg-light: #f8fafc;
                --bg-white: #ffffff;
                --card-bg: #ffffff;
                --shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                --border-radius: 8px;
                --border-color: #e2e8f0;
                --success-color: #48bb78;
                --error-color: #f56565;
            }}
            
            /* Dark Theme */
            [data-theme="dark"] {{
                --text-dark: #f7fafc;
                --text-light: #cbd5e0;
                --bg-light: #2d3748;
                --bg-white: #1a202c;
                --card-bg: #2d3748;
                --border-color: #4a5568;
                --shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
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
            }}
            
            .container {{
                background: var(--bg-white);
                border-radius: var(--border-radius);
                box-shadow: var(--shadow);
                overflow: hidden;
            }}
            
            .header {{
                background: linear-gradient(to right, var(--primary-color), #ff7676);
                color: white;
                padding: 30px 20px;
                text-align: center;
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
                background: var(--card-bg);
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
                background: var(--card-bg);
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
                background: var(--card-bg);
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
                transition: all 0.2s;
            }}
            
            .download-btn:hover {{
                background-color: var(--secondary-hover);
                transform: translateY(-2px);
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
                    
                    <div class="toggle-container">
                        <label class="toggle-switch">
                            <input type="checkbox" id="darkModeToggle">
                            <span class="toggle-slider"></span>
                        </label>
                        <span class="toggle-label">
                            <i class="fas fa-moon"></i> Dark Mode
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
        document.getElementById('fetchBtn').addEventListener('click', async () => {{
            const input = document.getElementById('videoInput').value.trim();
            const resultDiv = document.getElementById('result');
            const loader = document.querySelector('.loader');
            const infoMessage = document.querySelector('.info-message');
            
            if (!input) {{
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
            }}
            
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
                    resultDiv.innerHTML = `
                        <div class="error-msg">
                            <i class="fas fa-exclamation-circle"></i>
                            <span>Error: ${{data.error}}</span>
                        </div>
                    `;
                    return;
                }}
                
                // Get FFmpeg setting
                const useFFmpeg = document.getElementById('useFFmpeg').checked;
                
                // Create download buttons
                let buttonsHtml = '';
                if (data.formats && data.formats.length > 0) {{
                    data.formats.forEach(format => {{
                        // Determine if this is an audio format
                        const isAudioOnly = format.qualityLabel.includes('Audio Only');
                        const buttonClass = isAudioOnly ? 'download-btn audio' : 'download-btn';
                        const icon = isAudioOnly ? 'fa-music' : 'fa-video';
                        
                        // Clean up format label for audio and video
                        let formatLabel = format.qualityLabel;
                        if (formatLabel.includes('(MP3)')) {{
                            formatLabel = 'Audio Only (MP3)';
                        }} else if (formatLabel.includes('(AAC)')) {{
                            formatLabel = 'Audio Only (AAC)';
                        }} else if (formatLabel.includes('(with audio)')) {{
                            // Remove "(with audio)" text to keep format labels consistent
                            formatLabel = formatLabel.replace(' (with audio)', '');
                        }}
                        
                        buttonsHtml += `
                            <a class="${{buttonClass}}" 
                               href="/api/download?videoId=${{encodeURIComponent(videoId)}}&itag=${{format.itag}}&use_ffmpeg=${{useFFmpeg}}"
                               target="_blank">
                               <i class="fas ${{icon}}"></i> ${{formatLabel}}
                            </a>
                        `;
                    }});
                }}
                
                // Display video info
                resultDiv.innerHTML = `
                    <div class="video-info">
                        <div class="video-details">
                            <img src="${{data.thumbnail}}" class="video-thumbnail" alt="${{data.title}}">
                            <div class="video-text">
                                <h2>${{data.title || 'Unknown Title'}}</h2>
                                <p><i class="fas fa-user"></i> ${{data.channel || 'Unknown Channel'}}</p>
                                <p><i class="fas fa-info-circle"></i> Select your preferred format below</p>
                            </div>
                        </div>
                        
                        <div class="download-section">
                            <h3><i class="fas fa-download"></i> Available Download Options</h3>
                            <div class="download-grid">
                                ${{buttonsHtml || '<p>No formats available</p>'}}
                            </div>
                        </div>
                    </div>
                `;
            }} catch (error) {{
                resultDiv.innerHTML = `
                    <div class="error-msg">
                        <i class="fas fa-exclamation-circle"></i>
                        <span>Error: ${{error.message}}</span>
                    </div>
                `;
            }}
        }});
        
        // Auto-fetch on paste
        document.getElementById('videoInput').addEventListener('paste', (e) => {{
            // Short delay to let the paste complete
            setTimeout(() => {{
                const input = document.getElementById('videoInput').value.trim();
                if (input && (input.includes('youtube.com') || input.includes('youtu.be'))) {{
                    document.getElementById('fetchBtn').click();
                }}
            }}, 100);
        }});
        
        // Enter key event listener
        document.getElementById('videoInput').addEventListener('keypress', (e) => {{
            if (e.key === 'Enter') {{
                document.getElementById('fetchBtn').click();
            }}
        }});
        
        // Disable FFmpeg toggle if not available
        const ffmpegAvailable = {str(FFMPEG_AVAILABLE).lower()};
        if (!ffmpegAvailable) {{
            document.getElementById('useFFmpeg').disabled = true;
            document.querySelector('.toggle-label').innerHTML += ' <span style="color: var(--error-color); font-size: 12px;">(Not available)</span>';
        }}
        
        // Dark mode handling
        const darkModeToggle = document.getElementById('darkModeToggle');
        const htmlElement = document.documentElement;
        
        // Function to set theme
        function setTheme(isDark) {{
            if (isDark) {{
                htmlElement.setAttribute('data-theme', 'dark');
                darkModeToggle.checked = true;
            }} else {{
                htmlElement.removeAttribute('data-theme');
                darkModeToggle.checked = false;
            }}
            // Save preference
            localStorage.setItem('darkMode', isDark ? 'enabled' : 'disabled');
        }}
        
        // Check for saved theme preference
        const savedTheme = localStorage.getItem('darkMode');
        if (savedTheme === 'enabled') {{
            setTheme(true);
        }} else if (savedTheme === null) {{
            // Check if user prefers dark mode via OS settings
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            setTheme(prefersDark);
        }}
        
        // Toggle theme when switch is clicked
        darkModeToggle.addEventListener('change', function() {{
            setTheme(this.checked);
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