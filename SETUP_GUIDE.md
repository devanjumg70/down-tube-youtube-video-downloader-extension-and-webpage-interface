# YouTube Video Downloader Setup Guide

This guide provides step-by-step instructions for setting up and using the YouTube Video Downloader Chrome extension.

## Quick Start

1. Start the backend server: `python server.py`
2. Install the Chrome extension from the provided files
3. Click the extension icon and enter a YouTube URL
4. Select your preferred download quality

## Detailed Installation Instructions

### Backend Server Setup

1. **Install Python Dependencies**:
   ```bash
   pip install flask flask-cors yt-dlp
   ```

2. **Install FFmpeg** (recommended for better quality):
   - Windows: Download from [ffmpeg.org](https://ffmpeg.org/download.html)
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

3. **Start the Server**:
   ```bash
   python server.py
   ```
   
   The server runs on `http://localhost:8080` by default.

### Chrome Extension Installation

1. **Open Chrome Extensions Page**:
   - Navigate to `chrome://extensions/` in your Chrome browser
   - Enable "Developer mode" toggle in the top-right corner

2. **Load the Extension**:
   - Click "Load unpacked"
   - Select the folder containing the extension files
   - The extension icon should appear in your toolbar

## How to Use

1. **Visit a YouTube Video**:
   - Navigate to any YouTube video page
   - The extension will automatically detect the URL

2. **Or Enter a URL Manually**:
   - Click the extension icon
   - Paste a YouTube URL in the input field

3. **Fetch Video Information**:
   - Click the "Fetch Video" button
   - The extension will display the video title, channel, and thumbnail
   - Available download options will appear below

4. **Download the Video**:
   - Click on your preferred resolution/quality
   - Chrome will prompt you to choose a save location
   - The download will begin automatically

## Troubleshooting

### Extension Can't Connect to Server

- Ensure the Python server is running (`python server.py`)
- Check that the server is running on port 8080
- Verify there are no firewalls blocking the connection

### Download Fails

- Make sure the YouTube URL is valid
- Try a different resolution option
- Check your internet connection
- Ensure FFmpeg is installed for optimal quality

### Server Won't Start

- The port may already be in use
- Edit the port in `server.py` (line 86) if needed
- Don't forget to update the API_SERVER URL in `background.js` (line 4)

## Advanced Usage

### Supported Video Formats

The extension provides various formats:
- 360p (MP4)
- 480p (MP4)
- 720p (MP4)
- 1080p (MP4)
- Audio Only (MP3)

### Custom Download Names

Downloads are automatically named with:
- Video title
- Quality label
- File extension

Example: `Rick Astley - Never Gonna Give You Up - 720p.mp4`

## Security Considerations

- The extension requires permissions to access YouTube domains
- It uses the `downloads` API to save files to your computer
- All video processing happens through the backend server
- No data is sent to any third-party services

## Updates and Maintenance

To update the extension:
1. Pull the latest code
2. Update dependencies: `pip install -U flask flask-cors yt-dlp`
3. Reload the extension in Chrome

## Technical Support

If you encounter issues:
1. Check the browser console for errors (F12 > Console)
2. Review the server terminal output for backend errors
3. Verify all dependencies are installed correctly