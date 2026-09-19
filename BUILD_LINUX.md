# Build do executável Linux

O repositório gera um binário único para Linux x86_64 em `dist/AutoTyper`.
Ele contém o código Python, dependências, os recursos do `ttkbootstrap` e o
runtime Tcl/Tk. A definição inclui as bibliotecas Tcl/Tk do interpretador de
build, e o hook integrado do PyInstaller coleta os arquivos de dados Tcl/Tk.

## Pré-requisitos

- Linux x86_64;
- Python do ambiente de build com PyInstaller e as dependências do projeto;
- bibliotecas gráficas do sistema necessárias ao Tk e ao X11, quando usadas
  pela sessão de destino.

Para preparar o ambiente de build com `uv`:

```bash
uv venv --python 3.13 .venv-build
uv pip install --python .venv-build/bin/python -r requirements.txt pyinstaller
```

O script usa `.venv-build/bin/python` por padrão. Para usar outro ambiente,
defina `PYTHON_BIN` com o caminho absoluto para o interpretador que contém o
PyInstaller e as dependências do projeto.

## Gerar

```bash
./scripts/build_linux.sh
```

O resultado fica em `dist/AutoTyper`. A definição em
`packaging/autotyper.spec` inclui explicitamente os backends dinâmicos Xorg e
uinput do `pynput`, além dos módulos `evdev` usados pela seleção de driver em
sessões Wayland. As bibliotecas e os dados Tcl/Tk acompanham o binário.

O artefato entregue foi gerado com Python 3.13.14 e PyInstaller 6.22.3.

Para verificar a interface de linha de comando sem iniciar a GUI:

```bash
./dist/AutoTyper --help
```

Esse comando não cria uma janela nem envia teclas, mas a versão atual importa
`pynput` durante a inicialização. Execute-o em uma sessão com X11/Xwayland
acessível; sem ela, o import pode falhar antes de os argumentos serem lidos.

## Compatibilidade

O binário deve ser distribuído para Linux x86_64. Ele foi construído neste
ambiente com glibc 2.44, portanto não há garantia de execução em distribuições
com glibc anterior; gere-o em uma distribuição mais antiga para ampliar a
compatibilidade de glibc.

Em X11, a injeção de teclas usa `pynput` e requer uma sessão gráfica X11
acessível. Em Wayland, o aplicativo tenta usar `evdev` e `/dev/uinput`; isso
depende das permissões locais para criar o teclado virtual e, para ESC/ENTER,
ler dispositivos em `/dev/input`. Como `pynput` é importado antes da seleção
do driver, a versão atual também exige X11/Xwayland acessível em Wayland. O
suporte varia conforme compositor, política de sessão e layout de teclado.
Consulte `WAYLAND.md` para a matriz de validação e limitações conhecidas.

O painel de cofre requer a CLI oficial do Bitwarden, `bw`, instalada e
autenticada no `PATH` da máquina de destino; essa ferramenta externa não é
incorporada ao executável.
