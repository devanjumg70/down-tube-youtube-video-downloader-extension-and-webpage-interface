# YouTube Video Downloader Chrome Extension

A Chrome extension that allows users to download videos from YouTube in various resolutions. This extension uses a two-part architecture with a frontend Chrome extension and a backend Python server powered by yt-dlp for reliable video downloading.

## Features

- Enter a YouTube video URL or use the current tab's URL
- Fetch video information including title, channel, and thumbnail
- View available download options in different resolutions (360p, 480p, 720p, 1080p, audio-only)
- Download videos with a simple click
- Download entire YouTube playlists with batch processing
- Track download progress for batch operations
- Multi-threaded downloading with aria2c integration
- FFmpeg integration for high-quality video/audio merging
- Fallback mechanisms if connection to server fails

## System Requirements

- Google Chrome browser (or any Chromium-based browser)
- Python 3.6 or higher for the backend server
- FFmpeg (recommended for better video processing)

## Installation

### Step 1: Setting up the Backend Server

1. Install the required Python packages:
   ```
   pip install flask flask-cors yt-dlp
   ```

2. Install FFmpeg (recommended for optimal quality):
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt install ffmpeg` or equivalent for your distro

3. Start the server:
   ```
   python server.py
   ```
   
   The server will run on `http://localhost:8080` by default.

### Step 2: Installing the Chrome Extension

1. Download or clone this repository to your local machine
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode" by toggling the switch in the top-right corner
4. Click "Load unpacked" and select the folder containing the extension files
5. The extension should now be installed and visible in your Chrome toolbar

## Usage

### Single Video Download

1. Make sure the backend server is running (`python server.py`)
2. Click the extension icon in your Chrome toolbar
3. The extension will automatically fill in the URL if you're on a YouTube page
4. If not on YouTube, paste a YouTube URL in the input field
5. Click the "Fetch Video" button (or wait for auto-fetch)
6. Select your preferred resolution from the available options
7. Toggle the FFmpeg option for better quality (if available)
8. When you click a resolution button, your download will begin automatically
9. Choose where to save the file when prompted

### Playlist Download

1. Make sure the backend server is running (`python server.py`)
2. Navigate to any YouTube playlist page
3. Click the extension icon in your Chrome toolbar
4. The extension will automatically detect the playlist
5. View playlist information including video count, titles, and thumbnails
6. Select desired format for all videos from the dropdown
7. Toggle the FFmpeg option if needed
8. Click "Start Batch Download" to begin
9. Monitor the progress bar as videos download
10. Access downloaded files in your browser's download folder

## Troubleshooting

- **Extension shows "Failed to fetch video information"**: 
  - Ensure the backend server is running
  - Check that the server URL in background.js is correct (default: http://localhost:5000)
  - Verify you have internet connectivity

- **Download doesn't start**:
  - Check if FFmpeg is properly installed
  - Ensure the URL is a valid YouTube video URL
  - Try a different resolution option

- **Batch download not working**:
  - Verify the URL is a valid YouTube playlist
  - Check server console for any error messages
  - Make sure you have sufficient disk space
  - Try with a smaller playlist first

- **Slow download speeds**:
  - Enable the aria2c option for multi-threaded downloads
  - Check your internet connection speed
  - Try a different time of day when YouTube servers are less busy

- **Error: Address already in use**:
  - The port (5000) is already in use. Edit server.py to use a different port
  - If you change the port, also update the API_SERVER URL in background.js

## Technical Architecture

This extension uses a two-part architecture:

1. **Frontend Chrome Extension**:
   - Dual-mode user interface for single videos and playlists
   - Communication with backend server via fetch API
   - Chrome Extension APIs for browser integration and download management
   - Playlist detection and batch processing interface
   - Progress tracking for batch operations
   - Fallback to YouTube's oEmbed API if server connection fails

2. **Backend Python Server**:
   - Flask web server for handling API requests
   - yt-dlp library for reliable video extraction and batch processing
   - Threading for simultaneous batch downloads
   - Job tracking system for monitoring download progress
   - aria2c integration for multi-threaded downloading
   - FFmpeg integration for high-quality video/audio merging
   - CORS support for Chrome extension communication
   - Format filtering for providing clean resolution options

### File Structure

- **Extension Files**:
  - `manifest.json`: Extension configuration and permissions
  - `popup.html`: User interface for the extension
  - `popup.css`: Basic styling for the popup
  - `popup_new.css`: Enhanced modern styling with responsive design
  - `popup.js`: Frontend JavaScript for user interactions and batch processing
  - `background.js`: Background script for server communication and batch monitoring
  - `content.js`: Content script for interacting with YouTube pages
  - `icons/`: Extension icons in various sizes

- **Server Files**:
  - `server.py`: Flask server with yt-dlp integration and batch processing
  - `requirements.txt`: Python dependencies

## Advanced Configuration

### Customizing the Server

You can modify `server.py` to change:
- The port number (default: 5000)
- Available video qualities (currently 360p, 480p, 720p, 1080p)
- Batch processing parameters and threading options
- Additional formats like audio-only options
- CORS settings for security

If you change the server port, remember to update the `API_SERVER` variable in `background.js`.

### Adding Features

The extension can be extended with:
- Support for additional video platforms beyond YouTube
- Custom video range selection for partial downloads
- Auto-tagging of media files with metadata
- Subtitle extraction and embedding options
- Custom naming templates for downloaded files

## License

This project is for educational purposes only.

## Disclaimer

This extension is not affiliated with or endorsed by YouTube or Google. Users are responsible for ensuring compliance with YouTube's Terms of Service when using this extension. Video downloading may be subject to copyright laws in your country.