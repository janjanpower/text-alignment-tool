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
from gui.components.button_manager import ButtonManager  # 導入按鈕管理器

class BaseWindow:
    """基礎視窗類別，提供共用的視窗功能"""

    def __init__(self, title: str = "自定義視窗",
                 width: int = 800, height: int = 600,
                 corner_radius=20,
                 master: Optional[tk.Tk] = None,
                 make_topmost: bool = False) -> None:
        """
        初始化基礎視窗
        :param title: 視窗標題
        :param width: 視窗寬度
        :param height: 視窗高度
        :param master: 父視窗
        :param make_topmost: 是否設置為置頂視窗
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

        # 初始化按鈕管理器
        self.button_manager = ButtonManager(self.master)

        # 保存視窗尺寸
        self.window_width = width
        self.window_height = height

        # 設置視窗基本屬性
        self.master.title(title)
        self.master.geometry(f"{width}x{height}")
        self.master.configure(bg='#f0f0f0')

        # 初始化置頂狀態
        self._is_topmost = make_topmost

        # 初始化拖曳變數
        self._offsetx = 0
        self._offsety = 0

        # 設置無邊框
        self.master.overrideredirect(True)

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

    def set_topmost(self, is_topmost: bool = True) -> None:
        """
        設置視窗是否置頂
        :param is_topmost: 是否置頂
        """
        try:
            self._is_topmost = is_topmost
            self.master.attributes('-topmost', is_topmost)
            # 刷新視窗以確保置頂設置生效
            self.master.update()
        except Exception as e:
            self.logger.error(f"設置視窗置頂狀態時出錯: {e}")

    def toggle_topmost(self) -> bool:
        """
        切換視窗的置頂狀態
        :return: 切換後的置頂狀態
        """
        self._is_topmost = not self._is_topmost
        self.set_topmost(self._is_topmost)
        return self._is_topmost

    def is_topmost(self) -> bool:
        """
        獲取視窗當前的置頂狀態
        :return: 是否置頂
        """
        return self._is_topmost

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
        """清理資源"""
        try:
            # 設置清理標誌，避免重複清理
            if hasattr(self, '_cleanup_done') and self._cleanup_done:
                return
            self._cleanup_done = True

            self.logger.debug("開始清理資源...")

            # 1. 停止所有異步任務
            try:
                self._stop_async_tasks()
            except Exception as e:
                self.logger.error(f"停止異步任務時出錯: {e}")

            # 2. 清除數據和狀態
            try:
                self._clear_data()
            except Exception as e:
                self.logger.error(f"清除數據時出錯: {e}")

            # 3. 釋放資源
            try:
                self._release_resources()
            except Exception as e:
                self.logger.error(f"釋放資源時出錯: {e}")

            # 4. 清理 UI
            try:
                self._clear_ui()
            except Exception as e:
                self.logger.error(f"清理 UI 時出錯: {e}")

            # 5. 解綁事件
            try:
                self._unbind_all_events()
            except Exception as e:
                self.logger.error(f"解綁事件時出錯: {e}")

            # 6. 清理按鈕管理器
            try:
                if hasattr(self, 'button_manager'):
                    # 釋放按鈕相關的資源
                    self.button_manager.buttons.clear()
                    self.button_manager.button_icons.clear()
            except Exception as e:
                self.logger.error(f"清理按鈕管理器時出錯: {e}")

            self.logger.debug("資源清理完成")
        except Exception as e:
            self.logger.error(f"清理資源過程中出錯: {e}")

    def _unbind_all_events(self) -> None:
        """解綁所有事件"""
        try:
            # 首先檢查 master 是否仍然有效
            if not hasattr(self, 'master') or not self.master:
                return

            try:
                self.master.unbind_all('<Motion>')
                self.master.unbind_all('<Configure>')
                self.master.unbind_all('<Control-s>')
                self.master.unbind_all('<Control-o>')
                self.master.unbind_all('<Control-z>')
                self.master.unbind_all('<Control-y>')
            except Exception:
                pass

            # 解綁樹視圖相關事件
            if hasattr(self, 'tree'):
                try:
                    self.tree.unbind('<Button-1>')
                    self.tree.unbind('<Double-1>')
                    self.tree.unbind('<KeyRelease>')
                    self.tree.unbind('<Motion>')
                    self.tree.unbind('<Leave>')
                    self.tree.unbind('<<TreeviewSelect>>')
                except Exception:
                    pass

            # 解綁時間滑桿事件
            if hasattr(self, 'slider_controller'):
                try:
                    self.slider_controller.hide_slider()
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"解綁事件時出錯: {e}")

    def _stop_async_tasks(self) -> None:
        """停止所有異步任務"""
        try:
            # 停止所有計時器
            for after_id in self.master.tk.eval('after info').split():
                try:
                    self.master.after_cancel(after_id)
                except Exception as e:
                    self.logger.error(f"停止計時器時出錯: {e}")

            # 停止音頻播放
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()

            # 可能還有其他異步任務需要停止

        except Exception as e:
            self.logger.error(f"停止異步任務時出錯: {e}")

    def _clear_data(self) -> None:
        """清除數據"""
        try:
            # 清除 SRT 數據
            if hasattr(self, 'srt_data'):
                self.srt_data = []

            # 清除校正狀態
            if hasattr(self, 'correction_service'):
                self.correction_service.clear_correction_states()

            # 清除使用 Word 文本的標記
            if hasattr(self, 'use_word_text'):
                self.use_word_text.clear()

            # 清除編輯文本信息
            if hasattr(self, 'edited_text_info'):
                self.edited_text_info.clear()

            # 清除 Word 比對結果
            if hasattr(self, 'word_comparison_results'):
                self.word_comparison_results = {}

        except Exception as e:
            self.logger.error(f"清除數據時出錯: {e}")

    def _release_resources(self) -> None:
        """釋放資源"""
        try:
            # 釋放音頻資源
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()

            # 釋放字體管理器資源
            if hasattr(self, 'font_manager'):
                # 如果字體管理器有清理方法，調用它
                pass

        except Exception as e:
            self.logger.error(f"釋放資源時出錯: {e}")

    def safe_widget_operation(self, widget, operation, *args, **kwargs):
        """安全地對控件執行操作"""
        if widget is None:
            return False

        try:
            # 檢查控件是否還存在
            if hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                # 執行指定的操作
                operation_func = getattr(widget, operation, None)
                if operation_func and callable(operation_func):
                    operation_func(*args, **kwargs)
                    return True
        except tk.TclError:
            # 控件可能已經不存在
            pass
        except Exception as e:
            self.logger.error(f"執行控件操作 {operation} 時出錯: {e}")

        return False

    def _clear_ui(self) -> None:
        """清理 UI"""
        try:
            # 清除合併符號
            if hasattr(self, 'merge_symbol'):
                self.safe_widget_operation(self.merge_symbol, 'place_forget')
                self.safe_widget_operation(self.merge_symbol, 'destroy')

            # 清理滑桿
            if hasattr(self, 'slider_controller'):
                try:
                    self.slider_controller.hide_slider()
                except Exception as e:
                    self.logger.error(f"隱藏滑桿時出錯: {e}")

            # 清除浮動圖標
            if hasattr(self, 'floating_icon'):
                self.safe_widget_operation(self.floating_icon, 'place_forget')
                self.safe_widget_operation(self.floating_icon, 'destroy')

        except Exception as e:
            self.logger.error(f"清理 UI 時出錯: {e}")
    def close_window(self, event: Optional[tk.Event] = None) -> None:
        """關閉視窗，確保資源正確清理"""
        try:
            # 設置關閉標誌，防止重複操作
            if hasattr(self, '_closing') and self._closing:
                return
            self._closing = True

            # 執行清理操作
            try:
                self.cleanup()
            except Exception as e:
                self.logger.error(f"執行清理時出錯: {e}")

            # 確保處理完所有待處理的事件
            try:
                self.master.update_idletasks()
            except tk.TclError:
                pass  # 忽略可能的錯誤

            # 使用更安全的方式關閉視窗
            from utils.window_utils import close_window_safely
            close_window_safely(self.master, self._do_final_cleanup)

        except Exception as e:
            self.logger.error(f"關閉視窗時出錯: {e}")
            try:
                # 最後嘗試直接銷毀視窗
                self.master.destroy()
            except:
                pass
            # 強制退出
            import sys
            sys.exit(0)

    def _do_final_cleanup(self):
        """執行最終的清理工作，在視窗即將關閉前調用"""
        # 解除所有事件綁定
        try:
            for widget in self.master.winfo_children():
                for binding in widget.bind():
                    try:
                        widget.unbind(binding)
                    except Exception:
                        pass
        except Exception as e:
            self.logger.error(f"解除事件綁定時出錯: {e}")

        # 取消所有計時器
        try:
            for after_id in self.master.tk.eval('after info').split():
                try:
                    self.master.after_cancel(after_id)
                except Exception:
                    pass
        except Exception as e:
            self.logger.error(f"取消計時器時出錯: {e}")

    def set_on_closing(self, callback: Callable[[], None]) -> None:
        """
        設置視窗關閉時的回調函數
        :param callback: 回調函數
        """
        self.on_closing = callback

    def run(self) -> None:
        """運行視窗"""
        self.master.mainloop()