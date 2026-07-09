"""TyperApp — the main GUI class. Delegates all typing logic to TypingEngine."""

import os
import sys
import threading
from tkinter import filedialog, Menu

import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledText

from .config import (TRANSLATIONS, SPEED_PROFILES, StatusStyle,
                     platform_mono_font, AI_MODEL, AI_FALLBACK_MODELS, ModelInfo)
from .markers import parse_instructions
from .engine import TypingEngine, TypingCallbacks
from . import ai
from .ai import AIGenerator, AICallbacks
from . import vault
from .vault import BitwardenVault, VaultCallbacks, VaultItem


class TyperApp(ttk.Window):

    def __init__(self, lang: str = "en", initial_file: str | None = None,
                 interval_ms: int = 100, wait_s: float = 2.0) -> None:
        super().__init__(themename="darkly")

        self.lang    = lang
        self._engine = TypingEngine()
        self._ai     = AIGenerator()
        self._vault  = BitwardenVault()
        self._bw_items: list[VaultItem] = []
        # Static fallback until _refresh_ai_models_async() replaces it with the
        # live list from the Models API (see ai.list_models()).
        self._ai_models: list[ModelInfo] = list(AI_FALLBACK_MODELS)

        self.geometry("820x860")
        self.minsize(width=410, height=500)
        self.title("AutoTyper")

        self._build_header()
        self._build_settings(interval_ms, wait_s)
        self._check_wayland()
        self._build_ai_panel()
        self._build_bw_panel()
        self._build_text_area()
        self._build_char_counter()
        self._build_progress()
        self._build_log()
        self._build_status_bar()

        self._update_char_count()
        self._refresh_ai_models_async()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial_file:
            self._load_file_path(initial_file)

    def _on_close(self) -> None:
        """Lock the vault (drop the in-memory session) before closing."""
        if self._vault.is_unlocked:
            self._vault.lock()
        self.destroy()

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

    def _build_ai_panel(self) -> None:
        af = ttk.Labelframe(self, text=self.t("ai_title"), bootstyle="primary")
        af.pack(side="top", fill="x", padx=20, pady=(0, 8))
        af.columnconfigure(0, weight=1)
        self._af = af

        self._lbl_ai = ttk.Label(af, text=self.t("ai_prompt_label"))
        self._lbl_ai.grid(row=0, column=0, columnspan=4,
                          padx=15, pady=(8, 2), sticky="w")

        self._ai_entry = ttk.Entry(af)
        self._ai_entry.grid(row=1, column=0, padx=(15, 5), pady=(0, 4), sticky="ew")
        self._ai_entry.bind("<Return>", lambda _e: self.generate_with_ai())

        self._ai_model_var = ttk.StringVar(value=self._model_display(AI_MODEL))
        self._ai_model_combo = ttk.Combobox(af, textvariable=self._ai_model_var,
                                            values=[m.display_name for m in self._ai_models],
                                            state="readonly", width=12,
                                            bootstyle="secondary")
        self._ai_model_combo.grid(row=1, column=1, padx=5, pady=(0, 4))
        self._ai_model_combo.bind("<<ComboboxSelected>>",
                                  lambda _e: self._update_effort_options())

        self._effort_var = ttk.StringVar(value="")
        self._ai_effort_combo = ttk.Combobox(af, textvariable=self._effort_var,
                                             state="readonly", width=8,
                                             bootstyle="secondary")
        self._ai_effort_combo.grid(row=1, column=2, padx=5, pady=(0, 4))
        self._update_effort_options()

        self._btn_ai = ttk.Button(af, text=self.t("ai_generate_btn"), width=14,
                                  command=self.generate_with_ai, bootstyle="primary")
        self._btn_ai.grid(row=1, column=3, padx=(5, 15), pady=(0, 4), sticky="e")

        self._lbl_ai_hint = ttk.Label(af, text=self.t("ai_hint"),
                                      font=("", 9), bootstyle="secondary")
        self._lbl_ai_hint.grid(row=2, column=0, columnspan=4,
                               padx=15, pady=(0, 8), sticky="w")

    def _build_bw_panel(self) -> None:
        bf = ttk.Labelframe(self, text=self.t("bw_title"), bootstyle="warning")
        bf.pack(side="top", fill="x", padx=20, pady=(0, 8))
        bf.columnconfigure(1, weight=1)
        self._bf = bf

        # Row 0 ── Master password | Unlock | Lock
        self._lbl_bw_pw = ttk.Label(bf, text=self.t("bw_pw_label"))
        self._lbl_bw_pw.grid(row=0, column=0, padx=(15, 5), pady=(8, 4), sticky="w")

        self._bw_pw_entry = ttk.Entry(bf, show="•")
        self._bw_pw_entry.grid(row=0, column=1, padx=5, pady=(8, 4), sticky="ew")
        self._bw_pw_entry.bind("<Return>", lambda _e: self.bw_unlock())

        self._btn_bw_unlock = ttk.Button(bf, text=self.t("bw_unlock_btn"), width=15,
                                         command=self.bw_unlock, bootstyle="warning")
        self._btn_bw_unlock.grid(row=0, column=2, padx=5, pady=(8, 4))

        self._btn_bw_lock = ttk.Button(bf, text=self.t("bw_lock_btn"), width=13,
                                       command=self.bw_lock,
                                       bootstyle="warning-outline", state="disabled")
        self._btn_bw_lock.grid(row=0, column=3, padx=(5, 15), pady=(8, 4))

        # Row 1 ── Search credential | Search
        self._lbl_bw_search = ttk.Label(bf, text=self.t("bw_search_label"))
        self._lbl_bw_search.grid(row=1, column=0, padx=(15, 5), pady=4, sticky="w")

        self._bw_search_entry = ttk.Entry(bf, state="disabled")
        self._bw_search_entry.grid(row=1, column=1, padx=5, pady=4, sticky="ew")
        self._bw_search_entry.bind("<Return>", lambda _e: self.bw_search())

        self._btn_bw_search = ttk.Button(bf, text=self.t("bw_search_btn"), width=15,
                                         command=self.bw_search,
                                         bootstyle="secondary", state="disabled")
        self._btn_bw_search.grid(row=1, column=2, padx=5, pady=4)

        # Row 2 ── Results combobox | Type password
        self._bw_item_var = ttk.StringVar(value="")
        self._bw_item_combo = ttk.Combobox(bf, textvariable=self._bw_item_var,
                                           state="disabled", bootstyle="secondary")
        self._bw_item_combo.grid(row=2, column=0, columnspan=2,
                                 padx=(15, 5), pady=4, sticky="ew")

        self._btn_bw_type = ttk.Button(bf, text=self.t("bw_type_btn"), width=15,
                                       command=self.bw_type_password,
                                       bootstyle="warning", state="disabled")
        self._btn_bw_type.grid(row=2, column=2, columnspan=2,
                               padx=5, pady=4, sticky="e")

        self._lbl_bw_hint = ttk.Label(bf, text=self.t("bw_hint"),
                                      font=("", 9), bootstyle="secondary")
        self._lbl_bw_hint.grid(row=3, column=0, columnspan=4,
                               padx=15, pady=(0, 8), sticky="w")

    # -----------------------------------------------------------------------
    # Bitwarden vault — credentials via the `bw` CLI (see vault.py)
    # -----------------------------------------------------------------------
    def _bw_set_unlocked_ui(self, unlocked: bool) -> None:
        """Toggle the search/type controls that require an unlocked vault."""
        state = "normal" if unlocked else "disabled"
        self._bw_search_entry.configure(state=state)
        self._btn_bw_search.configure(state=state)
        self._btn_bw_lock.configure(state=state)
        self._btn_bw_unlock.configure(state="disabled" if unlocked else "normal")
        self._bw_pw_entry.configure(state="disabled" if unlocked else "normal")
        if unlocked:
            self._bw_pw_entry.delete(0, "end")   # don't keep the master password around
        else:
            self._bw_items = []
            self._bw_item_combo.configure(values=[], state="disabled")
            self._bw_item_var.set("")
            self._btn_bw_type.configure(state="disabled")

    def bw_unlock(self) -> None:
        if self._vault.is_busy or self._engine.is_typing:
            return
        if not vault.is_available():
            self.update_status(self.t("bw_err_lib"), StatusStyle.ERROR)
            return
        password = self._bw_pw_entry.get()
        if not password:
            self.update_status(self.t("bw_err_empty_pw"), StatusStyle.ERROR)
            return

        self._btn_bw_unlock.configure(state="disabled")
        self.update_status(self.t("bw_unlocking"), StatusStyle.WARNING)
        callbacks = VaultCallbacks(
            on_unlocked=lambda: self.after(0, self._bw_on_unlocked),
            on_error=lambda e: self.after(0, lambda e=e: self._bw_on_error(e)),
        )
        self._vault.unlock(password, callbacks)

    def _bw_on_unlocked(self) -> None:
        self._bw_set_unlocked_ui(True)
        self._log_append(self.t("bw_unlocked"))
        self.update_status(self.t("bw_unlocked"), StatusStyle.SUCCESS)

    def bw_lock(self) -> None:
        self._vault.lock()
        self._bw_set_unlocked_ui(False)
        self._log_append(self.t("bw_locked"))
        self.update_status(self.t("bw_locked"), StatusStyle.IDLE)

    def bw_search(self) -> None:
        if self._vault.is_busy:
            return
        if not self._vault.is_unlocked:
            self.update_status(self.t("bw_err_locked"), StatusStyle.ERROR)
            return
        query = self._bw_search_entry.get().strip()
        if not query:
            self.update_status(self.t("bw_err_empty_q"), StatusStyle.ERROR)
            return

        self._btn_bw_search.configure(state="disabled")
        self.update_status(self.t("bw_searching"), StatusStyle.WARNING)
        callbacks = VaultCallbacks(
            on_items=lambda items: self.after(0, lambda i=items: self._bw_on_items(i)),
            on_error=lambda e: self.after(0, lambda e=e: self._bw_on_error(e)),
        )
        self._vault.search(query, callbacks)

    def _bw_item_label(self, item: VaultItem) -> str:
        return f"{item.name} ({item.username})" if item.username else item.name

    def _bw_on_items(self, items: list[VaultItem]) -> None:
        self._btn_bw_search.configure(state="normal")
        self._bw_items = items
        labels = [self._bw_item_label(i) for i in items]
        self._bw_item_combo.configure(values=labels,
                                      state="readonly" if labels else "disabled")
        if labels:
            self._bw_item_var.set(labels[0])
            self._btn_bw_type.configure(state="normal")
            self.update_status(self.t("bw_found", n=len(items)), StatusStyle.SUCCESS)
        else:
            self._bw_item_var.set("")
            self._btn_bw_type.configure(state="disabled")
            self.update_status(self.t("bw_none"), StatusStyle.WARNING)

    def bw_type_password(self) -> None:
        if self._vault.is_busy or self._engine.is_typing:
            return
        idx = self._bw_item_combo.current()
        if idx < 0 or idx >= len(self._bw_items):
            self.update_status(self.t("bw_err_no_sel"), StatusStyle.ERROR)
            return

        self._btn_bw_type.configure(state="disabled")
        self.update_status(self.t("bw_fetching"), StatusStyle.WARNING)
        callbacks = VaultCallbacks(
            on_password=lambda pw: self.after(0, lambda p=pw: self._bw_on_password(p)),
            on_error=lambda e: self.after(0, lambda e=e: self._bw_on_error(e)),
        )
        self._vault.get_password(self._bw_items[idx].id, callbacks)

    def _bw_on_password(self, password: str) -> None:
        """Type the fetched password straight into the focused window — it never
        enters the editor or the log. Honors the configured wait + interval."""
        self._btn_bw_type.configure(state="normal")
        if not password:
            self._bw_on_error(RuntimeError("empty password"))
            return
        try:
            wait_s     = float(self._entry_wait.get())
            interval_s = float(self._entry_interval.get()) / 1000.0
        except ValueError:
            self.update_status(self.t("err_numeric"), StatusStyle.ERROR)
            return

        self.after(0, lambda: self._progress_var.set(0.0))
        self._btn_action.configure(state="normal", text=self.t("stop_btn"),
                                   bootstyle="danger", command=self.request_stop)
        self._btn_pause.configure(state="normal", text=self.t("pause_btn"))
        self._btn_ai.configure(state="disabled")
        self._set_ai_controls_enabled(False)
        self.update_status(self.t("bw_typing_pw"), StatusStyle.WARNING)

        # Deliberately minimal callbacks: the secret must not reach the log, so
        # we don't reuse the char-count log lines here — only progress/reset.
        callbacks = TypingCallbacks(
            on_progress=lambda done, total: self._set_progress(done, total),
            on_waiting=lambda s: self.update_status(
                self.t("status_waiting", s=s), StatusStyle.WARNING),
            on_done=lambda stopped, done, total: self.after(
                0, lambda: self._bw_on_type_done()),
            on_error=lambda e: self.after(0, lambda e=e: self._on_typing_error(e)),
            on_stop_requested=self.request_stop,
        )
        self._engine.start(password, wait_s, interval_s, False, callbacks)

    def _bw_on_type_done(self) -> None:
        self._progress_var.set(100.0)
        self.update_status(self.t("status_done"), StatusStyle.SUCCESS)
        self._reset_ui()

    def _bw_on_error(self, e: Exception) -> None:
        self._btn_bw_unlock.configure(
            state="disabled" if self._vault.is_unlocked else "normal")
        if self._vault.is_unlocked:
            self._btn_bw_search.configure(state="normal")
            if self._bw_items:
                self._btn_bw_type.configure(state="normal")
        if isinstance(e, vault.VaultLoggedOutError):
            self.update_status(self.t("bw_err_login"), StatusStyle.ERROR)
        else:
            self.update_status(self.t("bw_err_api", e=e), StatusStyle.ERROR)
        self._log_append(f"BITWARDEN ERROR: {e}")

    # -----------------------------------------------------------------------
    # AI model list (fetched live from the Models API; see ai.list_models())
    # -----------------------------------------------------------------------
    def _model_display(self, model_id: str) -> str:
        return next((m.display_name for m in self._ai_models if m.id == model_id), model_id)

    def _selected_model_info(self) -> ModelInfo:
        name = self._ai_model_var.get()
        for info in self._ai_models:
            if info.display_name == name:
                return info
        return self._ai_models[0] if self._ai_models else ModelInfo(AI_MODEL, AI_MODEL, False, ())

    def _selected_model(self) -> str:
        return self._selected_model_info().id

    def _selected_effort(self) -> str | None:
        return self._effort_var.get() or None

    def _update_effort_options(self, _event=None) -> None:
        levels = list(self._selected_model_info().effort_levels)
        self._ai_effort_combo.configure(values=levels)
        if levels:
            if self._effort_var.get() not in levels:
                self._effort_var.set("high" if "high" in levels else levels[0])
            self._ai_effort_combo.configure(state="readonly")
        else:
            self._effort_var.set("")
            self._ai_effort_combo.configure(state="disabled")

    def _refresh_ai_models_async(self) -> None:
        """Replace the static fallback with the live model list, in the
        background so a slow/unreachable API can't delay window startup."""
        if not ai.is_available() or not ai.has_credentials():
            return  # nothing to fetch from; keep the fallback list

        def worker() -> None:
            try:
                models = ai.list_models()
            except Exception:
                return  # offline, auth hiccup, etc. — keep the fallback list
            if models:
                self.after(0, lambda: self._apply_fetched_models(models))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_fetched_models(self, models: list[ModelInfo]) -> None:
        current_id = self._selected_model()
        self._ai_models = models
        display_names = [m.display_name for m in models]
        self._ai_model_combo.configure(values=display_names)
        ids = [m.id for m in models]
        self._ai_model_var.set(
            self._model_display(current_id) if current_id in ids else display_names[0])
        self._update_effort_options()

    def _set_ai_controls_enabled(self, enabled: bool) -> None:
        self._ai_model_combo.configure(state="readonly" if enabled else "disabled")
        if enabled:
            self._update_effort_options()   # restores values + enabled state
        else:
            self._ai_effort_combo.configure(state="disabled")

    def _build_text_area(self) -> None:
        tf = ttk.Frame(self)
        tf.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 2))
        self._text_info = ScrolledText(tf, height=8, width=100, font=platform_mono_font())
        self._text_info.pack(fill="both", expand=True)
        self._text_info.text.configure(undo=True)   # Ctrl+Z recovers AI replacement
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
        self._af.configure(text=self.t("ai_title"))
        self._lbl_ai.configure(text=self.t("ai_prompt_label"))
        self._lbl_ai_hint.configure(text=self.t("ai_hint"))
        if not self._ai.is_generating:
            self._btn_ai.configure(text=self.t("ai_generate_btn"))

        self._bf.configure(text=self.t("bw_title"))
        self._lbl_bw_pw.configure(text=self.t("bw_pw_label"))
        self._btn_bw_unlock.configure(text=self.t("bw_unlock_btn"))
        self._btn_bw_lock.configure(text=self.t("bw_lock_btn"))
        self._lbl_bw_search.configure(text=self.t("bw_search_label"))
        self._btn_bw_search.configure(text=self.t("bw_search_btn"))
        self._btn_bw_type.configure(text=self.t("bw_type_btn"))
        self._lbl_bw_hint.configure(text=self.t("bw_hint"))
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
        self._btn_ai.configure(state="disabled")
        self._set_ai_controls_enabled(False)
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

    # -----------------------------------------------------------------------
    # AI generation (Anthropic Claude)
    # -----------------------------------------------------------------------
    def generate_with_ai(self) -> None:
        # --- Read the prompt in the main thread, then hand off to a worker ---
        if self._engine.is_typing or self._ai.is_generating:
            return

        prompt = self._ai_entry.get().strip()
        if not prompt:
            self.update_status(self.t("ai_err_empty"), StatusStyle.ERROR)
            return
        if not ai.is_available():
            self.update_status(self.t("ai_err_lib"), StatusStyle.ERROR)
            return
        if not ai.has_credentials():
            self.update_status(self.t("ai_err_auth"), StatusStyle.ERROR)
            return

        self._btn_ai.configure(state="disabled", text=self.t("ai_generating_btn"))
        self._set_ai_controls_enabled(False)
        self._btn_action.configure(state="disabled")
        self.update_status(self.t("ai_generating"), StatusStyle.WARNING)
        self._ai_streamed = False   # editor is cleared on the first chunk, not before

        callbacks = AICallbacks(
            on_start=lambda: self.after(0, self._ai_on_start),
            on_text=lambda chunk: self.after(0, lambda c=chunk: self._ai_on_text(c)),
            on_done=lambda full: self.after(0, self._ai_on_done),
            on_error=lambda e: self.after(0, lambda e=e: self._ai_on_error(e)),
        )
        info = self._selected_model_info()
        self._ai.generate(prompt, self.lang, info.id, callbacks,
                          supports_adaptive=info.supports_adaptive,
                          effort=self._selected_effort())

    def _ai_on_start(self) -> None:
        self._log_append(self.t("ai_generating"))

    def _ai_on_text(self, chunk: str) -> None:
        if not self._ai_streamed:        # clear only once real output arrives
            self._text_info.delete("1.0", "end")
            self._ai_streamed = True
        self._text_info.insert("end", chunk)
        self._text_info.see("end")

    def _ai_on_done(self) -> None:
        self._update_char_count()
        self._btn_ai.configure(state="normal", text=self.t("ai_generate_btn"))
        self._set_ai_controls_enabled(True)
        self._btn_action.configure(state="normal")
        self._status_label.configure(text=self.t("ai_done"), bootstyle=StatusStyle.SUCCESS)

    def _ai_on_error(self, e: Exception) -> None:
        self._btn_ai.configure(state="normal", text=self.t("ai_generate_btn"))
        self._set_ai_controls_enabled(True)
        self._btn_action.configure(state="normal")
        if ai.is_auth_error(e):
            msg = self.t("ai_err_auth")            # bad/expired credential
        else:
            msg = self.t("ai_err_api", e=e)
        self._status_label.configure(text=msg, bootstyle=StatusStyle.ERROR)
        self._log_append(f"AI ERROR: {e}")

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
        self._btn_ai.configure(state="normal")
        self._set_ai_controls_enabled(True)
