"""Configuration constants: translations, speed profiles, status styles, fonts."""

import enum
import platform

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
        # Insert button + marker hint
        "insert_btn":     "📥 Insert Marker ▾",
        "marker_hint":    "[[pause:N]] · [[speed:N]] · [[key:F5]] · [[key:ctrl+c]]",
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
        # Botão inserir + hint marcadores
        "insert_btn":     "📥 Inserir Marcador ▾",
        "marker_hint":    "[[pause:N]] · [[speed:N]] · [[key:F5]] · [[key:ctrl+c]]",
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


class StatusStyle(enum.StrEnum):
    IDLE    = "secondary"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR   = "danger"


def platform_mono_font(size: int = 13) -> tuple[str, int]:
    fonts = {"Windows": "Consolas", "Darwin": "Menlo"}
    return (fonts.get(platform.system(), "Monospace"), size)
