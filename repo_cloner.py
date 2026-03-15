import customtkinter as ctk
import subprocess
import threading
import os
import re
import json
import sys
import platform
import requests
from tkinter import filedialog, StringVar, BooleanVar

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".repocloner_config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data: dict):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ── Helpers ───────────────────────────────────────────────────────────────────
def is_valid_github_url(url: str) -> bool:
    pattern = r"^https://github\.com/[\w.\-]+/[\w.\-]+(\.git)?$"
    return bool(re.match(pattern, url.strip()))

def extract_repo_name(url: str) -> str:
    return url.rstrip("/").replace(".git", "").split("/")[-1]

def create_github_repo(username, token, repo_name, private):
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    payload = {"name": repo_name, "private": private, "auto_init": False}
    resp = requests.post("https://api.github.com/user/repos", json=payload, headers=headers)
    if resp.status_code == 201:
        return True, resp.json().get("html_url", "")
    elif resp.status_code == 422:
        return True, f"https://github.com/{username}/{repo_name}"
    return False, resp.json().get("message", "Unknown error")

def validate_token(token):
    resp = requests.get("https://api.github.com/user", headers={"Authorization": f"token {token}"})
    if resp.status_code == 200:
        return True, resp.json().get("login", "")
    return False, ""

def get_git_cmd(os_pref: str) -> str:
    """Return git command path based on OS preference and fallbacks."""
    if os_pref == 'mac':
        candidates = ['/usr/bin/git', '/usr/local/bin/git', '/opt/homebrew/bin/git', 'git']
    else:
        candidates = ['git']
    for cmd in candidates:
        try:
            result = subprocess.run([cmd, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                return cmd
        except FileNotFoundError:
            continue
    return 'git'  # fallback

# ── Main App ──────────────────────────────────────────────────────────────────
class RepoClonerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Git Repo Cloner & Pusher")
        self.geometry("780x800")
        self.minsize(680, 600)
        self.resizable(True, True)
        self.configure(fg_color="#0d1117")

        # Set window icon — ico on Windows, png on Mac
        try:
            base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
            if platform.system() == "Darwin":
                from PIL import Image, ImageTk
                png_path = os.path.join(base, "repocloner.png")
                if os.path.exists(png_path):
                    img = ImageTk.PhotoImage(Image.open(png_path).resize((64, 64)))
                    self.iconphoto(True, img)
            else:
                icon_path = os.path.join(base, "repocloner.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
        except Exception:
            pass

        cfg = load_config()

        # Auto-detect OS if not saved
        detected_os = "mac" if platform.system() == "Darwin" else "windows"

        self.repo_rows         = []
        self.dest_path         = StringVar(value=cfg.get("dest_path", os.path.expanduser("~/cloned-repos")))
        self.gh_user           = StringVar(value=cfg.get("gh_user", ""))
        self.gh_token          = StringVar(value=cfg.get("gh_token", ""))
        self.push_mode         = StringVar(value=cfg.get("push_mode", "clone_only"))
        self.visibility        = StringVar(value=cfg.get("visibility", "public"))
        self.os_pref           = StringVar(value=cfg.get("os_pref", detected_os))
        self.token_status_var  = StringVar(value="")
        self.settings_expanded = BooleanVar(value=not bool(cfg.get("gh_user", "")))
        self.action_thread     = None

        for var in (self.dest_path, self.gh_user, self.gh_token, self.push_mode, self.visibility, self.os_pref):
            var.trace_add("write", lambda *_: self._save())

        self._build_ui()
        self._add_repo_row()

        if not cfg.get("gh_user", ""):
            self._log("👋  Welcome! Fill in your GitHub details in Settings, then hit Save & Collapse.", color="warning")

    # ── Persist ───────────────────────────────────────────────────────────────
    def _save(self):
        save_config({
            "dest_path":  self.dest_path.get(),
            "gh_user":    self.gh_user.get(),
            "gh_token":   self.gh_token.get(),
            "push_mode":  self.push_mode.get(),
            "visibility": self.visibility.get(),
            "os_pref":    self.os_pref.get(),
        })

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Fixed header (never scrolls)
        header = ctk.CTkFrame(self, fg_color="#161b22", corner_radius=0, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="⬇  Git Repo Cloner & Pusher",
            font=ctk.CTkFont(family="Courier New", size=20, weight="bold"),
            text_color="#58a6ff",
        ).pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(
            header, text="Clone → push to your GitHub",
            font=ctk.CTkFont(size=12), text_color="#8b949e",
        ).pack(side="left", padx=4)

        # Main scrollable canvas so everything below header scrolls
        self.main_scroll = ctk.CTkScrollableFrame(
            self, fg_color="#0d1117",
            scrollbar_button_color="#21262d",
            scrollbar_button_hover_color="#30363d",
        )
        self.main_scroll.pack(fill="both", expand=True, side="top")

        S = self.main_scroll   # shorthand

        # ── Settings panel ────────────────────────────────────────────────────
        self._build_settings_panel(S)

        # ── Mode selector ─────────────────────────────────────────────────────
        mode_frame = ctk.CTkFrame(S, fg_color="#161b22", corner_radius=10)
        mode_frame.pack(fill="x", padx=20, pady=(10, 0))
        ctk.CTkLabel(mode_frame, text="⚙  Action Mode",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#c9d1d9",
                     ).pack(anchor="w", padx=16, pady=(10, 6))
        mode_row = ctk.CTkFrame(mode_frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=16, pady=(0, 10))

        modes = [
            ("clone_only",    "Clone only",              "Just download locally"),
            ("push_new",      "Clone + Push (new repo)", "Creates new repo on your GitHub"),
            ("push_existing", "Clone + Push (existing)", "Push into an already-created repo"),
        ]
        for val, label, hint in modes:
            col = ctk.CTkFrame(mode_row, fg_color="transparent")
            col.pack(side="left", padx=(0, 20))
            ctk.CTkRadioButton(
                col, text=label, variable=self.push_mode, value=val,
                font=ctk.CTkFont(size=12), text_color="#c9d1d9",
                fg_color="#1f6feb", hover_color="#388bfd",
                command=self._update_mode_ui,
            ).pack(anchor="w")
            ctk.CTkLabel(col, text=hint, font=ctk.CTkFont(size=10),
                         text_color="#8b949e").pack(anchor="w")

        self.vis_frame = ctk.CTkFrame(mode_frame, fg_color="transparent")
        self.vis_frame.pack(anchor="w", padx=16, pady=(0, 8))
        ctk.CTkLabel(self.vis_frame, text="Visibility:",
                     font=ctk.CTkFont(size=11), text_color="#8b949e").pack(side="left", padx=(0, 8))
        for v, lbl in [("public", "Public"), ("private", "Private")]:
            ctk.CTkRadioButton(
                self.vis_frame, text=lbl, variable=self.visibility, value=v,
                font=ctk.CTkFont(size=12), text_color="#c9d1d9",
                fg_color="#1f6feb", hover_color="#388bfd",
            ).pack(side="left", padx=(0, 12))
        if self.push_mode.get() != "push_new":
            self.vis_frame.pack_forget()

        # ── Repos list ────────────────────────────────────────────────────────
        repos_header = ctk.CTkFrame(S, fg_color="transparent")
        repos_header.pack(fill="x", padx=20, pady=(10, 4))
        ctk.CTkLabel(repos_header, text="🔗  Repositories",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#c9d1d9").pack(side="left")
        ctk.CTkButton(
            repos_header, text="+ Add Repo", width=100, height=28,
            fg_color="#238636", hover_color="#2ea043", font=ctk.CTkFont(size=12),
            command=self._add_repo_row,
        ).pack(side="right")

        self.scroll_frame = ctk.CTkScrollableFrame(
            S, fg_color="#161b22",
            scrollbar_button_color="#21262d", scrollbar_button_hover_color="#30363d",
            corner_radius=10, height=200,
        )
        self.scroll_frame.pack(fill="x", padx=20)

        # ── Action button ─────────────────────────────────────────────────────
        self.action_btn = ctk.CTkButton(
            S, text="⬇  Clone All Repos", height=46,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#1f6feb", hover_color="#388bfd", corner_radius=8,
            command=self._start_action,
        )
        self.action_btn.pack(fill="x", padx=20, pady=(12, 0))
        self._update_mode_ui()

        # ── Log ───────────────────────────────────────────────────────────────
        ctk.CTkLabel(S, text="📋  Output Log",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#c9d1d9", anchor="w").pack(fill="x", padx=20, pady=(12, 4))
        self.log_box = ctk.CTkTextbox(
            S, height=200,
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color="#0d1117", border_color="#30363d", border_width=1,
            text_color="#c9d1d9", corner_radius=8, state="disabled",
        )
        self.log_box.pack(fill="x", padx=20, pady=(0, 20))

    # ── Settings panel (collapsible) ──────────────────────────────────────────
    def _build_settings_panel(self, parent):
        self.settings_bar = ctk.CTkFrame(parent, fg_color="#161b22", corner_radius=10)
        self.settings_bar.pack(fill="x", padx=20, pady=(12, 0))

        bar_inner = ctk.CTkFrame(self.settings_bar, fg_color="transparent")
        bar_inner.pack(fill="x", padx=16, pady=8)

        self.settings_summary = ctk.CTkLabel(
            bar_inner, text=self._settings_summary_text(),
            font=ctk.CTkFont(family="Courier New", size=11), text_color="#8b949e", anchor="w",
        )
        self.settings_summary.pack(side="left", fill="x", expand=True)

        self.toggle_btn = ctk.CTkButton(
            bar_inner,
            text="▲  Collapse" if self.settings_expanded.get() else "▼  Settings",
            width=120, height=28,
            fg_color="#21262d", hover_color="#30363d", border_color="#30363d",
            border_width=1, text_color="#c9d1d9", font=ctk.CTkFont(size=12),
            command=self._toggle_settings,
        )
        self.toggle_btn.pack(side="right")

        self.settings_panel = ctk.CTkFrame(parent, fg_color="#161b22", corner_radius=10)

        fields = ctk.CTkFrame(self.settings_panel, fg_color="transparent")
        fields.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(fields, text="Username", font=ctk.CTkFont(size=11),
                     text_color="#8b949e", width=80, anchor="w").grid(row=0, column=0, sticky="w", pady=5)
        ctk.CTkEntry(
            fields, textvariable=self.gh_user, placeholder_text="your-github-username",
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color="#0d1117", border_color="#30363d", text_color="#c9d1d9", height=34,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=5)

        ctk.CTkLabel(fields, text="Token (PAT)", font=ctk.CTkFont(size=11),
                     text_color="#8b949e", width=80, anchor="w").grid(row=1, column=0, sticky="w", pady=5)
        token_row = ctk.CTkFrame(fields, fg_color="transparent")
        token_row.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=5)
        ctk.CTkEntry(
            token_row, textvariable=self.gh_token, placeholder_text="ghp_xxxxxxxxxxxxxxxxxxxx",
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color="#0d1117", border_color="#30363d", text_color="#c9d1d9", height=34, show="*",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            token_row, text="Validate", width=80, height=34,
            fg_color="#21262d", hover_color="#30363d", border_color="#30363d",
            border_width=1, text_color="#c9d1d9", font=ctk.CTkFont(size=12),
            command=self._validate_token,
        ).pack(side="left", padx=(8, 0))
        self.token_status_label = ctk.CTkLabel(
            token_row, textvariable=self.token_status_var,
            font=ctk.CTkFont(size=11), text_color="#3fb950",
        )
        self.token_status_label.pack(side="left", padx=(8, 0))

        ctk.CTkLabel(fields, text="Folder", font=ctk.CTkFont(size=11),
                     text_color="#8b949e", width=80, anchor="w").grid(row=2, column=0, sticky="w", pady=5)
        folder_row = ctk.CTkFrame(fields, fg_color="transparent")
        folder_row.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=5)
        ctk.CTkEntry(
            folder_row, textvariable=self.dest_path,
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color="#0d1117", border_color="#30363d", text_color="#c9d1d9", height=34,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            folder_row, text="Browse", width=80, height=34,
            fg_color="#21262d", hover_color="#30363d", border_color="#30363d",
            border_width=1, text_color="#c9d1d9", font=ctk.CTkFont(size=12),
            command=self._browse_folder,
        ).pack(side="left", padx=(8, 0))
        # OS selector
        ctk.CTkLabel(fields, text="OS", font=ctk.CTkFont(size=11),
                     text_color="#8b949e", width=80, anchor="w").grid(row=3, column=0, sticky="w", pady=5)
        os_row = ctk.CTkFrame(fields, fg_color="transparent")
        os_row.grid(row=3, column=1, sticky="w", padx=(8, 0), pady=5)
        for os_val, os_lbl, os_hint in [("windows", "🪟  Windows", ".exe app"), ("mac", "🍎  macOS", ".app bundle")]:
            col = ctk.CTkFrame(os_row, fg_color="transparent")
            col.pack(side="left", padx=(0, 16))
            ctk.CTkRadioButton(
                col, text=os_lbl, variable=self.os_pref, value=os_val,
                font=ctk.CTkFont(size=12), text_color="#c9d1d9",
                fg_color="#1f6feb", hover_color="#388bfd",
            ).pack(anchor="w")
            ctk.CTkLabel(col, text=os_hint, font=ctk.CTkFont(size=10),
                         text_color="#8b949e").pack(anchor="w")

        fields.columnconfigure(1, weight=1)

        ctk.CTkLabel(
            self.settings_panel,
            text="ℹ  PAT needs 'repo' scope — github.com/settings/tokens",
            font=ctk.CTkFont(size=11), text_color="#8b949e",
        ).pack(anchor="w", padx=16, pady=(0, 4))

        ctk.CTkButton(
            self.settings_panel, text="💾  Save & Collapse", height=36, width=160,
            fg_color="#238636", hover_color="#2ea043", font=ctk.CTkFont(size=12),
            command=self._save_and_collapse,
        ).pack(anchor="e", padx=16, pady=(4, 12))

        if self.settings_expanded.get():
            self.settings_panel.pack(fill="x", padx=20, pady=(4, 0))

    def _settings_summary_text(self):
        user  = self.gh_user.get()  if hasattr(self, "gh_user")  else ""
        token = self.gh_token.get() if hasattr(self, "gh_token") else ""
        folder= self.dest_path.get()if hasattr(self, "dest_path")else ""
        os_p  = self.os_pref.get()  if hasattr(self, "os_pref")  else ""
        if user:
            hint     = f"{'*'*6}{token[-4:]}" if len(token) > 4 else "not set"
            folder_s = folder if len(folder) < 38 else "..." + folder[-36:]
            os_icon  = "🪟" if os_p == "windows" else "🍎"
            return f"@{user}   •   token: {hint}   •   {folder_s}   •   {os_icon}"
        return "Not configured — click Settings to set up"

    def _toggle_settings(self):
        if self.settings_expanded.get():
            self.settings_panel.pack_forget()
            self.settings_expanded.set(False)
            self.toggle_btn.configure(text="▼  Settings")
        else:
            self.settings_panel.pack(fill="x", padx=20, pady=(4, 0), after=self.settings_bar)
            self.settings_expanded.set(True)
            self.toggle_btn.configure(text="▲  Collapse")

    def _save_and_collapse(self):
        self._save()
        self.settings_summary.configure(text=self._settings_summary_text())
        self.settings_panel.pack_forget()
        self.settings_expanded.set(False)
        self.toggle_btn.configure(text="▼  Settings")
        self._log("✅  Settings saved.", color="success")

    # ── Mode UI ───────────────────────────────────────────────────────────────
    def _update_mode_ui(self):
        mode = self.push_mode.get()
        if mode == "push_new":
            self.vis_frame.pack(anchor="w", padx=16, pady=(0, 8))
        else:
            self.vis_frame.pack_forget()
        labels = {
            "clone_only":    "⬇  Clone All Repos",
            "push_new":      "⬇  Clone + Push to New GitHub Repos",
            "push_existing": "⬇  Clone + Push to Existing GitHub Repos",
        }
        if hasattr(self, "action_btn"):
            self.action_btn.configure(text=labels[mode])

    # ── Repo rows ─────────────────────────────────────────────────────────────
    def _add_repo_row(self):
        idx      = len(self.repo_rows)
        url_var  = StringVar()
        name_var = StringVar()

        row_frame = ctk.CTkFrame(
            self.scroll_frame, fg_color="#0d1117", corner_radius=8,
            border_color="#30363d", border_width=1,
        )
        row_frame.pack(fill="x", padx=8, pady=5)

        ctk.CTkLabel(
            row_frame, text=f"#{idx+1}", width=32,
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color="#8b949e", fg_color="#161b22", corner_radius=4,
        ).grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=10, sticky="ns")

        ctk.CTkLabel(row_frame, text="GitHub URL", font=ctk.CTkFont(size=11),
                     text_color="#8b949e").grid(row=0, column=1, sticky="w", padx=(0, 8), pady=(8, 0))
        ctk.CTkEntry(
            row_frame, textvariable=url_var,
            placeholder_text="https://github.com/username/repo",
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color="#161b22", border_color="#30363d", text_color="#c9d1d9",
            height=32, width=380,
        ).grid(row=0, column=2, padx=(0, 8), pady=(8, 0), sticky="ew")
        url_var.trace_add("write", lambda *_: self._autofill_name(url_var, name_var))

        ctk.CTkLabel(row_frame, text="Folder/Repo Name", font=ctk.CTkFont(size=11),
                     text_color="#8b949e").grid(row=1, column=1, sticky="w", padx=(0, 8), pady=(4, 8))
        ctk.CTkEntry(
            row_frame, textvariable=name_var,
            placeholder_text="auto-filled from URL",
            font=ctk.CTkFont(family="Courier New", size=12),
            fg_color="#161b22", border_color="#30363d", text_color="#c9d1d9",
            height=32, width=380,
        ).grid(row=1, column=2, padx=(0, 8), pady=(4, 8), sticky="ew")

        ctk.CTkButton(
            row_frame, text="✕", width=30, height=30,
            fg_color="#21262d", hover_color="#da3633",
            text_color="#8b949e", font=ctk.CTkFont(size=13),
            command=lambda f=row_frame, r=(row_frame, url_var, name_var): self._remove_repo_row(f, r),
        ).grid(row=0, column=3, rowspan=2, padx=(4, 10))

        row_frame.columnconfigure(2, weight=1)
        self.repo_rows.append((row_frame, url_var, name_var))

    def _remove_repo_row(self, frame, row_tuple):
        if len(self.repo_rows) <= 1:
            self._log("⚠️  Keep at least one repo row.", color="warning"); return
        frame.destroy()
        self.repo_rows.remove(row_tuple)

    def _clear_repo_rows(self):
        """Remove all repo rows and add a fresh empty one."""
        for frame, _, _ in self.repo_rows:
            frame.destroy()
        self.repo_rows.clear()
        self._add_repo_row()

    def _autofill_name(self, url_var, name_var):
        url = url_var.get().strip()
        if url and name_var.get() == "":
            name_var.set(extract_repo_name(url))

    # ── Actions ───────────────────────────────────────────────────────────────
    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.dest_path.get())
        if folder:
            self.dest_path.set(folder)

    def _validate_token(self):
        token = self.gh_token.get().strip()
        if not token:
            self.token_status_var.set("⚠️ Enter a token first")
            self.token_status_label.configure(text_color="#d29922"); return
        self.token_status_var.set("Checking...")
        self.token_status_label.configure(text_color="#8b949e")

        def _check():
            valid, username = validate_token(token)
            if valid:
                self.after(0, lambda: self.token_status_var.set(f"✅ @{username}"))
                self.after(0, lambda: self.token_status_label.configure(text_color="#3fb950"))
                if not self.gh_user.get():
                    self.after(0, lambda: self.gh_user.set(username))
            else:
                self.after(0, lambda: self.token_status_var.set("❌ Invalid"))
                self.after(0, lambda: self.token_status_label.configure(text_color="#f85149"))

        threading.Thread(target=_check, daemon=True).start()

    def _start_action(self):
        if self.action_thread and self.action_thread.is_alive(): return
        self.action_thread = threading.Thread(target=self._run_all, daemon=True)
        self.action_thread.start()

    def _run_all(self):
        mode  = self.push_mode.get()
        dest  = self.dest_path.get().strip()
        token = self.gh_token.get().strip()
        user  = self.gh_user.get().strip()
        GIT   = get_git_cmd(self.os_pref.get())

        if not dest:
            self._log("❌  No destination folder set. Open Settings to configure.", color="error"); return

        if mode != "clone_only":
            if not token or not user:
                self._log("❌  GitHub username and token required. Open Settings.", color="error"); return
            self._log("🔑  Validating GitHub token...")
            valid, fetched_user = validate_token(token)
            if not valid:
                self._log("❌  Invalid token. Open Settings and re-enter.", color="error"); return
            self._log(f"✅  Authenticated as @{fetched_user}", color="success")

        os.makedirs(dest, exist_ok=True)

        valid_repos = []
        for _, url_var, name_var in self.repo_rows:
            url = url_var.get().strip()
            if not url: continue
            if not is_valid_github_url(url):
                self._log(f"⚠️  Skipped invalid URL: {url}", color="warning"); continue
            name = name_var.get().strip() or extract_repo_name(url)
            valid_repos.append((url, name))

        if not valid_repos:
            self._log("❌  No valid GitHub URLs found.", color="error"); return

        self._set_btn_state("disabled")
        self._log(f"\n{'─'*55}\n🚀  Processing {len(valid_repos)} repo(s) — mode: {mode}\n{'─'*55}")

        all_succeeded = True

        for i, (url, name) in enumerate(valid_repos, 1):
            target = os.path.join(dest, name)
            self._log(f"\n[{i}/{len(valid_repos)}]  {name}")

            # Step 1: Clone
            if os.path.exists(target):
                self._log("  ⏭️  Already cloned locally, skipping clone.", color="warning")
            else:
                self._log(f"  ⬇️  Cloning from {url}...")
                try:
                    result = subprocess.run([GIT, "clone", url, target], capture_output=True, text=True)
                    if result.returncode != 0:
                        self._log(f"  ❌  Clone failed: {result.stderr.strip()}", color="error")
                        all_succeeded = False; continue
                    self._log(f"  ✅  Cloned → {target}", color="success")
                except FileNotFoundError:
                    os_p = self.os_pref.get()
                    if os_p == "mac":
                        self._log("  ❌  Git not found. Install via: brew install git", color="error")
                    else:
                        self._log("  ❌  Git not found. Install from git-scm.com and add to PATH.", color="error")
                    all_succeeded = False; break

            if mode == "clone_only":
                continue

            # Step 2: Create repo
            if mode == "push_new":
                self._log(f"  🌐  Creating '{name}' on GitHub...")
                ok, result_url = create_github_repo(user, token, name, private=(self.visibility.get() == "private"))
                if not ok:
                    self._log(f"  ❌  Could not create repo: {result_url}", color="error")
                    all_succeeded = False; continue
                self._log(f"  ✅  {result_url}", color="success")

            # Step 3: Push
            remote_url = f"https://{user}:{token}@github.com/{user}/{name}.git"
            self._log(f"  📤  Pushing to github.com/{user}/{name}...")
            try:
                subprocess.run([GIT, "-C", target, "remote", "remove", "origin"], capture_output=True)
                add_r = subprocess.run([GIT, "-C", target, "remote", "add", "origin", remote_url],
                                       capture_output=True, text=True)
                if add_r.returncode != 0:
                    self._log(f"  ❌  Remote error: {add_r.stderr.strip()}", color="error")
                    all_succeeded = False; continue

                branch = subprocess.run(
                    [GIT, "-C", target, "symbolic-ref", "--short", "HEAD"],
                    capture_output=True, text=True,
                ).stdout.strip() or "main"
                self._log(f"  🌿  Branch: {branch}")

                push_r = subprocess.run(
                    [GIT, "-C", target, "push", "--force", "-u", "origin", branch],
                    capture_output=True, text=True,
                )
                if push_r.returncode == 0:
                    self._log(f"  ✅  Pushed → github.com/{user}/{name}", color="success")
                else:
                    err = push_r.stderr.strip() or push_r.stdout.strip()
                    self._log(f"  ❌  Push failed: {err}", color="error")
                    self._log("  🔄  Retrying with --all...")
                    retry = subprocess.run(
                        [GIT, "-C", target, "push", "--force", "--all", "origin"],
                        capture_output=True, text=True,
                    )
                    if retry.returncode == 0:
                        self._log(f"  ✅  Pushed (all branches) → github.com/{user}/{name}", color="success")
                    else:
                        self._log(f"  ❌  Retry failed: {retry.stderr.strip()}", color="error")
                        all_succeeded = False
            except Exception as e:
                self._log(f"  ❌  Error: {e}", color="error")
                all_succeeded = False

        self._log(f"\n{'─'*55}\n🎉  All done!")
        self._set_btn_state("normal")

        # Clear repo rows only if everything succeeded
        if all_succeeded:
            self.after(0, self._clear_repo_rows)

    # ── Logging ───────────────────────────────────────────────────────────────
    def _log(self, message: str, color: str = "normal"):
        color_map = {
            "normal":  "#c9d1d9",
            "success": "#3fb950",
            "error":   "#f85149",
            "warning": "#d29922",
        }
        text_color = color_map.get(color, "#c9d1d9")

        def _insert():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            start = self.log_box.index("end-2l linestart")
            end   = self.log_box.index("end-1l lineend")
            tag   = f"color_{color}"
            self.log_box.tag_config(tag, foreground=text_color)
            self.log_box.tag_add(tag, start, end)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _insert)

    def _set_btn_state(self, state: str):
        self.after(0, lambda: self.action_btn.configure(state=state))


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = RepoClonerApp()
    app.mainloop()
