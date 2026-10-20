"""TyperApp — the main GUI class. Delegates all typing logic to TypingEngine."""

import os
import sys
import threading
from math import ceil, sqrt
from tkinter import TclError, filedialog, Menu

import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledText

from .config import (TRANSLATIONS, SPEED_PROFILES, StatusStyle,
                     platform_mono_font, ModelInfo,
                     is_safe_ai_output, normalize_ai_output)
from .markers import parse_instructions
from .engine import TypingEngine, TypingCallbacks
from .drivers import normalize_evdev_layout
from . import ai
from .ai import AIGenerator, AICallbacks
from . import vault
from .vault import (BitwardenVault, VaultCallbacks, VaultItem, is_current_vault_epoch,
                    is_missing_totp_error)


class CollapsibleFrame(ttk.Frame):
    """A section with a clickable header that shows/hides its body.

    Children go into ``self.body`` (a plain frame). Use ``set_title()`` to
    update the header text (for i18n). Starts collapsed unless ``expanded``.
    """

    def __init__(self, master, text: str = "", bootstyle: str = "secondary",
                 expanded: bool = False) -> None:
        super().__init__(master)
        self._text = text
        self._expanded = expanded
        self._header = ttk.Button(self, command=self.toggle,
                                  bootstyle=f"{bootstyle}-link", padding=(4, 3))
        self._header.pack(fill="x")
        self.body = ttk.Frame(self)
        self._render_header()
        if expanded:
            self.body.pack(fill="both", expand=True)

    def _render_header(self) -> None:
        arrow = "▾" if self._expanded else "▸"
        self._header.configure(text=f"{arrow}  {self._text}")

    def set_title(self, text: str) -> None:
        self._text = text
        self._render_header()

    def toggle(self) -> None:
        self._expanded = not self._expanded
        self._render_header()
        if self._expanded:
            self.body.pack(fill="both", expand=True)
        else:
            self.body.pack_forget()


class TyperApp(ttk.Window):

    _MAX_TEXT_AREAS = 6

    def __init__(self, lang: str = "en", initial_file: str | None = None,
                 interval_ms: int = 100, wait_s: float = 2.0,
                 keyboard_layout: str = "us") -> None:
        super().__init__(themename="darkly")

        self.lang    = lang
        self._typing_error = False
        # Store the canonical name so the GUI reflects CLI aliases such as
        # ``--keyboard-layout pt-br`` as the ABNT2 option.
        self._keyboard_layout = normalize_evdev_layout(keyboard_layout)
        self._engine = TypingEngine(keyboard_layout=self._keyboard_layout)
        self._ai     = AIGenerator()
        self._vault  = BitwardenVault()
        self._bw_items: list[VaultItem] = []
        self._bw_epoch = 0
        self._ai_models: list[ModelInfo] = []
        self._ai_selected_model_id: str | None = None
        self._ai_preview = ""
        self._ai_generation_id = 0
        self._ai_cancelling = False
        self._ai_provider_statuses = {}
        self._ai_provider_probe_ids = {}
        self._ai_pending_generate = None

        self.geometry("820x660")
        self.minsize(width=410, height=460)
        self.title("AutoTyper")

        self._build_header()
        self._build_settings(interval_ms, wait_s)
        self._check_wayland()
        self._build_ai_panel()
        self._build_bw_panel()
        # Bottom cluster — docked to the bottom and packed BEFORE the expanding
        # text area, so they keep a fixed height and are never clipped when the
        # window is resized smaller. The text area is the sole widget that
        # absorbs resizing (status is packed first, so it's the last to yield).
        self._build_status_bar()
        self._build_log()
        self._build_progress()
        self._build_char_counter()
        self._build_text_area()

        self._update_char_count()
        self._refresh_ai_models_async()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        if initial_file:
            self._load_file_path(initial_file)

    def _on_close(self) -> None:
        """Lock the vault and release engine driver before closing."""
        if self._ai.is_generating:
            self._ai.cancel()
        if self._vault.is_unlocked:
            self._vault.lock()
        self._engine.close()
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
                                    font=("", 18, "bold"), bootstyle="light")
        self._lbl_title.pack(side="left", padx=20, pady=6)

        # Language selector (far right)
        lang_frame = ttk.Frame(hf, bootstyle="dark")
        lang_frame.pack(side="right", padx=(5, 20), pady=6)
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
        self._btn_save.pack(side="right", padx=(5, 5), pady=6)

        self._btn_open = ttk.Button(hf, text=self.t("open_file"), width=16,
                                    command=self.open_file, bootstyle="secondary-outline")
        self._btn_open.pack(side="right", padx=5, pady=6)

    def _build_settings(self, interval_ms: int, wait_s: float) -> None:
        sf = ttk.Labelframe(self, text=self.t("config_title"), bootstyle="info")
        sf.pack(side="top", fill="x", padx=20, pady=(8, 6))
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
        self._entry_wait.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        self._entry_wait.insert(0, str(wait_s))

        self._chunk_var = ttk.BooleanVar(value=False)
        self._chk_chunk = ttk.Checkbutton(sf, text=self.t("chunk_label"),
                                          variable=self._chunk_var,
                                          bootstyle="info-round-toggle")
        self._chk_chunk.grid(row=1, column=2, columnspan=2,
                              padx=(20, 5), pady=5, sticky="w")

        # Row 2 ── Virtual keyboard layout.  This is mainly relevant to the
        # native Wayland/evdev driver, but remains visible on every platform
        # so a command-line layout choice is reflected in the GUI.
        self._lbl_keyboard_layout = ttk.Label(sf, text=self.t("keyboard_layout_label"))
        self._lbl_keyboard_layout.grid(row=2, column=0, padx=(15, 5), pady=(5, 10), sticky="w")
        self._keyboard_layout_var = ttk.StringVar(value=self._keyboard_layout_display())
        self._keyboard_layout_combo = ttk.Combobox(
            sf, textvariable=self._keyboard_layout_var,
            values=self._keyboard_layout_names(), state="readonly", width=20,
            bootstyle="secondary")
        self._keyboard_layout_combo.grid(row=2, column=1, padx=5, pady=(5, 10), sticky="w")
        self._keyboard_layout_combo.bind("<<ComboboxSelected>>", self._on_keyboard_layout_change)

        # Action + Pause buttons (span all settings rows, right side)
        btn_frame = ttk.Frame(sf)
        btn_frame.grid(row=0, column=4, rowspan=3, padx=(20, 15), pady=10, sticky="e")

        self._btn_action = ttk.Button(btn_frame, text=self.t("start_btn"), width=22,
                                      command=self.start_typing_thread, bootstyle="success")
        self._btn_action.pack(side="top", pady=(0, 6))

        self._btn_pause = ttk.Button(btn_frame, text=self.t("pause_btn"), width=22,
                                     command=self._toggle_pause,
                                     bootstyle="warning-outline", state="disabled")
        self._btn_pause.pack(side="top")

    def _build_ai_panel(self) -> None:
        section = CollapsibleFrame(self, text=self.t("ai_title"),
                                   bootstyle="primary", expanded=False)
        section.pack(side="top", fill="x", padx=20, pady=(0, 4))
        self._af = section
        af = section.body
        af.columnconfigure(0, weight=1)

        self._lbl_ai = ttk.Label(af, text=self.t("ai_prompt_label"))
        self._lbl_ai.grid(row=0, column=0, columnspan=6,
                          padx=15, pady=(8, 2), sticky="w")

        self._lbl_ai_provider = ttk.Label(af, text=self.t("ai_provider_label"))
        self._lbl_ai_provider.grid(row=1, column=0, padx=(15, 3), pady=(0, 4), sticky="w")
        self._ai_provider_var = ttk.StringVar(value=ai.Provider.CODEX.value)
        self._ai_provider_display = ttk.StringVar(value=self._provider_display(ai.Provider.CODEX))
        self._ai_provider_combo = ttk.Combobox(
            af, textvariable=self._ai_provider_display,
            values=[self._provider_display(provider) for provider in ai.Provider],
            state="readonly", width=15, bootstyle="secondary")
        self._ai_provider_combo.grid(row=1, column=1, padx=(0, 5), pady=(0, 4), sticky="w")
        self._ai_provider_combo.bind("<<ComboboxSelected>>", self._on_ai_provider_change)

        self._lbl_ai_model = ttk.Label(af, text=self.t("ai_model_label"))
        self._lbl_ai_model.grid(row=1, column=2, padx=(5, 3), pady=(0, 4), sticky="w")
        self._ai_model_var = ttk.StringVar(value="")
        self._ai_model_combo = ttk.Combobox(af, textvariable=self._ai_model_var,
                                            values=[m.display_name for m in self._ai_models],
                                            state="readonly", width=16,
                                            bootstyle="secondary")
        self._ai_model_combo.grid(row=1, column=3, padx=(0, 5), pady=(0, 4), sticky="w")
        self._ai_model_combo.bind("<<ComboboxSelected>>", self._on_ai_model_change)

        self._lbl_ai_effort = ttk.Label(af, text=self.t("ai_effort_label"))
        self._lbl_ai_effort.grid(row=1, column=4, padx=(5, 3), pady=(0, 4), sticky="w")
        self._effort_var = ttk.StringVar(value="")
        self._ai_effort_combo = ttk.Combobox(af, textvariable=self._effort_var,
                                             state="readonly", width=8,
                                             bootstyle="secondary")
        self._ai_effort_combo.grid(row=1, column=5, padx=(0, 15), pady=(0, 4), sticky="w")
        self._update_effort_options()

        self._ai_entry = ttk.Entry(af)
        self._ai_entry.grid(row=2, column=0, columnspan=4, padx=(15, 5), pady=(0, 4), sticky="ew")
        self._ai_entry.bind("<Return>", lambda _e: self.generate_with_ai())
        self._btn_ai = ttk.Button(af, text=self.t("ai_generate_btn"), width=14,
                                  command=self.generate_with_ai, bootstyle="primary")
        self._btn_ai.grid(row=2, column=4, padx=(5, 3), pady=(0, 4), sticky="e")
        self._btn_ai_cancel = ttk.Button(af, text=self.t("ai_cancel_btn"), width=10,
                                         command=self.cancel_ai_generation,
                                         bootstyle="warning-outline", state="disabled")
        self._btn_ai_cancel.grid(row=2, column=5, padx=(3, 15), pady=(0, 4), sticky="e")

        self._lbl_ai_hint = ttk.Label(af, text=self.t("ai_hint"),
                                      font=("", 9), bootstyle="secondary")
        self._lbl_ai_hint.grid(row=3, column=0, columnspan=6,
                               padx=15, pady=(0, 2), sticky="w")
        self._lbl_ai_preview = ttk.Label(af, text=self.t("ai_preview_label"),
                                         font=("", 9), bootstyle="secondary")
        self._lbl_ai_preview.grid(row=4, column=0, columnspan=6,
                                  padx=15, pady=(0, 2), sticky="w")
        self._ai_preview_text = ScrolledText(af, height=5, width=100,
                                             font=platform_mono_font())
        self._ai_preview_text.grid(row=5, column=0, columnspan=6,
                                   padx=15, pady=(0, 4), sticky="ew")
        self._ai_preview_text.text.configure(state="disabled")
        self._btn_ai_apply = ttk.Button(af, text=self.t("ai_apply_btn"), width=28,
                                        command=self.apply_ai_preview,
                                        bootstyle="success-outline", state="disabled")
        self._btn_ai_apply.grid(row=6, column=5, padx=(5, 15), pady=(0, 8), sticky="e")
        self._set_ai_controls_enabled(True)

    def _build_bw_panel(self) -> None:
        section = CollapsibleFrame(self, text=self.t("bw_title"),
                                   bootstyle="warning", expanded=False)
        section.pack(side="top", fill="x", padx=20, pady=(0, 4))
        self._bf = section
        bf = section.body
        bf.columnconfigure(1, weight=1)

        # Row 0 ── Email
        self._lbl_bw_email = ttk.Label(bf, text=self.t("bw_email_label"))
        self._lbl_bw_email.grid(row=0, column=0, padx=(15, 5), pady=(8, 4), sticky="w")

        self._bw_email_entry = ttk.Entry(bf)
        self._bw_email_entry.grid(row=0, column=1, columnspan=3, padx=(5, 15), pady=(8, 4), sticky="ew")

        # Row 1 ── Master password | Authenticate | Lock
        self._lbl_bw_pw = ttk.Label(bf, text=self.t("bw_pw_label"))
        self._lbl_bw_pw.grid(row=1, column=0, padx=(15, 5), pady=4, sticky="w")

        self._bw_pw_entry = ttk.Entry(bf, show="•")
        self._bw_pw_entry.grid(row=1, column=1, padx=5, pady=4, sticky="ew")
        self._bw_pw_entry.bind("<Return>", lambda _e: self.bw_unlock())

        self._btn_bw_unlock = ttk.Button(bf, text=self.t("bw_unlock_btn"), width=15,
                                         command=self.bw_unlock, bootstyle="warning")
        self._btn_bw_unlock.grid(row=1, column=2, padx=5, pady=4)

        self._btn_bw_lock = ttk.Button(bf, text=self.t("bw_lock_btn"), width=13,
                                       command=self.bw_lock,
                                       bootstyle="warning-outline", state="disabled")
        self._btn_bw_lock.grid(row=1, column=3, padx=(5, 15), pady=4)

        # Row 2 ── Search credential | Search
        self._lbl_bw_search = ttk.Label(bf, text=self.t("bw_search_label"))
        self._lbl_bw_search.grid(row=2, column=0, padx=(15, 5), pady=4, sticky="w")

        self._bw_search_entry = ttk.Entry(bf, state="disabled")
        self._bw_search_entry.grid(row=2, column=1, padx=5, pady=4, sticky="ew")
        self._bw_search_entry.bind("<Return>", lambda _e: self.bw_search())

        self._btn_bw_search = ttk.Button(bf, text=self.t("bw_search_btn"), width=15,
                                         command=self.bw_search,
                                         bootstyle="secondary", state="disabled")
        self._btn_bw_search.grid(row=2, column=2, padx=5, pady=4)

        # Row 3 ── Results combobox | Type password | Show OTP
        self._bw_item_var = ttk.StringVar(value="")
        self._bw_item_combo = ttk.Combobox(bf, textvariable=self._bw_item_var,
                                           state="disabled", bootstyle="secondary")
        self._bw_item_combo.grid(row=3, column=0, columnspan=2,
                                 padx=(15, 5), pady=4, sticky="ew")
        self._bw_item_combo.bind("<<ComboboxSelected>>", self._bw_on_item_selected)

        self._btn_bw_type = ttk.Button(bf, text=self.t("bw_type_btn"), width=15,
                                       command=self.bw_type_password,
                                       bootstyle="warning", state="disabled")
        self._btn_bw_type.grid(row=3, column=2, padx=5, pady=4)

        self._btn_bw_totp = ttk.Button(bf, text=self.t("bw_totp_btn"), width=15,
                                       command=self.bw_show_totp,
                                       bootstyle="secondary", state="disabled")
        self._btn_bw_totp.grid(row=3, column=3, padx=(5, 15), pady=4)

        self._btn_bw_passkey = ttk.Button(bf, text=self.t("bw_passkey_btn"), width=24,
                                          command=self.bw_show_passkey_details,
                                          bootstyle="secondary", state="disabled")
        self._btn_bw_passkey.grid(row=4, column=0, columnspan=4, padx=15, pady=(0, 2), sticky="w")

        self._lbl_bw_passkey_details = ttk.Label(
            bf, text=self.t("bw_passkey_details_none"), font=("", 9),
            bootstyle="secondary", justify="left", wraplength=760)
        self._lbl_bw_passkey_details.grid(row=5, column=0, columnspan=4,
                                          padx=15, pady=(0, 2), sticky="w")

        self._lbl_bw_metadata = ttk.Label(bf, text=self.t("bw_metadata_none"),
                                          font=("", 9), bootstyle="secondary")
        self._lbl_bw_metadata.grid(row=6, column=0, columnspan=4,
                                   padx=15, pady=(0, 2), sticky="w")

        self._lbl_bw_hint = ttk.Label(bf, text=self.t("bw_hint"),
                                      font=("", 9), bootstyle="secondary")
        self._lbl_bw_hint.grid(row=7, column=0, columnspan=4,
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
        self._bw_email_entry.configure(state="disabled" if unlocked else "normal")
        self._bw_pw_entry.configure(state="disabled" if unlocked else "normal")
        if unlocked:
            self._bw_pw_entry.delete(0, "end")   # don't keep the master password around
        else:
            self._bw_items = []
            self._bw_item_combo.configure(values=[], state="disabled")
            self._bw_item_var.set("")
            self._btn_bw_type.configure(state="disabled")
            self._btn_bw_totp.configure(state="disabled")
            self._btn_bw_passkey.configure(state="disabled")
            self._lbl_bw_metadata.configure(text=self.t("bw_metadata_none"))
            self._lbl_bw_passkey_details.configure(text=self.t("bw_passkey_details_none"))

    def bw_unlock(self) -> None:
        if self._vault.is_busy or self._engine.is_typing:
            return
        if not vault.is_available():
            self.update_status(self.t("bw_err_lib"), StatusStyle.ERROR)
            return
        email = self._bw_email_entry.get().strip()
        if not email:
            self.update_status(self.t("bw_err_empty_email"), StatusStyle.ERROR)
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
        self._vault.unlock(email, password, callbacks)

    def _bw_on_unlocked(self) -> None:
        self._bw_epoch += 1
        self._bw_set_unlocked_ui(True)
        self._log_append(self.t("bw_unlocked"))
        self.update_status(self.t("bw_unlocked"), StatusStyle.SUCCESS)

    def bw_lock(self) -> None:
        self._bw_epoch += 1
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
        self._bw_clear_sensitive_display()
        self.update_status(self.t("bw_searching"), StatusStyle.WARNING)
        epoch = self._bw_epoch
        callbacks = VaultCallbacks(
            on_items=lambda items: self.after(
                0, lambda i=items: self._bw_on_items(i, epoch)),
            on_error=lambda e: self.after(
                0, lambda error=e: self._bw_on_search_error(epoch, error)),
        )
        self._vault.search(query, callbacks)

    def _bw_item_label(self, item: VaultItem) -> str:
        label = f"{item.name} ({item.username})" if item.username else item.name
        return f"{label} · {self.t('bw_passkeys', n=item.passkey_count)}" if item.passkey_count else label

    def _bw_selected_item(self) -> VaultItem | None:
        idx = self._bw_item_combo.current()
        return self._bw_items[idx] if 0 <= idx < len(self._bw_items) else None

    def _bw_clear_sensitive_display(self) -> None:
        self._lbl_bw_metadata.configure(text=self.t("bw_metadata_none"))

    def _bw_clear_passkey_details(self) -> None:
        self._lbl_bw_passkey_details.configure(text=self.t("bw_passkey_details_none"))

    def _bw_update_selected_item_ui(self) -> None:
        item = self._bw_selected_item()
        self._bw_clear_sensitive_display()
        self._bw_clear_passkey_details()
        self._btn_bw_type.configure(state="normal" if item and item.has_password else "disabled")
        # `bw list items` may omit login.totp although `bw get totp` works.
        self._btn_bw_totp.configure(state="normal" if item else "disabled")
        self._btn_bw_passkey.configure(state="normal" if item and item.passkey_count else "disabled")
        if item and item.passkey_count:
            self._lbl_bw_metadata.configure(
                text=self.t("bw_passkeys", n=item.passkey_count))

    def _bw_on_item_selected(self, _event=None) -> None:
        self._bw_update_selected_item_ui()

    def _bw_response_is_current(self, item_id: str, epoch: int) -> bool:
        """Reject a queued vault response after a lock, re-unlock, or selection change."""
        item = self._bw_selected_item()
        return bool(is_current_vault_epoch(self._vault.is_unlocked, self._bw_epoch, epoch) and item
                    and item.id == item_id)

    def _bw_on_search_error(self, epoch: int, error: Exception) -> None:
        if is_current_vault_epoch(self._vault.is_unlocked, self._bw_epoch, epoch):
            self._bw_on_error(error)

    def _bw_on_items(self, items: list[VaultItem], epoch: int) -> None:
        if not is_current_vault_epoch(self._vault.is_unlocked, self._bw_epoch, epoch):
            return
        self._btn_bw_search.configure(state="normal")
        self._bw_items = items
        labels = [self._bw_item_label(i) for i in items]
        self._bw_item_combo.configure(values=labels,
                                      state="readonly" if labels else "disabled")
        if labels:
            self._bw_item_var.set(labels[0])
            self._bw_item_combo.current(0)
            self._bw_update_selected_item_ui()
            self.update_status(self.t("bw_found", n=len(items)), StatusStyle.SUCCESS)
        else:
            self._bw_item_var.set("")
            self._btn_bw_type.configure(state="disabled")
            self._btn_bw_totp.configure(state="disabled")
            self._btn_bw_passkey.configure(state="disabled")
            self._bw_clear_sensitive_display()
            self._bw_clear_passkey_details()
            self.update_status(self.t("bw_none"), StatusStyle.WARNING)

    def bw_type_password(self) -> None:
        if self._vault.is_busy or self._engine.is_typing:
            return
        item = self._bw_selected_item()
        if not item or not item.has_password:
            self.update_status(self.t("bw_err_no_sel"), StatusStyle.ERROR)
            return

        self._btn_bw_type.configure(state="disabled")
        self.update_status(self.t("bw_fetching"), StatusStyle.WARNING)
        item_id, epoch = item.id, self._bw_epoch
        callbacks = VaultCallbacks(
            on_password=lambda pw: self.after(
                0, lambda p=pw: self._bw_on_password(item_id, epoch, p)),
            on_error=lambda e: self.after(
                0, lambda error=e: self._bw_on_request_error(item_id, epoch, error)),
        )
        self._vault.get_password(item_id, callbacks)

    def bw_show_totp(self) -> None:
        """Request and display a current OTP without logging or persisting it."""
        if self._vault.is_busy or self._engine.is_typing:
            self.update_status(self.t("bw_busy"), StatusStyle.WARNING)
            return
        item = self._bw_selected_item()
        if not item:
            self.update_status(self.t("bw_err_no_sel"), StatusStyle.ERROR)
            return

        self._btn_bw_totp.configure(state="disabled")
        self._bw_clear_sensitive_display()
        self.update_status(self.t("bw_fetching_totp"), StatusStyle.WARNING)
        item_id, epoch = item.id, self._bw_epoch
        callbacks = VaultCallbacks(
            on_totp=lambda code: self.after(
                0, lambda c=code: self._bw_on_totp(item_id, epoch, c)),
            on_error=lambda e: self.after(
                0, lambda error=e: self._bw_on_totp_error(item_id, epoch, error)),
        )
        self._vault.get_totp(item_id, callbacks)

    def _bw_on_request_error(self, item_id: str, epoch: int, error: Exception) -> None:
        if self._bw_response_is_current(item_id, epoch):
            self._bw_on_error(error)

    def _bw_on_totp_error(self, item_id: str, epoch: int, error: Exception) -> None:
        if not self._bw_response_is_current(item_id, epoch):
            return
        if is_missing_totp_error(error):
            self._bw_update_selected_item_ui()
            self.update_status(self.t("bw_err_no_totp"), StatusStyle.ERROR)
            return
        self._bw_on_error(error)

    def _bw_on_totp(self, item_id: str, epoch: int, code: str) -> None:
        if not self._bw_response_is_current(item_id, epoch):
            return
        self._bw_update_selected_item_ui()
        if not code:
            self.update_status(self.t("bw_err_no_totp"), StatusStyle.ERROR)
            return
        # This short-lived code is intentionally only shown on explicit request.
        self._lbl_bw_metadata.configure(text=self.t("bw_totp_value", code=code))
        self.update_status(self.t("bw_totp_ready"), StatusStyle.SUCCESS)

    def bw_show_passkey_details(self) -> None:
        """Show only allowlisted metadata for the selected credential's passkey."""
        if self._vault.is_busy or self._engine.is_typing:
            return
        item = self._bw_selected_item()
        if not item or not item.passkey_count:
            self.update_status(self.t("bw_err_no_passkey"), StatusStyle.ERROR)
            return

        self._btn_bw_passkey.configure(state="disabled")
        self._bw_clear_passkey_details()
        self.update_status(self.t("bw_fetching_passkey"), StatusStyle.WARNING)
        item_id, epoch = item.id, self._bw_epoch
        callbacks = VaultCallbacks(
            on_passkey_details=lambda details: self.after(
                0, lambda d=details: self._bw_on_passkey_details(item_id, epoch, d)),
            on_error=lambda e: self.after(
                0, lambda error=e: self._bw_on_request_error(item_id, epoch, error)),
        )
        self._vault.get_passkey_details(item_id, callbacks)

    def _bw_on_passkey_details(self, item_id: str, epoch: int, details) -> None:
        if not self._bw_response_is_current(item_id, epoch):
            return
        self._bw_update_selected_item_ui()
        if not details:
            self._bw_on_error(RuntimeError("no passkey details"))
            return
        lines = [self.t("bw_passkey_details_title")]
        for number, detail in enumerate(details, start=1):
            parts = [f"{self.t('bw_passkey_number', n=number)}"]
            if detail.credential_id:
                parts.append(self.t("bw_passkey_credential_id", value=detail.credential_id))
            if detail.rp_id:
                parts.append(self.t("bw_passkey_rp_id", value=detail.rp_id))
            if detail.user_handle:
                parts.append(self.t("bw_passkey_user_handle", value=detail.user_handle))
            parts.extend(f"{label}: {value}" for label, value in detail.metadata)
            lines.append(" · ".join(parts))
        self._lbl_bw_passkey_details.configure(text="\n".join(lines))
        self.update_status(self.t("bw_passkey_ready"), StatusStyle.SUCCESS)

    def _bw_on_password(self, item_id: str, epoch: int, password: str) -> None:
        """Type the fetched password straight into the focused window — it never
        enters the editor or the log. Honors the configured wait + interval."""
        if not self._bw_response_is_current(item_id, epoch):
            return
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
        self._typing_error = False
        self._btn_action.configure(state="normal", text=self.t("stop_btn"),
                                   bootstyle="danger", command=self.request_stop)
        self._btn_pause.configure(state="normal", text=self.t("pause_btn"))
        self._btn_ai.configure(state="disabled")
        self._set_ai_controls_enabled(False)
        self._set_keyboard_layout_enabled(False)
        self.update_status(self.t("bw_typing_pw"), StatusStyle.WARNING)

        # Deliberately minimal callbacks: the secret must not reach the log, so
        # we don't reuse the char-count log lines here — only progress/reset.
        callbacks = TypingCallbacks(
            on_progress=lambda done, total: self._set_progress(done, total),
            on_waiting=lambda s: self.update_status(
                self.t("status_waiting", s=s), StatusStyle.WARNING),
            on_done=lambda stopped, done, total: self.after(
                0, lambda: self._bw_on_type_done(stopped)),
            on_error=lambda e: self.after(0, self._bw_on_type_error),
            on_stop_requested=self.request_stop,
        )
        self._engine.start(password, wait_s, interval_s, False, callbacks)

    def _bw_on_type_error(self) -> None:
        """Report a password typing failure without exposing the secret."""
        self._typing_error = True
        self.update_status(self.t("err_typing", e="password typing failed"), StatusStyle.ERROR)
        self._log_append("ERROR: password typing failed")

    def _bw_on_type_done(self, stopped: bool) -> None:
        if self._typing_error:
            self._reset_ui()
            return
        if stopped:
            self.update_status(self.t("status_stopped"), StatusStyle.WARNING)
            self._reset_ui()
            return
        self._progress_var.set(100.0)
        self.update_status(self.t("status_done"), StatusStyle.SUCCESS)
        self._reset_ui()

    def _bw_on_error(self, e: Exception) -> None:
        self._btn_bw_unlock.configure(
            state="disabled" if self._vault.is_unlocked else "normal")
        if self._vault.is_unlocked:
            self._btn_bw_search.configure(state="normal")
            self._bw_update_selected_item_ui()
        if isinstance(e, vault.VaultTwoFactorError):
            self.update_status(self.t("bw_err_2fa"), StatusStyle.ERROR)
        elif isinstance(e, vault.VaultDeviceVerificationError):
            self.update_status(self.t("bw_err_device_verification"), StatusStyle.ERROR)
        elif isinstance(e, vault.VaultLoggedInIdentityError):
            self.update_status(self.t("bw_err_identity"), StatusStyle.ERROR)
        elif isinstance(e, vault.VaultLoggedOutError):
            self.update_status(self.t("bw_err_login"), StatusStyle.ERROR)
        else:
            self.update_status(self.t("bw_err_api", e=e), StatusStyle.ERROR)
        self._log_append(f"BITWARDEN ERROR: {e}")

    # -----------------------------------------------------------------------
    # AI providers and models (local discovery only; no credentials leave app)
    # -----------------------------------------------------------------------
    @staticmethod
    def _provider_display(provider) -> str:
        return {
            ai.Provider.CODEX: "ChatGPT (Codex)",
            ai.Provider.CLAUDE: "Claude",
            ai.Provider.GOOGLE: "Google (Antigravity)",
        }[provider]

    def _selected_provider(self):
        return ai.Provider(self._ai_provider_var.get())

    def _set_selected_provider(self, provider) -> None:
        self._ai_provider_var.set(provider.value)
        self._ai_provider_display.set(self._provider_display(provider))

    def _model_display(self, model_id: str | None) -> str:
        if model_id is None:
            return ""
        return next((m.display_name for m in self._ai_models if m.id == model_id), model_id)

    def _selected_model_info(self) -> ModelInfo | None:
        for info in self._ai_models:
            if info.id == self._ai_selected_model_id:
                return info
        return None

    def _selected_model(self) -> str | None:
        info = self._selected_model_info()
        return info.id if info else None

    def _selected_effort(self) -> str | None:
        return self._effort_var.get() or None

    def _update_effort_options(self, _event=None) -> None:
        info = self._selected_model_info()
        levels = list(info.effort_levels) if info else []
        self._ai_effort_combo.configure(values=levels)
        if levels:
            if self._effort_var.get() not in levels:
                self._effort_var.set("high" if "high" in levels else levels[0])
            self._ai_effort_combo.configure(state="readonly")
        else:
            self._effort_var.set("")
            self._ai_effort_combo.configure(state="disabled")

    def _refresh_ai_models_async(self) -> None:
        """Refresh provider-local status and only its supported models."""
        self._refresh_ai_provider()

    def _on_ai_provider_change(self, _event=None) -> None:
        display = self._ai_provider_display.get()
        provider = next(
            provider for provider in ai.Provider
            if self._provider_display(provider) == display)
        self._set_selected_provider(provider)
        self._ai_pending_generate = None
        self._invalidate_ai_preview()
        self._refresh_ai_provider()

    def _on_ai_model_change(self, _event=None) -> None:
        display = self._ai_model_var.get()
        selected = next((model for model in self._ai_models
                         if model.display_name == display), None)
        if selected:
            self._ai_selected_model_id = selected.id
        self._invalidate_ai_preview()
        self._update_effort_options()

    def _refresh_ai_provider(self, pending_prompt: str | None = None) -> None:
        provider = self._selected_provider()
        model = self._selected_model_info() if pending_prompt is not None else None
        effort = self._selected_effort() if pending_prompt is not None else None
        self._apply_fetched_models([])
        probe_id = self._ai_provider_probe_ids.get(provider, 0) + 1
        self._ai_provider_probe_ids[provider] = probe_id
        if pending_prompt is not None:
            self._ai_pending_generate = (
                provider, probe_id, pending_prompt, model.id if model else None,
                effort,
            )

        def worker() -> None:
            status = ai.provider_status(provider)
            try:
                self.after(0, lambda: self._apply_ai_provider_status(provider, probe_id, status))
            except TclError:
                pass  # The window closed while its local CLI probe was running.

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ai_provider_status(self, provider, probe_id: int, status) -> None:
        if self._ai_provider_probe_ids.get(provider) != probe_id:
            return
        self._ai_provider_statuses[provider] = status
        if provider != self._selected_provider():
            return
        self._apply_fetched_models(ai.models_for(provider, status))
        name = self._provider_display(provider)
        if not getattr(status, "safe", True):
            message, style = self.t("ai_provider_unsafe", provider=name), StatusStyle.WARNING
        elif not status.installed:
            message, style = self.t("ai_provider_unavailable", provider=name), StatusStyle.WARNING
        elif not status.authenticated:
            message, style = self.t("ai_provider_unauthenticated", provider=name), StatusStyle.WARNING
        elif not status.available:
            message, style = self.t("ai_provider_unavailable", provider=name), StatusStyle.WARNING
        else:
            message, style = self.t("ai_provider_ready", provider=name), StatusStyle.IDLE
        self.update_status(message, style)
        pending = self._ai_pending_generate
        if pending and pending[:2] == (provider, probe_id):
            self._ai_pending_generate = None
            _provider, _probe, prompt, model_id, effort = pending
            if status.safe and status.available and status.authenticated:
                info = next(
                    (item for item in self._ai_models if item.id == model_id),
                    self._ai_models[0] if self._ai_models else None,
                )
                if info:
                    self._start_ai_generation(prompt, provider, info, effort)

    def _apply_fetched_models(self, models: list[ModelInfo]) -> None:
        self._ai_models = models
        display_names = [m.display_name for m in models]
        self._ai_model_combo.configure(values=display_names)
        ids = {m.id for m in models}
        self._ai_selected_model_id = (
            self._ai_selected_model_id if self._ai_selected_model_id in ids
            else (models[0].id if models else None))
        self._ai_model_var.set(self._model_display(self._ai_selected_model_id))
        self._update_effort_options()
        if not self._ai.is_generating:
            self._btn_ai.configure(state="normal" if models else "disabled")

    def _set_ai_controls_enabled(self, enabled: bool) -> None:
        self._ai_provider_combo.configure(state="readonly" if enabled else "disabled")
        self._ai_model_combo.configure(
            state="readonly" if enabled and self._ai_models else "disabled")
        if enabled:
            self._update_effort_options()   # restores values + enabled state
        else:
            self._ai_effort_combo.configure(state="disabled")

    def _build_text_area(self) -> None:
        self._text_frame = ttk.Frame(self)
        self._text_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 2))
        self._text_areas: list[tuple[ttk.Frame, ScrolledText]] = []
        self._active_text_info: ScrolledText | None = None
        self._set_text_area_count()

    def _set_text_area_count(self, _event=None) -> None:
        """Show the requested editors, retaining hidden editors in memory."""
        try:
            count = int(self._text_area_count.get())
        except (TclError, ValueError, TypeError):
            count = 1
        count = max(1, min(self._MAX_TEXT_AREAS, count))
        self._text_area_count.set(count)

        while len(self._text_areas) < count:
            cell = ttk.Frame(self._text_frame, padding=2)
            editor = ScrolledText(cell, height=8, width=100, font=platform_mono_font())
            editor.pack(fill="both", expand=True)
            editor.text.configure(undo=True)
            editor.text.bind("<FocusIn>", lambda _e, e=editor: self._set_active_text(e))
            editor.text.bind("<KeyRelease>", lambda _e: self._update_char_count())
            self._text_areas.append((cell, editor))

        columns_before, rows_before = self._text_frame.grid_size()
        for cell, _editor in self._text_areas:
            cell.grid_forget()
        for row in range(rows_before):
            self._text_frame.rowconfigure(row, weight=0)
        for column in range(columns_before):
            self._text_frame.columnconfigure(column, weight=0)

        columns = ceil(sqrt(count))
        rows = ceil(count / columns)
        for index, (cell, _editor) in enumerate(self._text_areas[:count]):
            cell.grid(row=index // columns, column=index % columns, sticky="nsew")
        for row in range(rows):
            self._text_frame.rowconfigure(row, weight=1)
        for column in range(columns):
            self._text_frame.columnconfigure(column, weight=1)

        visible_editors = [editor for _cell, editor in self._text_areas[:count]]
        if self._active_text_info not in visible_editors:
            self._set_active_text(visible_editors[0])

    def _set_active_text(self, editor: ScrolledText) -> None:
        self._active_text_info = editor
        self._update_char_count()

    def _active_text(self) -> ScrolledText:
        return self._active_text_info or self._text_areas[0][1]

    def _build_char_counter(self) -> None:
        row = ttk.Frame(self)
        row.pack(side="bottom", fill="x", padx=22, pady=(2, 0))
        self._lbl_text_areas = ttk.Label(row, text=self.t("text_areas_label"))
        self._lbl_text_areas.pack(side="left", padx=(0, 5))
        self._text_area_count = ttk.IntVar(value=1)
        self._text_area_spinbox = ttk.Spinbox(
            row, from_=1, to=self._MAX_TEXT_AREAS, width=3,
            textvariable=self._text_area_count, command=self._set_text_area_count)
        self._text_area_spinbox.pack(side="left")
        self._text_area_spinbox.bind("<Return>", self._set_text_area_count)
        self._text_area_spinbox.bind("<FocusOut>", self._set_text_area_count)
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

        def add_combos(menu, entries):
            for key, lbl in entries:
                menu.add_command(
                    label=lbl,
                    command=lambda k=key: self._insert_marker(f"[[key:{k}]]"))

        # Clipboard / editing
        add_combos(combo, [
            ("ctrl+c", "Ctrl+C  (copy / SIGINT)"),
            ("ctrl+v", "Ctrl+V  (paste)"),
            ("ctrl+x", "Ctrl+X  (cut)"),
            ("ctrl+z", "Ctrl+Z  (undo)"),
            ("ctrl+y", "Ctrl+Y  (redo)"),
            ("ctrl+a", "Ctrl+A  (select all)"),
            ("ctrl+s", "Ctrl+S  (save)"),
            ("ctrl+f", "Ctrl+F  (find)"),
            ("ctrl+w", "Ctrl+W  (close)"),
        ])
        combo.add_separator()
        # Terminal / shell (Linux)
        add_combos(combo, [
            ("ctrl+shift+c", "Ctrl+Shift+C  (copy)"),
            ("ctrl+shift+v", "Ctrl+Shift+V  (paste)"),
            ("ctrl+l",       "Ctrl+L  (clear)"),
            ("ctrl+r",       "Ctrl+R  (reverse search)"),
            ("ctrl+d",       "Ctrl+D  (EOF / logout)"),
            ("ctrl+alt+t",   "Ctrl+Alt+T  (open terminal)"),
        ])
        combo.add_separator()
        # Window / system
        add_combos(combo, [
            ("ctrl+alt+del",   "Ctrl+Alt+Del"),
            ("alt+f4",         "Alt+F4  (close window)"),
            ("alt+tab",        "Alt+Tab  (switch window)"),
            ("shift+tab",      "Shift+Tab"),
            ("ctrl+shift+esc", "Ctrl+Shift+Esc  (task manager)"),
        ])
        combo.add_separator()
        # Windows key
        add_combos(combo, [
            ("win+r", "Win+R  (run)"),
            ("win+e", "Win+E  (explorer)"),
            ("win+d", "Win+D  (show desktop)"),
            ("win+l", "Win+L  (lock)"),
        ])
        combo.add_separator()
        # Switch virtual terminal (Linux console)
        tty = Menu(combo, tearoff=0)
        add_combos(tty, [(f"ctrl+alt+F{n}", f"Ctrl+Alt+F{n}") for n in range(1, 8)])
        combo.add_cascade(label="Switch TTY (Linux)", menu=tty)

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
        editor = self._active_text()
        try:
            editor.insert("insert", marker)
        except Exception:
            editor.insert("end", marker)
        self._update_char_count()

    def _build_progress(self) -> None:
        self._progress_var = ttk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Progressbar(self, variable=self._progress_var,
                                             maximum=100, bootstyle="success-striped")
        self._progress_bar.pack(side="bottom", fill="x", padx=20, pady=(4, 0))

    def _build_log(self) -> None:
        self._log_frame = CollapsibleFrame(self, text=self.t("log_title"),
                                           bootstyle="secondary", expanded=False)
        self._log_frame.pack(side="bottom", fill="x", padx=20, pady=(4, 2))
        self._log_text = ScrolledText(self._log_frame.body, height=3, width=100,
                                      font=platform_mono_font(10))
        self._log_text.pack(fill="x", padx=5, pady=5)
        self._log_text.text.configure(state="disabled")

    def _build_status_bar(self) -> None:
        sb = ttk.Frame(self)
        sb.pack(side="bottom", fill="x", padx=20, pady=(0, 5))
        self._status_label = ttk.Label(sb, text=self.t("status_ready"),
                                       font=("", 10, "italic"), bootstyle=StatusStyle.IDLE)
        self._status_label.pack(side="left")

    # -----------------------------------------------------------------------
    # Linux / Wayland
    # -----------------------------------------------------------------------
    def _check_wayland(self) -> None:
        from .drivers import is_wayland, can_use_evdev

        if not is_wayland():
            return

        if can_use_evdev():
            wf = ttk.Frame(self, bootstyle="info")
            wf.pack(fill="x", padx=20, pady=(5, 0), before=self._sf)
            wf.columnconfigure(0, weight=1)
            self._warning_frame = wf
            self._lbl_wayland = ttk.Label(
                wf, text=self.t("info_wayland_active"),
                bootstyle="inverse-info", justify="left"
            )
            self._lbl_wayland.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="ew")
            ttk.Button(wf, text="✕", bootstyle="light-outline",
                       command=self._close_warning, width=2, padding=1) \
                .grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ne")
        else:
            wf = ttk.Frame(self, bootstyle="warning")
            wf.pack(fill="x", padx=20, pady=(5, 0), before=self._sf)
            wf.columnconfigure(0, weight=1)
            self._warning_frame = wf
            self._lbl_wayland = ttk.Label(
                wf, text=self.t("warn_wayland_perms"),
                bootstyle="inverse-warning", justify="left"
            )
            self._lbl_wayland.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="ew")
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
        self._lbl_keyboard_layout.configure(text=self.t("keyboard_layout_label"))
        self._chk_chunk.configure(text=self.t("chunk_label"))
        self._lbl_text_areas.configure(text=self.t("text_areas_label"))
        self._insert_btn.configure(text=self.t("insert_btn"))
        self._lbl_marker_hint.configure(text=self.t("marker_hint"))
        self._af.set_title(self.t("ai_title"))
        self._lbl_ai.configure(text=self.t("ai_prompt_label"))
        self._lbl_ai_provider.configure(text=self.t("ai_provider_label"))
        self._lbl_ai_model.configure(text=self.t("ai_model_label"))
        self._lbl_ai_effort.configure(text=self.t("ai_effort_label"))
        self._lbl_ai_hint.configure(text=self.t("ai_hint"))
        self._lbl_ai_preview.configure(text=self.t("ai_preview_label"))
        self._btn_ai_cancel.configure(text=self.t("ai_cancel_btn"))
        self._btn_ai_apply.configure(text=self.t("ai_apply_btn"))
        if not self._ai.is_generating:
            self._btn_ai.configure(text=self.t("ai_generate_btn"))

        self._bf.set_title(self.t("bw_title"))
        self._lbl_bw_email.configure(text=self.t("bw_email_label"))
        self._lbl_bw_pw.configure(text=self.t("bw_pw_label"))
        self._btn_bw_unlock.configure(text=self.t("bw_unlock_btn"))
        self._btn_bw_lock.configure(text=self.t("bw_lock_btn"))
        self._lbl_bw_search.configure(text=self.t("bw_search_label"))
        self._btn_bw_search.configure(text=self.t("bw_search_btn"))
        self._btn_bw_type.configure(text=self.t("bw_type_btn"))
        self._btn_bw_totp.configure(text=self.t("bw_totp_btn"))
        self._btn_bw_passkey.configure(text=self.t("bw_passkey_btn"))
        self._lbl_bw_hint.configure(text=self.t("bw_hint"))
        self._bw_update_selected_item_ui()
        self._log_frame.set_title(self.t("log_title"))
        self._status_label.configure(text=self.t("status_ready"))

        self._profile_combo.configure(values=self._profile_names())
        self._sync_profile_combo(current_ms)
        self._keyboard_layout_combo.configure(values=self._keyboard_layout_names())
        self._keyboard_layout_var.set(self._keyboard_layout_display())

        if not self._engine.is_typing:
            self._btn_action.configure(text=self.t("start_btn"))
            self._btn_pause.configure(text=self.t("pause_btn"))

        if hasattr(self, "_lbl_wayland") and self._lbl_wayland.winfo_exists():
            from .drivers import can_use_evdev
            key = "info_wayland_active" if can_use_evdev() else "warn_wayland_perms"
            self._lbl_wayland.configure(text=self.t(key))

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
    # Keyboard layout
    # -----------------------------------------------------------------------
    def _keyboard_layout_names(self) -> list[str]:
        return [self.t("keyboard_layout_us"), self.t("keyboard_layout_abnt2")]

    def _keyboard_layout_display(self) -> str:
        return self.t(f"keyboard_layout_{self._keyboard_layout}")

    def _set_keyboard_layout_enabled(self, enabled: bool) -> None:
        self._keyboard_layout_combo.configure(state="readonly" if enabled else "disabled")

    def _on_keyboard_layout_change(self, _event=None) -> None:
        """Replace the idle engine so the next run uses the selected layout."""
        names = self._keyboard_layout_names()
        try:
            selected = ("us", "abnt2")[names.index(self._keyboard_layout_var.get())]
        except ValueError:
            self._keyboard_layout_var.set(self._keyboard_layout_display())
            return

        if selected == self._keyboard_layout:
            return
        if self._engine.is_typing:
            # The combobox is disabled while typing, but retain this guard in
            # case a platform delivers a delayed selection event.
            self._keyboard_layout_var.set(self._keyboard_layout_display())
            return

        try:
            replacement = TypingEngine(keyboard_layout=selected)
        except Exception as e:
            self._keyboard_layout_var.set(self._keyboard_layout_display())
            self.update_status(self.t("err_typing", e=e), StatusStyle.ERROR)
            return

        old_engine = self._engine
        self._engine = replacement
        self._keyboard_layout = selected
        old_engine.close()

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
            text = self._active_text().get("1.0", "end-1c")
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
            editor = self._active_text()
            editor.delete("1.0", "end")
            editor.insert("1.0", content)
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
                content = self._active_text().get("1.0", "end-1c")
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
        text = self._active_text().get("1.0", "end-1c")
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
        self._typing_error = False

        self.after(0, lambda: self._progress_var.set(0.0))
        self._btn_action.configure(state="normal", text=self.t("stop_btn"),
                                   bootstyle="danger", command=self.request_stop)
        self._btn_pause.configure(state="normal", text=self.t("pause_btn"))
        self._btn_ai.configure(state="disabled")
        self._set_ai_controls_enabled(False)
        self._set_keyboard_layout_enabled(False)
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
    # AI generation: preview first; inserting into the typing editor is explicit.
    # -----------------------------------------------------------------------
    def generate_with_ai(self) -> None:
        # --- Read the prompt in the main thread, then hand off to a worker ---
        if self._engine.is_typing or self._ai.is_generating:
            return

        prompt = self._ai_entry.get().strip()
        if not prompt:
            self.update_status(self.t("ai_err_empty"), StatusStyle.ERROR)
            return
        # Authentication can change outside the app. Always probe asynchronously
        # rather than trusting a cached negative result or blocking the Tk loop.
        self.update_status(self.t("ai_checking"), StatusStyle.WARNING)
        self._refresh_ai_provider(pending_prompt=prompt)

    def _start_ai_generation(self, prompt: str, provider, info: ModelInfo,
                             effort: str | None) -> None:
        if self._engine.is_typing or self._ai.is_generating:
            return

        self._invalidate_ai_preview()
        self._ai_generation_id += 1
        generation_id = self._ai_generation_id
        self._ai_cancelling = False
        self._btn_ai.configure(state="disabled", text=self.t("ai_generating_btn"))
        self._btn_ai_cancel.configure(state="normal")
        self._set_ai_controls_enabled(False)
        self._btn_action.configure(state="disabled")
        self.update_status(self.t("ai_generating"), StatusStyle.WARNING)

        callbacks = AICallbacks(
            on_start=lambda: self.after(0, lambda: self._ai_on_start(generation_id)),
            on_text=lambda text: self.after(0, lambda value=text: self._ai_on_text(generation_id, value)),
            on_done=lambda full: self.after(0, lambda value=full: self._ai_on_done(generation_id, value)),
            on_error=lambda e: self.after(0, lambda error=e: self._ai_on_error(generation_id, error)),
        )
        self._ai.generate(prompt, self.lang, info.id, callbacks,
                          supports_adaptive=info.supports_adaptive,
                          effort=effort, provider=provider)

    def cancel_ai_generation(self) -> None:
        if self._ai_cancelling or not self._ai.cancel():
            return
        self._ai_cancelling = True
        self._invalidate_ai_preview()
        self._btn_ai_cancel.configure(state="disabled")
        self.update_status(self.t("ai_cancelling"), StatusStyle.WARNING)

    def _ai_callback_current(self, generation_id: int) -> bool:
        return generation_id == self._ai_generation_id

    def _ai_on_start(self, generation_id: int) -> None:
        if not self._ai_callback_current(generation_id) or self._ai_cancelling:
            return
        self._log_append(self.t("ai_generating"))

    def _ai_on_text(self, generation_id: int, text: str) -> None:
        # The core emits this once, after it has validated the complete output.
        if self._ai_callback_current(generation_id) and not self._ai_cancelling:
            self._ai_preview = text

    def _ai_on_done(self, generation_id: int, full: str) -> None:
        if not self._ai_callback_current(generation_id):
            return
        was_cancelling = self._ai_cancelling
        self._ai_cancelling = False
        self._btn_ai.configure(state="normal", text=self.t("ai_generate_btn"))
        self._btn_ai_cancel.configure(state="disabled")
        self._set_ai_controls_enabled(True)
        self._btn_action.configure(state="normal")
        if was_cancelling:
            self._invalidate_ai_preview()
            self._status_label.configure(text=self.t("status_stopped"),
                                         bootstyle=StatusStyle.WARNING)
            return
        if full:
            self._set_ai_preview(full)
            self._status_label.configure(text=self.t("ai_done"), bootstyle=StatusStyle.SUCCESS)
        else:
            self._invalidate_ai_preview()
            self._status_label.configure(text=self.t("ai_err_api", e="empty response"),
                                         bootstyle=StatusStyle.ERROR)

    def _ai_on_error(self, generation_id: int, e: Exception) -> None:
        if not self._ai_callback_current(generation_id):
            return
        was_cancelling = self._ai_cancelling
        self._ai_cancelling = False
        self._invalidate_ai_preview()
        self._btn_ai.configure(state="normal", text=self.t("ai_generate_btn"))
        self._btn_ai_cancel.configure(state="disabled")
        self._set_ai_controls_enabled(True)
        self._btn_action.configure(state="normal")
        if was_cancelling:
            msg = self.t("status_stopped")
        elif ai.is_auth_error(e):
            msg = self.t("ai_err_auth")            # bad/expired credential
        else:
            msg = self.t("ai_err_api", e=e)
        self._status_label.configure(text=msg, bootstyle=StatusStyle.ERROR)
        if not was_cancelling:
            self._log_append(f"AI ERROR: {e}")

    def _set_ai_preview(self, text: str) -> None:
        text = normalize_ai_output(text)
        self._ai_preview = text
        self._ai_preview_text.text.configure(state="normal")
        self._ai_preview_text.text.delete("1.0", "end")
        self._ai_preview_text.text.insert("1.0", text)
        self._ai_preview_text.text.configure(state="disabled")
        self._btn_ai_apply.configure(state="normal")

    def _invalidate_ai_preview(self) -> None:
        self._ai_preview = ""
        if not hasattr(self, "_ai_preview_text"):
            return
        self._ai_preview_text.text.configure(state="normal")
        self._ai_preview_text.text.delete("1.0", "end")
        self._ai_preview_text.text.configure(state="disabled")
        self._btn_ai_apply.configure(state="disabled")

    def apply_ai_preview(self) -> None:
        text = normalize_ai_output(self._ai_preview)
        if not text or not is_safe_ai_output(text):
            self._invalidate_ai_preview()
            self.update_status(self.t("ai_preview_rejected"), StatusStyle.ERROR)
            return
        editor = self._active_text()
        editor.text.insert("insert", text)
        editor.text.see("insert")
        self._invalidate_ai_preview()
        self._update_char_count()
        self.update_status(self.t("ai_applied"), StatusStyle.SUCCESS)

    def _on_chunk_done(self, cur: int, total: int) -> None:
        status = self.t("status_chunk", cur=cur, total=total)
        self._log_append(status)
        self._status_label.configure(text=status, bootstyle=StatusStyle.WARNING)
        self._progress_var.set((cur / total * 100) if total > 0 else 0.0)

    def _on_typing_error(self, e: Exception) -> None:
        self._typing_error = True
        self._status_label.configure(text=self.t("err_typing", e=e), bootstyle=StatusStyle.ERROR)
        self._log_append(f"ERROR: {e}")

    def _on_typing_done(self, stopped: bool, done: int, total: int) -> None:
        if self._typing_error:
            self._reset_ui()
            return
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
        self._btn_ai.configure(state="normal" if self._ai_models else "disabled")
        self._set_ai_controls_enabled(True)
        self._set_keyboard_layout_enabled(True)
