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
        # 創建後立即隱藏視窗，避免閃爍
        self.window.withdraw()

        self.window.title(self.title_text)
        self.window.geometry(f"{self.width}x{self.height}")

        # 設置無邊框樣式
        self.window.overrideredirect(True)

        # 設置對話框置頂
        self.window.attributes('-topmost', True)

        # 創建標題列
        self.create_title_bar()

        # 創建主框架
        self.main_frame = ttk.Frame(self.window, style='Custom.TFrame')
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 初始化按鈕管理器
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self.window)

        # 設置樣式
        self.setup_styles()

        # 置中顯示
        self.center_window()

        # 設置模態
        self.window.transient(self.parent)

        # 完成所有設置後再顯示視窗
        self.window.deiconify()
        self.window.update()

        # 獲取焦點
        self.window.grab_set()

        # 綁定事件
        self.bind_events()

    def create_title_bar(self) -> None:
        """創建標題列"""
        self.title_bar = tk.Frame(self.window, bg='#334D6D', height=30)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)

        # 標題
        self.title_label = tk.Label(
            self.title_bar,
            text=self.title_text,
            bg='#334D6D',
            fg='white',
            font=('Noto Sans TC', 10)
        )
        self.title_label.pack(side=tk.LEFT, padx=5)

        # 關閉按鈕 - 確保調用 cancel 方法
        self.close_button = tk.Button(
            self.title_bar,
            text="×",
            command=self.cancel,  # 修改這裡，使用 self.cancel
            bg='#334D6D',
            fg='white',
            bd=0,
            font=('Noto Sans TC', 12),
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
            lambda e: self.close_button.configure(bg='#334D6D'))

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
            # 清理按鈕管理器資源
            if hasattr(self, 'button_manager'):
                self.button_manager.buttons.clear()
                self.button_manager.button_icons.clear()

            # 釋放其他資源
            self.window.grab_release()
            self.window.destroy()
        except Exception as e:
            self.logger.error(f"關閉對話框時出錯: {e}")

    def show(self) -> Any:
        """顯示對話框並返回結果"""
        self.window.wait_window()
        return self.result

    def run(self) -> Any:
        """運行對話框並返回結果"""
        try:
            # 確保對話框置頂
            self.window.attributes('-topmost', True)
            self.window.update()

            # 使用 focus_force 確保對話框獲得焦點
            self.window.focus_force()

            # 等待對話框關閉
            self.window.wait_window()

            return self.result
        except Exception as e:
            self.logger.error(f"運行對話框時出錯: {e}")
            return None