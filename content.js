// Content script for Video Downloader extension
// This script runs on YouTube pages and helps with extracting video data

// Listen for messages from the background script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extractVideoData') {
    const videoData = extractVideoData();
    sendResponse(videoData);
  }
  return true; // Indicates async response
});

/**
 * Extract video information from the YouTube page
 * @returns {Object} Video data including formats available
 */
function extractVideoData() {
  const videoData = {
    title: document.title.replace(' - YouTube', ''),
    formats: []
  };
  
  // Try to find the video player
  const player = document.querySelector('#movie_player, .html5-video-player');
  
  if (player) {
    // In a real implementation, we'd extract available formats from the player
    // This is a simplified version as the actual extraction requires deeper parsing
    const video = document.querySelector('video');
    
    if (video) {
      // Get current video quality as a fallback
      const height = video.videoHeight;
      const qualityLabel = getQualityLabel(height);
      
      videoData.formats.push({
        itag: getItagFromHeight(height),
        qualityLabel: qualityLabel,
        container: 'mp4'
      });
      
      // Add other common formats
      if (!videoData.formats.find(f => f.qualityLabel === '360p')) {
        videoData.formats.push({ itag: '18', qualityLabel: '360p', container: 'mp4' });
      }
      if (!videoData.formats.find(f => f.qualityLabel === '720p')) {
        videoData.formats.push({ itag: '22', qualityLabel: '720p', container: 'mp4' });
      }
      if (!videoData.formats.find(f => f.qualityLabel === '1080p')) {
        videoData.formats.push({ itag: '137', qualityLabel: '1080p', container: 'mp4' });
      }
      
      // Always add audio
      videoData.formats.push({ itag: '140', qualityLabel: 'Audio Only', container: 'mp3' });
    }
  }
  
  // Get channel name if available
  const channelElement = document.querySelector('#owner-name a, #channel-name');
  if (channelElement) {
    videoData.channel = channelElement.textContent.trim();
  } else {
    videoData.channel = 'YouTube Channel';
  }
  
  return videoData;
}

/**
 * Convert video height to a quality label
 * @param {number} height - Video height in pixels
 * @returns {string} Quality label (e.g., '720p')
 */
function getQualityLabel(height) {
  if (height >= 1080) return '1080p';
  if (height >= 720) return '720p';
  if (height >= 480) return '480p';
  if (height >= 360) return '360p';
  return '240p';
}

/**
 * Get the YouTube itag value based on height
 * @param {number} height - Video height in pixels 
 * @returns {string} YouTube itag
 */
function getItagFromHeight(height) {
  if (height >= 1080) return '137';
  if (height >= 720) return '22';
  if (height >= 480) return '135';
  if (height >= 360) return '18';
  return '133';
}