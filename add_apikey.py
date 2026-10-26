import os
import tkinter as tk
from tkinter import messagebox
import winreg
import ctypes

DEFAULT_NAME = "DEEPSEEK_API_KEY"


def import_env():
    name = name_entry.get().strip()
    value = value_entry.get().strip()
    if not name or not value:
        messagebox.showwarning("提示", "变量名和值都不能为空")
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        os.environ[name] = value
        ctypes.windll.user32.SendMessageW(
            ctypes.c_void_p(0xFFFF),
            ctypes.c_uint(0x001A),
            0,
            ctypes.c_wchar_p("Environment")
        )
        messagebox.showinfo("成功", f"已导入环境变量 {name}\n重新打开终端 / 程序后生效")
        value_entry.delete(0, tk.END)
    except Exception as e:
        messagebox.showerror("失败", str(e))


root = tk.Tk()
root.title("导入环境变量")
root.resizable(False, False)

tk.Label(root, text="变量名").grid(row=0, column=0, padx=10, pady=(12, 6), sticky="e")
name_entry = tk.Entry(root, width=40)
name_entry.insert(0, DEFAULT_NAME)
name_entry.grid(row=0, column=1, padx=10, pady=(12, 6))

tk.Label(root, text="变量值").grid(row=1, column=0, padx=10, sticky="e")
value_entry = tk.Entry(root, width=40, show="*")
value_entry.grid(row=1, column=1, padx=10, pady=6)
value_entry.bind("<Return>", lambda e: import_env())
value_entry.focus_set()

tk.Button(root, text="导入", width=12, command=import_env).grid(row=2, column=0, columnspan=2, pady=12)

root.mainloop()