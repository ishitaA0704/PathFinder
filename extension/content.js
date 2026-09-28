// content.js – Pathfinder content script
// Injected into every YouTube page by Chrome (see manifest.json).
// This is the only script that can touch the YouTube DOM.
// It cannot call fetch() to Flask directly – it asks background.js to do that.

// ── State variables ───────────────────────────────────────────────────────────
// These live in module scope so they persist across yt-navigate-finish events
// for the lifetime of the tab.

// The last video title we sent to the backend.
// We compare against this before sending a new check, to avoid spamming
// the backend when YouTube fires multiple navigation events for one video.
let lastCheckedTitle = "";

// When the user clicks "Continue anyway", we record the expiry timestamp here.
// Any check() call before this time returns immediately without blocking.
let snoozeUntil = 0;  // 0 means "not snoozed"

// ── Entry point ───────────────────────────────────────────────────────────────
// Called once on initial page load AND once on every YouTube client-side navigation.
function main() {
  // Only run on watch pages (URLs that contain "/watch")
  if (!location.href.includes("/watch")) {
    return;
  }

  // Always remove the overlay from the previous video before we check the new one.
  // If we didn't do this, a user going from a blocked video to an allowed one
  // would still see the overlay until the new check finishes.
  removeOverlay();

  // Try to get the title. YouTube renders the h1 asynchronously after the
  // URL changes, so it may not be in the DOM yet. We retry up to ~3 seconds.
  waitForTitle((title) => {
    // Skip if it's the same video we just checked (YouTube can fire
    // yt-navigate-finish more than once per navigation).
    if (title === lastCheckedTitle) return;
    lastCheckedTitle = title;

    checkTitle(title);
  });
}

// ── WHY yt-navigate-finish instead of a page load event ───────────────────────
// YouTube is a Single-Page Application (SPA). When you click a video thumbnail,
// YouTube does NOT reload the full HTML page. Instead, it:
//   1. Updates the URL with history.pushState()
//   2. Fetches only the new video data via its own internal API
//   3. Re-renders the relevant parts of the DOM in-place
//
// Because there is no full page reload, browser events like "load" or
// "DOMContentLoaded" do NOT fire. Our content script was injected once
// when the tab first opened; it would never know the user switched videos.
//
// YouTube dispatches a custom event "yt-navigate-finish" on document
// every time its own router finishes loading a new page. Listening to
// that event is the standard way extension developers hook into YouTube's
// navigation cycle.
document.addEventListener("yt-navigate-finish", main);

// Also run immediately for the case where the tab was opened directly
// on a /watch URL (in that case yt-navigate-finish has already fired
// before our script was injected).
main();

// ── Wait for the title element with retry ─────────────────────────────────────
// YouTube updates the <h1> element a short time after the URL changes.
// If we read it immediately, we might get the OLD video's title or an empty string.
// We poll every 300 ms for up to 10 attempts (~3 seconds).
function waitForTitle(callback) {
  const MAX_ATTEMPTS = 10;
  const INTERVAL_MS  = 300;
  let attempts = 0;

  const interval = setInterval(() => {
    const title = extractTitle();
    attempts++;

    if (title) {
      // Found a non-empty title – stop polling and hand it to the callback.
      clearInterval(interval);
      callback(title);
    } else if (attempts >= MAX_ATTEMPTS) {
      // Gave up – stop polling. We won't check a video we can't name.
      clearInterval(interval);
      console.warn("[Pathfinder] Could not extract video title after retrying.");
    }
  }, INTERVAL_MS);
}

// ── Extract the video title from the DOM ──────────────────────────────────────
function extractTitle() {
  // Primary source: YouTube's h1 element inside the watch page.
  // We try two selectors because YouTube's DOM structure varies by layout version.
  const h1 =
    document.querySelector("h1.ytd-watch-metadata yt-formatted-string") ||
    document.querySelector("ytd-watch-metadata h1 yt-formatted-string")  ||
    document.querySelector("h1.ytd-watch-metadata");

  if (h1 && h1.textContent.trim()) {
    return h1.textContent.trim();
  }

  // Fallback: the browser tab title always contains "Video Name - YouTube".
  // We strip the " - YouTube" suffix to get just the video name.
  const tabTitle = document.title.replace(/ - YouTube$/, "").trim();
  if (tabTitle && tabTitle !== "YouTube") {
    return tabTitle;
  }

  // Return empty string if we couldn't find anything yet (caller will retry).
  return "";
}

// ── Send title to background.js and act on the response ──────────────────────
function checkTitle(title) {
  // If the user clicked "Continue anyway", snoozeUntil is set to a future
  // timestamp. Date.now() returns milliseconds since epoch.
  if (Date.now() < snoozeUntil) {
    console.log("[Pathfinder] Snoozed – skipping check for:", title);
    return;
  }

  // chrome.runtime.sendMessage sends a message to background.js.
  // The second argument is the callback that receives background.js's reply.
  // This is ASYNCHRONOUS: the current function returns immediately and the
  // callback runs later when background.js has finished calling Flask.
  //
  // Safety timeout: MV3 service workers can be killed by Chrome between events.
  // If that happens after we send the message but before background.js replies,
  // the callback would never fire and the tab would silently hang.
  // We set a 10-second timer; if no reply arrives, we allow the video and log a warning.
  let responded = false;
  const safetyTimer = setTimeout(() => {
    if (!responded) {
      console.warn("[Pathfinder] No response from background within 10 s – allowing video.");
    }
  }, 10000);

  chrome.runtime.sendMessage({ type: "CHECK_TITLE", title: title }, (response) => {
    responded = true;
    clearTimeout(safetyTimer);

    // If the extension context was invalidated (e.g. extension was reloaded
    // mid-session), chrome.runtime.lastError will be set. Guard against it.
    if (chrome.runtime.lastError) {
      console.warn("[Pathfinder] Message error:", chrome.runtime.lastError.message);
      return;
    }

    if (!response) return;

    console.log("[Pathfinder] Response for:", title, response);

    if (!response.allowed) {
      // The video is off-topic: pause it and show the lock overlay.
      pauseVideo();
      showOverlay(title, response);
    }
  });
}

// ── Pause the YouTube video player ───────────────────────────────────────────
function pauseVideo() {
  // YouTube renders the video inside an HTML <video> element.
  // .pause() is a standard DOM method on any <video> element.
  const video = document.querySelector("video");
  if (video && !video.paused) {
    video.pause();
  }
}

// ── DOM injection: build and insert the overlay ───────────────────────────────
// HOW DOM INJECTION WORKS:
//   1. document.createElement(tag) creates a new HTML element IN MEMORY.
//      It is not visible yet – it hasn't been added to the page.
//   2. We set properties like .className, .textContent, .id on it.
//   3. element.appendChild(child) attaches child INSIDE element.
//      Children become nested HTML tags.
//   4. document.body.appendChild(overlay) inserts the whole tree into
//      the live page DOM. The browser immediately renders it.
//   5. To remove it later, we call overlay.remove().
function showOverlay(title, response) {
  // Don't stack two overlays if one is already showing.
  if (document.getElementById("pf-overlay")) return;

  // response.score comes from Flask. Convert to a readable percentage.
  const score = typeof response.score === "number"
                ? (response.score * 100).toFixed(0) + "% relevant"
                : "";
  // response.mode is "gemini" or "fallback" – display which engine decided.
  const mode = response.mode && response.mode !== "off"
               ? `via ${response.mode}`
               : "";

  // ── Outer full-screen overlay ─────────────────────────────────────────────
  const overlay = document.createElement("div");
  overlay.id = "pf-overlay";
  overlay.className = "pf-overlay";

  // ── Inner card ────────────────────────────────────────────────────────────
  const card = document.createElement("div");
  card.className = "pf-card";

  // Lock icon
  const icon = document.createElement("span");
  icon.className = "pf-icon";
  icon.textContent = "🔒";

  // Heading
  const heading = document.createElement("h2");
  heading.className = "pf-heading";
  heading.innerHTML = `<span class="pf-accent">Off your path</span>`;

  // Sub-text — built with textContent (not innerHTML) to prevent XSS.
  const body = document.createElement("p");
  body.className = "pf-body";
  body.textContent = `Pathfinder paused this video because it doesn't match your focus:`;

  // Topic pill – populated by loadTopicAndRender after async storage read.
  const topicPill = document.createElement("span");
  topicPill.className = "pf-topic";

  loadTopicAndRender(topicPill, body, score, mode, card, icon, heading, overlay);
}

// Reads focus_topic from storage (async), then finishes building the overlay.
// We separate this because chrome.storage.local.get is asynchronous.
function loadTopicAndRender(topicPill, body, score, mode, card, icon, heading, overlay) {
  chrome.storage.local.get(["focus_topic"], (result) => {
    const topic = result.focus_topic || "your focus topic";

    topicPill.textContent = topic;

    // Score / mode line (only shown if we have data)
    const meta = document.createElement("p");
    meta.className = "pf-meta";
    if (score || mode) {
      meta.textContent = [score, mode].filter(Boolean).join(" · ");
    }

    // ── Buttons row ───────────────────────────────────────────────────────
    const btnRow = document.createElement("div");
    btnRow.className = "pf-btn-row";

    // "Go back" – takes the user to the previous page in their browser history.
    const backBtn = document.createElement("button");
    backBtn.className = "pf-btn pf-btn-primary";
    backBtn.textContent = "Go back";
    backBtn.addEventListener("click", () => {
      history.back();
    });

    // "Continue anyway (5 min)" – removes the overlay and snoozes checks.
    const continueBtn = document.createElement("button");
    continueBtn.className = "pf-btn pf-btn-ghost";
    continueBtn.textContent = "Continue anyway (5 min)";
    continueBtn.addEventListener("click", () => {
      // Set the snooze expiry to 5 minutes from now.
      // 5 * 60 * 1000 = 300,000 milliseconds.
      snoozeUntil = Date.now() + 5 * 60 * 1000;
      removeOverlay();

      // Resume playback so the user doesn't have to manually press play.
      const video = document.querySelector("video");
      if (video) video.play();
    });

    btnRow.appendChild(backBtn);
    btnRow.appendChild(continueBtn);

    // ── Assemble: append children in visual top-to-bottom order ──────────
    // Each appendChild call nests the element inside its parent.
    card.appendChild(icon);
    card.appendChild(heading);
    card.appendChild(body);
    card.appendChild(topicPill);
    if (score || mode) card.appendChild(meta);
    card.appendChild(btnRow);

    overlay.appendChild(card);

    // ── Insert into the live page DOM ─────────────────────────────────────
    // document.body.appendChild makes the overlay visible immediately.
    // Because blocker.css sets position:fixed and z-index:9999999,
    // it appears on top of every YouTube element.
    document.body.appendChild(overlay);
  });
}

// ── Remove the overlay ────────────────────────────────────────────────────────
function removeOverlay() {
  const existing = document.getElementById("pf-overlay");
  if (existing) {
    existing.remove();  // .remove() detaches the element from the DOM
  }
}