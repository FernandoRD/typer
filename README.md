# ⚡ AutoTyper

AutoTyper é uma aplicação de desktop simples e poderosa, construída com Python e `ttkbootstrap`, que automatiza a digitação. Cole ou carregue um texto, configure a velocidade e deixe a aplicação digitá-lo para si em qualquer outro programa. É perfeito para entrada de dados, preenchimento de formulários ou qualquer tarefa de digitação repetitiva.

!AutoTyper Screenshot


## ✨ Funcionalidades

*   **Digitação Automatizada:** Digita automaticamente o texto da aplicação em qualquer janela ativa.
*   **Velocidade Personalizável:** Defina o intervalo (em milissegundos) entre cada toque de tecla.
*   **Atraso Inicial:** Configure um tempo de espera (em segundos) antes do início da digitação, dando-lhe tempo para trocar de janela.
*   **Gestão de Ficheiros:** Abra facilmente texto de ficheiros `.txt` ou guarde o seu texto atual.
*   **Paragem de Emergência:** Pare instantaneamente o processo de digitação premindo a tecla `ESC` ou clicando no botão "STOP".
*   **Interface Moderna:** Uma interface limpa e amigável com um tema escuro, cortesia do `ttkbootstrap`.
*   **Multiplataforma (com uma ressalva):** Funciona em Windows, macOS e Linux (sessão X11 recomendada).

## ⚙️ Requisitos

*   Python 3.x
*   `ttkbootstrap`
*   `pynput`

## 🚀 Instalação

1.  Clone o repositório ou descarregue os ficheiros.
2.  Instale as dependências necessárias usando o pip:

    ```bash
    pip install ttkbootstrap pynput
    ```

## 📋 Como Usar

1.  Execute a aplicação:
    ```bash
    python typer.py
    ```
2.  Cole o seu texto na área de texto ou use o botão "**📂 Open File**" para carregar um ficheiro `.txt`.
3.  Ajuste as configurações "**Type interval (ms)**" e "**Wait (s) before typing**" conforme necessário.
4.  Clique no botão "**🚀 START TYPING**".
5.  Clique rapidamente na janela ou campo de texto onde deseja que o texto seja digitado.
6.  Para parar o processo a qualquer momento, prima a tecla **`ESC`**.

## 🐧 Nota para Utilizadores de Linux (Wayland)

> **⚠️ Importante:** Esta aplicação usa a biblioteca `pynput` para simular toques de tecla. Esta funcionalidade pode não funcionar corretamente numa sessão **Wayland** devido ao seu modelo de segurança. A aplicação exibirá um aviso se detetar que está a usar Wayland.
>
> Para um funcionamento fiável, é recomendado que termine a sessão e inicie uma nova usando **X11** (muitas vezes rotulado como "X.Org" ou "Standard" no seu ecrã de login).

## 📄 Licença

Este projeto está licenciado sob a Licença MIT.