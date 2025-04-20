"""自定義訊息框模組"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Any
import logging

class CustomMessageBox(tk.Toplevel):
    """自定義訊息框類別"""

    def __init__(self, title: str = "訊息",
             message: str = "",
             message_type: str = "info",
             parent: Optional[tk.Tk] = None,
             min_width: int = 250,
             min_height: int = 180) -> None:
        """
        初始化自定義訊息框
        :param title: 視窗標題
        :param message: 訊息內容
        :param message_type: 訊息類型 (info, warning, error, question)
        :param parent: 父視窗
        :param min_width: 最小視窗寬度
        :param min_height: 最小視窗高度
        """
        super().__init__(parent)

        # 基本設置
        self.title(title)
        self.message_type = message_type
        self.min_width = min_width
        self.min_height = min_height
        self.parent = parent
        self.message = message

        # 設置視窗屬性
        self.overrideredirect(True)
        self.resizable(False, False)

        # 初始化拖曳變數
        self.drag_start_x = 0
        self.drag_start_y = 0

        # 初始化結果
        self.result = None

         # 初始化按鈕管理器 (移至此處)
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self)

        # 創建界面
        self.setup_ui(title, message)

        # 調整視窗大小並置中
        self.adjust_window_size()
        self.center_window()

        # 設置模態
        if parent:
            self.transient(parent)
            self.wait_visibility()
            self.grab_set()
            self.focus_force()

        # 綁定事件
        self.bind_events()

    def calculate_text_dimensions(self, text: str, font_family: str = 'Arial',
                                font_size: int = 10, max_width: int = 500) -> tuple[int, int]:
        """
        計算文本需要的尺寸
        :param text: 要計算的文本
        :param font_family: 字體
        :param font_size: 字體大小
        :param max_width: 最大寬度
        :return: (寬度, 高度)
        """
        temp_label = ttk.Label(self, text=text, font=(font_family, font_size))
        temp_label.update_idletasks()
        text_width = temp_label.winfo_reqwidth()

        # 如果文本寬度超過最大寬度，計算換行後的高度
        if text_width > max_width:
            text_width = max_width
            # 估算每行能容納的字數
            chars_per_line = max_width // (font_size * 1.5)  # 1.5 是一個經驗值
            num_lines = len(text) / chars_per_line
            text_height = int(num_lines * (font_size * 1.5)) + 20  # 20是額外邊距
        else:
            text_height = temp_label.winfo_reqheight()

        temp_label.destroy()
        return text_width, text_height

    def adjust_window_size(self) -> None:
            """根據內容調整視窗大小"""
            self.update_idletasks()

            # 計算所需的文本區域大小
            text_width, text_height = self.calculate_text_dimensions(self.message)

            # 計算視窗所需的總寬度和高度
            # 文本寬度 + 圖標寬度(50) + 內邊距(60)
            window_width = min(text_width + 110, 600)
            window_width = max(window_width, self.min_width)

            # 文本高度 + 標題列高度(30) + 按鈕區域高度(50) + 內邊距(60)
            window_height = text_height + 140
            window_height = max(window_height, self.min_height)

            # 設置消息標籤的換行長度
            self.message_label.configure(wraplength=window_width - 110)

            # 更新視窗大小
            self.geometry(f"{window_width}x{window_height}")

    def setup_ui(self, title: str, message: str) -> None:
        """設置界面"""
        # 創建標題列
        self.create_title_bar(title)

        # 主要內容區域
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 圖標和訊息區域
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # 圖標
        icon_text = self.get_icon_text()
        icon_label = ttk.Label(
            content_frame,
            text=icon_text,
            font=('Noto Sans TC', 24),
            foreground=self.get_icon_color()
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 20))

        # 訊息
        self.message_label = ttk.Label(
            content_frame,
            text=message,
            justify=tk.LEFT,
            font=('Arial', 10)
        )
        self.message_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 按鈕區域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.create_buttons(button_frame)


    def create_title_bar(self, title: str) -> None:
        """創建標題列"""
        title_bar = tk.Frame(self, bg='#334D6D', relief='raised', bd=0)
        title_bar.pack(fill=tk.X)

        # 標題
        title_label = tk.Label(
            title_bar,
            text=title,
            bg='#334D6D',
            fg='white',
            font=('Arial', 10)
        )
        title_label.pack(side=tk.LEFT, pady=5, padx=5)

        # 關閉按鈕
        close_button = tk.Button(
            title_bar,
            text="×",
            command=self.cancel,
            bg='#334D6D',
            fg='white',
            bd=0,
            font=('Arial', 12),
            width=3,
            cursor='hand2'
        )
        close_button.pack(side=tk.RIGHT)

        # 設置懸停效果
        close_button.bind('<Enter>',
            lambda e: close_button.configure(bg='#ff0000'))
        close_button.bind('<Leave>',
            lambda e: close_button.configure(bg='#334D6D'))

        # 綁定拖曳事件
        title_bar.bind('<Button-1>', self.start_drag)
        title_bar.bind('<B1-Motion>', self.on_drag)
        title_label.bind('<Button-1>', self.start_drag)
        title_label.bind('<B1-Motion>', self.on_drag)

    def create_buttons(self, button_frame: ttk.Frame) -> None:
        """創建按鈕"""
        if self.message_type == "question":
            # 使用按鈕管理器創建按鈕
            button_configs = [
                {
                    'id': 'ok',
                    'normal_icon': 'ok_icon.png',
                    'hover_icon': 'ok_hover.png',
                    'command': self.ok,
                    'tooltip': '確認',
                    'side': tk.LEFT,
                    'padx': (50,0)
                },
                {
                    'id': 'cancel',
                    'normal_icon': 'cancel_icon.png',
                    'hover_icon': 'cancel_hover.png',
                    'command': self.cancel,
                    'tooltip': '取消',
                    'side': tk.RIGHT,
                    'padx': (0,50)
                }
            ]

            # 創建按鈕
            self.dialog_buttons = self.button_manager.create_button_set(button_frame, button_configs)

            # 設置預設焦點
            self.after(100, lambda: self.focus_set())
        else:
            # 對於非問題類型，只創建 OK 按鈕
            button_configs = [
                {
                    'id': 'ok',
                    'normal_icon': 'ok_icon.png',
                    'hover_icon': 'ok_hover.png',
                    'command': self.ok,
                    'tooltip': '確認',
                    'side': tk.BOTTOM,
                    'padx': 5
                }
            ]

            # 創建按鈕
            self.dialog_buttons = self.button_manager.create_button_set(button_frame, button_configs)

            # 設置預設焦點
            self.after(100, lambda: self.focus_set())

    def start_drag(self, event: tk.Event) -> None:
        """開始拖曳"""
        self.drag_start_x = event.x_root - self.winfo_x()
        self.drag_start_y = event.y_root - self.winfo_y()

    def on_drag(self, event: tk.Event) -> None:
        """拖曳中"""
        if event.x_root != 0 and event.y_root != 0:
            x = event.x_root - self.drag_start_x
            y = event.y_root - self.drag_start_y
            self.geometry(f"+{x}+{y}")

    def center_window(self) -> None:
        """將視窗置中"""
        self.update_idletasks()
        window_width = self.winfo_width()
        window_height = self.winfo_height()

        if self.parent:
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()

            x = parent_x + (parent_width - window_width) // 2
            y = parent_y + (parent_height - window_height) // 2
        else:
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2

        self.geometry(f"+{x}+{y}")

    def bind_events(self) -> None:
        """綁定事件"""
        self.bind('<Return>', lambda e: self.ok())
        self.bind('<Escape>', lambda e: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def get_icon_text(self) -> str:
        """獲取圖標文字"""
        icon_map = {
            "info": "ℹ",
            "warning": "⚠",
            "error": "✖",
            "question": "?"
        }
        return icon_map.get(self.message_type, "ℹ")

    def get_icon_color(self) -> str:
        """獲取圖標顏色"""
        color_map = {
            "info": "#334D6D",
            "warning": "#FDB40C",
            "error": "#E81123",
            "question": "#0078D7"
        }
        return color_map.get(self.message_type, "#0078D7")

    def ok(self) -> None:
        """確定按鈕事件"""
        self.result = True
        if self.parent:
            self.grab_release()
        self.destroy()

    def cancel(self) -> None:
        """取消按鈕事件"""
        self.result = False
        if self.parent:
            self.grab_release()
        self.destroy()

# 輔助函數保持不變
def show_message(title: str, message: str, message_type: str = "info",
                parent: Optional[tk.Tk] = None) -> None:
    """顯示訊息框"""
    dialog = CustomMessageBox(title, message, message_type, parent)
    if parent:
        parent.wait_window(dialog)
    else:
        dialog.wait_window()

def show_info(title: str, message: str, parent: Optional[tk.Tk] = None) -> None:
    """顯示信息訊息框"""
    show_message(title, message, "info", parent)

def show_warning(title: str, message: str, parent: Optional[tk.Tk] = None) -> None:
    """顯示警告訊息框"""
    show_message(title, message, "warning", parent)

def show_error(title: str, message: str, parent: Optional[tk.Tk] = None) -> None:
    """顯示錯誤訊息框"""
    show_message(title, message, "error", parent)

def ask_question(title: str, message: str,
                parent: Optional[tk.Tk] = None) -> bool:
    """顯示詢問訊息框"""
    dialog = CustomMessageBox(title, message, "question", parent)
    if parent:
        parent.wait_window(dialog)
    else:
        dialog.wait_window()
    return dialog.result