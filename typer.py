import time
import threading
import os
import sys
from tkinter import filedialog
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText
from pynput.keyboard import Controller, Listener, Key

class TyperApp(ttk.Window):
    def __init__(self):
        # ttkbootstrap usa 'themename' para definir o tema.
        # 'superhero' é um tema escuro popular. Outros: 'cyborg', 'darkly'
        super().__init__(themename="darkly")

        self.geometry("820x640")
        self.title("Typer")
        self.minsize(height=800, width=820)
        #root.maxsize(height=800, width=1000)

        # Inicializa o controlador de teclado de baixo nível para maior compatibilidade
        self.keyboard = Controller()
        self.stop_typing = False  # Flag para o botão de emergência

        # --- CABEÇALHO (Título & Botões de Ficheiro) ---
        # Em ttkbootstrap, usamos Frames com bootstyle para cor de fundo
        self.header_frame = ttk.Frame(self, bootstyle="dark")
        self.header_frame.pack(side="top", fill="x")

        self.app_title = ttk.Label(self.header_frame, text="⚡ AutoTyper", font=("", 22, "bold"), bootstyle="light")
        self.app_title.pack(side="left", padx=20, pady=10)

        # Botões estilizados com 'bootstyle'. 'secondary-outline' é um bom estilo para ações secundárias.
        self.btn_save = ttk.Button(self.header_frame, text="💾 Save File", width=12, command=self.save_file, bootstyle="secondary-outline")
        self.btn_save.pack(side="right", padx=(5, 20), pady=10)

        self.btn_open = ttk.Button(self.header_frame, text="📂 Open File", width=12, command=self.open_file, bootstyle="secondary-outline")
        self.btn_open.pack(side="right", padx=5, pady=10)

        # --- CARD DE CONFIGURAÇÕES ---
        # Labelframe cria um 'card' com título
        self.settings_frame = ttk.Labelframe(self, text=" ⚙️ Configuration ", bootstyle="info")
        self.settings_frame.pack(side="top", fill="x", padx=20, pady=(20, 10))
        self.settings_frame.columnconfigure((0, 1, 2, 3, 4), weight=1)

        # --- AVISO DE COMPATIBILIDADE (LINUX/WAYLAND) ---
        self.check_linux_compatibility()

        self.type_interval_message_1 = ttk.Label(self.settings_frame, text="Type interval (ms):")
        self.type_interval_message_1.grid(row=0, column=0, padx=(15, 5), pady=(10, 15), sticky="w")

        self.type_interval_value = ttk.Entry(self.settings_frame, width=10)
        self.type_interval_value.grid(row=0, column=1, padx=5, pady=(10, 15), sticky="w")
        self.type_interval_value.insert(0, "100")

        self.wait_time_message_1 = ttk.Label(self.settings_frame, text="Wait (s) before typing:")
        self.wait_time_message_1.grid(row=0, column=2, padx=(20, 5), pady=(10, 15), sticky="w")

        self.wait_time_value = ttk.Entry(self.settings_frame, width=10)
        self.wait_time_value.grid(row=0, column=3, padx=5, pady=(10, 15), sticky="w")
        self.wait_time_value.insert(0, "2")

        # O botão principal usa o bootstyle 'success' (verde)
        self.button = ttk.Button(self.settings_frame, text="🚀 START TYPING", command=self.start_typing_thread, width=18, bootstyle="success")
        self.button.grid(row=0, column=4, padx=(20, 15), pady=(10, 15), sticky="e")

        # --- ÁREA DE TEXTO PRINCIPAL ---
        self.text_frame = ttk.Frame(self)
        self.text_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(0, 10))

        # Usando ScrolledText do ttkbootstrap
        self.text_info = ScrolledText(self.text_frame, height=20, width=100, font=("Consolas", 13))
        self.text_info.pack(fill="both", expand=True)

        # --- BARRA DE STATUS INFERIOR ---
        self.status_bar = ttk.Frame(self)
        self.status_bar.pack(side="bottom", fill="x", padx=20, pady=(0, 5))
        
        self.status_label = ttk.Label(self.status_bar, text="Ready.", font=("", 12, "italic"), bootstyle="secondary")
        self.status_label.pack(side="left")

    def check_linux_compatibility(self):
        """Verifica se o programa está a ser executado em Wayland no Linux e exibe um aviso."""
        if sys.platform == "linux":
            session_type = os.environ.get('XDG_SESSION_TYPE')
            if session_type == "wayland":
                self.warning_frame = ttk.Frame(self, bootstyle="warning")
                self.warning_frame.pack(fill="x", padx=20, pady=(5, 0), before=self.settings_frame)
                self.warning_frame.columnconfigure(0, weight=1) # Faz a label expandir

                warning_label = ttk.Label(
                    self.warning_frame,
                    text="⚠️ Warning: You are running on Wayland. Keystroke simulation may not work.\n"
                         "For this app to function, please log out and start a session using 'X11' or 'X.Org'.",
                    bootstyle="inverse-warning",
                    justify="left"
                )
                warning_label.grid(row=0, column=0, padx=(10, 5), pady=5, sticky="ew")

                close_button = ttk.Button(self.warning_frame, text="X", bootstyle="light-outline", command=self.close_warning, width=1, padding=1)
                close_button.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ne")

    def close_warning(self):
        """Fecha (destrói) o frame do aviso de compatibilidade."""
        if hasattr(self, 'warning_frame') and self.warning_frame.winfo_exists():
            self.warning_frame.destroy()

    def update_status(self, text, color="gray"):
        """Atualiza a barra de status visualmente usando a thread principal da interface"""
        # Mapeia as cores para bootstyles
        style_map = {
            "#1dd1a1": "success",
            "#ff6b6b": "danger",
            "#feca57": "warning",
            "gray": "secondary"
        }
        bootstyle = style_map.get(color, "secondary")
        self.after(0, lambda: self.status_label.configure(text=text, bootstyle=bootstyle))

    def open_file(self):
        """Abre a caixa de diálogo padrão do sistema, que o ttkbootstrap estiliza."""
        filepath = filedialog.askopenfilename(
            title="Select a file",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, "r", encoding="utf-8") as file:
                    content = file.read()
                    self.text_info.delete("1.0", "end")
                    self.text_info.insert("1.0", content)
                    self.update_status(f"File loaded: {os.path.basename(filepath)}", color="#1dd1a1")
            except Exception as e:
                self.update_status(f"Erro ao carregar o ficheiro: {e}", color="#ff6b6b")

    def save_file(self):
        """Abre a caixa de diálogo padrão do sistema para guardar um ficheiro."""
        filepath = filedialog.asksaveasfilename(
            title="Save file as",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            defaultextension=".txt"
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as file:
                    content = self.text_info.get("1.0", "end-1c")
                    file.write(content)
                    self.update_status("File saved successfully!", color="#1dd1a1")
            except Exception as e:
                self.update_status(f"Erro ao guardar o ficheiro: {e}", color="#ff6b6b")

    def request_stop(self):
        """Sinaliza para parar a digitação e atualiza a UI de forma centralizada."""
        if not self.stop_typing:
            self.stop_typing = True
            self.button.configure(state="disabled", text="Stopping...")
            self.update_status("Stop requested by user...", color="#feca57")

    def start_typing_thread(self):
        # Reseta a flag de parada a cada nova execução
        self.stop_typing = False
        
        # Altera o botão para a função de PARAR, tornando-o clicável
        self.button.configure(
            state="normal",
            text="🛑 STOP TYPING",
            bootstyle="danger",
            command=self.request_stop
        )
        self.update_status("Starting auto-typer...", color="#feca57")
        
        # Inicia o processo de digitação em uma nova Thread para não travar a interface gráfica
        typing_thread = threading.Thread(target=self.type_text)
        typing_thread.daemon = True
        typing_thread.start()

    def type_text(self):
        # Função para escutar a tecla de emergência (ESC) globalmente
        def on_press(key):
            if key == Key.esc:
                # Usa a função centralizada para parar, que também atualiza a UI
                self.request_stop()
                return False  # Encerra o listener
                
        # Inicia o listener de teclado em background
        listener = Listener(on_press=on_press)
        listener.start()

        try:
            try:
                wait_s = float(self.wait_time_value.get())
                interval_ms = float(self.type_interval_value.get()) / 1000.0
            except ValueError:
                self.update_status("Erro: Os valores de tempo devem ser numéricos!", color="#ff6b6b")
                return
            
            # Pega o texto do início (1.0) até o final (end-1c ignora a quebra de linha vazia do final)
            text_to_type = self.text_info.get("1.0", "end-1c")

            # Aguarda o tempo definido
            self.update_status(f"Waiting {wait_s}s before typing...", color="#feca57")
            time.sleep(wait_s)
            
            self.update_status("Typing...", color="#1dd1a1")

            # Usando pynput para iterar caractere por caractere. 
            # É mais resiliente contra bloqueios de clipboard e variação de layout de teclado regional.
            for char in text_to_type:
                # Checa a flag de emergência antes de digitar cada caractere
                if self.stop_typing:
                    # A mensagem de status já foi definida em request_stop
                    break
                    
                if char == '\n':
                    self.keyboard.tap(Key.enter)
                else:
                    self.keyboard.type(char)
                time.sleep(interval_ms)
                
            if not self.stop_typing:
                self.update_status("Typing finished successfully!", color="#1dd1a1")
                
        except Exception as e:
            self.update_status(f"Erro durante a digitação: {e}", color="#ff6b6b")
        finally:
            # Garante que o listener de teclado seja encerrado ao final ou no cancelamento
            listener.stop()
            # Ao finalizar, restaura o botão usando o thread principal da interface (after)
            self.after(0, lambda: self.button.configure(
                state="normal",
                text="🚀 START TYPING",
                bootstyle="success",
                command=self.start_typing_thread
            ))

if __name__ == "__main__":
    app = TyperApp()
    app.mainloop()
