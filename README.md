# YouTube Video Downloader Chrome Extension

A Chrome extension that allows users to download videos from YouTube in various resolutions. This extension uses a two-part architecture with a frontend Chrome extension and a backend Python server powered by yt-dlp for reliable video downloading.

## Features

- Enter a YouTube video URL or use the current tab's URL
- Fetch video information including title, channel, and thumbnail
- View available download options in different resolutions (360p, 480p, 720p, 1080p, audio-only)
- Download videos with a simple click
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

1. Make sure the backend server is running (`python server.py`)
2. Click the extension icon in your Chrome toolbar
3. The extension will automatically fill in the URL if you're on a YouTube page
4. If not on YouTube, paste a YouTube URL in the input field
5. Click the "Fetch Video" button to retrieve video information
6. Select your preferred resolution from the available options
7. When you click a resolution button, your download will begin automatically
8. Choose where to save the file when prompted

## Troubleshooting

- **Extension shows "Failed to fetch video information"**: 
  - Ensure the backend server is running
  - Check that the server URL in background.js is correct (default: http://localhost:8080)
  - Verify you have internet connectivity

- **Download doesn't start**:
  - Check if FFmpeg is properly installed
  - Ensure the URL is a valid YouTube video URL
  - Try a different resolution option

- **Error: Address already in use**:
  - The port (8080) is already in use. Edit server.py to use a different port
  - If you change the port, also update the API_SERVER URL in background.js

## Technical Architecture

This extension uses a two-part architecture:

1. **Frontend Chrome Extension**:
   - User interface built with HTML, CSS, and JavaScript
   - Communication with backend server via fetch API
   - Chrome Extension APIs for browser integration
   - Fallback to YouTube's oEmbed API if server connection fails

2. **Backend Python Server**:
   - Flask web server for handling API requests
   - yt-dlp library for reliable video extraction
   - CORS support for Chrome extension communication
   - Format filtering for providing clean resolution options

### File Structure

- **Extension Files**:
  - `manifest.json`: Extension configuration and permissions
  - `popup.html`: User interface for the extension
  - `popup.css`: Styling for the popup
  - `popup.js`: Frontend JavaScript for user interactions
  - `background.js`: Background script for server communication
  - `content.js`: Content script for interacting with YouTube pages
  - `icons/`: Extension icons in various sizes

- **Server Files**:
  - `server.py`: Flask server with yt-dlp integration
  - `requirements.txt`: Python dependencies

## Advanced Configuration

### Customizing the Server

You can modify `server.py` to change:
- The port number (default: 8080)
- Available video qualities (currently 360p, 480p, 720p, 1080p)
- Additional formats like audio-only options
- CORS settings for security

If you change the server port, remember to update the `API_SERVER` variable in `background.js`.

### Adding Features

The extension can be extended with:
- Support for additional video platforms
- Batch download capabilities
- Custom download naming options
- Metadata extraction (subtitles, chapters, etc.)

## License

This project is for educational purposes only.

## Disclaimer

This extension is not affiliated with or endorsed by YouTube or Google. Users are responsible for ensuring compliance with YouTube's Terms of Service when using this extension. Video downloading may be subject to copyright laws in your country.