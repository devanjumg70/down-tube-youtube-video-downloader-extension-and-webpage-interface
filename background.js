// Background script for Video Downloader extension

// Server URL for video processing API
// For security, this would normally be an environment variable
const API_SERVER = 'https://video-downloader-api.example.com';

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
    // In a real-world scenario, this would call a server-side API
    // that uses a library like youtube-dl or similar to get video info
    const response = await fetch(`${API_SERVER}/api/video-info?videoId=${videoId}`);
    
    if (!response.ok) {
      const errorData = await response.json();
      sendResponse({ error: errorData.message || 'Failed to fetch video information' });
      return;
    }
    
    const data = await response.json();
    
    // Example response format (in a real implementation this would come from the API)
    const mockVideoData = {
      title: data.title || 'Video Title',
      channel: data.author_name || 'Channel Name',
      thumbnail: data.thumbnail_url || `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
      formats: data.formats || [
        { itag: '18', qualityLabel: '360p', container: 'mp4' },
        { itag: '22', qualityLabel: '720p', container: 'mp4' },
        { itag: '137', qualityLabel: '1080p', container: 'mp4' },
        { itag: '140', qualityLabel: 'Audio Only', container: 'mp3' }
      ]
    };
    
    sendResponse(mockVideoData);
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
    // In a real implementation, this would generate a download URL through a server
    // that handles video extraction
    const downloadUrl = `${API_SERVER}/api/download?videoId=${videoId}&itag=${itag}`;
    
    // Start the download
    chrome.downloads.download({
      url: downloadUrl,
      filename: sanitizeFileName(fileName),
      saveAs: true
    }, (downloadId) => {
      if (chrome.runtime.lastError) {
        sendResponse({ error: chrome.runtime.lastError.message });
      } else {
        sendResponse({ success: true, downloadId });
      }
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
