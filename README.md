# repo-cloner 🐙⬇️

A sleek desktop GUI tool to **clone any public GitHub repo and push it directly to your own GitHub account** — in one click. Built with Python and CustomTkinter, packaged as a standalone `.exe` (Windows) or `.app` (macOS).

No terminal. No commands. Just paste, click, done.

---

## Features

- 🔗 **Clone + Push in one flow** — clone any public repo and push it to your GitHub automatically
- 🐙 **GitHub API integration** — creates the destination repo on your account via the GitHub API
- 💾 **Persistent settings** — username, token and folder are saved locally and auto-loaded on every launch
- ⚙️ **Collapsible settings panel** — configure once, hidden on every subsequent run
- ➕ **Multi-repo support** — add multiple repos and process them all in one click
- 🌿 **Auto branch detection** — detects `main` or `master` automatically
- 🎨 **Dark themed UI** — GitHub-inspired dark color scheme
- 📋 **Color-coded log output** — green for success, red for errors, yellow for warnings
- 🪟 **Resizable & scrollable** — works on any screen size, fully maximizable
- 📦 **Standalone binary** — `.exe` for Windows, `.app` for macOS; no Python installation needed on the target machine

---

## Screenshots

> Dark themed UI with collapsible settings, multi-repo list, and live output log.

---

## Installation

### Option 1 — Run from source

**Requirements:** Python 3.8+, Git installed and on PATH

```bash
# Clone this repo
git clone https://github.com/samarthvmurthy/repo-cloner

cd repo-cloner

# Install dependencies
pip install customtkinter requests pyinstaller

# Run
python repo_cloner.py
```

### Option 2 — Download the pre-built binary

Download from the [Releases](../../releases) page. No Python needed — just requires **Git** to be installed.

| Platform | File |
|---|---|
| Windows | `RepoClonerApp.exe` |
| macOS | `RepoClonerApp-mac.zip` (extract and run `RepoClonerApp.app`) |

---

## Build yourself

Make sure `repo_cloner.py`, `repocloner.ico`, and `repocloner.png` are in the same folder.

**Windows:**
```bash
pyinstaller --onefile --windowed --icon=repocloner.ico --name=RepoClonerApp repo_cloner.py
```
Your `.exe` will be in `dist/`.

**macOS:**
```bash
pyinstaller --windowed --name=RepoClonerApp repo_cloner.py
zip -r RepoClonerApp-mac.zip dist/RepoClonerApp.app
```
Your `.app` bundle will be in `dist/`.

---

## Usage

### First time
1. Open the app — the **Settings panel** opens automatically
2. Enter your **GitHub username** (e.g. `samarthvmurthy`)
3. Paste your **Personal Access Token (PAT)** — needs `repo` and `workflow` scopes
4. Set your **local destination folder**
5. Select your **OS** (Windows or macOS — auto-detected)
6. Hit **💾 Save & Collapse**

> Generate a PAT at: [github.com/settings/tokens](https://github.com/settings/tokens)

### Every time after
1. Paste a GitHub URL into the repo field
2. Select your **Action Mode**:
   - `Clone only` — downloads locally
   - `Clone + Push (new repo)` — clones and creates + pushes to your GitHub
   - `Clone + Push (existing repo)` — clones and pushes to an existing repo
3. Hit **⬇ Clone**

The repo list clears automatically after a successful run.

---

## Requirements

| Requirement | Details |
|---|---|
| Git | Must be installed and on PATH — [git-scm.com](https://git-scm.com/downloads) |
| GitHub PAT | Needs `repo` scope, `workflow` scope for repos with GitHub Actions |
| OS | Windows (`.exe`) or macOS (`.app`); Linux run from source |
| Python (dev only) | 3.8+ with `customtkinter`, `requests`, `pyinstaller` |

---

## Tech Stack

- **Python 3**
- **CustomTkinter** — modern dark UI framework
- **Requests** — GitHub REST API calls
- **PyInstaller** — packaging to `.exe`
- **Git** — clone and push operations via subprocess

---

## License

MIT — free to use, modify and distribute.
