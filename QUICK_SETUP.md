# YouTube Video Downloader: Quick Setup Guide

This guide provides step-by-step instructions for setting up and using the YouTube Video Downloader Chrome Extension.

## Installation

### Backend Server Setup

1. **Prerequisites**:
   - Python 3.11 or newer
   - pip (Python package manager)

2. **Install Required Packages**:
   ```bash
   pip install flask flask-cors yt-dlp trafilatura
   ```

3. **Start the Server**:
   ```bash
   python server.py
   ```
   The server will start on port 5000 by default. You should see:
   ```
   YouTube Downloader API Server running on port 5000
   * Running on http://127.0.0.1:5000
   ```

### Chrome Extension Setup

1. **Load the Extension**:
   - Open Chrome and navigate to `chrome://extensions/`
   - Enable "Developer mode" (toggle in the top-right corner)
   - Click "Load unpacked" and select the extension directory

2. **Verify Installation**:
   - You should see the YouTube Video Downloader extension in your browser
   - Click the extension icon to open the popup interface

## Usage

### Downloading Videos

1. **Navigate to a YouTube Video**:
   - Go to any YouTube video page
   - Click the extension icon to open the popup

2. **Automatic URL Detection**:
   - The extension will automatically detect the URL of the current YouTube video
   - Alternatively, paste a YouTube URL into the input field

3. **Fetch Video Information**:
   - Click "Fetch Video" to retrieve available formats
   - The extension will display the video title, channel, and thumbnail

4. **Select Download Quality**:
   - Choose from available resolution options (360p, 480p, 720p, 1080p, etc.)
   - Click the corresponding quality button to start the download

5. **Save the File**:
   - Chrome will prompt you to save the file with a pre-filled name
   - Choose your desired location and click "Save"

### Troubleshooting

If you encounter issues:

1. **Check Server Connection**:
   - Ensure the Python server is running on port 5000
   - Look for any error messages in the terminal running the server

2. **Inspect Console Logs**:
   - Right-click the extension popup and select "Inspect"
   - Check the Console tab for any error messages

3. **Try Direct API Interface**:
   - Open http://localhost:5000/ in your browser
   - Use the test interface to verify the API works correctly

## FAQ

**Q: Why does the extension need a backend server?**
A: YouTube's Terms of Service prohibit direct downloading from their site. The server uses yt-dlp, a specialized library for handling YouTube's video formats and encryption.

**Q: Can I download videos from other websites?**
A: Currently, the extension only supports YouTube videos. Support for other platforms may be added in future updates.

**Q: Is there a limit to the video quality I can download?**
A: The extension provides all available formats that YouTube offers for each video, typically up to 1080p. Higher resolutions may be available for some videos.

**Q: Why do I see "Server connection failed" errors?**
A: This usually means the Python backend server isn't running. Start the server with `python server.py` and ensure port 5000 isn't blocked by a firewall.

## Tips

- For best video quality, choose the highest resolution format available
- The "Audio Only" option is ideal for music videos
- If a download fails, try a different resolution
- Some videos may have region restrictions that prevent downloading
- Keep yt-dlp updated with `pip install -U yt-dlp` to handle YouTube site changes