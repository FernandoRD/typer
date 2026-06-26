# Referência Técnica — AutoTyper

## Visão Geral

AutoTyper simula pressionamentos de tecla em qualquer janela ativa do SO, digitando texto caractere por caractere com intervalo configurável. Suporta marcadores embutidos no texto (`[[pause:N]]`, `[[speed:N]]`, `[[key:F5]]`) e modo por linha para scripts interativos.

---

## Estrutura do Pacote

```text
typer.py               — shim de compatibilidade: importa e executa autotyper.__main__.main()
autotyper/
├── __init__.py        — docstring do pacote, sem exports
├── __main__.py        — entry point: parse_args() → run_headless() ou TyperApp.mainloop()
├── config.py          — TRANSLATIONS, SPEED_PROFILES, StatusStyle, platform_mono_font()
├── markers.py         — Instruction, parse_instructions(), _MARKER_RE, _SPECIAL_KEYS
├── engine.py          — TypingEngine, TypingCallbacks (sem dependência de tkinter)
├── app.py             — TyperApp (GUI, tkinter/ttkbootstrap)
└── cli.py             — parse_args(), run_headless()
```

---

## Módulos

### `autotyper/config.py`

| Símbolo | Tipo | Descrição |
| --- | --- | --- |
| `TRANSLATIONS` | `dict[str, dict[str, str]]` | Todas as strings visíveis ao usuário em EN e PT |
| `SPEED_PROFILES` | `list[tuple[int \| None, str]]` | Pares `(ms, chave_tradução)` para o combo de perfil |
| `StatusStyle` | `enum.StrEnum` | Constantes de estilo ttkbootstrap: `IDLE`, `SUCCESS`, `WARNING`, `ERROR` |
| `platform_mono_font(size)` | `func → tuple[str, int]` | Fonte monoespaçada por plataforma (Consolas / Menlo / Monospace) |

---

### `autotyper/markers.py`

| Símbolo | Tipo | Descrição |
| --- | --- | --- |
| `Instruction` | `TypeAlias` | `tuple[str, str \| float \| None]` — um item da lista de instruções |
| `parse_instructions(text)` | `func → list[Instruction]` | Converte texto bruto em lista de instruções tipadas |
| `_MARKER_RE` | `re.Pattern` | Regex que reconhece `[[diretiva:valor]]` |
| `_SPECIAL_KEYS` | `dict[str, Key]` | Mapa de nome de tecla → constante pynput.Key |

#### Formato de instrução

| Tupla | Significado |
| --- | --- |
| `('char', str)` | Digitar este caractere |
| `('pause', float)` | Aguardar N segundos (só aceito se N > 0) |
| `('speed', float)` | Alterar intervalo para N ms (só aceito se N > 0) |
| `('speed', None)` | Restaurar intervalo base |
| `('key', str)` | Pressionar tecla ou combinação (`'ctrl+c'`, `'F5'`, `'win'`) |

Marcadores com valor numérico ≤ 0, formato inválido ou diretiva desconhecida são silenciosamente descartados.

---

### `autotyper/engine.py`

#### `TypingCallbacks`

Dataclass com todos os callbacks opcionais. Todos são chamados da **thread worker** — o chamador é responsável por despachar para a thread principal se necessário.

| Campo | Assinatura | Quando |
| --- | --- | --- |
| `on_session_start` | `(dt_str: str, total: int)` | Antes do wait inicial |
| `on_waiting` | `(wait_s: float)` | Ao iniciar o período de espera |
| `on_progress` | `(done: int, total: int)` | A cada lote de chars digitados (modo normal) |
| `on_chunk_done` | `(cur: int, total: int)` | Após cada linha (modo chunk) |
| `on_done` | `(stopped: bool, done: int, total: int)` | Ao encerrar a sessão |
| `on_error` | `(e: Exception)` | Em caso de exceção no worker |
| `on_stop_requested` | `()` | Quando ESC é pressionado dentro do engine |

#### `TypingEngine`

| Membro | Descrição |
| --- | --- |
| `start(text, wait_s, interval_s, chunk_mode, callbacks)` | Inicia o worker em daemon thread. `interval_s` é em **segundos** |
| `stop()` | Sinaliza parada imediata (idempotente) |
| `toggle_pause() → bool` | Alterna pause/resume; retorna `True` se agora pausado |
| `is_typing: bool` | Propriedade — True enquanto o worker estiver ativo |
| `is_paused: bool` | Propriedade — True enquanto pausado |

**Nota de contrato:** `interval_s` está em segundos. Converta ms → s antes de chamar (`interval_ms / 1000.0`).

---

### `autotyper/app.py` — `TyperApp`

| Método | Thread | Descrição |
| --- | --- | --- |
| `__init__(lang, initial_file, interval_ms, wait_s)` | Principal | Constrói a janela; `interval_ms` é em ms (convertido internamente) |
| `start_typing_thread()` | Principal | Lê widgets, constrói `TypingCallbacks`, chama `engine.start()` |
| `request_stop()` | Qualquer | Para o engine; seguro chamar de qualquer thread |
| `_toggle_pause()` | Principal | Delega ao engine e atualiza botão |
| `_on_chunk_done(cur, total)` | Principal (via after) | Atualiza log, status e barra de progresso após cada linha |
| `_on_typing_error(e)` | Principal (via after) | Exibe erro no status e no log |
| `_on_typing_done(stopped, done, total)` | Principal (via after) | Atualiza log, status e reseta UI |
| `update_status(text, style)` | Qualquer | Thread-safe via `after(0, ...)` |
| `t(key, **kwargs)` | Qualquer | Lookup de tradução; retorna `[chave]` se ausente |

**Regra de thread safety:** nenhum widget é lido ou escrito de fora da thread principal. Os callbacks recebem dados primitivos e delegam modificações de UI via `self.after(0, ...)`.

---

### `autotyper/cli.py`

| Símbolo | Descrição |
| --- | --- |
| `parse_args() → Namespace` | Argparse com flags `--file`, `--interval`, `--wait`, `--lang`, `--headless` |
| `run_headless(file_path, interval_ms, wait_s)` | Modo sem GUI; `interval_ms` é em ms (dividido por 1000 antes de passar ao engine) |

---

## Modelo de Threading

```text
Thread principal (Tkinter event loop)
│
│  engine.start(...)
│       └─── Thread worker (daemon)
│                ├── _run()
│                │    ├── _type_all()      — normal mode
│                │    └── _type_by_chunks() — chunk mode
│                └── callbacks → self.after(0, fn) → thread principal
│
│  _stop_event.set() / _pause_event.clear()   ← UI → worker
│  self.after(0, callback)                    ← worker → UI
```

| Evento | Estado inicial | Semântica |
| --- | --- | --- |
| `_stop_event` | cleared | `set()` = parar imediatamente |
| `_pause_event` | set | `set()` = rodando; `clear()` = pausado |

`_interruptible_sleep(seconds)` dorme em chunks de ≤ 20ms, testando `_stop_event` e `_pause_event` a cada iteração. Latência máxima de reação ao stop/pause: ~50ms.

---

## Marcadores — Fluxo de Parsing

```text
texto bruto
    ↓ parse_instructions(text)
list[Instruction]
    ↓ engine._type_all() / _type_by_chunks()
ações de teclado + sleeps
```

`[[speed:N]]` armazena N em ms na instrução. O engine converte para segundos no momento de aplicar (`val / 1000.0`), mantendo `base_interval` (em s) como referência para `[[speed:reset]]`.

---

## Perfis de Velocidade

```python
SPEED_PROFILES = [
    (200,  "prof_slow"),    # Lento   / Slow
    (100,  "prof_normal"),  # Normal
    (50,   "prof_fast"),    # Rápido  / Fast
    (10,   "prof_turbo"),   # Turbo
    (None, "prof_custom"),  # Personalizado / Custom
]
```

Selecionar um perfil atualiza o campo de intervalo. Editar o campo manualmente seleciona "Custom" se o valor não corresponder a nenhum perfil.

---

## Modo Linha por Linha (Chunk Mode)

1. `parse_instructions` retorna a lista completa (incluindo `('char', '\n')`).
2. `_type_by_chunks` divide a lista em sub-listas por `\n`.
3. Após cada sub-lista, dispara `on_chunk_done` e bloqueia em `_wait_for_enter_or_esc`.
4. ENTER → pressiona Enter no teclado e avança para a próxima linha; ESC → `request_stop()`.

---

## Fluxo de Estados

```text
[IDLE]
  │  START
  ▼
[WAITING]   — _interruptible_sleep(wait_s)
  │
  ▼
[TYPING]    — _type_all() ou _type_by_chunks()
  ├── ESC / STOP ──→ [STOPPED]
  ├── PAUSE ────────→ [PAUSED] ──→ RESUME ──→ [TYPING]
  └── fim do texto ──→ [DONE] ──→ [IDLE]
```

---

## Compatibilidade de Plataformas

| Plataforma | Status | Observação |
| --- | --- | --- |
| Windows 10/11 | Totalmente suportado | Fonte: Consolas |
| macOS | Suportado | Requer permissão de Acessibilidade; fonte: Menlo |
| Linux X11 | Suportado | Fonte: Monospace |
| Linux Wayland | Não suportado | Aviso exibido automaticamente; pynput não funciona |

---

## Notas de Compatibilidade de Biblioteca

### ttkbootstrap >= 1.20.0 — ScrolledText

`ScrolledText` passou a herdar de `Frame` (não mais de `Text`). O widget interno é acessado via `.text`:

```python
self._log_text.text.configure(state="disabled")   # correto
self._log_text.text.insert("end", msg)
self._log_text.configure(state="disabled")        # TclError — Frame não tem state
```

Import path: `from ttkbootstrap.widgets.scrolled import ScrolledText`.
