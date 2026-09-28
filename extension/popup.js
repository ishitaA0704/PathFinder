const topicInput = document.getElementById("topic");
const saveButton = document.getElementById("save-btn");
const statusDiv = document.getElementById("status");
document.addEventListener("DOMContentLoaded", async () => {
    const store = await chrome.storage.local.get("topic");
        if (store.topic) {
            topicInput.value = store.topic;
    }
});
saveButton.addEventListener("click", async () => {
    const newtopic = topicInput.value.trim();
    if (!newtopic) return;
    await chrome.storage.local.set({ topic: newtopic });
    statusDiv.textContent = "Topic updated!";
    setTimeout(() => {
        statusDiv.textContent = "";
    }, 2000);
});
