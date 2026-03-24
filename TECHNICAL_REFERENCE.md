# Referência Técnica — AutoTyper v2

## Visão Geral

O AutoTyper é uma aplicação de desktop single-file (`typer.py`) construída em Python. Ele simula pressionamentos de tecla em qualquer janela ativa do sistema operacional, digitando o texto carregado caractere por caractere com intervalo configurável.

---

## Arquitetura

```
typer.py
│
├── Módulo
│   ├── TRANSLATIONS        — dict com todas as strings PT/EN
│   ├── SPEED_PROFILES      — lista de perfis (ms, chave_de_tradução)
│   ├── StatusStyle         — constantes de estilo de status
│   ├── platform_mono_font()— fonte monoespaçada por plataforma
│   ├── run_headless()      — modo CLI sem interface gráfica
│   └── _parse_args()       — argparse
│
└── TyperApp (ttk.Window)
    │
    ├── UI (thread principal Tkinter)
    │   ├── _build_header()     — título, idioma, Open/Save
    │   ├── _build_settings()   — perfil, intervalo, espera, chunk, Start/Stop/Pause
    │   ├── _check_wayland()    — aviso condicional Linux/Wayland
    │   ├── _build_text_area()  — ScrolledText + bind KeyRelease
    │   ├── _build_char_counter() — label de contagem de caracteres
    │   ├── _build_progress()   — Progressbar
    │   ├── _build_log()        — ScrolledText readonly (log de sessão)
    │   └── _build_status_bar() — label de status inferior
    │
    └── Thread de digitação (daemon)
        ├── _type_text()        — orquestra espera, tipo, finally
        ├── _type_all()         — loop char-a-char com progresso
        ├── _type_by_chunks()   — loop linha-a-linha
        ├── _wait_for_enter_or_esc() — listener temporário em chunk mode
        ├── _wait_if_paused()   — bloqueia enquanto pausado
        └── _interruptible_sleep()  — sleep fragmentado, honra stop/pause
```

---

## Dependências

| Biblioteca | Versão mínima | Uso |
| --- | --- | --- |
| `ttkbootstrap` | 1.10.0 | Framework de UI (widgets + temas) |
| `pynput` | 1.7.0 | Controle e monitoramento de teclado |
| `tkinter` | stdlib | Base da UI |
| `threading` | stdlib | Thread de digitação, eventos de controle |
| `time` | stdlib | Intervalos e sleep |
| `argparse` | stdlib | Flags de linha de comando |
| `platform` | stdlib | Detecção de SO para fonte |
| `os` | stdlib | Variáveis de ambiente (Wayland) |
| `sys` | stdlib | Detecção de plataforma e saída |
| `datetime` | stdlib | Timestamps no log de sessão |

---

## Modelo de Threading

A aplicação usa dois `threading.Event` para coordenar a thread de digitação com a UI:

| Evento | Estado inicial | Significado |
| --- | --- | --- |
| `_stop_event` | cleared | `set()` = parar imediatamente |
| `_pause_event` | set | `set()` = rodando; `clear()` = pausado |

### Comunicação entre threads

| Direção | Mecanismo |
| --- | --- |
| UI → thread | `_stop_event.set()` / `_pause_event.clear()` |
| Thread → UI | `self.after(0, callback)` — agenda na thread principal |

O texto e os valores de configuração são capturados na thread principal dentro de `start_typing_thread()` e passados como argumentos para a thread secundária. **Nenhum widget é lido de fora da thread principal.**

---

## Internacionalização (i18n)

Todas as strings visíveis ao usuário estão em `TRANSLATIONS["en"]` e `TRANSLATIONS["pt"]`. O método `t(key, **kwargs)` faz a lookup e formatação:

```python
self.t("status_typing", done=50, total=200)
# → "Typing… 50/200 chars"  (EN)
# → "Digitando… 50/200 caracteres"  (PT)
```

A troca de idioma dispara `_refresh_ui_text()`, que reconfigura todos os widgets sem recriar a janela.

---

## Referência da Classe `TyperApp`

### `__init__(self, lang, initial_file, interval_ms, wait_s)`

| Parâmetro | Tipo | Padrão | Descrição |
| --- | --- | --- | --- |
| `lang` | `str` | `"en"` | Idioma inicial (`"en"` ou `"pt"`) |
| `initial_file` | `str \| None` | `None` | Arquivo a carregar ao iniciar |
| `interval_ms` | `int` | `100` | Intervalo inicial entre teclas (ms) |
| `wait_s` | `float` | `2.0` | Espera inicial antes de digitar (s) |

---

### Métodos de controle

| Método | Thread | Descrição |
| --- | --- | --- |
| `start_typing_thread()` | Principal | Valida entrada, captura texto, inicia thread |
| `request_stop()` | Qualquer | Sinaliza parada (idempotente) |
| `_toggle_pause()` | Principal | Alterna entre pause/resume |
| `_reset_ui()` | Principal (via after) | Restaura botões ao estado inicial |

---

### Métodos da thread de digitação

| Método | Descrição |
| --- | --- |
| `_type_text(text, wait_s, interval_ms, chunk_mode)` | Orquestra a sessão de digitação |
| `_type_all(text, interval_ms, total)` | Digita todo o texto de uma vez |
| `_type_by_chunks(text, interval_ms)` | Digita linha a linha, aguardando ENTER |
| `_wait_for_enter_or_esc()` | Bloqueia até ENTER (True) ou ESC (False) |
| `_wait_if_paused()` | Bloqueia enquanto pausado; False se parado |
| `_interruptible_sleep(seconds)` | Sleep fragmentado em chunks de 20ms |

---

### `_interruptible_sleep(seconds)`

Em vez de `time.sleep(interval)` simples (que bloquearia a resposta ao stop/pause), o sleep é fragmentado:

```
while tempo não esgotou:
    se stop_event → retorna False
    se pausado    → espera 50ms e re-testa (sem consumir o budget)
    senão         → dorme min(20ms, tempo_restante)
retorna True
```

Isso garante que ao pressionar ESC ou STOP, a parada ocorre em no máximo ~50ms.

---

## Perfis de Velocidade

```python
SPEED_PROFILES = [
    (200,  "prof_slow"),    # Lento   / Slow
    (100,  "prof_normal"),  # Normal
    (50,   "prof_fast"),    # Rápido  / Fast
    (10,   "prof_turbo"),   # Turbo
    (None, "prof_custom"),  # Personalizado / Custom (entrada livre)
]
```

Ao selecionar um perfil, o campo de intervalo é atualizado automaticamente. Ao editar o campo manualmente, o combo seleciona "Custom" se o valor não corresponder a nenhum perfil.

---

## Modo Linha por Linha (Chunk Mode)

Quando ativado, o texto é dividido por `\n`. Após cada linha:

1. O status exibe a instrução para pressionar ENTER ou ESC.
2. Um `pynput.Listener` temporário aguarda a tecla.
3. ENTER → a linha seguinte começa; ESC → `request_stop()`.

Isso permite digitar scripts interativos onde cada linha requer confirmação visual.

---

## Modo CLI (Headless)

```bash
python typer.py --file script.txt --interval 80 --wait 3 --headless
```

| Flag | Curta | Tipo | Padrão | Descrição |
| --- | --- | --- | --- | --- |
| `--file` | `-f` | str | — | Arquivo de texto a digitar |
| `--interval` | `-i` | float | 100 | Intervalo entre teclas (ms) |
| `--wait` | `-w` | float | 2 | Espera antes de digitar (s) |
| `--lang` | `-l` | str | en | Idioma da UI (`en`/`pt`) |
| `--headless` | — | flag | — | Sem GUI; requer `--file` |

Em modo headless, o Tkinter não é iniciado. O texto é digitado diretamente usando `pynput.Controller` na thread principal. ESC e Ctrl+C interrompem a operação.

---

## Compatibilidade de Plataformas

| Plataforma | Status | Observação |
| --- | --- | --- |
| Windows 10/11 | Totalmente suportado | Fonte: Consolas |
| macOS | Suportado | Requer permissão de Acessibilidade; fonte: Menlo |
| Linux X11 | Suportado | Fonte: Monospace |
| Linux Wayland | Não suportado | Aviso exibido automaticamente |

---

## Fluxo de Estados

```text
[IDLE]
  │  clique em START / python typer.py --headless
  ▼
[WAITING]    — _interruptible_sleep(wait_s)
  │
  ▼
[TYPING]     — loop de digitação (_type_all ou _type_by_chunks)
  │  ESC / STOP
  ├──────────────────→ [STOPPED]
  │  PAUSE
  ├──────────────────→ [PAUSED] → RESUME → [TYPING]
  │  texto esgotado
  ▼
[DONE]
  └──→ [IDLE]
```
