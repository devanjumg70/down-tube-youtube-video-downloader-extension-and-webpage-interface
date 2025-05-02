# YouTube Video Downloader - Quick Guide

## What is it?
A Chrome extension that lets you download YouTube videos and entire playlists in various qualities.

## What you need:
1. Google Chrome browser
2. Python installed on your computer
3. The extension files from this package
4. FFmpeg (optional but recommended for better quality)

## Setup in 60 seconds:

### Start the server:
1. Open a terminal/command prompt
2. Navigate to the folder containing these files
3. Run: `pip install flask flask-cors yt-dlp`
4. Run: `python server.py`
5. Keep this terminal window open

### Install the extension:
1. Open Chrome and go to: `chrome://extensions/`
2. Turn on "Developer mode" (top-right toggle)
3. Click "Load unpacked" 
4. Select the folder containing these files
5. The extension icon will appear in your toolbar

## Using the extension:

### Single Video Download:
1. Go to any YouTube video
2. Click the extension icon
3. Click "Fetch Video" (or the URL will be auto-detected)
4. Select your preferred quality
5. Choose where to save the file
6. Enjoy your downloaded video!

### Playlist Download:
1. Go to any YouTube playlist
2. Click the extension icon
3. The playlist will be auto-detected
4. View playlist information including total videos
5. Select desired format for all videos
6. Click "Start Batch Download"
7. Monitor progress as videos download
8. Files will be saved to your downloads folder

## Remember:
- The server must be running whenever you use the extension
- For best quality, enable the FFmpeg option in the extension UI
- Use the aria2c option for faster, multi-threaded downloads
- Downloading copyrighted content may violate YouTube's Terms of Service

## Need help?
See the full documentation in README.md and SETUP_GUIDE.md