# YouTube Video Downloader - Quick Guide

## What is it?
A Chrome extension that lets you download YouTube videos in various qualities.

## What you need:
1. Google Chrome browser
2. Python installed on your computer
3. The extension files from this package

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
1. Go to any YouTube video
2. Click the extension icon
3. Click "Fetch Video" 
4. Select your preferred quality
5. Choose where to save the file
6. Enjoy your downloaded video!

## Remember:
- The server must be running whenever you use the extension
- For best quality, install FFmpeg: `pip install ffmpeg-python`
- Downloading copyrighted content may violate YouTube's Terms of Service

## Need help?
See the full documentation in README.md and SETUP_GUIDE.md