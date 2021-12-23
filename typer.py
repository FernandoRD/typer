from time import sleep
import tkinter as tk
from tkinter import Button, Text, Scrollbar
from tkinter import messagebox
import tkinter
import pyautogui
from tkinter.constants import BOTH, BOTTOM, END, RIGHT, TOP, Y
from tkinter import filedialog

root = tk.Tk()
root.geometry("800x600")
root.title("Typer")
root.minsize(height=600, width=800)
root.maxsize(height=600, width=800)

menubar = tk.Menu(root)

filemenu = tk.Menu(menubar, tearoff=0)
filemenu.add_command(label="Exit", command=root.quit)

menubar.add_cascade(label="File", menu=filemenu)

root.config(menu=menubar)

text_frame = tk.Frame(root, height=550, width=800)
buttoms_frame = tk.Frame(root, height=50, width=800)

# adding scrollbar
scrollbar = Scrollbar(text_frame)
  
# packing scrollbar
scrollbar.pack(side=RIGHT, fill=Y)

text_info = Text(text_frame, yscrollcommand=scrollbar.set, height=35 , width=100)
text_info.pack()

def type_text():
    sleep(int(wait_time_value.get()))
    interval_value = float(type_interval_value.get())/1000
    pyautogui.write(str(text_info.get(1.0,END)), interval=interval_value)
    
   
button = tk.Button(buttoms_frame, text="Type", command=type_text)
button.place(x=680,y=0, width=100, height=30)

type_interval = tk.Message(root, text="Type interval:               ms", width=200)
type_interval.place(x=1, y=5)
type_interval_value = tk.Entry(root)
type_interval_value.place(x=80, y=7, width=40)
type_interval_value.insert(0, 100)

wait_time = tk.Message(root, text="Wait               s until start typying", width=200)
wait_time.place(x=145, y=5)
wait_time_value = tk.Entry(root)
wait_time_value.place(x=180, y=7, width=40)
wait_time_value.insert(0,2)

text_frame.pack(side=BOTTOM)
buttoms_frame.pack(side=TOP)

# configuring the scrollbar
scrollbar.config(command=text_info.yview)
  
root.mainloop()