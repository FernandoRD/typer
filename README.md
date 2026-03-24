# ⚡ AutoTyper

AutoTyper é uma ferramenta de desktop desenvolvida em Python que simula digitação de texto em qualquer janela ativa do sistema operacional. Nasceu da necessidade prática de gerenciar servidores remotos cujos protocolos de conexão não permitem copiar e colar grandes volumes de texto (KVM over IP, iDRAC, iLO, console serial, etc.) — dando autonomia ao analista sem depender do administrador do servidor remoto.

---

## Por que AutoTyper?

Em ambientes de gerência remota, ferramentas como KVM over IP ou consoles seriais frequentemente não suportam transferência via clipboard. Transferir scripts, arquivos de configuração ou comandos longos exigiria intervenção do administrador do servidor. O AutoTyper resolve isso simulando pressionamentos de tecla um a um, exatamente como uma pessoa digitaria, de forma compatível com qualquer aplicação que aceite entrada de teclado.

---

## ✨ Funcionalidades

| Funcionalidade | Descrição |
| --- | --- |
| Digitação automatizada | Digita qualquer texto em qualquer campo ou janela ativa |
| Velocidade configurável | Ajuste o intervalo entre teclas em milissegundos |
| Atraso inicial | Tempo de espera antes de começar, permitindo trocar para a janela de destino |
| Gestão de arquivos | Abre e salva arquivos `.txt` |
| Parada de emergência | Tecla `ESC` ou botão `STOP TYPING` interrompem imediatamente |
| Interface moderna | Tema escuro com `ttkbootstrap` |
| Multiplataforma | Windows, macOS e Linux (X11) |

---

## ⚙️ Requisitos

- Python **3.8** ou superior
- [`ttkbootstrap`](https://ttkbootstrap.readthedocs.io/) >= 1.10.0
- [`pynput`](https://pynput.readthedocs.io/) >= 1.7.0

---

## 🚀 Instalação

```bash
git clone https://github.com/seu-usuario/typer.git
cd typer
pip install ttkbootstrap pynput
```

---

## 📋 Como Usar

1. Execute a aplicação:

   ```bash
   python typer.py
   ```

2. Cole o texto diretamente na área de texto, **ou** use o botão **📂 Open File** para carregar um arquivo `.txt`.

3. Configure os parâmetros de digitação:
   - **Type interval (ms)** — intervalo entre cada tecla (padrão: `100` ms). Valores menores = mais rápido.
   - **Wait (s) before typing** — tempo de espera antes de iniciar (padrão: `2` s). Use esse tempo para clicar na janela de destino.

4. Clique em **🚀 START TYPING**.

5. Clique rapidamente na janela ou campo onde deseja que o texto seja digitado.

6. Para interromper a qualquer momento: pressione `ESC` ou clique em **🛑 STOP TYPING**.

---

## 🐧 Nota para Usuários Linux (Wayland)

> **⚠️ Importante:** A biblioteca `pynput` não funciona corretamente em sessões **Wayland** devido ao seu modelo de segurança isolado. A aplicação detecta automaticamente esse ambiente e exibe um aviso na interface.
>
> Para uso pleno, encerre a sessão e inicie uma nova usando **X11** (geralmente rotulado como "X.Org" ou "Standard" na tela de login).

---

## 📄 Licença

Este projeto está licenciado sob a [Licença MIT](LICENSE).
