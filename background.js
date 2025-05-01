// Background script for Video Downloader extension

// API URL for our backend server
const API_SERVER = 'http://localhost:5000';

// Log to help with debugging
console.log('Background script loaded. API_SERVER:', API_SERVER);

// Adding simple ping function to test server connectivity
async function pingServer() {
  try {
    const response = await fetch(`${API_SERVER}/`);
    console.log('Server ping response:', response.status, response.statusText);
    return response.ok;
  } catch (error) {
    console.error('Server ping failed:', error);
    return false;
  }
}

// Try to ping the server when the background script loads
pingServer();

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'fetchVideoInfo') {
    fetchVideoInfo(request.videoId, sendResponse);
    return true; // Indicates async response
  } 
  else if (request.action === 'downloadVideo') {
    downloadVideo(request.videoId, request.itag, request.fileName, request.downloadUrl, request.useFFmpeg, sendResponse);
    return true; // Indicates async response
  }
});

/**
 * Fetches video information from YouTube using our backend server
 * @param {string} videoId - The YouTube video ID
 * @param {function} sendResponse - Callback to send response to popup
 */
async function fetchVideoInfo(videoId, sendResponse) {
  try {
    // Log to help with debugging
    console.log(`Fetching video info for ID: ${videoId} from ${API_SERVER}/api/info`);
    
    // Call our API server to get video information
    const apiUrl = `${API_SERVER}/api/info?videoId=${videoId}`;
    console.log('Making request to:', apiUrl);
    
    const response = await fetch(apiUrl);
    console.log('Response received:', response.status, response.statusText);
    
    if (!response.ok) {
      console.error('Error response:', response.status, response.statusText);
      const errorData = await response.json();
      sendResponse({ error: errorData.error || 'Failed to fetch video information' });
      return;
    }
    
    console.log('Response OK, parsing JSON');
    const data = await response.json();
    console.log('Parsed data:', data);
    
    // Send the response back to the popup
    sendResponse({
      title: data.title || 'YouTube Video',
      channel: data.channel || 'YouTube Channel',
      thumbnail: data.thumbnail || `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
      formats: data.formats || []
    });
  } catch (error) {
    console.error('Error fetching video info:', error);
    
    // If our server fails, fall back to basic information
    try {
      // Fallback to oEmbed for basic info
      const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
      const oEmbedUrl = `https://www.youtube.com/oembed?url=${encodeURIComponent(videoUrl)}&format=json`;
      
      const oembedResponse = await fetch(oEmbedUrl);
      if (oembedResponse.ok) {
        const oembedData = await oembedResponse.json();
        
        sendResponse({
          title: oembedData.title || 'YouTube Video',
          channel: oembedData.author_name || 'YouTube Channel',
          thumbnail: oembedData.thumbnail_url || `https://i.ytimg.com/vi/${videoId}/maxresdefault.jpg`,
          formats: [
            { itag: '18', qualityLabel: '360p', container: 'mp4' },
            { itag: '22', qualityLabel: '720p', container: 'mp4' },
            { itag: '137', qualityLabel: '1080p', container: 'mp4' },
            { itag: '140', qualityLabel: 'Audio Only', container: 'mp3' }
          ],
          error: 'Server connection failed. Using fallback data.'
        });
      } else {
        throw new Error('Both API and oEmbed failed');
      }
    } catch (fallbackError) {
      sendResponse({ error: 'Failed to fetch video information. Please try again later.' });
    }
  }
}

/**
 * Downloads video using the specified format
 * @param {string} videoId - The YouTube video ID
 * @param {string} itag - The format identifier
 * @param {string} fileName - The file name for the download
 * @param {string} downloadUrl - The direct download URL from our server
 * @param {boolean} useFFmpeg - Whether to use FFmpeg for audio/video merging
 * @param {function} sendResponse - Callback to send response to popup
 */
async function downloadVideo(videoId, itag, fileName, downloadUrl, useFFmpeg, sendResponse) {
  try {
    console.log(`Download requested: videoId=${videoId}, itag=${itag}, useFFmpeg=${useFFmpeg}`);
    
    if (downloadUrl) {
      // Use the direct download URL from our server
      console.log('Using direct download URL');
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
    } else {
      // If we don't have a direct URL, call our API server to get one
      let apiUrl = `${API_SERVER}/api/download?videoId=${videoId}&itag=${itag}`;
      
      // Add FFmpeg parameter if specified
      if (useFFmpeg !== undefined) {
        apiUrl += `&useFFmpeg=${useFFmpeg ? 'true' : 'false'}`;
      }
      
      console.log('Starting download with API URL:', apiUrl);
      
      // Start the download via the server
      chrome.downloads.download({
        url: apiUrl,
        filename: sanitizeFileName(fileName),
        saveAs: true
      }, (downloadId) => {
        if (chrome.runtime.lastError) {
          console.error('Chrome download error:', chrome.runtime.lastError);
          sendResponse({ error: chrome.runtime.lastError.message });
        } else {
          console.log('Download started with ID:', downloadId);
          sendResponse({ success: true, downloadId });
        }
      });
    }
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
