// background.js – Pathfinder service worker
// In Manifest V3, the background page is replaced by a "service worker":
// a script that Chrome runs in the background, separate from any tab.
//
// WHY fetch() lives here instead of content.js:
//   content.js runs INSIDE the YouTube tab. Browsers enforce a security
//   rule: a web page (or a script injected into one) can only make network
//   requests to the SAME origin unless the server adds CORS headers.
//   Our Flask server is on http://localhost:5000, which is a DIFFERENT origin
//   from https://www.youtube.com.  Even though we have CORS enabled on Flask,
//   Chrome extensions restrict content scripts further – they can only use
//   fetch() to domains listed in "host_permissions" when running in a tab.
//   The service worker has no such tab-context restriction; it can freely
//   fetch any URL in host_permissions.  So: content.js notices the video,
//   sends a message to background.js, and background.js does the fetch.

// ── Message listener ──────────────────────────────────────────────────────────
// chrome.runtime.onMessage fires every time ANYONE calls chrome.runtime.sendMessage().
// 'sender' tells us which tab/script sent the message (we don't use it here).
// 'sendResponse' is a callback we call to reply.
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {

  // Only handle our specific message type; ignore anything else Chrome might send.
  if (message.type !== "CHECK_TITLE") {
    return;  // returning nothing (undefined) = don't handle this message
  }

  // ── WHY "return true" is critical ────────────────────────────────────────
  // sendResponse() must be called synchronously (in the same call stack) OR
  // the message channel stays open and Chrome expects an answer.
  // But our fetch() is ASYNCHRONOUS – we can't call sendResponse before
  // the network request finishes.
  //
  // Returning `true` from the listener tells Chrome:
  //   "I know, I'll call sendResponse() later. Keep the channel open."
  // Without `return true`, Chrome closes the channel after this function
  // returns, sendResponse becomes a no-op, and content.js never gets the answer.
  //
  // We call the async function and return true IMMEDIATELY so Chrome keeps waiting.
  handleCheckTitle(message.title, sendResponse);
  return true;  // ← MUST be the last statement in the listener
});

// ── Async handler (separate function so we can use await) ────────────────────
async function handleCheckTitle(title, sendResponse) {

  // Step 1: read the user's saved settings from storage.
  // chrome.storage.local.get returns a Promise in MV3, so we can await it.
  const { focus_topic, enabled } = await chrome.storage.local.get([
    "focus_topic",
    "enabled",
  ]);

  // Step 2: if focus mode is OFF, allow immediately – no need to call Flask.
  // This is the "fast path": zero network latency, video plays instantly.
  if (!enabled) {
    sendResponse({ allowed: true, score: 1.0, mode: "off" });
    return;
  }

  // Step 3: if there's no topic saved, allow (nothing to compare against).
  if (!focus_topic) {
    sendResponse({ allowed: true, score: 1.0, mode: "off" });
    return;
  }

  // Step 4: call the Flask backend.
  try {
    const response = await fetch("http://localhost:5000/check-title", {
      method: "POST",
      // "Content-Type: application/json" tells Flask to parse the body as JSON.
      // Without this header, request.get_json() in Flask returns None.
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title, focus_topic: focus_topic }),
    });

    // response.json() parses the HTTP response body as JSON.
    // We await it because JSON parsing of a streamed body is also async.
    const data = await response.json();

    // Pass the Flask response straight through to content.js.
    sendResponse(data);

  } catch (err) {
    // The fetch failed: Flask is down, no internet, CORS error, etc.
    // We ALLOW the video rather than break YouTube.
    // We also pass the error string so content.js can log it for debugging.
    console.warn("[Pathfinder] Backend unreachable, allowing video.", err);
    sendResponse({
      allowed: true,
      score: 1.0,
      mode: "fallback",
      error: err.message,
    });
  }
}