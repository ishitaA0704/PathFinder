// popup.js – Pathfinder popup logic
// This script runs ONLY inside the popup window (popup.html).
// It cannot touch the YouTube page directly – that's content.js's job.
// It talks to neither Gemini nor Flask – that's background.js's job.
// Its only job: read/write chrome.storage.local and update the UI.

// ── Grab references to the HTML elements we need to interact with ────────────
// We do this at the top because every function below needs them.
const topicInput = document.getElementById("topic-input");
const toggle     = document.getElementById("toggle");
const saveBtn    = document.getElementById("save-btn");
const statusEl   = document.getElementById("status");

// ── Load saved state when the popup opens ────────────────────────────────────
// The popup is destroyed when the user closes it and re-created when they
// open it again. chrome.storage.local persists data across those open/close
// cycles, so we restore the UI to whatever the user last saved.
chrome.storage.local.get(["focus_topic", "enabled"], (result) => {
  // result is a plain object, e.g. { focus_topic: "DBMS", enabled: true }
  // If a key was never saved, result[key] is undefined – we use "" or false.

  topicInput.value  = result.focus_topic || "";
  toggle.checked    = result.enabled     || false;

  // Show the current status immediately so the user sees it without saving.
  updateStatus(result.focus_topic || "", result.enabled || false);
});

// ── Save button handler ───────────────────────────────────────────────────────
saveBtn.addEventListener("click", () => {
  const topic   = topicInput.value.trim();   // trim removes accidental spaces
  const enabled = toggle.checked;

  // Reject saving if focus mode is ON but the topic is empty.
  // An empty topic would cause the backend to return a 400 error.
  if (enabled && !topic) {
    statusEl.textContent = "⚠️ Please enter a focus topic first.";
    statusEl.classList.remove("active");
    return;  // stop here, don't save
  }

  // chrome.storage.local.set() writes key-value pairs to persistent storage.
  // The callback fires AFTER the write completes.
  chrome.storage.local.set({ focus_topic: topic, enabled: enabled }, () => {
    updateStatus(topic, enabled);

    // Brief visual confirmation the save worked.
    saveBtn.textContent = "Saved ✓";
    setTimeout(() => { saveBtn.textContent = "Save"; }, 1200);
  });
});

// ── Helper: update the status paragraph ──────────────────────────────────────
// A function so we call the same UI logic from both the load handler
// and the save handler without repeating code.
function updateStatus(topic, enabled) {
  if (enabled && topic) {
    statusEl.textContent = `Pathfinder is ON for "${topic}"`;
    statusEl.classList.add("active");       // turns text accent-coloured
  } else if (!enabled) {
    statusEl.textContent = "Focus mode: OFF";
    statusEl.classList.remove("active");
  } else {
    // enabled is true but topic is empty (shouldn't happen after validation,
    // but we handle it defensively).
    statusEl.textContent = "Set a topic and save to start.";
    statusEl.classList.remove("active");
  }
}
