# YouTube Video Downloader Chrome Extension

A Chrome extension that allows users to download videos from YouTube in various resolutions.

## Features

- Enter a YouTube video URL or use the current tab's URL
- Fetch video information including title, channel, and thumbnail
- View available download options in different resolutions (360p, 720p, 1080p, audio-only)
- Download videos with a simple click

## Installation

### Local Installation

1. Download or clone this repository to your local machine
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode" by toggling the switch in the top-right corner
4. Click "Load unpacked" and select the folder containing the extension files
5. The extension should now be installed and visible in your Chrome toolbar

## Usage

1. Navigate to a YouTube video or paste a YouTube URL in the extension popup
2. Click the "Fetch Video" button to retrieve video information
3. Select your preferred resolution from the available options
4. Your download will begin automatically

## Limitations

This extension is designed for educational purposes and has some limitations:

1. Direct video downloads from YouTube are subject to YouTube's Terms of Service
2. Higher quality formats may require additional processing
3. Not all videos will have all resolutions available

## Technical Details

This extension uses the following technologies:

- HTML, CSS, and JavaScript for the user interface
- Chrome Extension APIs for browser integration
- YouTube's oEmbed API for video metadata

### File Structure

- `manifest.json`: Extension configuration
- `popup.html`: User interface for the extension
- `popup.css`: Styling for the popup
- `popup.js`: Frontend JavaScript for user interactions
- `background.js`: Background script for handling video processing
- `content.js`: Content script for interacting with YouTube pages
- `icons/`: Extension icons in various sizes

## License

This project is for educational purposes only.

## Disclaimer

This extension is not affiliated with or endorsed by YouTube or Google. Users are responsible for ensuring compliance with YouTube's Terms of Service when using this extension.