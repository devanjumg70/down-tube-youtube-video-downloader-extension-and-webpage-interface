document.addEventListener('DOMContentLoaded', function() {
  // Elements
  const videoUrlInput = document.getElementById('video-url');
  const fetchBtn = document.getElementById('fetch-btn');
  const loader = document.getElementById('loader');
  const errorContainer = document.getElementById('error-container');
  const errorMessage = document.getElementById('error-message');
  const videoInfo = document.getElementById('video-info');
  const videoTitle = document.getElementById('video-title');
  const videoChannel = document.getElementById('video-channel');
  const videoThumbnail = document.getElementById('video-thumbnail');
  const resolutionButtons = document.getElementById('resolution-buttons');
  
  // Helper function to show/hide elements
  function toggleElement(element, show) {
    element.classList.toggle('hidden', !show);
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
  }
  
  // Function to validate YouTube URL
  function isValidYouTubeUrl(url) {
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})(&.*)?$/;
    return youtubeRegex.test(url);
  }
  
  // Function to extract video ID from YouTube URL
  function extractVideoId(url) {
    const regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#&?]*).*/;
    const match = url.match(regExp);
    return (match && match[7].length === 11) ? match[7] : false;
  }
  
  // Function to fetch video information
  async function fetchVideoInfo(url) {
    clearPreviousData();
    toggleElement(loader, true);
    
    if (!isValidYouTubeUrl(url)) {
      showError('Please enter a valid YouTube URL');
      return;
    }
    
    const videoId = extractVideoId(url);
    
    if (!videoId) {
      showError('Could not extract video ID from the URL');
      return;
    }
    
    try {
      // Send message to background script to fetch video info
      chrome.runtime.sendMessage(
        { action: 'fetchVideoInfo', videoId: videoId },
        function(response) {
          toggleElement(loader, false);
          
          if (response.error) {
            showError(response.error);
            return;
          }
          
          // Display video information
          videoTitle.textContent = response.title;
          videoChannel.textContent = `By: ${response.channel}`;
          videoThumbnail.src = response.thumbnail;
          
          // Create resolution buttons
          response.formats.forEach(format => {
            const button = document.createElement('button');
            button.className = 'resolution-btn';
            button.textContent = `${format.qualityLabel} (${format.container})`;
            button.addEventListener('click', () => {
              chrome.runtime.sendMessage({
                action: 'downloadVideo',
                videoId: videoId,
                itag: format.itag,
                fileName: `${response.title} - ${format.qualityLabel}.${format.container}`,
                downloadUrl: format.url // Pass the direct download URL from the server
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
  
  // Event listeners
  fetchBtn.addEventListener('click', () => {
    const url = videoUrlInput.value.trim();
    if (url) {
      fetchVideoInfo(url);
    } else {
      showError('Please enter a video URL');
    }
  });
  
  // Allow fetching when pressing Enter in the input field
  videoUrlInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      const url = videoUrlInput.value.trim();
      if (url) {
        fetchVideoInfo(url);
      } else {
        showError('Please enter a video URL');
      }
    }
  });
  
  // Automatically fetch URL if Chrome has it in clipboard
  navigator.clipboard.readText().then(text => {
    if (isValidYouTubeUrl(text)) {
      videoUrlInput.value = text;
    }
  }).catch(() => {
    // Clipboard permission denied, ignore
  });
  
  // Prefill input with URL from current tab if it's YouTube
  chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
    const currentUrl = tabs[0].url;
    if (isValidYouTubeUrl(currentUrl)) {
      videoUrlInput.value = currentUrl;
    }
  });
});
