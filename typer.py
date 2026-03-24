"""
AutoTyper — simulates keyboard typing of any text into any active window.
Usage: python typer.py [--file FILE] [--interval MS] [--wait S] [--lang en|pt] [--headless]
"""

import argparse
import datetime
import os
import platform
import sys
import threading
import time
from tkinter import filedialog

import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText
from pynput.keyboard import Controller, Key, Listener

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        # Header
        "app_title":      "⚡ AutoTyper",
        "open_file":      "📂 Open File",
        "save_file":      "💾 Save File",
        "lang_label":     "Language:",
        # Settings
        "config_title":   " ⚙️ Configuration ",
        "profile_label":  "Speed profile:",
        "interval_label": "Type interval (ms):",
        "wait_label":     "Wait (s) before typing:",
        "chunk_label":    "Line-by-line mode (press ENTER to advance)",
        "start_btn":      "🚀 START TYPING",
        "stop_btn":       "🛑 STOP",
        "pause_btn":      "⏸ PAUSE",
        "resume_btn":     "▶ RESUME",
        # Wayland warning
        "warn_wayland": (
            "⚠️  Warning: Wayland session detected. Keystroke simulation may not work.\n"
            "Please log out and start a session using 'X11' or 'X.Org'."
        ),
        # Log section
        "log_title":      " 📋 Session Log ",
        # Status messages
        "status_ready":   "Ready.",
        "status_start":   "Starting auto-typer...",
        "status_waiting": "Waiting {s}s before typing...",
        "status_typing":  "Typing… {done}/{total} chars",
        "status_paused":  "Paused.",
        "status_stopped": "Stopped by user.",
        "status_done":    "Typing finished successfully!",
        "status_chunk":   "Line {cur}/{total} typed — press ENTER to continue or ESC to stop.",
        # File status
        "file_loaded":    "File loaded: {name}",
        "file_saved":     "File saved.",
        # Errors
        "err_numeric":    "Error: time values must be numeric.",
        "err_empty":      "Error: no text to type.",
        "err_load":       "Error loading file: {e}",
        "err_save":       "Error saving file: {e}",
        "err_typing":     "Error during typing: {e}",
        # Log entries
        "log_start":      "=== Session started {dt} | {total} chars ===",
        "log_done":       "=== Done: {chars}/{total} chars typed ===",
        "log_stopped":    "=== Stopped: {chars}/{total} chars typed ===",
        # Char counter
        "chars_count":    "{total} chars",
        # Speed profiles
        "prof_slow":      "Slow  (200 ms)",
        "prof_normal":    "Normal (100 ms)",
        "prof_fast":      "Fast   (50 ms)",
        "prof_turbo":     "Turbo  (10 ms)",
        "prof_custom":    "Custom",
    },
    "pt": {
        # Cabeçalho
        "app_title":      "⚡ AutoTyper",
        "open_file":      "📂 Abrir Arquivo",
        "save_file":      "💾 Salvar Arquivo",
        "lang_label":     "Idioma:",
        # Configurações
        "config_title":   " ⚙️ Configurações ",
        "profile_label":  "Perfil de velocidade:",
        "interval_label": "Intervalo entre teclas (ms):",
        "wait_label":     "Aguardar (s) antes de digitar:",
        "chunk_label":    "Modo por linha (pressione ENTER para avançar)",
        "start_btn":      "🚀 INICIAR DIGITAÇÃO",
        "stop_btn":       "🛑 PARAR",
        "pause_btn":      "⏸ PAUSAR",
        "resume_btn":     "▶ RETOMAR",
        # Aviso Wayland
        "warn_wayland": (
            "⚠️  Aviso: sessão Wayland detectada. A simulação de teclas pode não funcionar.\n"
            "Encerre a sessão e inicie uma nova usando 'X11' ou 'X.Org'."
        ),
        # Log
        "log_title":      " 📋 Log de Sessão ",
        # Status
        "status_ready":   "Pronto.",
        "status_start":   "Iniciando...",
        "status_waiting": "Aguardando {s}s...",
        "status_typing":  "Digitando… {done}/{total} caracteres",
        "status_paused":  "Pausado.",
        "status_stopped": "Parado pelo usuário.",
        "status_done":    "Digitação concluída!",
        "status_chunk":   "Linha {cur}/{total} digitada — pressione ENTER para continuar ou ESC para parar.",
        # Arquivo
        "file_loaded":    "Arquivo carregado: {name}",
        "file_saved":     "Arquivo salvo.",
        # Erros
        "err_numeric":    "Erro: os valores de tempo devem ser numéricos.",
        "err_empty":      "Erro: nenhum texto para digitar.",
        "err_load":       "Erro ao carregar arquivo: {e}",
        "err_save":       "Erro ao salvar arquivo: {e}",
        "err_typing":     "Erro durante a digitação: {e}",
        # Log
        "log_start":      "=== Sessão iniciada {dt} | {total} caracteres ===",
        "log_done":       "=== Concluído: {chars}/{total} caracteres digitados ===",
        "log_stopped":    "=== Interrompido: {chars}/{total} caracteres digitados ===",
        # Contador
        "chars_count":    "{total} caracteres",
        # Perfis de velocidade
        "prof_slow":      "Lento   (200 ms)",
        "prof_normal":    "Normal  (100 ms)",
        "prof_fast":      "Rápido   (50 ms)",
        "prof_turbo":     "Turbo    (10 ms)",
        "prof_custom":    "Personalizado",
    },
}

# ms value (None = user-editable) paired with its translation key
SPEED_PROFILES: list[tuple[int | None, str]] = [
    (200,  "prof_slow"),
    (100,  "prof_normal"),
    (50,   "prof_fast"),
    (10,   "prof_turbo"),
    (None, "prof_custom"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class StatusStyle:
    IDLE    = "secondary"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR   = "danger"


def platform_mono_font(size: int = 13) -> tuple[str, int]:
    fonts = {"Windows": "Consolas", "Darwin": "Menlo"}
    return (fonts.get(platform.system(), "Monospace"), size)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class TyperApp(ttk.Window):

    def __init__(self, lang: str = "en", initial_file: str | None = None,
                 interval_ms: int = 100, wait_s: float = 2.0) -> None:
        super().__init__(themename="darkly")

        self.lang = lang
        self.keyboard      = Controller()
        self._stop_event   = threading.Event()
        self._pause_event  = threading.Event()
        self._pause_event.set()                # set = running; clear = paused
        self._typing_active = False

        self.geometry("820x860")
        self.minsize(width=820, height=860)
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
        self._text_info = ScrolledText(tf, height=14, width=100, font=platform_mono_font())
        self._text_info.pack(fill="both", expand=True)
        self._text_info.bind("<KeyRelease>", lambda _e: self._update_char_count())

    def _build_char_counter(self) -> None:
        self._lbl_chars = ttk.Label(self, text="", font=("", 10), bootstyle=StatusStyle.IDLE)
        self._lbl_chars.pack(side="top", anchor="e", padx=22)

    def _build_progress(self) -> None:
        self._progress_var = ttk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(self, variable=self._progress_var,
                                             maximum=100, bootstyle="success-striped")
        self._progress_bar.pack(side="top", fill="x", padx=20, pady=(4, 0))

    def _build_log(self) -> None:
        self._log_frame = ttk.Labelframe(self, text=self.t("log_title"), bootstyle="secondary")
        self._log_frame.pack(side="top", fill="x", padx=20, pady=(6, 2))
        self._log_text = ScrolledText(self._log_frame, height=4, width=100,
                                      font=platform_mono_font(10), state="disabled")
        self._log_text.pack(fill="x", padx=5, pady=5)

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
        self._log_frame.configure(text=self.t("log_title"))
        self._status_label.configure(text=self.t("status_ready"))

        self._profile_combo.configure(values=self._profile_names())
        self._sync_profile_combo(current_ms)

        if not self._typing_active:
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
            total = len(self._text_info.get("1.0", "end-1c"))
        except Exception:
            total = 0
        self._lbl_chars.configure(text=self.t("chars_count", total=total))

    def _log(self, message: str) -> None:
        def _append():
            self._log_text.configure(state="normal")
            self._log_text.insert("end", message + "\n")
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        self.after(0, _append)

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
        if not self._stop_event.is_set():
            self._stop_event.set()
            self._pause_event.set()    # unblock pause so the thread can exit
            self.after(0, lambda: self._btn_action.configure(state="disabled"))
            self.update_status(self.t("status_stopped"), StatusStyle.WARNING)

    def _toggle_pause(self) -> None:
        if self._pause_event.is_set():           # running → pause
            self._pause_event.clear()
            self.after(0, lambda: self._btn_pause.configure(text=self.t("resume_btn")))
            self.update_status(self.t("status_paused"), StatusStyle.WARNING)
        else:                                    # paused → resume
            self._pause_event.set()
            self.after(0, lambda: self._btn_pause.configure(text=self.t("pause_btn")))

    def start_typing_thread(self) -> None:
        # --- All widget reads happen here, in the main thread (thread-safe) ---
        text = self._text_info.get("1.0", "end-1c")
        if not text:
            self.update_status(self.t("err_empty"), StatusStyle.ERROR)
            return

        try:
            wait_s      = float(self._entry_wait.get())
            interval_ms = float(self._entry_interval.get()) / 1000.0
        except ValueError:
            self.update_status(self.t("err_numeric"), StatusStyle.ERROR)
            return

        chunk_mode = self._chunk_var.get()

        # Reset state
        self._stop_event.clear()
        self._pause_event.set()
        self._typing_active = True
        self.after(0, lambda: self._progress_var.set(0.0))

        self._btn_action.configure(state="normal", text=self.t("stop_btn"),
                                   bootstyle="danger", command=self.request_stop)
        self._btn_pause.configure(state="normal", text=self.t("pause_btn"))
        self.update_status(self.t("status_start"), StatusStyle.WARNING)

        threading.Thread(target=self._type_text,
                         args=(text, wait_s, interval_ms, chunk_mode),
                         daemon=True).start()

    # -----------------------------------------------------------------------
    # Worker thread helpers
    # -----------------------------------------------------------------------
    def _wait_if_paused(self) -> bool:
        """Block while paused. Return False immediately if stop is requested."""
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(0.05)
        return not self._stop_event.is_set()

    def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep in small chunks, honouring stop and pause. Returns False if stopped."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop_event.is_set():
                return False
            if not self._pause_event.is_set():
                # Paused — spin without consuming the sleep budget
                time.sleep(0.05)
                continue
            remaining = end - time.monotonic()
            time.sleep(min(0.02, max(0.0, remaining)))
        return not self._stop_event.is_set()

    # -----------------------------------------------------------------------
    # Typing thread
    # -----------------------------------------------------------------------
    def _type_text(self, text: str, wait_s: float,
                   interval_ms: float, chunk_mode: bool) -> None:
        total      = len(text)
        chars_done = 0

        def on_esc(key):
            if key == Key.esc:
                self.request_stop()
                return False

        listener = Listener(on_press=on_esc)
        listener.start()

        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log(self.t("log_start", dt=dt, total=total))

        try:
            self.update_status(self.t("status_waiting", s=wait_s), StatusStyle.WARNING)
            if not self._interruptible_sleep(wait_s):
                return

            if chunk_mode:
                chars_done = self._type_by_chunks(text, interval_ms)
            else:
                chars_done = self._type_all(text, interval_ms, total)

        except Exception as e:
            self.update_status(self.t("err_typing", e=e), StatusStyle.ERROR)
            self._log(f"ERROR: {e}")

        finally:
            listener.stop()
            self._typing_active = False
            stopped = self._stop_event.is_set()

            if stopped:
                self._log(self.t("log_stopped", chars=chars_done, total=total))
                self.update_status(self.t("status_stopped"), StatusStyle.WARNING)
            else:
                self._log(self.t("log_done", chars=chars_done, total=total))
                self.update_status(self.t("status_done"), StatusStyle.SUCCESS)
                self.after(0, lambda: self._progress_var.set(100.0))

            self.after(0, self._reset_ui)

    def _type_all(self, text: str, interval_ms: float, total: int) -> int:
        """Type every character. Returns the number of characters typed."""
        chars_done   = 0
        update_every = max(5, total // 200)   # at most ~200 progress updates

        for char in text:
            if not self._wait_if_paused():
                break
            if char == "\n":
                self.keyboard.tap(Key.enter)
            else:
                self.keyboard.type(char)
            chars_done += 1
            if chars_done % update_every == 0 or chars_done == total:
                self._set_progress(chars_done, total)
            if not self._interruptible_sleep(interval_ms):
                break

        return chars_done

    def _type_by_chunks(self, text: str, interval_ms: float) -> int:
        """Type one line at a time, waiting for ENTER between lines."""
        lines       = text.split("\n")
        total_lines = len(lines)
        chars_done  = 0

        for i, line in enumerate(lines, start=1):
            # Type the line character by character
            for char in line:
                if not self._wait_if_paused():
                    return chars_done
                self.keyboard.type(char)
                chars_done += 1
                if not self._interruptible_sleep(interval_ms):
                    return chars_done

            if self._stop_event.is_set():
                break

            self.update_status(
                self.t("status_chunk", cur=i, total=total_lines), StatusStyle.WARNING)
            self._log(self.t("status_chunk", cur=i, total=total_lines))
            self._set_progress(i, total_lines)

            if i < total_lines:
                if not self._wait_for_enter_or_esc():
                    break
                self.keyboard.tap(Key.enter)
                chars_done += 1

        return chars_done

    def _wait_for_enter_or_esc(self) -> bool:
        """Block until ENTER (True) or ESC (False) is pressed."""
        proceed = threading.Event()
        result  = [True]

        def on_key(key):
            if key == Key.enter:
                result[0] = True
                proceed.set()
                return False
            if key == Key.esc:
                result[0] = False
                self.request_stop()
                proceed.set()
                return False

        with Listener(on_press=on_key):
            proceed.wait()

        return result[0]

    def _reset_ui(self) -> None:
        self._btn_action.configure(state="normal", text=self.t("start_btn"),
                                   bootstyle="success", command=self.start_typing_thread)
        self._btn_pause.configure(state="disabled", text=self.t("pause_btn"))


# ---------------------------------------------------------------------------
# Headless (CLI) mode
# ---------------------------------------------------------------------------
def run_headless(file_path: str, interval_ms: float, wait_s: float) -> None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    print(f"AutoTyper headless | {len(text)} chars | {interval_ms} ms interval")
    print(f"Waiting {wait_s}s — switch to the target window now…")
    time.sleep(wait_s)
    print("Typing… (press Ctrl+C or ESC to stop)")

    keyboard = Controller()
    stop     = threading.Event()

    def on_esc(key):
        if key == Key.esc:
            stop.set()
            return False

    chars_done = 0
    with Listener(on_press=on_esc):
        try:
            for char in text:
                if stop.is_set():
                    break
                if char == "\n":
                    keyboard.tap(Key.enter)
                else:
                    keyboard.type(char)
                chars_done += 1
                time.sleep(interval_ms / 1000.0)
        except KeyboardInterrupt:
            stop.set()

    print(f"\nDone. {chars_done}/{len(text)} characters typed.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="typer",
        description="AutoTyper — simulates keyboard typing of any text.")
    parser.add_argument("--file",     "-f", metavar="FILE",
                        help="Text file to load on startup.")
    parser.add_argument("--interval", "-i", type=float, default=100.0, metavar="MS",
                        help="Typing interval in milliseconds (default: 100).")
    parser.add_argument("--wait",     "-w", type=float, default=2.0,   metavar="S",
                        help="Seconds to wait before typing (default: 2).")
    parser.add_argument("--lang",     "-l", choices=["en", "pt"], default="en",
                        help="Interface language: en or pt (default: en).")
    parser.add_argument("--headless", action="store_true",
                        help="Run without GUI. Requires --file.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    if args.headless:
        if not args.file:
            print("Error: --headless requires --file.")
            sys.exit(1)
        run_headless(args.file, args.interval, args.wait)
    else:
        app = TyperApp(
            lang=args.lang,
            initial_file=args.file,
            interval_ms=int(args.interval),
            wait_s=args.wait,
        )
        app.mainloop()
