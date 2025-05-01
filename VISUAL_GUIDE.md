# YouTube Video Downloader - Visual Guide

## System Architecture
```
┌─────────────────┐      HTTP Requests      ┌──────────────────┐
│                 │ ─────────────────────▶  │                  │
│  Chrome         │                         │  Python Server   │
│  Extension      │                         │  (Flask + yt-dlp)│
│                 │ ◀─────────────────────  │                  │
└─────────────────┘      JSON Responses     └──────────────────┘
```

## Installation Flow
```
1. Install Dependencies ──▶ 2. Start Server ──▶ 3. Install Extension ──▶ 4. Use Extension
   pip install flask         python server.py    Load in Chrome          Click extension icon
   flask-cors yt-dlp                            developer mode           in toolbar
```

## User Workflow
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│              │     │              │     │              │     │              │
│  Enter URL   │──▶  │ Fetch Video  │──▶  │  Select      │──▶  │  Download    │
│  or use      │     │ Information  │     │  Quality     │     │  Begins      │
│  current tab │     │              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

## Extension UI Layout
```
┌────────────────────────────────────────┐
│ YouTube Video Downloader               │
├────────────────────────────────────────┤
│                                        │
│ ┌────────────────────────────────┐     │
│ │ https://youtu.be/dQw4w9WgXcQ   │     │
│ └────────────────────────────────┘     │
│                                        │
│ ┌────────────────┐                     │
│ │  Fetch Video   │                     │
│ └────────────────┘                     │
│                                        │
│  Video Information:                    │
│  ┌──────────────────────────────────┐  │
│  │                                  │  │
│  │         [Video Thumbnail]        │  │
│  │                                  │  │
│  ├──────────────────────────────────┤  │
│  │ Title: Never Gonna Give You Up   │  │
│  │ Channel: Rick Astley             │  │
│  └──────────────────────────────────┘  │
│                                        │
│  Available Downloads:                  │
│  ┌─────────────┐ ┌─────────────┐      │
│  │ 1080p (mp4) │ │ 720p (mp4)  │      │
│  └─────────────┘ └─────────────┘      │
│  ┌─────────────┐ ┌─────────────┐      │
│  │ 480p (mp4)  │ │ 360p (mp4)  │      │
│  └─────────────┘ └─────────────┘      │
│  ┌─────────────┐                      │
│  │ Audio (mp3) │                      │
│  └─────────────┘                      │
│                                        │
└────────────────────────────────────────┘
```

## Server Console Output (Example)
```
* Serving Flask app 'server'
* Debug mode: off
* Running on http://127.0.0.1:8080
* Running on http://0.0.0.0:8080
127.0.0.1 - - [01/May/2025 07:15:12] "GET /api/info?videoId=dQw4w9WgXcQ HTTP/1.1" 200 -
127.0.0.1 - - [01/May/2025 07:15:25] "GET /api/download?videoId=dQw4w9WgXcQ&itag=230 HTTP/1.1" 302 -
```

## Troubleshooting Flowchart
```
┌───────────────┐     No      ┌───────────────┐
│ Extension     │──────────▶  │ Start server  │
│ connecting?   │             │ python server.py │
└───────┬───────┘             └───────────────┘
        │ Yes
        ▼
┌───────────────┐     No      ┌───────────────┐
│ Video info    │──────────▶  │ Check valid   │
│ displaying?   │             │ YouTube URL   │
└───────┬───────┘             └───────────────┘
        │ Yes
        ▼
┌───────────────┐     No      ┌───────────────┐
│ Download      │──────────▶  │ Try different │
│ working?      │             │ resolution    │
└───────┬───────┘             └───────────────┘
        │ Yes
        ▼
┌───────────────┐
│ Enjoy your    │
│ video!        │
└───────────────┘
```