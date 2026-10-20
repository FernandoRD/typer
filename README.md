# ⚡ AutoTyper

AutoTyper é uma ferramenta de desktop desenvolvida em Python que simula digitação de texto em qualquer janela ativa do sistema operacional. Nasceu da necessidade prática de gerenciar servidores remotos cujos protocolos de conexão não permitem copiar e colar grandes volumes de texto (KVM over IP, iDRAC, iLO, console serial, etc.) — dando autonomia ao analista sem depender do administrador do servidor remoto.

---

## ✨ Funcionalidades

| Funcionalidade | Descrição |
| --- | --- |
| Digitação automatizada | Digita qualquer texto em qualquer campo ou janela ativa |
| **Assistente IA** | Gera um rascunho via Claude e o mantém em prévia não acionável; Codex e Google/Antigravity exibem apenas status fail-closed |
| **Seletor de provedor/modelo** | Mostra somente os modelos permitidos para o provedor selecionado |
| **Autenticação local** | Reutiliza apenas a sessão já autenticada na CLI do provedor — o app não lê tokens, cookies ou arquivos de credenciais |
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
   Em Wayland, selecione também o **Layout do teclado**: use **ABNT2 (Português - Brasil)**
   para uma sessão Citrix/NetScaler com esse layout; **US** continua sendo o padrão.
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

No painel **🤖 Assistente IA**, escolha **ChatGPT (Codex)**, **Claude** ou **Google (Antigravity)** e um dos modelos exibidos para esse provedor. Descreva o rascunho desejado (por exemplo, *"script de backup do /etc com rotação de 7 dias"*). A resposta aparece primeiro em uma **prévia não acionável**: ela não altera o editor e nunca aciona o teclado. Após revisar, use **Inserir saída gerada**; só então revise o editor e clique em **INICIAR** normalmente.

- **Segurança:** a saída é normalizada para quebras de linha LF; conteúdo com marcadores `[[...]]` ou caracteres de controle inseguros é recusado ao inserir. A IA não pode criar pausas, teclas especiais ou outros marcadores de automação.
- **Cancelar:** durante a geração, use **Cancelar**. A prévia é descartada em toda nova geração, cancelamento, erro ou troca de provedor/modelo.
- **Diagnóstico local:** o painel verifica somente se a CLI instalada já está autenticada; não lê, exibe, salva ou envia tokens, cookies, e-mails ou caminhos de credenciais.
- **ChatGPT/Codex e Google/Antigravity:** permanecem indisponíveis enquanto o núcleo não conseguir confirmar o contrato de execução contida de cada CLI. Não há fallback automático para outro provedor.

Atualmente, somente a CLI local já autenticada do **Claude** pode gerar rascunhos, em modo restrito. **Codex** e **Google/Antigravity (agy)** permanecem em modo somente-status/fail-closed: o painel pode informar seu estado local, mas não oferece geração nem fallback. Se uma CLI não estiver instalada, não estiver autenticada ou não puder comprovar execução segura, o restante do app continua disponível.

### 🔐 Cofre Bitwarden

No painel **🔐 Bitwarden** você desbloqueia seu cofre, busca uma credencial e manda o app **digitar a senha diretamente na janela em foco** — ideal para consoles remotos (iDRAC, iLO, KVM over IP) onde não há copiar-colar.

**Segurança:** a senha buscada **nunca aparece no editor nem no log**; a senha mestra e o token de sessão trafegam para o `bw` por variável de ambiente (não ficam visíveis na lista de processos); nada é gravado em disco; o cofre é bloqueado ao fechar a janela.

**Fluxo:** informe e-mail + senha mestra → **Entrar** → Buscar (ex.: *iDRAC*) → selecionar → focar a janela de destino → **⌨ Digitar senha** (respeita o *tempo de espera* e o *intervalo* configurados).

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

O app faz `bw login` não interativo diretamente e mantém a chave de sessão apenas na memória do processo; não é preciso executar `bw login` antes nem exportar `BW_SESSION`. Senha mestra passa somente por `BW_PASSWORD` no ambiente do subprocesso, nunca por argumentos. O app não aceita nem envia códigos 2FA, para não expô-los nos argumentos de processo.

> ⚠️ A CLI do Bitwarden aceita 2FA não interativo com `--method` e `--code`, mas o AutoTyper deliberadamente não oferece isso: o TOTP ficaria exposto nos argumentos do processo. Contas com 2FA e verificações de novo dispositivo devem concluir um fluxo externo/CLI do Bitwarden antes. Para servidor próprio/Vaultwarden, execute antes `bw config server https://seu-servidor`. Se a CLI já estiver autenticada, o AutoTyper confirma que o e-mail é o mesmo antes de desbloqueá-la; nunca chama `bw logout` nem destrói o login externo existente.

> Sem o `bw` no PATH, o painel continua visível e apenas as ações do Bitwarden exibem um erro claro — o restante do app não é afetado.

### Modo headless (sem GUI)

```bash
python typer.py --headless --file script.txt --interval 80 --wait 3
# Wayland/Citrix with a Brazilian ABNT2 target layout:
python typer.py --keyboard-layout abnt2
```

| Flag | Curta | Padrão | Descrição |
| --- | --- | --- | --- |
| `--file` | `-f` | — | Arquivo de texto a digitar (obrigatório em headless) |
| `--interval` | `-i` | `100` | Intervalo entre teclas (ms) |
| `--wait` | `-w` | `2` | Segundos de espera antes de iniciar |
| `--lang` | `-l` | `en` | Idioma da UI (`en` / `pt`) |
| `--keyboard-layout` | — | `us` | Layout do teclado virtual Wayland: `us`, `abnt2` ou alias `pt-br` |
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
- O layout do teclado virtual do `evdev` é **US** por padrão. Para um destino ABNT2 (por exemplo, uma sessão Citrix configurada como Português do Brasil), inicie com `--keyboard-layout abnt2` ou `--keyboard-layout pt-br`; isso ajusta símbolos como `[`, `|` e `/`. PT-PT não é mapeado e deve continuar usando `us` ou um layout suportado explicitamente.
- Para detalhes de arquitetura e instruções de permissões udev caso necessário, consulte o documento completo em [WAYLAND.md](WAYLAND.md).
- Em sessões **X11**, o driver `pynput` continua sendo utilizado com total transparência.

---

## 📄 Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).
