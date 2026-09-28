"content_scripts": [
  {
    "matches": ["https://www.youtube.com/*"],
    "js": ["content.js"],
    "css": ["styles.css"],
    "run_at": "document_idle"
  }
]