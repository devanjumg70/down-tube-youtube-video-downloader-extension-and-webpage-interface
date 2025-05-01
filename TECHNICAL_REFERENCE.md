# YouTube Video Downloader: Technical Reference Guide

This technical reference guide provides detailed information about the codebase architecture, API endpoints, and implementation details for developers who want to modify or extend the project.

## Project Structure

```
youtube-video-downloader/
├── background.js         # Extension background script
├── content.js            # Content script for YouTube page interaction
├── icons/                # Extension icons in various sizes
│   ├── icon16.svg
│   ├── icon48.svg
│   └── icon128.svg
├── manifest.json         # Extension manifest file
├── popup.css             # Styles for extension popup
├── popup.html            # Popup HTML interface
├── popup.js              # Popup interaction logic
├── server.py             # Python Flask backend server
├── README.md             # Project overview
├── DEVELOPMENT_GUIDE.md  # Comprehensive development documentation
├── QUICK_SETUP.md        # Quick setup instructions
└── TECHNICAL_REFERENCE.md # This detailed technical reference
```

## Backend API Reference

### Server Initialization

The Flask server runs on port 5000 by default and includes CORS headers to allow cross-origin requests from the extension.

```python
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "expose_headers": "*"}})

# Add CORS headers to all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response
```

### API Endpoints

#### 1. Root Endpoint (`/`)

- **Method**: GET
- **Description**: Serves an interactive test page for the API
- **Response**: HTML page for API testing

#### 2. Video Information (`/api/info`)

- **Method**: GET
- **Parameters**:
  - `videoId` (required): YouTube video ID or URL
- **Description**: Retrieves video metadata and available formats
- **Response Example**:
```json
{
  "title": "Video Title",
  "channel": "Channel Name",
  "thumbnail": "https://i.ytimg.com/vi/VIDEO_ID/maxresdefault.jpg",
  "formats": [
    {
      "itag": "137",
      "qualityLabel": "1080p",
      "container": "mp4",
      "url": "https://example.com/video-url"
    },
    {
      "itag": "22",
      "qualityLabel": "720p",
      "container": "mp4",
      "url": "https://example.com/video-url"
    }
  ]
}
```

#### 3. Video Download (`/api/download`)

- **Method**: GET
- **Parameters**:
  - `videoId` (required): YouTube video ID
  - `itag` (required): Format identifier from the info endpoint
- **Description**: Downloads and processes the video with audio on the server, then serves the combined file
- **Response**: Video file with both audio and video streams combined in MP4 format

### Video Processing and Audio Handling

The server now offers two methods for video processing to ensure videos include audio:

#### 1. yt-dlp Built-in Merging

```python
def download_with_ytdlp(url, video_id, itag, file_id):
    """Download and process using yt-dlp's built-in merging capability"""
    output_path = os.path.join(TEMP_DIR, f"youtube_{video_id}_{file_id}.mp4")
    
    # Set up options for yt-dlp
    ydl_opts = {
        "format": f"{itag}+bestaudio/best",  # Specified format + best audio, or best combined
        "merge_output_format": "mp4",        # Force mp4 for compatibility
        "outtmpl": output_path,              # Output filename template
        "quiet": True,                       # Don't print progress
    }
    
    # Download and process the video on the server
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        
        # Return the processed file to the client
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"{title}.mp4",
            mimetype="video/mp4"
        )
```

#### 2. FFmpeg Direct Merging

```python
def download_with_ffmpeg(url, video_id, itag, file_id):
    """Download video and audio separately and merge with FFmpeg"""
    # Create temporary paths for video, audio, and output
    temp_video = os.path.join(TEMP_DIR, f"video_{video_id}_{file_id}.mp4")
    temp_audio = os.path.join(TEMP_DIR, f"audio_{video_id}_{file_id}.m4a")
    output_path = os.path.join(TEMP_DIR, f"merged_{video_id}_{file_id}.mp4")
    
    # Download video and audio separately
    with YoutubeDL({"format": itag, "outtmpl": temp_video}) as ydl:
        ydl.download([url])
    
    with YoutubeDL({"format": "bestaudio[ext=m4a]", "outtmpl": temp_audio}) as ydl:
        ydl.download([url])
    
    # Merge with FFmpeg
    ffmpeg_cmd = [
        'ffmpeg', 
        '-i', temp_video,  # Video stream
        '-i', temp_audio,  # Audio stream
        '-c:v', 'copy',    # Copy video stream (no re-encoding)
        '-c:a', 'aac',     # Use AAC codec for audio
        '-strict', 'experimental',
        output_path
    ]
    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)
    
    # Return the merged file
    return send_file(
        output_path,
        as_attachment=True,
        download_name=f"{title}.mp4",
        mimetype="video/mp4"
    )
```

#### FFmpeg Availability Detection

The server automatically detects if FFmpeg is installed on the system:

```python
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
```

### Format Filtering

The server filters video formats while clearly identifying formats that contain both video and audio:

```python
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
```

## Frontend Reference

### Manifest V3 Configuration

```json
{
  "manifest_version": 3,
  "name": "Video Downloader",
  "version": "1.0",
  "permissions": [
    "activeTab",
    "downloads",
    "scripting",
    "storage"
  ],
  "host_permissions": [
    "https://*.youtube.com/*",
    "https://www.youtube.com/oembed*",
    "https://i.ytimg.com/*",
    "http://localhost:*/*",
    "http://127.0.0.1:*/*"
  ],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [
    {
      "matches": ["https://*.youtube.com/*"],
      "js": ["content.js"]
    }
  ],
  "action": {
    "default_popup": "popup.html"
  }
}
```

### Background Script Architecture

The background script (`background.js`) serves as an intermediary between the popup UI and the backend server. It handles:

1. **Server Communication**: Makes fetch requests to the backend API
2. **Error Handling**: Provides fallback mechanisms when the server is unavailable
3. **Download Management**: Utilizes Chrome's download API to save files

```javascript
// API Server configuration
const API_SERVER = 'http://localhost:5000';

// Communication structure using Message API
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fetchVideoInfo') {
    fetchVideoInfo(request.videoId, sendResponse);
    return true; // Indicates async response
  } 
  else if (request.action === 'downloadVideo') {
    downloadVideo(request.videoId, request.itag, request.fileName, request.downloadUrl, sendResponse);
    return true; // Indicates async response
  }
});
```

### Popup Architecture

The popup script (`popup.js`) handles:

1. **User Interface**: Manages UI elements and state
2. **URL Validation**: Checks and extracts video IDs from YouTube URLs
3. **Background Communication**: Sends messages to the background script
4. **Dynamic UI Updates**: Creates resolution buttons based on available formats

```javascript
// Video ID extraction from YouTube URLs
function extractVideoId(url) {
  const regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*/;
  const match = url.match(regExp);
  return (match && match[7].length === 11) ? match[7] : false;
}

// Main communication flow
async function fetchVideoInfo(url) {
  // Extract video ID
  const videoId = extractVideoId(url);
  
  // Request video info from background script
  chrome.runtime.sendMessage(
    { action: 'fetchVideoInfo', videoId: videoId },
    function(response) {
      // Handle response
      // Display video information
      // Create download buttons
    }
  );
}
```

## Error Handling Strategy

### Backend Errors

The server catches exceptions during video info extraction and returns structured error responses:

```python
try:
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        # Process info...
except Exception as e:
    return jsonify({"error": str(e)})
```

### Frontend Fallbacks

The extension implements a tiered fallback strategy:

1. **Primary**: Try Flask backend API for complete video information
2. **Secondary**: If server fails, use YouTube's oEmbed API for basic metadata
3. **Tertiary**: If all APIs fail, display a user-friendly error message

```javascript
try {
  // Primary: Flask backend API
  const response = await fetch(`${API_SERVER}/api/info?videoId=${videoId}`);
  // Process response...
} catch (error) {
  // Secondary: oEmbed fallback
  try {
    const oEmbedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(videoUrl)}&format=json`;
    const oembedResponse = await fetch(oEmbedUrl);
    // Process oEmbed response...
  } catch (fallbackError) {
    // Tertiary: User-friendly error
    sendResponse({ error: 'Failed to fetch video information. Please try again later.' });
  }
}
```

## Security Considerations

### CORS Configuration

The extension requires specific CORS headers to communicate with the backend:

```python
response.headers['Access-Control-Allow-Origin'] = '*'
response.headers['Access-Control-Allow-Headers'] = '*'
response.headers['Access-Control-Allow-Methods'] = '*'
```

### Host Permissions

The extension requires explicit permissions in `manifest.json` to access:

1. YouTube domains for content extraction
2. Local server for API communication
3. YouTube's oEmbed API for fallback metadata

### Data Handling

1. The extension does not store user data or video content
2. Downloads are initiated through Chrome's download API, providing built-in security
3. Video URLs are obtained through yt-dlp, which follows YouTube's HTML structure changes

## Optimization Techniques

### Performance Optimizations

The server employs several strategies to optimize download and processing speed:

#### 1. Multi-threaded Downloads with aria2c

The server automatically detects and utilizes aria2c for faster downloads:

```python
# Check if aria2c is available
def check_aria2c():
    try:
        subprocess.run(['aria2c', '--version'], check=True, capture_output=True)
        logger.info("aria2c is available")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("aria2c is not available, falling back to default downloader")
        return False

# When aria2c is available, add multi-threading options
if ARIA2C_AVAILABLE:
    ydl_opts.update({
        "external_downloader": "aria2c",
        "external_downloader_args": [
            "--max-connection-per-server=16", 
            "--min-split-size=1M", 
            "--max-concurrent-downloads=16"
        ]
    })
```

#### 2. Optimized FFmpeg Parameters

FFmpeg merging uses optimized parameters for faster processing and better quality:

```python
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
```

#### 3. Direct Format Selection

The server detects and prioritizes formats that already have both video and audio:

```python
# Check if a format has both video and audio streams
has_both_streams = False
try:
    with YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        for f in info["formats"]:
            if f["format_id"] == itag and f.get("vcodec") != "none" and f.get("acodec") != "none":
                has_both_streams = True
                logger.info(f"Format {itag} already has both video and audio streams")
                break
    
    # If format already has both streams, use direct download
    ydl_opts = {
        "format": itag if has_both_streams else f"{itag}+bestaudio/best",
        # Other options...
    }
except Exception as e:
    logger.warning(f"Error checking format streams: {str(e)}")
```

#### 4. Efficient Cleanup

The server uses background cleanup to ensure temporary files are removed:

```python
@response.call_on_close
def cleanup():
    try:
        for file_path in [temp_video, temp_audio, output_path]:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error removing files: {str(e)}")
```

### Format Filtering

Instead of offering all available formats (which can be numerous), the server filters to common resolutions:

```python
if f["ext"] == "mp4" and f.get("height") in [360, 480, 720, 1080]:
    # Include this format
```

### Quality Deduplication

The server removes duplicate quality formats to simplify the user experience:

```python
seen_qualities = set()
if quality not in seen_qualities:
    # Add to formats list
    seen_qualities.add(quality)
```

### Asynchronous Communication

The extension uses asynchronous messaging with explicit `return true` for proper callback handling:

```javascript
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Process request asynchronously
  return true; // Keeps the message channel open
});
```

## Extension to Server Communication Flow

1. User clicks "Fetch Video" in the popup
2. Popup extracts video ID and sends to background script
3. Background script requests info from Flask server
4. Server uses yt-dlp to extract video information
5. Server returns formatted JSON response
6. Background script processes and returns to popup
7. Popup displays video info and format buttons
8. User clicks desired format button
9. Download request sent to background script
10. Server downloads and processes video with audio
11. Server combines video and audio streams
12. Server sends complete file to browser
13. Browser handles file download to user's device

## Advanced Customization

### Adding Support for Additional Platforms

To extend beyond YouTube:

1. Create new extraction functions in `server.py`
2. Add platform detection logic in the extension
3. Update URL validation patterns for the new platform

### Custom Format Filtering

To customize available formats:

1. Modify the format filtering logic in `server.py`:
```python
# Change this list for different resolutions
if f.get("height") in [360, 480, 720, 1080, 1440, 2160]:
    # Include this format
```

### UI Customization

#### Web Interface with FFmpeg Toggle

The server includes a web interface (`/` route) that allows direct testing with built-in FFmpeg support:

```html
<div class="form-group">
    <!-- FFmpeg status display -->
    <p><strong>System Status:</strong> FFmpeg is <span class="status {status_class}">{ffmpeg_status}</span></p>
    
    <!-- URL input -->
    <input type="text" id="videoInput" placeholder="YouTube URL">
    <button id="testBtn">Fetch Video</button>
    
    <!-- FFmpeg toggle option -->
    <label>
        <input type="checkbox" id="useFFmpeg"> 
        Use FFmpeg for merging (if available locally)
    </label>
</div>
```

#### Chrome Extension

The popup interface can be customized by modifying:

1. `popup.html` for structure changes:
   ```html
   <!-- Add FFmpeg toggle to the popup -->
   <div class="options">
     <label>
       <input type="checkbox" id="useFFmpeg"> 
       Use FFmpeg merging (if available)
     </label>
   </div>
   ```

2. `popup.css` for styling:
   ```css
   /* Add styling for the FFmpeg status indicator */
   .ffmpeg-status {
     display: inline-block;
     padding: 2px 6px;
     border-radius: 3px;
     font-size: 12px;
     margin-left: 5px;
   }
   .available { background: #d4edda; color: #155724; }
   .unavailable { background: #f8d7da; color: #721c24; }
   ```

3. `popup.js` for dynamic elements and FFmpeg support:
   ```javascript
   // Add FFmpeg availability check
   async function checkFFmpegAvailability() {
     try {
       const response = await fetch(`${API_SERVER}/api/info?videoId=dQw4w9WgXcQ`);
       const data = await response.json();
       return data.ffmpeg_available || false;
     } catch (error) {
       return false;
     }
   }
   
   // Update download request to include FFmpeg preference
   function downloadVideo(videoId, itag, title) {
     const useFFmpeg = document.getElementById('useFFmpeg').checked;
     chrome.runtime.sendMessage({
       action: 'downloadVideo',
       videoId: videoId,
       itag: itag,
       fileName: `${title}.mp4`,
       useFFmpeg: useFFmpeg
     }, handleDownloadResponse);
   }
   ```