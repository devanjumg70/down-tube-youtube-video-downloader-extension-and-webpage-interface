# YouTube Video Downloader: Quick Setup Guide

This guide provides step-by-step instructions for setting up and using the YouTube Video Downloader Chrome Extension.

## Installation

### Backend Server Setup

1. **Prerequisites**:
   - Python 3.11 or newer
   - pip (Python package manager)
   - FFmpeg (optional but recommended for better video quality)

2. **Install Required Packages**:
   ```bash
   pip install flask flask-cors yt-dlp trafilatura
   ```

3. **Install FFmpeg** (optional but recommended):
   - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to your PATH
   - **macOS**: Use Homebrew: `brew install ffmpeg`
   - **Linux**: Use your package manager, e.g., `sudo apt install ffmpeg`

4. **Start the Server**:
   ```bash
   python server.py
   ```
   The server will start on port 5000 by default. You should see:
   ```
   FFmpeg is available
   YouTube Downloader API Server running on port 5000
   * Running on http://127.0.0.1:5000
   ```
   
   If FFmpeg is not found, you'll see "FFmpeg is not available, falling back to yt-dlp merging" which is still functional but may provide lower quality in some cases.

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

**Q: Why do downloads take longer now?**
A: The server now processes videos to ensure audio and video are properly combined. This takes a bit more time but guarantees complete downloads with both audio and video.

**Q: Why do I see "Server connection failed" errors?**
A: This usually means the Python backend server isn't running. Start the server with `python server.py` and ensure port 5000 isn't blocked by a firewall.

**Q: How does the extension handle audio?**
A: The server now offers two methods for combining video and audio:
   1. **yt-dlp Merging**: The default method uses yt-dlp to process the streams.
   2. **FFmpeg Merging**: If you have FFmpeg installed and check the "Use FFmpeg" option, it will use FFmpeg for potentially better quality and faster processing.

**Q: What's the difference between yt-dlp and FFmpeg merging?**
A: yt-dlp merging works on any system without additional software, while FFmpeg merging often provides better quality and handles more formats but requires FFmpeg to be installed on your system.

## Tips

- For best video quality, choose the highest resolution format available
- Use FFmpeg merging when available for better quality (check the box in the interface)
- For audio-only downloads, look for the "Audio Only" format option (ideal for music)
- If a download fails, try a different resolution or merging method
- Some videos may have region restrictions that prevent downloading
- Keep yt-dlp updated with `pip install -U yt-dlp` to handle YouTube site changes
- If you're using the Chrome extension, make sure to enable it on YouTube pages for the best experience