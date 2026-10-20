"""Configuration constants: translations, speed profiles, status styles, fonts."""

import enum
import platform
import unicodedata
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
        "keyboard_layout_label": "Keyboard layout (Wayland):",
        "keyboard_layout_us": "US (English)",
        "keyboard_layout_abnt2": "ABNT2 (Portuguese - Brazil)",
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
        "ai_prompt_label":  "Describe what you want drafted (commands, script, config…):",
        "ai_provider_label": "Provider:",
        "ai_model_label":   "Model:",
        "ai_effort_label":  "Effort:",
        "ai_preview_label": "Preview (not inserted or typed):",
        "ai_generate_btn":  "✨ Generate",
        "ai_generating_btn":"⏳ Generating…",
        "ai_cancel_btn":    "Cancel",
        "ai_apply_btn":     "Insert generated output",
        "ai_hint":          "Generation stays in this preview. Review it, then explicitly insert it into the editor.",
        "ai_generating":    "Generating with AI…",
        "ai_checking":      "Checking local provider status…",
        "ai_cancelling":    "Cancelling AI generation…",
        "ai_done":          "AI generation complete — review the preview, then explicitly insert it.",
        "ai_applied":       "Generated output inserted into the editor. Review before typing.",
        "ai_preview_rejected": "Generated output was not inserted: automation markers or unsafe control characters are not allowed.",
        "ai_provider_unavailable": "{provider} is unavailable on this device.",
        "ai_provider_unauthenticated": "{provider} is not authenticated locally.",
        "ai_provider_unsafe": "{provider} is unavailable because safe execution cannot be confirmed.",
        "ai_provider_ready": "{provider} is ready. Authentication is checked locally only.",
        "ai_err_empty":     "Error: describe what you want the AI to type first.",
        "ai_err_auth":      "Error: the selected provider is not authenticated locally.",
        "ai_err_lib":       "Error: the selected provider is unavailable.",
        "ai_err_api":       "AI error: {e}",
        # Bitwarden vault
        "bw_title":         " 🔐 Bitwarden ",
        "bw_email_label":   "Email:",
        "bw_pw_label":      "Master password:",
        "bw_unlock_btn":    "🔓 Sign in",
        "bw_lock_btn":      "🔒 Lock",
        "bw_search_label":  "Search credential:",
        "bw_search_btn":    "🔍 Search",
        "bw_type_btn":      "⌨ Type password",
        "bw_totp_btn":      "🔢 Show OTP",
        "bw_passkey_btn":   "🔑 Credential passkey details",
        "bw_passkeys":      "Passkeys: {n}",
        "bw_passkey_details_none": "Credential passkey details appear here on request; private key material remains protected.",
        "bw_passkey_details_title": "Credential passkey details (private material protected):",
        "bw_passkey_number": "Passkey {n}",
        "bw_passkey_credential_id": "Credential ID: {value}",
        "bw_passkey_rp_id": "RP ID/domain: {value}",
        "bw_passkey_user_handle": "User handle: {value}",
        "bw_metadata_none": "Passkey metadata and OTP appear here only on request.",
        "bw_totp_value":    "Current OTP: {code}",
        "bw_hint":          "Sign in with your Bitwarden email and master password. Two-factor or device verification must be completed in the Bitwarden CLI. Passwords are typed directly; OTPs are shown only when requested and are not saved.",
        "bw_unlocking":     "Signing in to vault…",
        "bw_unlocked":      "Vault unlocked.",
        "bw_locked":        "Vault locked.",
        "bw_searching":     "Searching…",
        "bw_found":         "{n} credential(s) found.",
        "bw_none":          "No credentials matched.",
        "bw_fetching":      "Fetching password…",
        "bw_fetching_totp": "Fetching current OTP…",
        "bw_busy":         "Bitwarden is busy or typing is active. Wait for the current operation to finish.",
        "bw_fetching_passkey": "Fetching credential passkey details…",
        "bw_totp_ready":    "Current OTP displayed.",
        "bw_passkey_ready": "Credential passkey details displayed.",
        "bw_typing_pw":     "Typing password into the focused window…",
        "bw_err_lib":       "Error: Bitwarden CLI ('bw') not found on PATH. Install it first.",
        "bw_err_empty_email": "Error: enter your Bitwarden email.",
        "bw_err_locked":    "Error: unlock the vault first.",
        "bw_err_empty_pw":  "Error: enter your master password.",
        "bw_err_empty_q":   "Error: type something to search for.",
        "bw_err_no_sel":    "Error: select a credential first.",
        "bw_err_no_totp":   "Error: the selected credential has no OTP.",
        "bw_err_no_passkey": "Error: the selected credential has no passkey.",
        "bw_err_login":     "Error: Bitwarden is not authenticated. Enter your email and master password, then sign in.",
        "bw_err_2fa":       "Error: Bitwarden requires two-factor authentication. Complete login in the Bitwarden CLI, then return here.",
        "bw_err_device_verification": "Error: Bitwarden requires new-device verification. Complete it in the Bitwarden CLI, then return here.",
        "bw_err_identity":  "Error: the Bitwarden CLI is signed in with a different or unverifiable account.",
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
        "keyboard_layout_label": "Layout do teclado (Wayland):",
        "keyboard_layout_us": "US (Inglês)",
        "keyboard_layout_abnt2": "ABNT2 (Português - Brasil)",
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
        "ai_prompt_label":  "Descreva o que quer gerar (comandos, script, configuração…):",
        "ai_provider_label": "Provedor:",
        "ai_model_label":   "Modelo:",
        "ai_effort_label":  "Esforço:",
        "ai_preview_label": "Prévia (não inserida nem digitada):",
        "ai_generate_btn":  "✨ Gerar",
        "ai_generating_btn":"⏳ Gerando…",
        "ai_cancel_btn":    "Cancelar",
        "ai_apply_btn":     "Inserir saída gerada",
        "ai_hint":          "A geração fica nesta prévia. Revise e então insira-a explicitamente no editor.",
        "ai_generating":    "Gerando com IA…",
        "ai_checking":      "Verificando o estado local do provedor…",
        "ai_cancelling":    "Cancelando geração da IA…",
        "ai_done":          "Geração da IA concluída — revise a prévia e insira-a explicitamente.",
        "ai_applied":       "Saída gerada inserida no editor. Revise antes de digitar.",
        "ai_preview_rejected": "A saída gerada não foi inserida: marcadores de automação ou controles inseguros não são permitidos.",
        "ai_provider_unavailable": "{provider} está indisponível neste dispositivo.",
        "ai_provider_unauthenticated": "{provider} não está autenticado localmente.",
        "ai_provider_unsafe": "{provider} está indisponível porque a execução segura não pôde ser confirmada.",
        "ai_provider_ready": "{provider} está pronto. A autenticação é verificada somente localmente.",
        "ai_err_empty":     "Erro: descreva primeiro o que a IA deve digitar.",
        "ai_err_auth":      "Erro: o provedor selecionado não está autenticado localmente.",
        "ai_err_lib":       "Erro: o provedor selecionado está indisponível.",
        "ai_err_api":       "Erro da IA: {e}",
        # Cofre Bitwarden
        "bw_title":         " 🔐 Bitwarden ",
        "bw_email_label":   "E-mail:",
        "bw_pw_label":      "Senha mestra:",
        "bw_unlock_btn":    "🔓 Entrar",
        "bw_lock_btn":      "🔒 Bloquear",
        "bw_search_label":  "Buscar credencial:",
        "bw_search_btn":    "🔍 Buscar",
        "bw_type_btn":      "⌨ Digitar senha",
        "bw_totp_btn":      "🔢 Ver OTP",
        "bw_passkey_btn":   "🔑 Detalhes da chave da credencial",
        "bw_passkeys":      "Chaves de acesso: {n}",
        "bw_passkey_details_none": "Os detalhes da chave de acesso da credencial aparecem aqui sob demanda; o material privado permanece protegido.",
        "bw_passkey_details_title": "Detalhes da chave de acesso da credencial (material privado protegido):",
        "bw_passkey_number": "Chave de acesso {n}",
        "bw_passkey_credential_id": "ID da credencial: {value}",
        "bw_passkey_rp_id": "RP ID/domínio: {value}",
        "bw_passkey_user_handle": "User handle: {value}",
        "bw_metadata_none": "Metadados de chaves de acesso e OTP aparecem aqui somente sob demanda.",
        "bw_totp_value":    "OTP atual: {code}",
        "bw_hint":          "Entre com seu e-mail Bitwarden e senha mestra. A autenticação em dois fatores ou verificação de dispositivo deve ser concluída na CLI do Bitwarden. Senhas são digitadas diretamente; OTPs só aparecem sob demanda e não são salvos.",
        "bw_unlocking":     "Entrando no cofre…",
        "bw_unlocked":      "Cofre desbloqueado.",
        "bw_locked":        "Cofre bloqueado.",
        "bw_searching":     "Buscando…",
        "bw_found":         "{n} credencial(is) encontrada(s).",
        "bw_none":          "Nenhuma credencial encontrada.",
        "bw_fetching":      "Obtendo senha…",
        "bw_fetching_totp": "Obtendo OTP atual…",
        "bw_busy":         "O Bitwarden está ocupado ou a digitação está ativa. Aguarde a operação atual terminar.",
        "bw_fetching_passkey": "Obtendo detalhes da chave da credencial…",
        "bw_totp_ready":    "OTP atual exibido.",
        "bw_passkey_ready": "Detalhes da chave da credencial exibidos.",
        "bw_typing_pw":     "Digitando a senha na janela em foco…",
        "bw_err_lib":       "Erro: CLI do Bitwarden ('bw') não encontrada no PATH. Instale-a primeiro.",
        "bw_err_empty_email": "Erro: informe seu e-mail Bitwarden.",
        "bw_err_locked":    "Erro: desbloqueie o cofre primeiro.",
        "bw_err_empty_pw":  "Erro: informe a senha mestra.",
        "bw_err_empty_q":   "Erro: digite algo para buscar.",
        "bw_err_no_sel":    "Erro: selecione uma credencial primeiro.",
        "bw_err_no_totp":   "Erro: a credencial selecionada não tem OTP.",
        "bw_err_no_passkey": "Erro: a credencial selecionada não tem chave de acesso.",
        "bw_err_login":     "Erro: Bitwarden não está autenticado. Informe e-mail e senha mestra e entre.",
        "bw_err_2fa":       "Erro: Bitwarden exige autenticação em dois fatores. Conclua o login na CLI do Bitwarden e volte aqui.",
        "bw_err_device_verification": "Erro: Bitwarden exige verificação de novo dispositivo. Conclua-a na CLI do Bitwarden e volte aqui.",
        "bw_err_identity":  "Erro: a CLI do Bitwarden está autenticada em uma conta diferente ou não verificável.",
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


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str
    supports_adaptive: bool          # accepts thinking={"type": "adaptive"}
    effort_levels: tuple[str, ...]   # supported output_config.effort values

# System prompt shared by both languages.  Generated text first goes through a
# non-actionable preview, then needs an explicit user insertion before typing.
_AI_SYSTEM_BASE = """\
You generate text that an auto-typing tool will type keystroke-by-keystroke \
into a draft for an auto-typing tool. The main use case is remote server \
consoles (KVM over IP, iDRAC, iLO, serial) where the clipboard and paste are \
unavailable, so everything must be typed.

OUTPUT RULES (critical):
- Output ONLY the exact text/commands to be typed. No explanations, no \
commentary, no surrounding prose.
- Never wrap the output in Markdown code fences (```), quotes, or headings — \
they would be typed literally.
- The output is reviewed and explicitly inserted by the user before it can be \
typed. Each newline may later become an Enter keypress.
- Prefer POSIX-portable commands unless the user specifies an OS or shell.

Never emit AutoTyper automation markers such as [[pause:N]], [[speed:N]], or \
[[key:name]]. They are rejected by the application.

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


def normalize_ai_output(text: str) -> str:
    """Use one newline representation in previews and the typing editor."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def is_safe_ai_output(text: str) -> bool:
    """Reject text that could turn a reviewed draft into typing automation."""
    if not isinstance(text, str):
        return False
    text = normalize_ai_output(text)
    if "[[" in text or "]]" in text:
        return False
    return all(
        char in "\n\t" or unicodedata.category(char) not in {"Cc", "Cf"}
        for char in text
    )
