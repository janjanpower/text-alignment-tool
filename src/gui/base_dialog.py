"""基礎對話框類別模組"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Any
import logging

class BaseDialog:
    """基礎對話框類別，繼承 BaseWindow 的樣式"""

    def __init__(self, parent: tk.Tk, title: str = "自定義對話框",
                 width: int = 400, height: int = 300) -> None:
        """
        初始化基礎對話框
        :param parent: 父視窗
        :param title: 對話框標題
        :param width: 寬度
        :param height: 高度
        """
        self.parent = parent
        self.width = width
        self.height = height
        self.title_text = title
        self.result = None
        self.logger = logging.getLogger(self.__class__.__name__)

        # 創建對話框
        self.create_dialog()

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(self.title_text)
        self.window.geometry(f"{self.width}x{self.height}")

        # 設置無邊框樣式
        self.window.overrideredirect(True)

        # 創建標題列
        self.create_title_bar()

        # 創建主框架
        self.main_frame = ttk.Frame(self.window, style='Custom.TFrame')
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 設置樣式
        self.setup_styles()

        # 置中顯示
        self.center_window()

        # 設置模態
        self.window.transient(self.parent)
        self.window.grab_set()

        # 綁定事件
        self.bind_events()

    def create_title_bar(self) -> None:
        """創建標題列"""
        self.title_bar = tk.Frame(self.window, bg='#404040', height=30)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)

        # 標題
        self.title_label = tk.Label(
            self.title_bar,
            text=self.title_text,
            bg='#404040',
            fg='white',
            font=('Arial', 10)
        )
        self.title_label.pack(side=tk.LEFT, padx=5)

        # 關閉按鈕
        self.close_button = tk.Button(
            self.title_bar,
            text="×",
            command=self.cancel,
            bg='#404040',
            fg='white',
            bd=0,
            font=('Arial', 12),
            width=3,
            cursor='hand2'
        )
        self.close_button.pack(side=tk.RIGHT)

        # 綁定拖曳事件
        self.title_bar.bind('<Button-1>', self.start_move)
        self.title_bar.bind('<B1-Motion>', self.do_move)
        self.title_label.bind('<Button-1>', self.start_move)
        self.title_label.bind('<B1-Motion>', self.do_move)

    def setup_styles(self) -> None:
        """設置樣式"""
        style = ttk.Style()
        style.configure('Custom.TFrame', background='#f0f0f0')
        style.configure('Custom.TLabel', background='#f0f0f0')
        style.configure('Custom.TButton', padding=5)

    def start_move(self, event: tk.Event) -> None:
        """開始拖曳"""
        self._offsetx = event.x
        self._offsety = event.y

    def do_move(self, event: tk.Event) -> None:
        """拖曳中"""
        x = self.window.winfo_x() + (event.x - self._offsetx)
        y = self.window.winfo_y() + (event.y - self._offsety)
        self.window.geometry(f"+{x}+{y}")

    def center_window(self) -> None:
        """置中視窗"""
        self.window.update_idletasks()

        x = self.parent.winfo_x() + (self.parent.winfo_width() - self.width) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - self.height) // 2

        self.window.geometry(f"+{x}+{y}")

    def bind_events(self) -> None:
        """綁定事件"""
        self.window.bind('<Escape>', lambda e: self.cancel())

        # 設置關閉按鈕懸停效果
        self.close_button.bind('<Enter>',
            lambda e: self.close_button.configure(bg='#ff0000'))
        self.close_button.bind('<Leave>',
            lambda e: self.close_button.configure(bg='#404040'))

    def ok(self, event: Optional[tk.Event] = None) -> None:
        """確定按鈕事件"""
        if self.validate():
            self.apply()
            self.close()

    def cancel(self, event: Optional[tk.Event] = None) -> None:
        """取消按鈕事件"""
        self.result = None
        self.close()

    def validate(self) -> bool:
        """驗證輸入"""
        return True

    def apply(self) -> None:
        """應用更改"""
        pass

    def close(self) -> None:
        """關閉對話框"""
        try:
            self.window.grab_release()
            self.window.destroy()
        except Exception as e:
            self.logger.error(f"關閉對話框時出錯: {e}")

    def show(self) -> Any:
        """顯示對話框並返回結果"""
        self.window.wait_window()
        return self.result