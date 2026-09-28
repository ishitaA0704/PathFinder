# 🧭 Pathfinder

**Stay on your path while you study.**

Pathfinder is an AI-powered Chrome extension designed to eliminate YouTube rabbit holes during study sessions. Tell it what you're trying to learn, and it acts as an intelligent guardian—allowing educational content related to your topic while instantly blocking distracting, off-topic videos.

*Built in under 2 hours for a hackathon.*

---

## ✨ Features

- **AI-Powered Relevance Engine**: Uses Google's Gemini 3.8 Flash model to analyze YouTube video titles against your current study topic in real-time.
- **Fail-Safe Offline Mode**: If you lose internet or the AI API goes down, the system seamlessly falls back to a blazing-fast local keyword matching algorithm.
- **Fail-Open Design**: YouTube will never break. If the backend server crashes, the extension allows all videos so your browsing experience is never interrupted.
- **Sleek UI**: A clean, distraction-free extension popup built with vanilla HTML/CSS.
- **Temporary Bypasses**: Really need a 5-minute break? You can temporarily bypass a block if you acknowledge you're going off-path.

## 🛠️ Tech Stack

**Frontend (Chrome Extension):**
- Manifest V3
- Vanilla JavaScript (Content Scripts, Background Service Worker)
- HTML5 / CSS3

**Backend (Local API):**
- Python 3
- Flask (API Routing)
- Flask-SQLAlchemy & SQLite (Logging & Analytics)
- Google Generative AI SDK (Gemini Integration)

---

## 🚀 How to Run Locally

### 1. Start the Backend Server

1. Open your terminal and navigate to the backend folder:
   ```bash
   cd backend
   ```
2. Create a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   # On Windows: venv\Scripts\activate
   # On Mac/Linux: source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up your environment variables:
   - Copy `.env.example` to `.env`
   - Get a free API key from [Google AI Studio](https://aistudio.google.com/) and add it to your `.env` file.
5. Run the Flask server:
   ```bash
   python app.py
   ```
   *The server will start on `http://localhost:5000`.*

### 2. Install the Chrome Extension

1. Open Google Chrome and navigate to `chrome://extensions`.
2. Toggle **Developer mode** ON in the top right corner.
3. Click the **Load unpacked** button in the top left.
4. Select the `extension` folder from this repository.
5. Pin the Pathfinder icon 🧭 to your toolbar!

---

## 🎮 How to Use

1. Click the Pathfinder 🧭 icon in your Chrome toolbar.
2. Enter your current study topic (e.g., "DBMS exam prep" or "Calculus limits").
3. Turn the switch **ON** and click **Save**.
4. Go to YouTube and try watching a video about video games or cooking—Pathfinder will block it!
5. Search for a tutorial related to your topic—Pathfinder will let it play seamlessly.

---

## 📖 Deep Dive

Curious about the technical decisions, architecture, or how to explain this project to hackathon judges? 

Check out the [EXPLAINED.md](./EXPLAINED.md) file included in this repository for an in-depth breakdown of the code, request flow, and potential interview questions.
