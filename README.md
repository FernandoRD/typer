# ⚡ AutoTyper

AutoTyper é uma ferramenta de desktop desenvolvida em Python que simula digitação de texto em qualquer janela ativa do sistema operacional. Nasceu da necessidade prática de gerenciar servidores remotos cujos protocolos de conexão não permitem copiar e colar grandes volumes de texto (KVM over IP, iDRAC, iLO, console serial, etc.) — dando autonomia ao analista sem depender do administrador do servidor remoto.

---

## ✨ Funcionalidades

| Funcionalidade | Descrição |
| --- | --- |
| Digitação automatizada | Digita qualquer texto em qualquer campo ou janela ativa |
| **Assistente IA** | Descreva em linguagem natural e a IA (Claude) gera o texto/comandos a digitar, opcionalmente com marcadores de automação |
| **Seletor de modelo** | Escolha entre Opus 4.8, Sonnet 5 ou Haiku 4.5 |
| **Login por browser** | Reaproveita o login OAuth do Claude Code / plugin do VS Code — sem exportar chave de API |
| **Cofre Bitwarden** | Busca credenciais no seu cofre Bitwarden (via `bw` CLI) e digita a senha direto na janela em foco — sem exibir nem salvar o segredo |
| Velocidade configurável | Ajuste o intervalo entre teclas em milissegundos |
| Marcadores embutidos | `[[pause:N]]`, `[[speed:N]]`, `[[key:ctrl+c]]` controlam o comportamento mid-texto |
| Menu de inserção | Dropdown para inserir marcadores de timing, teclas de função, modificadores e combinações (agrupadas por uso: área de transferência, terminal, janela/sistema, tecla Windows e troca de TTY no Linux) |
| Atraso inicial | Tempo de espera antes de começar, permitindo trocar para a janela de destino |
| Modo por linha | Pausa após cada linha e aguarda ENTER para avançar (útil para scripts interativos) |
| Pausa / Retomada | Botão PAUSE suspende e retoma sem perder o ponto atual |
| Parada de emergência | Tecla `ESC` ou botão STOP interrompem em ≤ 50ms |
| Gestão de arquivos | Abre e salva arquivos `.txt` |
| Interface moderna | Tema escuro com `ttkbootstrap`; painéis recolhíveis (IA, Bitwarden, Log) para uma janela compacta; rodapé de altura fixa; bilingue EN/PT com troca em tempo real |
| Multiplataforma | Windows, macOS e Linux (X11) |
| Modo headless | Operação sem GUI via linha de comando |

---

## ⚙️ Requisitos

- Python **3.11** ou superior
- [`ttkbootstrap`](https://ttkbootstrap.readthedocs.io/) >= 1.20.0
- [`pynput`](https://pynput.readthedocs.io/) >= 1.7.0
- [`anthropic`](https://github.com/anthropics/anthropic-sdk-python) >= 0.40.0 *(opcional — só para o Assistente IA)*
- [**Bitwarden CLI (`bw`)**](https://bitwarden.com/help/cli/) *(opcional — só para o Cofre Bitwarden; instalação externa, ver abaixo)*

---

## 🚀 Instalação

```bash
git clone git@gitea.durso.tec.br:fernando/typer.git
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
| `[[key:ctrl+alt+del]]` | Envia Ctrl+Alt+Del (útil em KVM/iDRAC/iLO) |
| `[[key:enter]]` | Pressiona Enter |

Uma combinação (`[[key:mod+mod+tecla]]`) pode misturar modificadores com qualquer tecla especial ou caractere simples. Nomes de teclas aceitam aliases comuns (`del`, `pgup`, `pgdn`, `return`, `escape`, `ins`). Use o botão **📥 Inserir Marcador ▾** para inserir qualquer marcador via menu.

### 🤖 Assistente IA

No painel **🤖 Assistente IA**, descreva em linguagem natural o que você quer digitar (ex.: *"script de backup do /etc com rotação de 7 dias"*, *"comandos para diagnosticar rede que não sobe"*). A IA (Claude) gera o texto/comandos — podendo usar os marcadores de automação quando fizer sentido — e o resultado aparece **no editor para revisão**. Você revisa e clica em **INICIAR** normalmente. Ideal para consoles remotos onde não há copiar-colar.

- **Seletor de modelo:** escolha **Opus 4.8** (mais capaz), **Sonnet 5** (equilíbrio) ou **Haiku 4.5** (mais rápido/leve) no combo ao lado do campo.
- **Segurança:** o texto atual só é substituído quando a primeira parte da resposta chega, e `Ctrl+Z` recupera o conteúdo anterior.

#### Autenticação (sem exportar chave)

O assistente resolve credenciais na mesma ordem que o Claude Code e a CLI da Anthropic, **sem armazenar nada**:

1. Variável de ambiente `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`
2. Perfil OAuth do `ant auth login` (`~/.config/anthropic/`)
3. **Login por browser do Claude Code / plugin do VS Code** (`~/.claude/.credentials.json`)

Se você já usa o Claude Code, o item 3 funciona automaticamente — nenhum passo extra. Essa opção consome a cota da sua assinatura Claude (compartilhada com o Claude Code); uso pesado simultâneo de Opus nos dois pode gerar `429` (troque para Haiku nesse caso).

> Sem o pacote `anthropic` ou sem credencial, o painel continua visível e apenas a geração exibe um erro claro — o restante do app não é afetado.

### 🔐 Cofre Bitwarden

No painel **🔐 Bitwarden** você desbloqueia seu cofre, busca uma credencial e manda o app **digitar a senha diretamente na janela em foco** — ideal para consoles remotos (iDRAC, iLO, KVM over IP) onde não há copiar-colar.

**Segurança:** a senha buscada **nunca aparece no editor nem no log**; a senha mestra e o token de sessão trafegam para o `bw` por variável de ambiente (não ficam visíveis na lista de processos); nada é gravado em disco; o cofre é bloqueado ao fechar a janela.

**Fluxo:** Desbloquear (senha mestra) → Buscar (ex.: *iDRAC*) → selecionar → focar a janela de destino → **⌨ Digitar senha** (respeita o *tempo de espera* e o *intervalo* configurados).

#### Dependência: Bitwarden CLI (`bw`)

O recurso usa o cliente oficial de linha de comando da Bitwarden. **Instale-o separadamente** (não é um pacote pip):

```bash
# Windows
winget install Bitwarden.CLI
# ou, em qualquer plataforma com Node.js:
npm install -g @bitwarden/cli
# macOS (Homebrew)
brew install bitwarden-cli
# Linux (Snap)
sudo snap install bw
```

> ⚠️ **Faça `bw login` no terminal antes de abrir o painel.** O AutoTyper **só desbloqueia** o cofre (`bw unlock`) — ele **nunca** faz login, porque isso exigiria lidar com sua senha mestra, 2FA e verificação de dispositivo. Se você tentar desbloquear sem ter feito login, o app mostra a mensagem *"você não está logado no Bitwarden. Rode 'bw login'…"*.

Faça login **uma vez** pelo terminal (e-mail + senha + 2FA). Na primeira vez, o Bitwarden pode exigir uma verificação de dispositivo — ele envia um **OTP para o seu e-mail** que você digita no terminal:

```bash
# Servidor próprio (self-hosted / Vaultwarden): configure o servidor ANTES do login
bw config server https://seu-servidor

bw login
# ? Email address: voce@exemplo.com
# ? Master password: [hidden]
# ? New device verification required. Enter OTP sent to login email: 123456
# You are logged in!
```

O login persiste entre sessões — você não precisa repeti-lo a cada vez, só o desbloqueio (com a senha mestra) dentro do app. Para sair de vez: `bw logout`.

> Sem o `bw` no PATH (ou sem `bw login` feito), o painel continua visível e apenas as ações do Bitwarden exibem um erro claro — o restante do app não é afetado.

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
├── config.py          — traduções, perfis de velocidade, StatusStyle, modelos de IA
├── markers.py         — parsing de marcadores embutidos
├── drivers.py         — Drivers de teclado (PynputDriver para X11/Win/macOS, EvdevDriver para Wayland)
├── engine.py          — TypingEngine + TypingCallbacks (sem dependência de Tkinter)
├── ai.py              — AIGenerator + resolução de credenciais (sem dependência de Tkinter)
├── vault.py           — BitwardenVault (integração com o `bw` CLI, sem dependência de Tkinter)
├── app.py             — TyperApp (GUI, Tkinter/ttkbootstrap)
└── cli.py             — parse_args() + run_headless()
requirements.txt
```

---

## 🐧 Suporte a Linux (Wayland e X11)

O AutoTyper possui suporte nativo tanto para sessões **X11** quanto para **Wayland**:
- Em sessões **Wayland**, a aplicação ativa automaticamente o driver nativo baseado em `evdev` (`/dev/uinput`), criando um dispositivo de teclado virtual reconhecido diretamente pelo compositor (KDE Plasma, GNOME, Sway, Hyprland, etc.).
- Para detalhes de arquitetura e instruções de permissões udev caso necessário, consulte o documento completo em [WAYLAND.md](WAYLAND.md).
- Em sessões **X11**, o driver `pynput` continua sendo utilizado com total transparência.

---

## 📄 Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).
