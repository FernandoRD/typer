# ⚡ AutoTyper

AutoTyper é uma ferramenta de desktop desenvolvida em Python que simula digitação de texto em qualquer janela ativa do sistema operacional. Nasceu da necessidade prática de gerenciar servidores remotos cujos protocolos de conexão não permitem copiar e colar grandes volumes de texto (KVM over IP, iDRAC, iLO, console serial, etc.) — dando autonomia ao analista sem depender do administrador do servidor remoto.

---

## ✨ Funcionalidades

| Funcionalidade | Descrição |
| --- | --- |
| Digitação automatizada | Digita qualquer texto em qualquer campo ou janela ativa |
| Velocidade configurável | Ajuste o intervalo entre teclas em milissegundos |
| Marcadores embutidos | `[[pause:N]]`, `[[speed:N]]`, `[[key:ctrl+c]]` controlam o comportamento mid-texto |
| Menu de inserção | Dropdown para inserir marcadores de timing, teclas de função, modificadores e combinações |
| Atraso inicial | Tempo de espera antes de começar, permitindo trocar para a janela de destino |
| Modo por linha | Pausa após cada linha e aguarda ENTER para avançar (útil para scripts interativos) |
| Pausa / Retomada | Botão PAUSE suspende e retoma sem perder o ponto atual |
| Parada de emergência | Tecla `ESC` ou botão STOP interrompem em ≤ 50ms |
| Gestão de arquivos | Abre e salva arquivos `.txt` |
| Interface moderna | Tema escuro com `ttkbootstrap`; bilingue EN/PT com troca em tempo real |
| Multiplataforma | Windows, macOS e Linux (X11) |
| Modo headless | Operação sem GUI via linha de comando |

---

## ⚙️ Requisitos

- Python **3.11** ou superior
- [`ttkbootstrap`](https://ttkbootstrap.readthedocs.io/) >= 1.20.0
- [`pynput`](https://pynput.readthedocs.io/) >= 1.7.0

---

## 🚀 Instalação

```bash
git clone https://github.com/seu-usuario/typer.git
cd typer
python -m venv venv
venv\Scripts\activate     # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

---

## 📋 Como Usar

### Interface gráfica

```bash
python typer.py
# ou
python -m autotyper
```

1. Cole o texto na área de texto ou use **📂 Open File** para carregar um `.txt`.
2. Configure **intervalo entre teclas** e **tempo de espera** inicial.
3. Clique em **🚀 START TYPING** e troque imediatamente para a janela de destino.
4. Para interromper: pressione `ESC` ou clique em **🛑 STOP**.

### Marcadores embutidos

Insira marcadores diretamente no texto para controlar o comportamento durante a digitação:

| Marcador | Efeito |
| --- | --- |
| `[[pause:2]]` | Pausa de 2 segundos neste ponto |
| `[[speed:200]]` | Altera o intervalo para 200 ms a partir daqui |
| `[[speed:reset]]` | Restaura o intervalo original |
| `[[key:F5]]` | Pressiona a tecla F5 |
| `[[key:ctrl+c]]` | Executa o atalho Ctrl+C |
| `[[key:enter]]` | Pressiona Enter |

Use o botão **📥 Inserir Marcador ▾** para inserir qualquer marcador via menu.

### Modo headless (sem GUI)

```bash
python typer.py --headless --file script.txt --interval 80 --wait 3
```

| Flag | Curta | Padrão | Descrição |
| --- | --- | --- | --- |
| `--file` | `-f` | — | Arquivo de texto a digitar (obrigatório em headless) |
| `--interval` | `-i` | `100` | Intervalo entre teclas (ms) |
| `--wait` | `-w` | `2` | Segundos de espera antes de iniciar |
| `--lang` | `-l` | `en` | Idioma da UI (`en` / `pt`) |
| `--headless` | — | — | Executa sem janela gráfica |

---

## 📁 Estrutura do Projeto

```text
typer.py               — shim de compatibilidade (delega para autotyper)
autotyper/
├── __init__.py        — pacote
├── __main__.py        — entry point de `python -m autotyper`
├── config.py          — traduções, perfis de velocidade, StatusStyle
├── markers.py         — parsing de marcadores embutidos
├── engine.py          — TypingEngine + TypingCallbacks (sem dependência de Tkinter)
├── app.py             — TyperApp (GUI, Tkinter/ttkbootstrap)
└── cli.py             — parse_args() + run_headless()
requirements.txt
```

---

## 🐧 Nota para Usuários Linux (Wayland)

> **⚠️ Importante:** A biblioteca `pynput` não funciona corretamente em sessões **Wayland**. A aplicação detecta automaticamente esse ambiente e exibe um aviso na interface.
>
> Para uso pleno, encerre a sessão e inicie uma nova usando **X11** (geralmente rotulado como "X.Org" na tela de login).

---

## 📄 Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).
