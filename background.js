// Background script for Video Downloader extension

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fetchVideoInfo') {
    fetchVideoInfo(request.videoId, sendResponse);
    return true; // Indicates async response
  } 
  else if (request.action === 'downloadVideo') {
    downloadVideo(request.videoId, request.itag, request.fileName, sendResponse);
    return true; // Indicates async response
  }
});

/**
 * Fetches video information from YouTube
 * @param {string} videoId - The YouTube video ID
 * @param {function} sendResponse - Callback to send response to popup
 */
async function fetchVideoInfo(videoId, sendResponse) {
  try {
    // Get basic video info using the oEmbed API
    const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
    const oEmbedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(videoUrl)}&format=json`;
    
    let videoData = {
      title: 'YouTube Video',
      channel: 'YouTube Channel',
      thumbnail: `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
      formats: [
        { itag: '18', qualityLabel: '360p', container: 'mp4' },
        { itag: '22', qualityLabel: '720p', container: 'mp4' },
        { itag: '137', qualityLabel: '1080p', container: 'mp4' },
        { itag: '140', qualityLabel: 'Audio Only', container: 'mp3' }
      ]
    };
    
    // Try to get metadata from oEmbed
    try {
      const response = await fetch(oEmbedUrl);
      if (response.ok) {
        const data = await response.json();
        videoData.title = data.title || videoData.title;
        videoData.channel = data.author_name || videoData.channel;
        videoData.thumbnail = data.thumbnail_url || videoData.thumbnail;
      }
    } catch (oembedError) {
      console.warn('oEmbed fetch failed, using fallback data:', oembedError);
    }
    
    // Try to get additional data from the content script if we're on a YouTube page
    try {
      // Query the active tab to see if it's a YouTube page
      const tabs = await chrome.tabs.query({active: true, currentWindow: true});
      const currentUrl = tabs[0].url;
      
      // If we're on the same video page, get more detailed info from the page itself
      if (currentUrl && currentUrl.includes('youtube.com/watch') && currentUrl.includes(videoId)) {
        await chrome.tabs.sendMessage(tabs[0].id, {action: 'extractVideoData'}, function(contentResponse) {
          // If we got content data, use it to enhance our video info
          if (contentResponse && !contentResponse.error) {
            // Merge with content script data if available
            videoData.title = contentResponse.title || videoData.title;
            videoData.channel = contentResponse.channel || videoData.channel;
            
            // Merge formats, preferring content script data when available
            if (contentResponse.formats && contentResponse.formats.length > 0) {
              // Add any formats from content script that we don't already have
              contentResponse.formats.forEach(format => {
                if (!videoData.formats.find(f => f.itag === format.itag)) {
                  videoData.formats.push(format);
                }
              });
            }
          }
          
          // Send the final response
          sendResponse(videoData);
        });
      } else {
        // If we're not on the video page, just use what we have
        sendResponse(videoData);
      }
    } catch (error) {
      // If content script communication fails, still return the basic data
      sendResponse(videoData);
    }
  } catch (error) {
    console.error('Error fetching video info:', error);
    sendResponse({ error: 'Failed to fetch video information. Please try again later.' });
  }
}

/**
 * Downloads video using the specified format
 * @param {string} videoId - The YouTube video ID
 * @param {string} itag - The format identifier
 * @param {string} fileName - The file name for the download
 * @param {function} sendResponse - Callback to send response to popup
 */
async function downloadVideo(videoId, itag, fileName, sendResponse) {
  try {
    // For YouTube videos, direct download URLs require special access
    // In a production extension, we would:
    // 1. Generate a downloadable URL from a streaming URL
    // 2. Use a proxy server with youtube-dl/yt-dlp to get the actual URL
    
    // For demonstration purposes, we'll simulate downloading by redirecting to the YouTube page
    // with a parameter that indicates the download quality for demo purposes
    // This is not a real download but simulates the workflow
    
    let simulatedDownloadUrl = `https://www.youtube.com/watch?v=${videoId}&feature=youtu.be&t=0s`;
    
    if (itag === '140') {
      // Redirect to YouTube Music page for audio-only
      simulatedDownloadUrl = `https://music.youtube.com/watch?v=${videoId}`;
    }
    
    // For a real implementation, the following would be a direct video stream URL
    // We would need to extract this from the YouTube player or use an API
    
    // Notify user about the simulated download
    chrome.tabs.create({ 
      url: simulatedDownloadUrl,
      active: true
    });
    
    sendResponse({ 
      success: true, 
      message: `Opening YouTube page for ${fileName}`
    });
  } catch (error) {
    console.error('Error downloading video:', error);
    sendResponse({ error: 'Failed to download video. Please try again later.' });
  }
}

/**
 * Sanitizes file name to be valid for file systems
 * @param {string} fileName - The raw file name
 * @returns {string} Sanitized file name
 */
function sanitizeFileName(fileName) {
  return fileName
    .replace(/[/\\?%*:|"<>]/g, '-')  // Replace invalid characters
    .replace(/\s+/g, ' ')            // Replace multiple spaces with single space
    .trim();                         // Trim spaces from start and end
}
