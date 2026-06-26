"""TyperApp — the main GUI class. Delegates all typing logic to TypingEngine."""

import os
import sys
from tkinter import filedialog, Menu

import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledText

from .config import TRANSLATIONS, SPEED_PROFILES, StatusStyle, platform_mono_font
from .markers import parse_instructions
from .engine import TypingEngine, TypingCallbacks


class TyperApp(ttk.Window):

    def __init__(self, lang: str = "en", initial_file: str | None = None,
                 interval_ms: int = 100, wait_s: float = 2.0) -> None:
        super().__init__(themename="darkly")

        self.lang    = lang
        self._engine = TypingEngine()

        self.geometry("820x860")
        self.minsize(width=410, height=500)
        self.title("AutoTyper")

        self._build_header()
        self._build_settings(interval_ms, wait_s)
        self._check_wayland()
        self._build_text_area()
        self._build_char_counter()
        self._build_progress()
        self._build_log()
        self._build_status_bar()

        self._update_char_count()

        if initial_file:
            self._load_file_path(initial_file)

    # -----------------------------------------------------------------------
    # Translation helper
    # -----------------------------------------------------------------------
    def t(self, key: str, **kwargs) -> str:
        text = TRANSLATIONS[self.lang].get(key, f"[{key}]")
        return text.format(**kwargs) if kwargs else text

    # -----------------------------------------------------------------------
    # UI builders
    # -----------------------------------------------------------------------
    def _build_header(self) -> None:
        hf = ttk.Frame(self, bootstyle="dark")
        hf.pack(side="top", fill="x")

        self._lbl_title = ttk.Label(hf, text=self.t("app_title"),
                                    font=("", 22, "bold"), bootstyle="light")
        self._lbl_title.pack(side="left", padx=20, pady=10)

        # Language selector (far right)
        lang_frame = ttk.Frame(hf, bootstyle="dark")
        lang_frame.pack(side="right", padx=(5, 20), pady=10)
        self._lbl_lang = ttk.Label(lang_frame, text=self.t("lang_label"), bootstyle="light")
        self._lbl_lang.pack(side="left", padx=(0, 5))
        self._lang_display = ttk.StringVar(value="English" if self.lang == "en" else "Português")
        lang_combo = ttk.Combobox(lang_frame, textvariable=self._lang_display,
                                  values=["English", "Português"],
                                  state="readonly", width=11, bootstyle="secondary")
        lang_combo.pack(side="left")
        lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        self._btn_save = ttk.Button(hf, text=self.t("save_file"), width=16,
                                    command=self.save_file, bootstyle="secondary-outline")
        self._btn_save.pack(side="right", padx=(5, 5), pady=10)

        self._btn_open = ttk.Button(hf, text=self.t("open_file"), width=16,
                                    command=self.open_file, bootstyle="secondary-outline")
        self._btn_open.pack(side="right", padx=5, pady=10)

    def _build_settings(self, interval_ms: int, wait_s: float) -> None:
        sf = ttk.Labelframe(self, text=self.t("config_title"), bootstyle="info")
        sf.pack(side="top", fill="x", padx=20, pady=(20, 10))
        sf.columnconfigure((0, 1, 2, 3), weight=1)
        self._sf = sf

        # Row 0 ── Speed profile | Interval entry
        self._lbl_profile = ttk.Label(sf, text=self.t("profile_label"))
        self._lbl_profile.grid(row=0, column=0, padx=(15, 5), pady=(10, 5), sticky="w")

        self._profile_var = ttk.StringVar()
        self._profile_combo = ttk.Combobox(sf, textvariable=self._profile_var,
                                           values=self._profile_names(),
                                           state="readonly", width=20, bootstyle="secondary")
        self._profile_combo.grid(row=0, column=1, padx=5, pady=(10, 5), sticky="w")
        self._profile_combo.bind("<<ComboboxSelected>>", self._on_profile_change)

        self._lbl_interval = ttk.Label(sf, text=self.t("interval_label"))
        self._lbl_interval.grid(row=0, column=2, padx=(20, 5), pady=(10, 5), sticky="w")

        self._entry_interval = ttk.Entry(sf, width=8)
        self._entry_interval.grid(row=0, column=3, padx=5, pady=(10, 5), sticky="w")
        self._entry_interval.insert(0, str(interval_ms))
        self._entry_interval.bind("<FocusOut>", self._on_interval_edited)
        self._entry_interval.bind("<Return>",   self._on_interval_edited)
        self._sync_profile_combo(interval_ms)

        # Row 1 ── Wait | Chunk mode
        self._lbl_wait = ttk.Label(sf, text=self.t("wait_label"))
        self._lbl_wait.grid(row=1, column=0, padx=(15, 5), pady=(5, 10), sticky="w")

        self._entry_wait = ttk.Entry(sf, width=8)
        self._entry_wait.grid(row=1, column=1, padx=5, pady=(5, 10), sticky="w")
        self._entry_wait.insert(0, str(wait_s))

        self._chunk_var = ttk.BooleanVar(value=False)
        self._chk_chunk = ttk.Checkbutton(sf, text=self.t("chunk_label"),
                                          variable=self._chunk_var,
                                          bootstyle="info-round-toggle")
        self._chk_chunk.grid(row=1, column=2, columnspan=2,
                              padx=(20, 5), pady=(5, 10), sticky="w")

        # Action + Pause buttons (span both rows, right side)
        btn_frame = ttk.Frame(sf)
        btn_frame.grid(row=0, column=4, rowspan=2, padx=(20, 15), pady=10, sticky="e")

        self._btn_action = ttk.Button(btn_frame, text=self.t("start_btn"), width=22,
                                      command=self.start_typing_thread, bootstyle="success")
        self._btn_action.pack(side="top", pady=(0, 6))

        self._btn_pause = ttk.Button(btn_frame, text=self.t("pause_btn"), width=22,
                                     command=self._toggle_pause,
                                     bootstyle="warning-outline", state="disabled")
        self._btn_pause.pack(side="top")

    def _build_text_area(self) -> None:
        tf = ttk.Frame(self)
        tf.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 2))
        self._text_info = ScrolledText(tf, height=8, width=100, font=platform_mono_font())
        self._text_info.pack(fill="both", expand=True)
        self._text_info.bind("<KeyRelease>", lambda _e: self._update_char_count())

    def _build_char_counter(self) -> None:
        row = ttk.Frame(self)
        row.pack(side="top", fill="x", padx=22, pady=(2, 0))
        self._insert_btn = ttk.Button(row, text=self.t("insert_btn"), width=22,
                                      bootstyle="info-outline",
                                      command=self._show_insert_menu)
        self._insert_btn.pack(side="left")
        self._lbl_marker_hint = ttk.Label(row, text=self.t("marker_hint"),
                                          font=("", 9), bootstyle="secondary")
        self._lbl_marker_hint.pack(side="left", padx=(10, 0))
        self._lbl_chars = ttk.Label(row, text="", font=("", 10), bootstyle=StatusStyle.IDLE)
        self._lbl_chars.pack(side="right")
        self._insert_menu = self._build_insert_menu()

    # -----------------------------------------------------------------------
    # Insert-marker dropdown
    # -----------------------------------------------------------------------
    def _build_insert_menu(self) -> Menu:
        m = Menu(self, tearoff=0)

        # ── Timing ──────────────────────────────────────────────────────────
        timing = Menu(m, tearoff=0)
        for secs in [0.5, 1, 2, 3, 5, 10]:
            timing.add_command(
                label=f"Pause {secs}s",
                command=lambda s=secs: self._insert_marker(f"[[pause:{s}]]"))
        timing.add_separator()
        for ms, label in [(200, "Slow (200 ms)"), (100, "Normal (100 ms)"),
                          (50, "Fast (50 ms)"), (10, "Turbo (10 ms)")]:
            timing.add_command(
                label=f"Speed: {label}",
                command=lambda v=ms: self._insert_marker(f"[[speed:{v}]]"))
        timing.add_command(label="Speed: Reset",
                           command=lambda: self._insert_marker("[[speed:reset]]"))
        m.add_cascade(label="⏱  Timing", menu=timing)

        # ── Function Keys ────────────────────────────────────────────────────
        fn = Menu(m, tearoff=0)
        for i in range(1, 13):
            fn.add_command(label=f"F{i}",
                           command=lambda n=i: self._insert_marker(f"[[key:F{n}]]"))
        m.add_cascade(label="🔑  Function Keys", menu=fn)

        # ── Modifier Keys ────────────────────────────────────────────────────
        mod = Menu(m, tearoff=0)
        for key, lbl in [("ctrl", "Ctrl"), ("alt", "Alt"), ("altgr", "AltGr"),
                         ("shift", "Shift"), ("win", "Win ⊞")]:
            mod.add_command(label=lbl,
                            command=lambda k=key: self._insert_marker(f"[[key:{k}]]"))
        m.add_cascade(label="⌨  Modifier Keys", menu=mod)

        # ── Key Combos ───────────────────────────────────────────────────────
        combo = Menu(m, tearoff=0)
        for key, lbl in [
            ("ctrl+c",       "Ctrl+C"),
            ("ctrl+v",       "Ctrl+V"),
            ("ctrl+x",       "Ctrl+X"),
            ("ctrl+z",       "Ctrl+Z"),
            ("ctrl+y",       "Ctrl+Y"),
            ("ctrl+a",       "Ctrl+A"),
            ("ctrl+s",       "Ctrl+S"),
            ("ctrl+alt+del", "Ctrl+Alt+Del"),
            ("alt+f4",       "Alt+F4"),
            ("alt+tab",      "Alt+Tab"),
            ("shift+tab",    "Shift+Tab"),
            ("ctrl+shift+esc", "Ctrl+Shift+Esc"),
        ]:
            combo.add_command(label=lbl,
                              command=lambda k=key: self._insert_marker(f"[[key:{k}]]"))
        m.add_cascade(label="🗜  Key Combos", menu=combo)

        # ── Navigation & Editing ─────────────────────────────────────────────
        nav = Menu(m, tearoff=0)
        for key, lbl in [
            ("esc",         "Esc"),
            ("tab",         "Tab"),
            ("enter",       "Enter"),
            ("backspace",   "Backspace"),
            ("delete",      "Delete"),
            ("insert",      "Insert"),
            ("space",       "Space"),
            ("home",        "Home"),
            ("end",         "End"),
            ("pageup",      "Page Up"),
            ("pagedown",    "Page Down"),
            ("up",          "↑ Up"),
            ("down",        "↓ Down"),
            ("left",        "← Left"),
            ("right",       "→ Right"),
            ("printscreen", "Print Screen"),
            ("capslock",    "Caps Lock"),
            ("numlock",     "Num Lock"),
            ("scrolllock",  "Scroll Lock"),
            ("pause_break", "Pause / Break"),
        ]:
            nav.add_command(label=lbl,
                            command=lambda k=key: self._insert_marker(f"[[key:{k}]]"))
        m.add_cascade(label="🧭  Navigation & Editing", menu=nav)

        return m

    def _show_insert_menu(self) -> None:
        btn = self._insert_btn
        self._insert_menu.post(btn.winfo_rootx(),
                               btn.winfo_rooty() + btn.winfo_height())

    def _insert_marker(self, marker: str) -> None:
        try:
            self._text_info.insert("insert", marker)
        except Exception:
            self._text_info.insert("end", marker)
        self._update_char_count()

    def _build_progress(self) -> None:
        self._progress_var = ttk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(self, variable=self._progress_var,
                                             maximum=100, bootstyle="success-striped")
        self._progress_bar.pack(side="top", fill="x", padx=20, pady=(4, 0))

    def _build_log(self) -> None:
        self._log_frame = ttk.Labelframe(self, text=self.t("log_title"), bootstyle="secondary")
        self._log_frame.pack(side="top", fill="x", padx=20, pady=(6, 2))
        self._log_text = ScrolledText(self._log_frame, height=4, width=100,
                                      font=platform_mono_font(10))
        self._log_text.pack(fill="x", padx=5, pady=5)
        self._log_text.text.configure(state="disabled")

    def _build_status_bar(self) -> None:
        sb = ttk.Frame(self)
        sb.pack(side="bottom", fill="x", padx=20, pady=(0, 5))
        self._status_label = ttk.Label(sb, text=self.t("status_ready"),
                                       font=("", 12, "italic"), bootstyle=StatusStyle.IDLE)
        self._status_label.pack(side="left")

    # -----------------------------------------------------------------------
    # Linux / Wayland
    # -----------------------------------------------------------------------
    def _check_wayland(self) -> None:
        if sys.platform == "linux" and os.environ.get("XDG_SESSION_TYPE") == "wayland":
            wf = ttk.Frame(self, bootstyle="warning")
            wf.pack(fill="x", padx=20, pady=(5, 0), before=self._sf)
            wf.columnconfigure(0, weight=1)
            self._warning_frame = wf
            ttk.Label(wf, text=self.t("warn_wayland"),
                      bootstyle="inverse-warning", justify="left") \
                .grid(row=0, column=0, padx=(10, 5), pady=5, sticky="ew")
            ttk.Button(wf, text="✕", bootstyle="light-outline",
                       command=self._close_warning, width=2, padding=1) \
                .grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ne")

    def _close_warning(self) -> None:
        if hasattr(self, "_warning_frame") and self._warning_frame.winfo_exists():
            self._warning_frame.destroy()

    # -----------------------------------------------------------------------
    # Language switching
    # -----------------------------------------------------------------------
    def _on_language_change(self, _event=None) -> None:
        new_lang = "en" if self._lang_display.get() == "English" else "pt"
        if new_lang == self.lang:
            return
        self.lang = new_lang
        self._refresh_ui_text()

    def _refresh_ui_text(self) -> None:
        try:
            current_ms = int(self._entry_interval.get())
        except ValueError:
            current_ms = 100

        self._lbl_title.configure(text=self.t("app_title"))
        self._lbl_lang.configure(text=self.t("lang_label"))
        self._btn_open.configure(text=self.t("open_file"))
        self._btn_save.configure(text=self.t("save_file"))
        self._sf.configure(text=self.t("config_title"))
        self._lbl_profile.configure(text=self.t("profile_label"))
        self._lbl_interval.configure(text=self.t("interval_label"))
        self._lbl_wait.configure(text=self.t("wait_label"))
        self._chk_chunk.configure(text=self.t("chunk_label"))
        self._insert_btn.configure(text=self.t("insert_btn"))
        self._lbl_marker_hint.configure(text=self.t("marker_hint"))
        self._log_frame.configure(text=self.t("log_title"))
        self._status_label.configure(text=self.t("status_ready"))

        self._profile_combo.configure(values=self._profile_names())
        self._sync_profile_combo(current_ms)

        if not self._engine.is_typing:
            self._btn_action.configure(text=self.t("start_btn"))
            self._btn_pause.configure(text=self.t("pause_btn"))

        self._update_char_count()

    # -----------------------------------------------------------------------
    # Speed profiles
    # -----------------------------------------------------------------------
    def _profile_names(self) -> list[str]:
        return [self.t(key) for _, key in SPEED_PROFILES]

    def _sync_profile_combo(self, current_ms: int) -> None:
        names = self._profile_names()
        for i, (ms, _) in enumerate(SPEED_PROFILES):
            if ms == current_ms:
                self._profile_var.set(names[i])
                return
        self._profile_var.set(names[-1])   # Custom

    def _on_profile_change(self, _event=None) -> None:
        idx = self._profile_combo.current()
        ms, _ = SPEED_PROFILES[idx]
        if ms is not None:
            self._entry_interval.delete(0, "end")
            self._entry_interval.insert(0, str(ms))

    def _on_interval_edited(self, _event=None) -> None:
        try:
            self._sync_profile_combo(int(self._entry_interval.get()))
        except ValueError:
            pass

    # -----------------------------------------------------------------------
    # Status, progress, log helpers (all thread-safe via after())
    # -----------------------------------------------------------------------
    def update_status(self, text: str, style: str = StatusStyle.IDLE) -> None:
        self.after(0, lambda: self._status_label.configure(text=text, bootstyle=style))

    def _set_progress(self, done: int, total: int) -> None:
        pct = (done / total * 100) if total > 0 else 0.0
        txt = self.t("status_typing", done=done, total=total)
        self.after(0, lambda: self._progress_var.set(pct))
        self.after(0, lambda: self._status_label.configure(text=txt,
                                                           bootstyle=StatusStyle.SUCCESS))

    def _update_char_count(self) -> None:
        try:
            text = self._text_info.get("1.0", "end-1c")
            total = sum(1 for op, _ in parse_instructions(text) if op == 'char')
        except Exception:
            total = 0
        self._lbl_chars.configure(text=self.t("chars_count", total=total))

    def _log_append(self, message: str) -> None:
        self._log_text.text.configure(state="normal")
        self._log_text.text.insert("end", message + "\n")
        self._log_text.text.see("end")
        self._log_text.text.configure(state="disabled")

    # -----------------------------------------------------------------------
    # File operations
    # -----------------------------------------------------------------------
    def open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select a file",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if path:
            self._load_file_path(path)

    def _load_file_path(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            self._text_info.delete("1.0", "end")
            self._text_info.insert("1.0", content)
            self._update_char_count()
            self.update_status(self.t("file_loaded", name=os.path.basename(path)),
                               StatusStyle.SUCCESS)
        except Exception as e:
            self.update_status(self.t("err_load", e=e), StatusStyle.ERROR)

    def save_file(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save file as",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            defaultextension=".txt")
        if path:
            try:
                content = self._text_info.get("1.0", "end-1c")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.update_status(self.t("file_saved"), StatusStyle.SUCCESS)
            except Exception as e:
                self.update_status(self.t("err_save", e=e), StatusStyle.ERROR)

    # -----------------------------------------------------------------------
    # Typing control
    # -----------------------------------------------------------------------
    def request_stop(self) -> None:
        if self._engine.is_typing:
            self._engine.stop()
            self.after(0, lambda: self._btn_action.configure(state="disabled"))
            self.update_status(self.t("status_stopped"), StatusStyle.WARNING)

    def _toggle_pause(self) -> None:
        now_paused = self._engine.toggle_pause()
        if now_paused:
            self.after(0, lambda: self._btn_pause.configure(text=self.t("resume_btn")))
            self.update_status(self.t("status_paused"), StatusStyle.WARNING)
        else:
            self.after(0, lambda: self._btn_pause.configure(text=self.t("pause_btn")))

    def start_typing_thread(self) -> None:
        # --- All widget reads happen here, in the main thread (thread-safe) ---
        text = self._text_info.get("1.0", "end-1c")
        if not text:
            self.update_status(self.t("err_empty"), StatusStyle.ERROR)
            return

        try:
            wait_s     = float(self._entry_wait.get())
            interval_s = float(self._entry_interval.get()) / 1000.0
        except ValueError:
            self.update_status(self.t("err_numeric"), StatusStyle.ERROR)
            return

        chunk_mode = self._chunk_var.get()

        self.after(0, lambda: self._progress_var.set(0.0))
        self._btn_action.configure(state="normal", text=self.t("stop_btn"),
                                   bootstyle="danger", command=self.request_stop)
        self._btn_pause.configure(state="normal", text=self.t("pause_btn"))
        self.update_status(self.t("status_start"), StatusStyle.WARNING)

        # Build callbacks — all called from worker thread, so wrap with after(0,...)
        callbacks = TypingCallbacks(
            on_session_start=lambda dt, total: self.after(
                0, lambda: self._log_append(self.t("log_start", dt=dt, total=total))),
            on_progress=lambda done, total: self._set_progress(done, total),
            on_waiting=lambda s: self.update_status(
                self.t("status_waiting", s=s), StatusStyle.WARNING),
            on_chunk_done=lambda cur, total: self.after(
                0, lambda cur=cur, total=total: self._on_chunk_done(cur, total)),
            on_done=lambda stopped, done, total: self.after(
                0, lambda stopped=stopped, done=done, total=total:
                    self._on_typing_done(stopped, done, total)),
            on_error=lambda e: self.after(
                0, lambda e=e: self._on_typing_error(e)),
            on_stop_requested=self.request_stop,
        )

        self._engine.start(text, wait_s, interval_s, chunk_mode, callbacks)

    def _on_chunk_done(self, cur: int, total: int) -> None:
        status = self.t("status_chunk", cur=cur, total=total)
        self._log_append(status)
        self._status_label.configure(text=status, bootstyle=StatusStyle.WARNING)
        self._progress_var.set((cur / total * 100) if total > 0 else 0.0)

    def _on_typing_error(self, e: Exception) -> None:
        self._status_label.configure(text=self.t("err_typing", e=e), bootstyle=StatusStyle.ERROR)
        self._log_append(f"ERROR: {e}")

    def _on_typing_done(self, stopped: bool, done: int, total: int) -> None:
        if stopped:
            self._log_append(self.t("log_stopped", chars=done, total=total))
            self._status_label.configure(text=self.t("status_stopped"),
                                         bootstyle=StatusStyle.WARNING)
        else:
            self._log_append(self.t("log_done", chars=done, total=total))
            self._status_label.configure(text=self.t("status_done"),
                                         bootstyle=StatusStyle.SUCCESS)
            self._progress_var.set(100.0)
        self._reset_ui()

    def _reset_ui(self) -> None:
        self._btn_action.configure(state="normal", text=self.t("start_btn"),
                                   bootstyle="success", command=self.start_typing_thread)
        self._btn_pause.configure(state="disabled", text=self.t("pause_btn"))
