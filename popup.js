document.addEventListener('DOMContentLoaded', function() {
  console.log('Popup script loaded');
  
  // Elements
  const videoUrlInput = document.getElementById('video-url');
  const fetchBtn = document.getElementById('fetch-btn');
  const useFFmpegCheckbox = document.getElementById('use-ffmpeg');
  const loader = document.getElementById('loader');
  const errorContainer = document.getElementById('error-container');
  const errorMessage = document.getElementById('error-message');
  const videoInfo = document.getElementById('video-info');
  const videoTitle = document.getElementById('video-title');
  const videoChannel = document.getElementById('video-channel');
  const videoThumbnail = document.getElementById('video-thumbnail');
  const resolutionButtons = document.getElementById('resolution-buttons');
  
  // Variables for debounce
  let fetchTimeout = null;
  const DEBOUNCE_DELAY = 800; // ms delay for auto-fetch
  
  // Tracks currently fetching URL to avoid double fetches
  let currentlyFetchingUrl = '';
  let lastFetchedUrl = '';
  
  console.log('All DOM elements found and initialized');
  
  // Helper function to show/hide elements
  function toggleElement(element, show) {
    if (element) {
      element.classList.toggle('hidden', !show);
    }
  }
  
  // Helper function to clear previous video data
  function clearPreviousData() {
    videoTitle.textContent = '';
    videoChannel.textContent = '';
    videoThumbnail.src = '';
    resolutionButtons.innerHTML = '';
    toggleElement(videoInfo, false);
    toggleElement(errorContainer, false);
  }
  
  // Function to show error message
  function showError(message) {
    errorMessage.textContent = message;
    toggleElement(errorContainer, true);
    toggleElement(loader, false);
    currentlyFetchingUrl = ''; // Reset fetching state
  }
  
  // Function to validate YouTube URL
  function isValidYouTubeUrl(url) {
    if (!url) return false;
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})(&.*)?$/;
    return youtubeRegex.test(url);
  }
  
  // Function to extract video ID from YouTube URL
  function extractVideoId(url) {
    if (!url) return false;
    const regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[7].length === 11) ? match[7] : false;
  }
  
  // Function to fetch video information
  async function fetchVideoInfo(url, force = false) {
    // Don't fetch if we're already fetching this URL
    if (currentlyFetchingUrl === url && !force) {
      console.log('Already fetching this URL, skipping:', url);
      return;
    }
    
    // Don't fetch if it's the same as last time unless forced
    if (lastFetchedUrl === url && !force) {
      console.log('URL already fetched, skipping:', url);
      return;
    }
    
    console.log('fetchVideoInfo called with URL:', url);
    clearPreviousData();
    toggleElement(loader, true);
    currentlyFetchingUrl = url;
    
    if (!isValidYouTubeUrl(url)) {
      console.log('Invalid YouTube URL:', url);
      showError('Please enter a valid YouTube URL');
      return;
    }
    
    const videoId = extractVideoId(url);
    console.log('Extracted video ID:', videoId);
    
    if (!videoId) {
      console.log('Failed to extract video ID from URL:', url);
      showError('Could not extract video ID from the URL');
      return;
    }
    
    try {
      console.log('Sending message to background script for video ID:', videoId);
      // Send message to background script to fetch video info
      chrome.runtime.sendMessage(
        { action: 'fetchVideoInfo', videoId: videoId },
        function(response) {
          console.log('Received response from background script:', response);
          toggleElement(loader, false);
          currentlyFetchingUrl = ''; // Reset fetching state
          lastFetchedUrl = url;      // Set last successful fetch
          
          if (response && response.error) {
            console.error('Error in response:', response.error);
            showError(response.error);
            return;
          }
          
          if (!response) {
            console.error('No response received from background script');
            showError('Failed to get response from the server. Please try again later.');
            return;
          }
          
          // Display video information
          videoTitle.textContent = response.title;
          videoChannel.textContent = `By: ${response.channel}`;
          videoThumbnail.src = response.thumbnail;
          
          // Create resolution buttons
          response.formats.forEach(format => {
            const button = document.createElement('button');
            button.className = format.has_audio && !format.has_video ? 'resolution-btn audio' : 'resolution-btn';
            
            // Add appropriate icon based on format
            let icon = 'fa-video';
            let formatLabel = format.qualityLabel;
            
            if (format.has_audio && !format.has_video) {
              icon = 'fa-music';
            } else if (formatLabel.includes('with audio')) {
              icon = 'fa-file-video';
              formatLabel = formatLabel.replace(' (with audio)', ''); // Cleaner display
            }
            
            button.innerHTML = `<i class="fas ${icon}"></i> ${formatLabel}`;
            
            button.addEventListener('click', () => {
              // Get FFmpeg option value
              const useFFmpeg = useFFmpegCheckbox.checked;
              
              chrome.runtime.sendMessage({
                action: 'downloadVideo',
                videoId: videoId,
                itag: format.itag,
                fileName: `${response.title} - ${format.qualityLabel}.${format.container}`,
                useFFmpeg: useFFmpeg
              });
            });
            
            resolutionButtons.appendChild(button);
          });
          
          toggleElement(videoInfo, true);
        }
      );
    } catch (error) {
      showError(`Error fetching video information: ${error.message}`);
    }
  }
  
  // Debounced auto-fetch function
  function debouncedFetch(url) {
    // Clear any existing timeout
    if (fetchTimeout) {
      clearTimeout(fetchTimeout);
    }
    
    // Set new timeout to fetch after delay
    fetchTimeout = setTimeout(() => {
      if (url && isValidYouTubeUrl(url)) {
        fetchVideoInfo(url);
      }
    }, DEBOUNCE_DELAY);
  }
  
  // Event listeners
  fetchBtn.addEventListener('click', () => {
    const url = videoUrlInput.value.trim();
    if (url) {
      // Force fetch even if it's the same URL 
      fetchVideoInfo(url, true);
    } else {
      showError('Please enter a video URL');
    }
  });
  
  // Auto-fetch on input changes (with debounce)
  videoUrlInput.addEventListener('input', (e) => {
    const url = e.target.value.trim();
    if (url && isValidYouTubeUrl(url)) {
      debouncedFetch(url);
    }
  });
  
  // Allow fetching when pressing Enter in the input field
  videoUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      const url = videoUrlInput.value.trim();
      if (url) {
        // Force fetch even if it's the same URL
        fetchVideoInfo(url, true);
      } else {
        showError('Please enter a video URL');
      }
    }
  });
  
  // Prefill input with URL from current tab if it's YouTube and auto-fetch
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    if (tabs && tabs.length > 0) {
      const currentUrl = tabs[0].url;
      console.log('Current tab URL:', currentUrl);
      
      if (isValidYouTubeUrl(currentUrl)) {
        videoUrlInput.value = currentUrl;
        // Auto-fetch immediately for YouTube page
        fetchVideoInfo(currentUrl);
      } else {
        // Fallback to clipboard check if not a YouTube tab
        try {
          navigator.clipboard.readText().then(text => {
            if (isValidYouTubeUrl(text) && !videoUrlInput.value) {
              videoUrlInput.value = text;
              fetchVideoInfo(text);
            }
          }).catch(() => {
            // Clipboard permission denied, ignore
            console.log('Clipboard access denied or empty');
          });
        } catch (e) {
          console.log('Clipboard API not available:', e);
        }
      }
    }
  });
});
