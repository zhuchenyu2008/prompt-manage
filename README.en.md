# Prompt Manager

Language: English | [简体中文](README.md)

A feature-complete local prompt management system with versioning, search, tags, and import/export. Built with Python + Flask + SQLite — no external services or build steps required.

## Change Language:
Default is Chinese. You can switch to English in the "设置-语言-英文" at the top right corner.

## ✨ Core Features

### 📝 Prompt Management
- Create & edit: name, source, tags, notes and more
- Content preview: show summary on home; one-click copy full content
- Pin important prompts for quick access
- Smart search across name, source, notes, tags and content
- Language Switching: Supports Chinese/English toggle

### 🔄 Versioning
- Semantic versioning: `major.minor.patch`
- Flexible bumps: patch (+0.0.1), minor (+0.1.0), major (+1.0.0)
- History rollback: create a new version from any historical one
- Auto pruning: keep only the latest N versions per prompt (default 200)

### 📊 Diff & Compare
- Side-by-side diff view
- Word-level highlighting (default)
- Line-level view also available
- Quick toggle between word/line modes

### 🏷️ Tag System
- Hierarchical tags like `Scene/Support`
- Smart suggestions while typing
- Sort and filter by tags

### 🎨 UX
- Light/Dark themes; auto follow system
- Responsive for desktop and mobile
- Smooth interaction and transitions
- Keyboard shortcuts (e.g., Ctrl+S to save, Ctrl+P to preview)
- Desktop view toggle (grid/list) with preference remembered
- Prompt color accents (new): set a color in “Advanced Settings” (#RGB/#RRGGBB). Home cards show a subtle ring; includes color picker, swatch preview, and “clear” button. Empty = unset
- UI language (new): switch UI language in Settings (Chinese/English), default Chinese

### 📤 Data
- Import/Export full backup in JSON
- Local SQLite only (no cloud dependency)
- Settings management: version cleanup threshold, access password, and UI language

### 🔒 Optional Access Password
- Three modes (Settings): Off / Per‑prompt / Global
- Password length: 4–8 digits; required when enabling for the first time
- Per‑prompt: check “Require password” in the editor
- Home behavior (Per‑prompt mode): protected cards show only title and “Source: Password required”; click to unlock
- Session unlock: unlocked prompts allowed for current session; “Logout” clears auth

## 🚀 Quick Start

### Option 1: Docker (recommended)

Requirements
- Docker and Docker Compose

Using official image

- Image: `docker.io/zhuchenyu2008/prompt-manage:latest`

```bash
# Pull
docker pull zhuchenyu2008/prompt-manage:latest

# Run with a named volume for data
docker run -d \
  --name prompt-manage \
  -p 3501:3501 \
  -v prompt-data:/app/data \
  zhuchenyu2008/prompt-manage:latest

# Open http://localhost:3501
```

Using Docker Compose

1. Clone
   ```bash
   git clone https://github.com/zhuchenyu2008/prompt-manage
   cd prompt
   ```
2. Start (build locally)
   ```bash
   docker-compose up
   # or in background
   docker-compose up -d
   ```
   Visit: http://localhost:3501
3. Use published image (recommended for production)
   Replace `build:` in `docker-compose.yml` with:
   ```yaml
   services:
     prompt-manager:
       image: zhuchenyu2008/prompt-manage:latest
       ports:
         - "3501:3501"
       volumes:
         - prompt-data:/app/data
       environment:
         - FLASK_ENV=production
       restart: unless-stopped
   ```

Using raw Docker

```bash
# Build (for local dev)
docker build -t prompt-manager .

# Run
docker run -d -p 3501:3501 -v prompt-data:/app/data prompt-manager
```

### Option 2: Local Python

Requirements
- Python 3.9+
- Flask + Werkzeug

Steps
1. Clone
   ```bash
   git clone https://github.com/zhuchenyu2008/prompt-manage
   cd prompt
   ```
2. Install deps
   ```bash
   pip install -r requirements.txt
   ```
3. Run
   ```bash
   python app.py
   ```
4. Open http://localhost:3501

Notes
- On first run, the app creates the SQLite DB automatically.
- Container/Compose default DB path: `/app/data/data.sqlite3` (mounted volume).
- Local direct run: override with `DB_PATH=./data.sqlite3 python app.py` (DB in project root).

## 📁 Project Structure

```
prompt/
├── app.py              # Flask app
├── requirements.txt    # Python deps
├── data.sqlite3        # Optional local DB (via DB_PATH)
├── Dockerfile          # Docker image config
├── docker-compose.yml  # Docker Compose config
├── .dockerignore       # Docker build ignore
├── templates/          # HTML templates
│   ├── layout.html
│   ├── index.html
│   ├── prompt_detail.html
│   ├── versions.html
│   ├── diff.html
│   ├── settings.html
│   └── auth.html
├── static/             # Static assets
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
└── README.md           # Docs
```

## 🗄️ Database

Tables
- prompts: id, name, source, notes, color, tags, pinned, created_at, updated_at, current_version_id, require_password
- versions: id, prompt_id, version, content, created_at, parent_version_id
- settings: key, value
  - Keys:
    - version_cleanup_threshold: version keep threshold (default 200)
    - auth_mode: `off` | `per` | `global`
    - auth_password_hash: SHA‑256 of the password
    - language: `zh` | `en` (UI language)

Export example

```json
{
  "prompts": [
    {
      "id": 1,
      "name": "Support Assistant",
      "source": "ChatGPT",
      "notes": "Standard replies for customer support",
      "color": "#409eff",
      "tags": ["Scene/Support", "Business/After-sales"],
      "pinned": true,
      "require_password": false,
      "created_at": "2024-01-01T00:00:00",
      "updated_at": "2024-01-02T12:34:56",
      "current_version_id": 3,
      "versions": [
        {
          "id": 1,
          "prompt_id": 1,
          "version": "1.0.0",
          "content": "You are a professional support assistant...",
          "created_at": "2024-01-01T00:00:00",
          "parent_version_id": null
        }
      ]
    }
  ]
}
```

## 🎯 User Guide

### Basics
1. Create a prompt
   - Click “New Prompt” on home
   - Fill name, source, etc.
   - Write content
   - Choose bump type and save
2. Versioning
   - Check “Save as new version” while editing
   - View full history on the detail page
   - Compare any two versions
   - Roll back by creating a new version from history
3. Search & Filter
   - Full‑text search on home
   - Sort by created, updated, name, tags
   - Pin important prompts

### Advanced
- Tags: use `/` for hierarchy, e.g. `Dept/Tech/Dev`
- Bulk: import/export for mass data
- Diff: word‑level and line‑level
- Theme: toggle dark/light via top‑right button
- Colors: JSON export includes `color`; import validates & normalizes

### Access Password
1. Settings → Access Password.
2. Set/change password (4–8 digits).
3. Modes:
   - Per‑prompt: check “Require password” in editor.
   - Global: every page requires auth when on.
4. In Per‑prompt mode, protected cards hide tags/notes/content; shows “Source: Password required”.

### Home View Toggle (Desktop)
- Location: small rounded button under stats, above list.
- Icons: `fa-table-cells` (grid) and `fa-list` (list).
- Default: grid; columns auto-fit.
- Remembered in `localStorage.viewMode`.
- Mobile: toggle hidden; single-column enforced.

## ⚙️ Configuration

### Port
Default port is `3501`. In `app.py`:

```python
app.run(host='0.0.0.0', port=3501, debug=True)
```

### Version Cleanup
- Keep latest 200 versions per prompt by default
- Oldest are pruned when exceeding the limit
- Adjustable in Settings

### Security Notes
- The access password is lightweight; SHA‑256 without salt. Do not use for high‑security scenarios.
- Forgot password? Clear via SQLite:
  ```sql
  DELETE FROM settings WHERE key='auth_password_hash';
  UPDATE settings SET value='off' WHERE key='auth_mode';
  ```
  Restart app and reconfigure in Settings.

## 🛠️ Development

### Stack
- Backend: Flask
- DB: SQLite
- Frontend: HTML/CSS/JS
- Styling: CSS variables + Flex/Grid
- Icons: Font Awesome
- Deps: Flask, Werkzeug

### Highlights
- Theme system using CSS variables and `data-theme`
- Responsive (mobile‑first)
- No build tools (pure static assets)
- Preferences saved in localStorage

## 🔧 Troubleshooting

### Common Issues
1. Missing Flask: `pip install flask`
2. Port in use: change port in `app.py`
3. Permission: ensure read/write on working dir
4. DB corrupted: delete DB_PATH file and restart (container default `/app/data/data.sqlite3`; local example `./data.sqlite3`)

### Reset All Data
Delete the DB file pointed by DB_PATH and restart (container default `/app/data/data.sqlite3`; local `./data.sqlite3`).

### Environment
- `DB_PATH`: path to SQLite file
  - Container/Compose default: `/app/data/data.sqlite3`
  - Local example: `DB_PATH=./data.sqlite3 python app.py`
  - If omitted, default is used; app creates the folder and DB on first run

## 📝 Changelog

### Latest
- New: prompt color accents with picker/swatch/clear; import/export `color`
- New: grid layout on home + desktop view toggle
- Improved dark mode
- One‑click copy preview on home
- Dynamic page titles
- Simplified UI and enhanced color system
- New: access password (off/per/global) with card lock UI
- New: UI language switch (Chinese/English)

### Changes & Fixes
- Always use relative `next` during redirects
  - Normalize `next` path to stay on‑site
- Respect reverse proxy headers
  - `ProxyFix` to use `X-Forwarded-*`
- Fix unauthorized password change in Settings

