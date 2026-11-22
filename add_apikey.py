# -*- coding: utf-8 -*-
"""把 DeepSeek API Key 写入当前用户的环境变量（不用改注册表就能用，双击即可运行）。

写入位置：HKEY_CURRENT_USER\\Environment\\DEEPSEEK_API_KEY
写入后，新打开的终端 / 程序都能读到；已打开的窗口需要重启。
"""

import ctypes
import os
import tkinter as tk
import winreg
from tkinter import messagebox

DEFAULT_NAME = "DEEPSEEK_API_KEY"
HWND_BROADCAST = 0xFFFF
WM_SETTINGCHANGE = 0x001A


def broadcast_env_change():
    """通知资源管理器等已运行程序刷新环境变量。"""
    try:
        ctypes.windll.user32.SendMessageW(
            ctypes.c_void_p(HWND_BROADCAST),
            ctypes.c_uint(WM_SETTINGCHANGE),
            0,
            ctypes.c_wchar_p("Environment"),
        )
    except Exception:
        pass


def import_env(name_entry, value_entry):
    name = name_entry.get().strip() or DEFAULT_NAME
    value = value_entry.get().strip()

    if not name:
        messagebox.showwarning("提示", "变量名不能为空")
        return
    if not value:
        messagebox.showwarning("提示", "变量值不能为空")
        return
    if any(ch.isspace() for ch in value):
        messagebox.showwarning("提示", "API Key 中不能有空格或换行，请重新粘贴")
        return
    if len(value) < 20:
        messagebox.showwarning("提示", "这串字符太短，不像有效的 API Key（形如 sk-xxxxxxxx）")
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)

        # 让当前进程也立即生效（可选，方便调试）
        os.environ[name] = value
        broadcast_env_change()

        messagebox.showinfo(
            "成功",
            f"已写入环境变量 {name}\n\n"
            "请关闭已打开的程序（含本窗口和命令行），重新双击「启动.bat」后生效。",
        )
        value_entry.delete(0, tk.END)
    except Exception as e:
        messagebox.showerror("失败", f"写入失败：{e}")


def main():
    root = tk.Tk()
    root.title("配置 DeepSeek API Key")
    root.resizable(False, False)

    tk.Label(root, text="变量名").grid(row=0, column=0, padx=10, pady=(12, 6), sticky="e")
    name_entry = tk.Entry(root, width=42)
    name_entry.insert(0, DEFAULT_NAME)
    name_entry.grid(row=0, column=1, padx=10, pady=(12, 6))

    tk.Label(root, text="变量值").grid(row=1, column=0, padx=10, sticky="e")
    value_entry = tk.Entry(root, width=42, show="*")
    value_entry.grid(row=1, column=1, padx=10, pady=6)
    value_entry.bind("<Return>", lambda e: import_env(name_entry, value_entry))
    value_entry.focus_set()

    tk.Label(
        root,
        text="提示：到 platform.deepseek.com 创建密钥，形如 sk- 开头。\n"
             "也可以直接在网页右上角「设置密钥」里填写。",
        justify="left",
        fg="#6b7280",
        font=("Microsoft YaHei", 9),
    ).grid(row=2, column=0, columnspan=2, padx=10, pady=(2, 8), sticky="w")

    tk.Button(
        root,
        text="写入并生效",
        width=14,
        command=lambda: import_env(name_entry, value_entry),
    ).grid(row=3, column=0, columnspan=2, pady=(0, 12))

    root.mainloop()


if __name__ == "__main__":
    main()
