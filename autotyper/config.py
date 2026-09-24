"""Configuration constants: translations, speed profiles, status styles, fonts."""

import enum
import platform
from dataclasses import dataclass

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
        # Wayland messages
        "info_wayland_active": (
            "✨ Wayland session detected: running via native evdev (uinput) engine."
        ),
        "warn_wayland_perms": (
            "⚠️  Warning: Wayland session detected, but /dev/uinput is not accessible.\n"
            "To enable typing simulation, add udev rules or run: sudo usermod -aG input $USER"
        ),
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
        "text_areas_label": "Text areas:",
        # Insert button + marker hint
        "insert_btn":     "📥 Insert Marker ▾",
        "marker_hint":    "[[pause:N]] · [[speed:N]] · [[key:F5]] · [[key:ctrl+c]]",
        # Speed profiles
        "prof_slow":      "Slow  (200 ms)",
        "prof_normal":    "Normal (100 ms)",
        "prof_fast":      "Fast   (50 ms)",
        "prof_turbo":     "Turbo  (10 ms)",
        "prof_custom":    "Custom",
        # AI assistant
        "ai_title":         " 🤖 AI Assistant ",
        "ai_prompt_label":  "Describe what you want typed (commands, script, config…):",
        "ai_generate_btn":  "✨ Generate",
        "ai_generating_btn":"⏳ Generating…",
        "ai_hint":          "Generated text lands in the editor below — review it, then press START.",
        "ai_generating":    "Generating with AI…",
        "ai_done":          "AI generation complete — review before typing.",
        "ai_err_empty":     "Error: describe what you want the AI to type first.",
        "ai_err_auth":      "Error: not authenticated. Log in with your Claude Code / VS Code browser session, run 'ant auth login', or set ANTHROPIC_API_KEY.",
        "ai_err_lib":       "Error: the 'anthropic' package is not installed (pip install anthropic).",
        "ai_err_api":       "AI error: {e}",
        # Bitwarden vault
        "bw_title":         " 🔐 Bitwarden ",
        "bw_pw_label":      "Master password:",
        "bw_unlock_btn":    "🔓 Unlock",
        "bw_lock_btn":      "🔒 Lock",
        "bw_search_label":  "Search credential:",
        "bw_search_btn":    "🔍 Search",
        "bw_type_btn":      "⌨ Type password",
        "bw_hint":          "Unlock, search an item, then type its password into the focused window. Nothing is shown or saved.",
        "bw_unlocking":     "Unlocking vault…",
        "bw_unlocked":      "Vault unlocked.",
        "bw_locked":        "Vault locked.",
        "bw_searching":     "Searching…",
        "bw_found":         "{n} credential(s) found.",
        "bw_none":          "No credentials matched.",
        "bw_fetching":      "Fetching password…",
        "bw_typing_pw":     "Typing password into the focused window…",
        "bw_err_lib":       "Error: Bitwarden CLI ('bw') not found on PATH. Install it and run 'bw login' first.",
        "bw_err_locked":    "Error: unlock the vault first.",
        "bw_err_empty_pw":  "Error: enter your master password.",
        "bw_err_empty_q":   "Error: type something to search for.",
        "bw_err_no_sel":    "Error: select a credential first.",
        "bw_err_login":     "Error: not logged in to Bitwarden. Run 'bw login' in a terminal first, then unlock here.",
        "bw_err_api":       "Bitwarden error: {e}",
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
        # Mensagens Wayland
        "info_wayland_active": (
            "✨ Sessão Wayland detectada: executando via driver nativo evdev (uinput)."
        ),
        "warn_wayland_perms": (
            "⚠️  Aviso: sessão Wayland detectada, mas /dev/uinput não está acessível.\n"
            "Para permitir a simulação, configure a regra udev ou execute: sudo usermod -aG input $USER"
        ),
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
        "text_areas_label": "Áreas de texto:",
        # Botão inserir + hint marcadores
        "insert_btn":     "📥 Inserir Marcador ▾",
        "marker_hint":    "[[pause:N]] · [[speed:N]] · [[key:F5]] · [[key:ctrl+c]]",
        # Perfis de velocidade
        "prof_slow":      "Lento   (200 ms)",
        "prof_normal":    "Normal  (100 ms)",
        "prof_fast":      "Rápido   (50 ms)",
        "prof_turbo":     "Turbo    (10 ms)",
        "prof_custom":    "Personalizado",
        # Assistente IA
        "ai_title":         " 🤖 Assistente IA ",
        "ai_prompt_label":  "Descreva o que quer digitar (comandos, script, configuração…):",
        "ai_generate_btn":  "✨ Gerar",
        "ai_generating_btn":"⏳ Gerando…",
        "ai_hint":          "O texto gerado aparece no editor abaixo — revise e depois clique em INICIAR.",
        "ai_generating":    "Gerando com IA…",
        "ai_done":          "Geração da IA concluída — revise antes de digitar.",
        "ai_err_empty":     "Erro: descreva primeiro o que a IA deve digitar.",
        "ai_err_auth":      "Erro: não autenticado. Faça login pelo browser (Claude Code / VS Code), rode 'ant auth login' ou defina ANTHROPIC_API_KEY.",
        "ai_err_lib":       "Erro: o pacote 'anthropic' não está instalado (pip install anthropic).",
        "ai_err_api":       "Erro da IA: {e}",
        # Cofre Bitwarden
        "bw_title":         " 🔐 Bitwarden ",
        "bw_pw_label":      "Senha mestra:",
        "bw_unlock_btn":    "🔓 Desbloquear",
        "bw_lock_btn":      "🔒 Bloquear",
        "bw_search_label":  "Buscar credencial:",
        "bw_search_btn":    "🔍 Buscar",
        "bw_type_btn":      "⌨ Digitar senha",
        "bw_hint":          "Desbloqueie, busque um item e digite a senha na janela em foco. Nada é exibido nem salvo.",
        "bw_unlocking":     "Desbloqueando cofre…",
        "bw_unlocked":      "Cofre desbloqueado.",
        "bw_locked":        "Cofre bloqueado.",
        "bw_searching":     "Buscando…",
        "bw_found":         "{n} credencial(is) encontrada(s).",
        "bw_none":          "Nenhuma credencial encontrada.",
        "bw_fetching":      "Obtendo senha…",
        "bw_typing_pw":     "Digitando a senha na janela em foco…",
        "bw_err_lib":       "Erro: CLI do Bitwarden ('bw') não encontrada no PATH. Instale-a e rode 'bw login' antes.",
        "bw_err_locked":    "Erro: desbloqueie o cofre primeiro.",
        "bw_err_empty_pw":  "Erro: informe a senha mestra.",
        "bw_err_empty_q":   "Erro: digite algo para buscar.",
        "bw_err_no_sel":    "Erro: selecione uma credencial primeiro.",
        "bw_err_login":     "Erro: você não está logado no Bitwarden. Rode 'bw login' num terminal antes e então desbloqueie aqui.",
        "bw_err_api":       "Erro do Bitwarden: {e}",
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


class StatusStyle(enum.StrEnum):
    IDLE    = "secondary"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR   = "danger"


def platform_mono_font(size: int = 13) -> tuple[str, int]:
    fonts = {"Windows": "Consolas", "Darwin": "Menlo"}
    return (fonts.get(platform.system(), "Monospace"), size)


# ---------------------------------------------------------------------------
# AI assistant (Anthropic Claude)
# ---------------------------------------------------------------------------
AI_MODEL = "claude-opus-4-8"   # default selection, used as a last-resort id


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    supports_adaptive: bool          # accepts thinking={"type": "adaptive"}
    effort_levels: tuple[str, ...]   # supported output_config.effort values


# Used only when the live Models API can't be reached — no `anthropic` package,
# no credentials, or a network/API error. ai.list_models() fetches the real,
# current list (with real capabilities) at runtime, so this fallback is never
# the source of truth and shouldn't need editing when a new model ships.
AI_FALLBACK_MODELS: list[ModelInfo] = [
    ModelInfo("claude-fable-5",   "Fable 5",   True,  ("low", "medium", "high", "xhigh", "max")),
    ModelInfo("claude-opus-4-8",  "Opus 4.8",  True,  ("low", "medium", "high", "xhigh", "max")),
    ModelInfo("claude-sonnet-5",  "Sonnet 5",  True,  ("low", "medium", "high", "xhigh", "max")),
    ModelInfo("claude-haiku-4-5", "Haiku 4.5", False, ()),
]

# System prompt shared by both languages, with a per-language instruction on
# what language to write comments in. Output goes straight into the typing
# buffer, so the model must return only the raw text to be typed.
_AI_SYSTEM_BASE = """\
You generate text that an auto-typing tool will type keystroke-by-keystroke \
into the currently focused OS window. The main use case is remote server \
consoles (KVM over IP, iDRAC, iLO, serial) where the clipboard and paste are \
unavailable, so everything must be typed.

OUTPUT RULES (critical):
- Output ONLY the exact text/commands to be typed. No explanations, no \
commentary, no surrounding prose.
- Never wrap the output in Markdown code fences (```), quotes, or headings — \
they would be typed literally.
- The output is inserted verbatim. Each newline you emit becomes an Enter \
keypress, so a trailing newline runs the last command.
- Prefer POSIX-portable commands unless the user specifies an OS or shell.

AUTOMATION MARKERS (optional — use only when timing or special keys are \
actually needed, otherwise plain text is better):
- [[pause:N]]        wait N seconds (e.g. after starting a service)
- [[speed:N]]        set the typing interval to N milliseconds
- [[speed:reset]]    restore the base typing speed
- [[key:name]]       press a special key or chord, e.g. [[key:enter]], \
[[key:tab]], [[key:ctrl+c]], [[key:F5]], [[key:up]]

SAFETY: If the request implies a destructive or irreversible action \
(e.g. rm -rf, mkfs, dd onto a disk, DROP DATABASE), still produce it when it \
is clearly what the user asked for, but prepend a single comment line warning \
about it.
"""

_AI_LANG_NOTE = {
    "en": "Write any comments in English.",
    "pt": "Escreva os comentários em português.",
}


def ai_system_prompt(lang: str) -> str:
    note = _AI_LANG_NOTE.get(lang, _AI_LANG_NOTE["en"])
    return f"{_AI_SYSTEM_BASE}\n{note}"
