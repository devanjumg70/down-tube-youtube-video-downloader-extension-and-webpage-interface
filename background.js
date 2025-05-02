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
  else if (request.action === 'fetchPlaylistInfo') {
    fetchPlaylistInfo(request.playlistId, sendResponse);
    return true; // Indicates async response
  }
  else if (request.action === 'startBatchDownload') {
    startBatchDownload(request.playlistId, request.format, request.useFFmpeg, sendResponse);
    return true; // Indicates async response
  }
  else if (request.action === 'checkBatchStatus') {
    checkBatchStatus(request.jobId, sendResponse);
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
 * @param {number} retryCount - Number of retry attempts (default 0)
 */
async function downloadVideo(videoId, itag, fileName, downloadUrl, useFFmpeg, sendResponse, retryCount = 0) {
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

    // Attempt to retry failed downloads
    if (retryCount < 3) {
      console.log(`Retrying download (attempt ${retryCount + 1}/3)...`);
      setTimeout(() => {
        downloadVideo(videoId, itag, fileName, downloadUrl, useFFmpeg, sendResponse, retryCount + 1);
      }, 2000); // Wait 2 seconds before retry
      return;
    }

    sendResponse({ 
      error: 'Download failed after multiple attempts. Please try again later.',
      details: error.message
    });
  }
}

/**
 * Fetches playlist information from YouTube using our backend server
 * @param {string} playlistId - The YouTube playlist ID
 * @param {function} sendResponse - Callback to send response to popup
 */
async function fetchPlaylistInfo(playlistId, sendResponse) {
  try {
    console.log(`Fetching playlist info for ID: ${playlistId} from ${API_SERVER}/api/playlist`);

    // Call our API server to get playlist information
    const apiUrl = `${API_SERVER}/api/playlist?playlistId=${playlistId}`;
    console.log('Making request to:', apiUrl);

    const response = await fetch(apiUrl);
    console.log('Playlist response received:', response.status, response.statusText);

    if (!response.ok) {
      console.error('Error playlist response:', response.status, response.statusText);
      const errorData = await response.json();
      sendResponse({ error: errorData.error || 'Failed to fetch playlist information' });
      return;
    }

    console.log('Playlist response OK, parsing JSON');
    const data = await response.json();
    console.log('Parsed playlist data:', data);

    // Send the response back to the popup
    sendResponse({
      title: data.title || 'YouTube Playlist',
      channel: data.channel || 'YouTube Channel',
      thumbnail: data.thumbnail || (data.videos && data.videos[0] ? `https://i.ytimg.com/vi/${data.videos[0].id}/maxresdefault.jpg` : 'https://i.ytimg.com/vi/playlist/default.jpg'),
      videoCount: data.videoCount || 0,
      videos: data.videos || []
    });
  } catch (error) {
    console.error('Error fetching playlist info:', error);
    sendResponse({ error: 'Failed to fetch playlist information. Please try again later.' });
  }
}

/**
 * Starts a batch download of videos in a playlist
 * @param {string} playlistId - The YouTube playlist ID
 * @param {string} format - The format to download (best, 1080, 720, etc.)
 * @param {boolean} useFFmpeg - Whether to use FFmpeg for processing
 * @param {function} sendResponse - Callback to send response to popup
 */
async function startBatchDownload(playlistId, format, useFFmpeg, sendResponse) {
  try {
    console.log(`Starting batch download: playlistId=${playlistId}, format=${format}, useFFmpeg=${useFFmpeg}`);

    // Call our API server to start the batch download
    const apiUrl = `${API_SERVER}/api/batch/download`;
    console.log('Making batch download request to:', apiUrl);

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        playlistId: playlistId,
        format: format,
        useFFmpeg: useFFmpeg
      })
    });

    console.log('Batch download response received:', response.status, response.statusText);

    if (!response.ok) {
      console.error('Error batch download response:', response.status, response.statusText);
      const errorData = await response.json();
      sendResponse({ error: errorData.error || 'Failed to start batch download' });
      return;
    }

    console.log('Batch download response OK, parsing JSON');
    const data = await response.json();
    console.log('Parsed batch download data:', data);

    // Send the response back to the popup
    sendResponse({
      jobId: data.jobId,
      totalVideos: data.total_videos,
      message: data.message || 'Batch download started'
    });
  } catch (error) {
    console.error('Error starting batch download:', error);
    sendResponse({ error: 'Failed to start batch download. Please try again later.' });
  }
}

/**
 * Checks the status of a batch download job
 * @param {string} jobId - The batch job ID
 * @param {function} sendResponse - Callback to send response to popup
 */
async function checkBatchStatus(jobId, sendResponse) {
  try {
    console.log(`Checking batch status for job: ${jobId}`);

    // Call our API server to check the batch status
    const apiUrl = `${API_SERVER}/api/batch/status?jobId=${jobId}`;
    console.log('Making batch status request to:', apiUrl);

    const response = await fetch(apiUrl);
    console.log('Batch status response received:', response.status, response.statusText);

    if (!response.ok) {
      console.error('Error batch status response:', response.status, response.statusText);
      const errorData = await response.json();
      sendResponse({ error: errorData.error || 'Failed to check batch status' });
      return;
    }

    console.log('Batch status response OK, parsing JSON');
    const data = await response.json();
    console.log('Parsed batch status data:', data);

    // Send the response back to the popup
    sendResponse({
      status: data.status,
      total: data.total,
      completed: data.completed,
      failed: data.failed
    });
  } catch (error) {
    console.error('Error checking batch status:', error);
    sendResponse({ error: 'Failed to check batch status. Please try again later.' });
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