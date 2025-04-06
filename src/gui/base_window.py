"""基礎視窗類別模組"""

import os
import logging
import sys

# 添加項目根目錄到 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable


from utils.resource_cleaner import ResourceCleaner
from utils.font_manager import FontManager
class BaseWindow:
    """基礎視窗類別，提供共用的視窗功能"""

    def __init__(self, title: str = "自定義視窗",
                 width: int = 800, height: int = 600,
                 corner_radius=20,
                 master: Optional[tk.Tk] = None) -> None:
        """
        初始化基礎視窗
        :param title: 視窗標題
        :param width: 視窗寬度
        :param height: 視窗高度
        :param master: 父視窗
        """
        # 初始化主視窗
        if master is None:
            self.master = tk.Tk()
        else:
            self.master = master

        # 設置日誌
        self.logger = logging.getLogger(self.__class__.__name__)

        # 立即初始化字型管理器
        self.font_manager = FontManager(self.config if hasattr(self, 'config') else None)

        # 保存視窗尺寸
        self.window_width = width
        self.window_height = height

        # 設置視窗基本屬性
        self.master.title(title)
        self.master.geometry(f"{width}x{height}")
        self.master.configure(bg='#f0f0f0')

        # 初始化拖曳變數
        self._offsetx = 0
        self._offsety = 0

        # 設置無邊框
        self.master.overrideredirect(True)
        self.master.attributes('-topmost', False)

        if isinstance(self.master, tk.Tk):
            # 設置任務欄圖標
            try:
                from ctypes import windll
                windll.shell32.SetCurrentProcessExplicitAppUserModelID("TextAlignmentTool")
            except Exception:
                pass

        # 創建界面元素
        self.create_title_bar(title)
        self.create_menu_frame()
        self.create_main_frame()

        # 設置視窗位置
        self.center_window()

        # 設置樣式
        self.setup_styles()

        # 初始化字型管理器
        self.font_manager = FontManager(self.config if hasattr(self, 'config') else None)

        # 統一設定關閉協議
        self.master.protocol("WM_DELETE_WINDOW", self._handle_close)

    def setup_styles(self) -> None:
        """設定通用樣式"""
        style = ttk.Style()
        style.configure('Custom.TButton', padding=5, font=self.font_manager.get_font(size=9))

        # 使用字型管理器設置樣式
        self.font_manager.apply_to_style(style, 'Custom.TButton', size=10)
        self.font_manager.apply_to_style(style, 'Custom.TLabel', size=10)

        style.configure('Custom.TButton', padding=5)
        style.configure('Custom.TFrame', background='#f0f0f0')
        style.configure('Custom.TLabel', background='#f0f0f0')

        # 設定標題字型
        title_font = self.font_manager.get_font(size=11)
        self.title_label.configure(font=title_font)

        # 設定按鈕字型
        button_font = self.font_manager.get_font(size=10)
        self.min_button.configure(font=button_font)
        self.close_button.configure(font=button_font)

    def create_title_bar(self, title: str) -> None:
        """創建標題列"""
        self.title_bar = tk.Frame(self.master, bg='#334D6D', height=30)
        self.title_bar.pack(fill=tk.X)
        self.title_bar.pack_propagate(False)

        # 圖標
        icon_path = os.path.join(os.path.dirname(__file__), "..", "assets", "logo.png")
        if os.path.exists(icon_path):
            try:
                self.icon = tk.PhotoImage(file=icon_path)
                icon_label = tk.Label(self.title_bar, image=self.icon, bg='#334D6D')
                icon_label.pack(side=tk.LEFT, padx=5)
                self._bind_drag(icon_label)
            except Exception as e:
                self.logger.error(f"載入圖標失敗: {e}")

        # 標題
        self.title_label = tk.Label(
            self.title_bar,
            text=title,
            bg='#334D6D',
            fg='white',
            font=('Noto Sans TC', 10),

        )
        self.title_label.pack(side=tk.LEFT, padx=5)
        self._bind_drag(self.title_label)

        # 控制按鈕框架
        btn_frame = tk.Frame(self.title_bar, bg='#334D6D')
        btn_frame.pack(side=tk.RIGHT)

        # 最小化按鈕
        self.min_button = tk.Button(
            btn_frame,
            text="−",
            command=self._minimize_window,
            bg='#334D6D',
            fg='white',
            bd=0,
            font=('Noto Sans TC', 12),
            width=3,
            cursor='hand2'
        )
        self.min_button.pack(side=tk.LEFT)

        # 關閉按鈕
        self.close_button = tk.Button(
            btn_frame,
            text="×",
            command=self.close_window,
            bg='#334D6D',
            fg='white',
            bd=0,
            font=('Noto Sans TC', 12),
            width=3,
            cursor='hand2'
        )
        self.close_button.pack(side=tk.LEFT)

        # 設置按鈕懸停效果
        self._setup_button_hovering()

        # 為整個標題列綁定拖曳
        self._bind_drag(self.title_bar)

    def create_menu_frame(self) -> None:
        """創建選單框架"""
        self.menu_frame = ttk.Frame(self.master)
        self.menu_frame.pack(fill=tk.X)

    def create_main_frame(self) -> None:
        """創建主要內容框架"""
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def _bind_drag(self, widget: tk.Widget) -> None:
        """
        綁定拖曳事件
        :param widget: 要綁定拖曳事件的控件
        """
        widget.bind('<Button-1>', self._start_drag)
        widget.bind('<B1-Motion>', self._on_drag)

    def _start_drag(self, event: tk.Event) -> None:
        """
        開始拖曳
        :param event: 事件對象
        """
        self._offsetx = event.x_root - self.master.winfo_x()
        self._offsety = event.y_root - self.master.winfo_y()

    def _on_drag(self, event: tk.Event) -> None:
        """
        拖曳中
        :param event: 事件對象
        """
        x = event.x_root - self._offsetx
        y = event.y_root - self._offsety
        self.master.geometry(f'+{x}+{y}')

    def _minimize_window(self) -> None:
        """最小化視窗"""
        self.master.update_idletasks()
        self.master.overrideredirect(False)
        self.master.state('iconic')

        def check_state():
            if self.master.state() == 'normal':
                self.master.overrideredirect(True)
                self.master.lift()
            else:
                self.master.after(100, check_state)

        self.master.bind('<Map>', lambda e: check_state())

    def _setup_button_hovering(self) -> None:
        """設置按鈕懸停效果"""
        def on_enter(button: tk.Button, color: str) -> None:
            button.configure(bg=color)

        def on_leave(button: tk.Button) -> None:
            button.configure(bg='#334D6D')

        self.min_button.bind('<Enter>', lambda e: on_enter(self.min_button, '#666666'))
        self.min_button.bind('<Leave>', lambda e: on_leave(self.min_button))
        self.close_button.bind('<Enter>', lambda e: on_enter(self.close_button, '#ff0000'))
        self.close_button.bind('<Leave>', lambda e: on_leave(self.close_button))

    def center_window(self) -> None:
        """將視窗置中"""
        self.master.update_idletasks()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = (screen_width - self.window_width) // 2
        y = (screen_height - self.window_height) // 2
        self.master.geometry(f'+{x}+{y}')

    def set_title(self, title: str) -> None:
        """
        設置視窗標題
        :param title: 新標題
        """
        self.title_label.config(text=title)
        self.master.title(title)


    def _handle_close(self):
        """統一的關閉處理"""
        try:
            # 先執行子類的清理工作
            if hasattr(self, 'cleanup'):
                self.cleanup()

            # 執行關閉流程
            self.close_window()
        except Exception as e:
            logging.error(f"關閉視窗時出錯: {e}")
            sys.exit(1)

    def cleanup(self) -> None:
        """標準資源清理流程"""
        # 1. 停止所有異步任務
        self._stop_async_tasks()

        # 2. 清除數據
        self._clear_data()

        # 3. 釋放資源
        self._release_resources()

        # 4. 清理 UI
        self._clear_ui()


    def close_window(self, event: Optional[tk.Event] = None) -> None:
        """關閉視窗"""
        try:
            # 檢查子類是否有登出方法，如果有則調用
            if hasattr(self, 'update_logout_status') and hasattr(self, 'user_id'):
                self.update_logout_status(self.user_id)

            # 停止所有計時器
            for after_id in self.master.tk.eval('after info').split():
                try:
                    self.master.after_cancel(after_id)
                except Exception:
                    pass

            # 解除所有事件綁定
            for widget in self.master.winfo_children():
                try:
                    for binding in widget.bind():
                        widget.unbind(binding)
                except Exception:
                    pass

            # 確保處理完所有待處理的事件
            self.master.update_idletasks()

            # 銷毀視窗
            self.master.destroy()
            import sys
            sys.exit(0)

        except Exception as e:
            logging.error(f"關閉視窗時出錯: {e}")
            import sys
            sys.exit(1)

    def set_on_closing(self, callback: Callable[[], None]) -> None:
        """
        設置視窗關閉時的回調函數
        :param callback: 回調函數
        """
        self.on_closing = callback

    def run(self) -> None:
        """運行視窗"""
        self.master.mainloop()