# Pathfinder: Explained

> **Tagline: "Stay on your path."**
> A beginner's complete guide to understanding, defending, and extending this project.

---

## The Name & The Idea

A **pathfinder** is someone — or something — that scouts the route ahead so
you don't get lost. Students get lost all the time: they open YouTube to watch
one lecture and wake up an hour later in a gaming rabbit-hole.

The name earns its meaning at every layer of the product:

| Layer | How "Pathfinder" shows up |
|---|---|
| **Product** | It literally finds whether a video is on or off your chosen path |
| **Tagline** | "Stay on your path" is a direct instruction — imperative, motivational |
| **Overlay** | "Off your path" and "Pathfinder paused this video" use the metaphor consistently |
| **Popup** | "Pathfinder is ON for DBMS exam prep" — the tool is actively guiding you |
| **Brand feel** | The compass emoji 🧭 reinforces navigation, direction, purpose |

The product idea is simple: **a compass for your browser tab.** You set your
destination (the focus topic). Pathfinder checks every YouTube video against
that destination and blocks the ones that pull you off course. When you're
back on track, it gets out of your way.

---

## 1. Plain-English Summary

Pathfinder is a Chrome browser extension that sits invisibly in the background
while you study. You tell it your focus topic — say, "DBMS exam prep" — by
typing it into a small popup and clicking Save. From that moment, every time
you open a YouTube video, Pathfinder quietly reads the video's title and sends
it to a small Python web server running on your own computer. That server asks
Google's Gemini AI "is this video relevant to DBMS exam prep?" and gets back a
score between 0 and 1. If Gemini isn't available (no internet, no API key, rate
limit), the server falls back to a pure keyword-matching algorithm that works
entirely offline. If the score is below 0.6, the server tells the extension
"not allowed" and the extension immediately pauses the video and covers the
screen with a lock overlay that shows your focus topic and lets you either go
back or override for 5 minutes. Every check is saved to a local SQLite database
so you can see your full session history at any time.

### Request Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROWSER (Chrome)                                                        │
│                                                                          │
│  ┌──────────────┐   opens popup      ┌──────────────────┐               │
│  │  popup.js    │ ─────────────────► │ chrome.storage   │               │
│  │  (popup.html)│ ◄───────────────── │ .local           │               │
│  └──────────────┘   reads/saves      │ {focus_topic,    │               │
│                     topic+enabled    │  enabled}        │               │
│                                      └──────┬───────────┘               │
│  ┌──────────────────────────────────────────┼────────────────────────┐  │
│  │  YouTube Tab (youtube.com/watch?v=...)   │                        │  │
│  │                                          │ reads settings         │  │
│  │  yt-navigate-finish event fires          │                        │  │
│  │         │                                │                        │  │
│  │         ▼                                │                        │  │
│  │  content.js                              │                        │  │
│  │  extractTitle() ──► "DBMS Full Course"   │                        │  │
│  │         │                                │                        │  │
│  │         │  sendMessage({type:            │                        │  │
│  │         │    "CHECK_TITLE",              │                        │  │
│  │         │    title: "DBMS Full Course"}) │                        │  │
│  │         │                                │                        │  │
│  └─────────┼────────────────────────────────┘                        │  │
│            │  (message crosses JS worlds)                            │  │
│            ▼                                                          │  │
│  ┌─────────────────────┐                                             │  │
│  │  background.js      │ ◄── reads storage ──────────────────────────┘  │
│  │  (service worker)   │                                                 │
│  │                     │  fetch POST /check-title                        │
│  └─────────┬───────────┘  {title, focus_topic}                          │
│            │                                                             │
└────────────┼─────────────────────────────────────────────────────────────┘
             │  HTTP (crosses process boundary)
             ▼
┌────────────────────────────────────────────────────────────────────────┐
│  PYTHON FLASK SERVER  (localhost:5000)                                  │
│                                                                         │
│  app.py  POST /check-title                                              │
│       │                                                                 │
│       ├──► gemini_client.py ──► Gemini API ──► score: 0.91             │
│       │         (online)        (internet)      mode: "gemini"         │
│       │                                                                 │
│       │   [if Gemini fails]                                             │
│       └──► fallback_classifier.py ──► keyword math ──► score: 0.33    │
│                 (offline)               (no internet)   mode:"fallback" │
│                                                                         │
│       score >= 0.6?  YES → allowed:true   NO → allowed:false           │
│                                                                         │
│       VideoLog row saved to SQLite  ──────────────────────────────────► │
│                                             instance/pathfinder.db      │
│       return {"allowed":false,"score":0.91,"mode":"gemini"}            │
└────────────────────────────────────────────────────────────────────────┘
             │  JSON response travels back
             ▼
┌────────────────────────────────────────────────────────────────────────┐
│  background.js  sendResponse(data)                                      │
│       │                                                                 │
│       ▼                                                                 │
│  content.js  callback fires                                             │
│       │                                                                 │
│       ├── allowed:true  ──► do nothing, video plays ▶                  │
│       │                                                                 │
│       └── allowed:false ──► video.pause()                              │
│                             showOverlay()  ──► 🔒 lock screen appears  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. File-by-File Reference Table

### Backend

| File | Purpose | Key functions / variables | Concept it teaches |
|---|---|---|---|
| `app.py` | Flask web server; defines all HTTP routes | `create_app()`, `check_title()`, `get_logs()`, `RELEVANCE_THRESHOLD` | Flask app factory, routing, request validation, app context |
| `extensions.py` | Holds the shared `db` object | `db = SQLAlchemy()` | Circular import prevention; application factory pattern |
| `models.py` | Defines the two database tables as Python classes | `FocusSession`, `VideoLog`, `to_dict()` | ORM — mapping classes to SQL tables |
| `services/gemini_client.py` | Calls the Gemini API; raises a custom error on any failure | `get_gemini_score()`, `GeminiUnavailableError`, `GEMINI_TIMEOUT_SECONDS` | Custom exceptions, external API calls, defensive parsing |
| `services/fallback_classifier.py` | Pure-Python keyword overlap scorer; works offline | `score_title()`, `_tokenize()`, `_prefix_match()`, `STOPWORDS` | Pure functions, string processing, normalization |
| `requirements.txt` | Lists all Python dependencies | — | Dependency management with pip |
| `.env.example` | Template for secret environment variables | `GEMINI_API_KEY`, `FORCE_FALLBACK` | 12-factor app config; never commit secrets |

### Extension

| File | Purpose | Key functions / variables | Concept it teaches |
|---|---|---|---|
| `manifest.json` | Tells Chrome everything about the extension | `permissions`, `host_permissions`, `content_scripts`, `background` | Manifest V3; principle of least privilege |
| `popup.html` | The UI the user sees when clicking the toolbar icon | — | Semantic HTML; extension popup structure |
| `popup.css` | Styles for the popup | CSS variables, toggle pill, card layout | CSS custom properties; accessible toggles with pure CSS |
| `popup.js` | Reads/writes `chrome.storage.local`; updates the popup UI | `updateStatus()`, `chrome.storage.local.set/get` | Browser storage API; event listeners; form handling |
| `background.js` | Service worker; fetches Flask; bridges content ↔ network | `handleCheckTitle()`, `chrome.runtime.onMessage` | MV3 service workers; async messaging; `return true` pattern |
| `content.js` | Injected into YouTube; detects navigation, title, overlay | `main()`, `waitForTitle()`, `extractTitle()`, `showOverlay()`, `checkTitle()` | SPA navigation hooks; DOM injection; content script isolation |
| `blocker.css` | Styles for the lock overlay injected into YouTube | `.pf-overlay`, `.pf-card`, `.pf-btn-primary`, `.pf-btn-ghost` | CSS z-index; fixed positioning; animation |

---

## 3. The 6 Most Important Code Snippets

---

### Snippet 1 — The app factory and app context (`backend/app.py`)

```python
def create_app():
    load_dotenv()                              # line A
    app = Flask(__name__)                      # line B
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///pathfinder.db"  # line C
    db.init_app(app)                           # line D
    CORS(app)                                  # line E
    with app.app_context():                    # line F
        db.create_all()                        # line G
    return app                                 # line H
```

| Line | What it does | Why it exists |
|---|---|---|
| A | Reads `.env` into `os.environ` | So your API key is available as `os.environ["GEMINI_API_KEY"]` without hardcoding it |
| B | Creates the Flask application object | Everything else hangs off this object: routes, config, extensions |
| C | Tells SQLAlchemy where to store data | `sqlite:///` = relative path; Flask creates the `instance/` folder automatically |
| D | Links the `db` object to this specific app | `db` was created in `extensions.py` with no app attached; this completes the connection |
| E | Adds CORS headers to every response | Without this, Chrome blocks the extension's fetch() call as a cross-origin request |
| F | Manually pushes an application context | Outside a request, Flask's globals aren't set up. This line says "pretend we're in a request" |
| G | Runs `CREATE TABLE IF NOT EXISTS` for every model class | Safe to call on every startup — only creates tables that don't exist yet |
| H | Returns the configured app | The factory pattern means tests can call `create_app()` too, with different settings |

---

### Snippet 2 — Hybrid Gemini/fallback routing (`backend/app.py`)

```python
force_fallback = os.environ.get("FORCE_FALLBACK", "false").lower() == "true"  # line A

if force_fallback:                           # line B
    score = score_title(title, focus_topic)  # line C
    mode  = "fallback"                       # line D
else:
    try:                                     # line E
        score = get_gemini_score(title, focus_topic)  # line F
        mode  = "gemini"                     # line G
    except GeminiUnavailableError as e:      # line H
        print(f"[Pathfinder] Gemini unavailable: {e}")  # line I
        score = score_title(title, focus_topic)          # line J
        mode  = "fallback"                               # line K

allowed = score >= RELEVANCE_THRESHOLD       # line L
```

| Line | What it does | Why it exists |
|---|---|---|
| A | Reads `FORCE_FALLBACK` from the environment | Lets you toggle offline mode by editing `.env` without changing code |
| B–D | Skips Gemini entirely if the flag is set | Demo safety net: deterministic, no internet needed, no API quota burned |
| E | Opens the "try" block | Everything inside runs normally unless an exception is raised |
| F | Calls Gemini and gets a score | The happy path: fast, context-aware, AI-powered |
| G | Records which scorer was used | The API contract requires `"mode"` in the response |
| H | Catches ONLY our custom error type | We don't want to accidentally swallow bugs in other code |
| I | Logs the failure reason to the server console | Invisible to the user, visible to the developer for debugging |
| J–K | Falls back to keyword matching | The video gets checked; the user never sees a crash or blank response |
| L | Applies the threshold as a single boolean | `RELEVANCE_THRESHOLD = 0.6` is the one constant that controls allow/block |

---

### Snippet 3 — The fallback classifier (`backend/services/fallback_classifier.py`)

```python
def score_title(title: str, topic: str) -> float:
    title_words = _tokenize(title)            # line A
    topic_words = _tokenize(topic)            # line B
    if not topic_words:                       # line C
        return 0.0
    total_points = 0.0
    for topic_word in topic_words:            # line D
        best = 0.0
        for title_word in title_words:        # line E
            if title_word == topic_word:      # line F
                best = EXACT_MATCH_SCORE      # = 1.0
                break
            elif _prefix_match(title_word, topic_word):  # line G
                best = PREFIX_MATCH_SCORE     # = 0.5
        total_points += best                  # line H
    return max(0.0, min(1.0, total_points / len(topic_words)))  # line I
```

| Line | What it does | Why it exists |
|---|---|---|
| A–B | Converts raw strings to clean word lists | `_tokenize` lowercases, strips punctuation, removes stopwords like "the" |
| C | Returns 0.0 if topic had only stopwords | Prevents division by zero; a topic of "the" should block nothing |
| D | Iterates over each topic keyword | Every topic word gets a chance to match something in the title |
| E | Iterates over each title word | We look for the *best* title word that satisfies this topic word |
| F | Exact match: full 1.0 point | "dbms" == "dbms" → break immediately, can't do better |
| G | Prefix match: 0.5 point | "norm" matches "normalization" → partial credit for root words |
| H | Accumulates the best score for each topic word | We don't double-count; one title word satisfies at most one topic word check |
| I | Normalizes by topic length, clamps to [0,1] | A 3-word topic and a 1-word topic produce comparable scores |

---

### Snippet 4 — `return true` for async messaging (`extension/background.js`)

```javascript
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type !== "CHECK_TITLE") {   // line A
    return;                               // line B
  }
  handleCheckTitle(message.title, sendResponse);  // line C
  return true;                            // line D ← the critical line
});

async function handleCheckTitle(title, sendResponse) {
  const { focus_topic, enabled } = await chrome.storage.local.get([...]);  // line E
  if (!enabled) { sendResponse({ allowed: true }); return; }               // line F
  try {
    const res  = await fetch("http://localhost:5000/check-title", {...});   // line G
    const data = await res.json();        // line H
    sendResponse(data);                   // line I
  } catch (err) {
    sendResponse({ allowed: true, error: err.message });  // line J
  }
}
```

| Line | What it does | Why it exists |
|---|---|---|
| A–B | Filters out messages that aren't ours | Chrome itself sends internal messages; we ignore them |
| C | Starts the async work in a separate function | We can't use `await` directly inside the listener (it's not async) |
| D | Returns `true` to Chrome | Tells Chrome: "I'll call sendResponse later — keep the channel open." Without this, `sendResponse` becomes a no-op |
| E | Reads storage with `await` | `chrome.storage.local.get` returns a Promise in MV3; await pauses until data is ready |
| F | Fast path: focus mode off | No network call, no latency, video plays instantly |
| G | POSTs to Flask | The actual relevance check; `await` pauses until the HTTP response arrives |
| H | Parses JSON from the response body | `response.json()` is also async — the body streams in separately from the headers |
| I | Delivers the result back to content.js | This is the callback content.js passed as the second argument to `sendMessage` |
| J | Fail-open: allows the video if anything goes wrong | Flask down, no internet, CORS issue — we never break YouTube |

---

### Snippet 5 — SPA navigation hook and title retry (`extension/content.js`)

```javascript
document.addEventListener("yt-navigate-finish", main);  // line A
main();                                                  // line B

function main() {
  if (!location.href.includes("/watch")) return;         // line C
  removeOverlay();                                       // line D
  waitForTitle((title) => {                              // line E
    if (title === lastCheckedTitle) return;              // line F
    lastCheckedTitle = title;                            // line G
    checkTitle(title);                                   // line H
  });
}

function waitForTitle(callback) {
  let attempts = 0;
  const interval = setInterval(() => {                   // line I
    const title = extractTitle();
    attempts++;
    if (title) { clearInterval(interval); callback(title); }      // line J
    else if (attempts >= 10) { clearInterval(interval); }         // line K
  }, 300);
}
```

| Line | What it does | Why it exists |
|---|---|---|
| A | Listens for YouTube's custom navigation event | YouTube is a SPA — no `load` events fire on video changes; this is the correct hook |
| B | Runs immediately on first injection | For the case where the user opened a `/watch` URL directly |
| C | Skips if not a watch page | We don't check the homepage, search results, or channel pages |
| D | Removes the previous overlay | So a user going from blocked→allowed doesn't see a stale lock screen |
| E | Hands off to the retry loop | We don't check the title synchronously — YouTube hasn't rendered it yet |
| F | Deduplication guard | YouTube can fire `yt-navigate-finish` twice per navigation; prevents double-checking |
| G | Records what we checked | So the next navigation event can compare against it |
| H | Starts the actual check | Sends message to background.js → Flask → response → overlay or nothing |
| I | Polls every 300 ms | The `<h1>` title appears asynchronously; we need to wait for it |
| J | Title found — stop polling, call callback | `clearInterval` stops the repeating timer |
| K | Gave up after 3 seconds — stop polling | Prevents infinite polling on weird YouTube states |

---

### Snippet 6 — DOM injection: building the overlay (`extension/content.js`)

```javascript
const overlay = document.createElement("div");     // line A
overlay.id        = "pf-overlay";                  // line B
overlay.className = "pf-overlay";                  // line C

const card    = document.createElement("div");     // line D
card.className = "pf-card";

const heading = document.createElement("h2");      // line E
heading.className = "pf-heading";
heading.innerHTML = `<span class="pf-accent">Off your path</span>`;  // line F

const body = document.createElement("p");          // line G
body.textContent = `Pathfinder paused this video…`; // line H (NOT innerHTML)

card.appendChild(heading);                         // line I
card.appendChild(body);                            // line J
overlay.appendChild(card);                         // line K
document.body.appendChild(overlay);               // line L
```

| Line | What it does | Why it exists |
|---|---|---|
| A | Creates a `<div>` element in memory | It has no parent yet and is invisible to the user |
| B | Sets the `id` attribute | Lets us find and remove it later with `getElementById("pf-overlay")` |
| C | Assigns the CSS class | `blocker.css` defines `.pf-overlay { position:fixed; z-index:9999999; … }` |
| D | Creates the inner card `<div>` | Separation of concerns: overlay = backdrop, card = content |
| E | Creates the heading element | An `<h2>` is semantically correct for a section title |
| F | Uses `innerHTML` for the purple accent span | Safe here because the string is a hardcoded literal, not user input |
| G–H | Creates the body text with `textContent` | **Never use `innerHTML` with user-supplied data** — a video title with `<script>` in it would execute |
| I–J | Nests heading and body inside card | `appendChild` builds the in-memory tree: card → [heading, body] |
| K | Nests card inside overlay | overlay → card → [heading, body] |
| L | Inserts the entire tree into the live page | This is the single line that makes the overlay visible. Everything before this was invisible |

---

## 4. Questions Judges Might Ask

---

**Q1: Why use a hybrid Gemini + keyword fallback? Why not just one or the other?**

Gemini alone fails silently in four real situations: no internet, expired API
key, rate limit exceeded, or network timeout. A hackathon demo with a single
point of failure is a bad demo. The keyword fallback is always available — it's
pure Python math with no external dependencies. The tradeoff is that keywords
miss semantic relationships ("GATE lecture" isn't literally "exam prep"), but
Gemini catches those. Together: Gemini handles meaning when it can, keywords
handle availability when it can't. The `try/except GeminiUnavailableError`
pattern makes the switch seamless and invisible to the user.

---

**Q2: Why does `background.js` make the HTTP request to Flask instead of `content.js`?**

Content scripts run inside the YouTube tab's security sandbox. Browsers
enforce that a script running in a tab can only freely fetch resources from
the same origin as that page. YouTube's origin is `https://www.youtube.com`;
our Flask server is `http://localhost:5000` — a completely different origin.
Even with CORS headers on Flask, Chrome further restricts content scripts
in MV3. The service worker (`background.js`) runs in Chrome's own background
process, outside any tab's origin, and can fetch any URL listed in the
manifest's `host_permissions`. So the data flow is: content.js (notices the
video) → message → background.js (does the fetch) → message back → content.js
(shows or doesn't show the overlay).

---

**Q3: What happens if Gemini is down during the demo?**

Nothing visible breaks. `get_gemini_score()` is wrapped in a `try/except`
that catches every possible failure — timeout, network error, bad response,
missing API key — and raises a single custom `GeminiUnavailableError`. Back
in `app.py`, the `except GeminiUnavailableError` block calls `score_title()`
instead and sets `mode = "fallback"`. The response JSON looks identical to
the Gemini path; the extension can't tell the difference except for the
`"mode"` field. You can also pre-empt this by setting `FORCE_FALLBACK=true`
in `.env` before presenting.

---

**Q4: Walk me through exactly how the fallback classifier scores a title.**

Given title `"SQL Joins Explained – GATE DBMS Lecture"` and topic `"DBMS exam prep"`:

1. `_tokenize(title)` → `["sql", "joins", "explained", "gate", "dbms", "lecture"]`
2. `_tokenize(topic)` → `["dbms", "exam", "prep"]`
3. For topic word `"dbms"`: scan title words. "dbms" == "dbms" → exact match → 1.0 point.
4. For topic word `"exam"`: scan title words. None match exactly. No 4-char prefix match ("join"≠"exam", "expl"≠"exam", etc.) → 0.0 points.
5. For topic word `"prep"`: scan title words. No match → 0.0 points.
6. Total = 1.0 / 3 topic words = **0.333**. Below the 0.6 threshold → **blocked**.

This is intentional: the fallback is conservative. It doesn't understand that a "GATE lecture" on DBMS is relevant exam prep. That's exactly where Gemini adds value.

---

**Q5: How is data stored, and what's actually in the database?**

Data lives in two places:
- **`chrome.storage.local`** (browser): stores the user's `focus_topic` (string) and `enabled` (boolean). Persists across browser restarts. Shared between popup, background, and content scripts.
- **SQLite file** (`backend/instance/pathfinder.db`): one `video_log` row per check. Each row stores: video title, focus topic, relevance score, allowed/blocked result, mode used (gemini/fallback), and timestamp. Accessible via `GET /logs` for the demo.

SQLAlchemy is the bridge: you write Python classes (`VideoLog`), it writes SQL. No raw SQL needed.

---

**Q6: How would this scale if it had real users?**

The current architecture is local-first by design (single Flask process, SQLite, localhost). To scale:

1. **Database**: swap SQLite for PostgreSQL. Change one line: `SQLALCHEMY_DATABASE_URI`.
2. **Backend**: deploy Flask behind gunicorn + nginx on any cloud VM; or containerize with Docker.
3. **Gemini**: already uses a cloud API — scales automatically. Add a Redis cache to avoid re-checking identical titles.
4. **Extension**: the extension code doesn't change at all — just update the endpoint URL from `localhost:5000` to the production server.
5. **Multi-user**: add user accounts (Flask-Login), associate `VideoLog` rows with user IDs.

The fact that Flask, SQLAlchemy, and the extension are already decoupled makes each layer independently upgradeable.

---

**Q7: What are the privacy implications?**

Currently, every video title the user watches is sent to two places:
- Our Flask server (running locally — no third party involved)
- Google's Gemini API (if online mode is used)

This means Google receives video title strings. They do **not** receive: the user's identity, their YouTube account, cookies, or browsing history. Titles are non-PII but could reveal study habits.

For a production version: add a toggle to opt out of Gemini entirely (the `FORCE_FALLBACK` flag already supports this); add a clear privacy policy; consider hashing or truncating titles before sending. The local fallback classifier is the privacy-preserving path — it processes everything on-device.

---

**Q8: What would you build next if you had more time?**

Ordered by impact:

1. **Session analytics UI**: a simple HTML page that fetches `/logs` and shows a bar chart of allowed vs. blocked videos per hour. Judges love a dashboard.
2. **Smart threshold**: let the user set their strictness level (strict / balanced / relaxed) in the popup, which maps to `0.8 / 0.6 / 0.4` thresholds.
3. **Topic history**: store past focus topics in a dropdown so switching between "DBMS exam prep" and "Machine Learning" is one click.
4. **YouTube Shorts support**: `content.js` currently only checks `/watch` URLs; Shorts use `/shorts/` and need a different title selector.
5. **Caching**: cache `(title, topic) → score` in memory so re-visiting a video doesn't hit Gemini twice.
6. **Published extension**: submit to the Chrome Web Store with a real icon, onboarding flow, and the backend deployed to a free-tier cloud server.

---

## 5. What I'd Learn Next

Each part of Pathfinder points to a real skill worth adding to your stack:

| Part of Pathfinder | What it uses now | What to learn next |
|---|---|---|
| Flask routes & `request.get_json()` | Basic Flask routing | **Flask Blueprints** (organizing large apps into modules); **Flask-Login** (user accounts) |
| SQLAlchemy ORM & SQLite | Simple single-file database | **Database migrations with Alembic** (change table schemas without losing data); **PostgreSQL** (production-grade database) |
| `try/except GeminiUnavailableError` | Custom exceptions & error handling | **Retry logic with exponential backoff**; **circuit breaker pattern** (automatically stop calling a failing service) |
| `score_title()` pure-Python classifier | String processing & word overlap | **TF-IDF** (term frequency scoring); **spaCy or NLTK** (proper NLP tokenization, lemmatization, named-entity recognition) |
| Gemini API call with prompt engineering | Basic generative AI | **Structured output / JSON mode** in Gemini (ask the model to return JSON instead of plain text, eliminating the `float()` parse step); **LangChain** for chaining AI calls |
| `chrome.storage.local` | Browser key-value store | **IndexedDB** (structured browser database for larger datasets); **Chrome Sync storage** (sync settings across devices) |
| `yt-navigate-finish` + DOM polling | SPA navigation hooks | **MutationObserver** (the modern, event-driven alternative to polling — watches for DOM changes instead of using `setInterval`) |
| `document.createElement` + `appendChild` | Manual DOM construction | **Web Components** (`<template>` + `<slot>`) for reusable custom HTML elements without a framework |
| `manifest.json` permissions model | Extension security basics | **Content Security Policy (CSP)**; publishing to the Chrome Web Store (requires privacy policy, screenshots, and review) |
| `python-dotenv` + `.env` files | Environment variable management | **12-factor app methodology**; **Docker secrets**; **cloud secret managers** (AWS Secrets Manager, Google Secret Manager) |

---

*Built at a hackathon in one hour. Every file in this project is something you can read, understand, and extend — that's the point.*
