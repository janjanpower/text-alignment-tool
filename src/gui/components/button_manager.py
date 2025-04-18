"""按鈕管理器模組，統一管理所有圖片按鈕的創建和事件處理"""

import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional, Callable, Tuple, Union

from PIL import Image, ImageTk

class ButtonManager:
    """按鈕管理器類別，統一處理圖片按鈕的創建和事件"""

    def __init__(self, parent: tk.Widget):
        """
        初始化按鈕管理器
        :param parent: 父控件
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

        # 按鈕圖標緩存
        self.button_icons = {}

        # 按鈕默認尺寸
        self.default_width = 108
        self.default_height = 30

        # 按鈕集合
        self.buttons = {}

        # 載入圖標路徑
        self.icon_base_path = self._get_icon_path()
        self.logger.debug(f"圖標目錄路徑: {self.icon_base_path}")

    def _get_icon_path(self) -> str:
        """獲取圖標目錄路徑"""
        try:
            # 獲取當前模組所在目錄
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 獲取 gui 目錄
            gui_dir = os.path.dirname(current_dir)
            # 獲取 src 目錄
            src_dir = os.path.dirname(gui_dir)
            # 獲取專案根目錄 (src 的父目錄)
            project_root = os.path.dirname(src_dir)

            # 打印路徑信息用於調試
            self.logger.debug(f"當前目錄: {current_dir}")
            self.logger.debug(f"GUI 目錄: {gui_dir}")
            self.logger.debug(f"SRC 目錄: {src_dir}")
            self.logger.debug(f"專案根目錄: {project_root}")

            # 圖標目錄路徑
            buttons_path = os.path.join(project_root, "assets", "buttons")

            # 檢查路徑是否存在
            if not os.path.exists(buttons_path):
                self.logger.warning(f"按鈕圖標目錄不存在: {buttons_path}")
                # 嘗試查找其他可能的路徑
                alt_paths = [
                    os.path.join(src_dir, "assets", "buttons"),
                    os.path.join(gui_dir, "assets", "buttons"),
                    os.path.join(current_dir, "assets", "buttons")
                ]

                for path in alt_paths:
                    if os.path.exists(path):
                        self.logger.info(f"找到替代按鈕圖標目錄: {path}")
                        return path

                # 如果所有路徑都不存在，記錄警告
                self.logger.warning("無法找到按鈕圖標目錄")

            return buttons_path
        except Exception as e:
            self.logger.error(f"獲取圖標路徑時出錯: {e}")
            return ""

    def load_icons(self, icon_names: List[Tuple[str, str]], size: Tuple[int, int] = None) -> None:
        """
        載入指定的圖標
        :param icon_names: 圖標名稱列表，每項為 (normal_icon, hover_icon) 元組
        :param size: 圖標大小，格式為 (寬, 高)
        """
        if size is None:
            size = (self.default_width, self.default_height)

        try:
            for normal_icon, hover_icon in icon_names:
                # 載入正常狀態圖標
                normal_path = os.path.join(self.icon_base_path, normal_icon)
                # 檢查文件名是否包含後綴
                if '.' not in normal_icon:
                    # 嘗試添加通用圖片後綴
                    for ext in ['.png', '.jpg', '.gif']:
                        test_path = normal_path + ext
                        if os.path.exists(test_path):
                            normal_path = test_path
                            break

                if os.path.exists(normal_path):
                    img = Image.open(normal_path)
                    img = img.resize(size, Image.LANCZOS)
                    self.button_icons[normal_icon] = ImageTk.PhotoImage(img)
                    self.logger.debug(f"已載入圖標: {normal_icon} ({normal_path})")
                else:
                    self.logger.warning(f"找不到圖標文件: {normal_path}")

                # 載入懸停狀態圖標
                hover_path = os.path.join(self.icon_base_path, hover_icon)
                # 檢查文件名是否包含後綴
                if '.' not in hover_icon:
                    # 嘗試添加通用圖片後綴
                    for ext in ['.png', '.jpg', '.gif']:
                        test_path = hover_path + ext
                        if os.path.exists(test_path):
                            hover_path = test_path
                            break

                if os.path.exists(hover_path):
                    img = Image.open(hover_path)
                    img = img.resize(size, Image.LANCZOS)
                    self.button_icons[hover_icon] = ImageTk.PhotoImage(img)
                    self.logger.debug(f"已載入圖標: {hover_icon} ({hover_path})")
                else:
                    self.logger.warning(f"找不到圖標文件: {hover_path}")
        except Exception as e:
            self.logger.error(f"載入圖標時出錯: {e}")

    def create_image_button(self, parent: tk.Widget, normal_icon: str, hover_icon: str, command: Callable = None,
                        tooltip: str = "", pack_side: str = tk.LEFT, padx: int = 5, pady: int = 0) -> tk.Label:
        """創建圖片按鈕"""
        try:
            # 檢查父控件是否還存在
            if hasattr(parent, 'winfo_exists') and not parent.winfo_exists():
                self.logger.warning("父控件已不存在，無法創建按鈕")
                return None

            # 確保圖標已載入
            if normal_icon not in self.button_icons:
                self.load_icons([(normal_icon, hover_icon)])

            normal_img = self.button_icons.get(normal_icon)
            hover_img = self.button_icons.get(hover_icon)

            if not normal_img:
                self.logger.warning(f"圖標 {normal_icon} 未載入，使用占位圖像")
                # 創建占位圖像
                normal_img = self._create_placeholder_image()
                self.button_icons[normal_icon] = normal_img

            if not hover_img:
                hover_img = normal_img

            # 創建按鈕框架
            btn_frame = ttk.Frame(parent)
            btn_frame.pack(side=pack_side, padx=padx, pady=pady)

            # 創建標籤按鈕
            btn = tk.Label(
                btn_frame,
                image=normal_img,
                cursor="hand2"
            )
            btn.normal_image = normal_img  # 保存引用以避免垃圾回收
            btn.hover_image = hover_img    # 保存引用以避免垃圾回收
            btn.pack()

            # 儲存原始命令
            btn.command = command

            # 綁定按下和釋放事件
            btn.bind("<ButtonPress-1>", lambda e, b=btn: self._on_button_press(e, b))
            btn.bind("<ButtonRelease-1>", lambda e, b=btn: self._on_button_release(e, b))

            # 綁定懸停事件
            btn.bind("<Enter>", lambda e, b=btn: self._on_hover_enter(e, b))
            btn.bind("<Leave>", lambda e, b=btn: self._on_hover_leave(e, b))

            # 添加提示文字
            if tooltip:
                self._create_tooltip(btn, tooltip)

            # 將按鈕添加到集合中
            button_id = len(self.buttons)
            self.buttons[button_id] = btn

            return btn

        except Exception as e:
            self.logger.error(f"創建圖片按鈕時出錯: {e}")
            # 返回一個空的框架避免程式崩潰
            empty_frame = ttk.Frame(parent)
            empty_frame.pack(side=pack_side, padx=padx, pady=pady)
            return empty_frame

    def _create_placeholder_image(self) -> ImageTk.PhotoImage:
        """創建占位圖像"""
        try:
            # 創建一個簡單的占位圖像
            img = Image.new('RGB', (self.default_width, self.default_height), color='#cccccc')
            return ImageTk.PhotoImage(img)
        except Exception as e:
            self.logger.error(f"創建占位圖像時出錯: {e}")
            # 創建最小的可能圖像
            return ImageTk.PhotoImage(Image.new('RGB', (1, 1), color='#cccccc'))

    def _on_button_press(self, event, button):
        """滑鼠按下按鈕事件處理"""
        # 檢查按鈕是否還存在
        if not hasattr(button, 'winfo_exists') or not button.winfo_exists():
            return

        if hasattr(button, 'hover_image'):
            button.configure(image=button.hover_image)
            # 保存按下的位置
            button.press_x = event.x
            button.press_y = event.y

    def _on_button_release(self, event, button):
        """滑鼠釋放按鈕事件處理"""
        if hasattr(button, 'normal_image'):
            button.configure(image=button.normal_image)

            # 判斷釋放是否在按鈕範圍內
            if hasattr(button, 'press_x') and hasattr(button, 'press_y'):
                # 檢查滑鼠是否仍在按鈕上
                if (0 <= event.x <= button.winfo_width() and
                    0 <= event.y <= button.winfo_height()):
                    # 在按鈕上釋放，執行命令
                    if hasattr(button, 'command') and callable(button.command):
                        button.command()

    def _on_hover_enter(self, event, button):
        """滑鼠進入按鈕事件處理"""
        if hasattr(button, 'hover_image'):
            button.configure(image=button.hover_image)

    def _on_hover_leave(self, event, button):
        """滑鼠離開按鈕事件處理"""
        if hasattr(button, 'normal_image') and not hasattr(button, 'press_x'):
            button.configure(image=button.normal_image)
        elif hasattr(button, 'press_x'):
            # 如果按下狀態下離開，也恢復正常圖像
            delattr(button, 'press_x')
            delattr(button, 'press_y')
            button.configure(image=button.normal_image)

    def _create_tooltip(self, widget, text: str) -> None:
        """
        為控件創建提示文字
        :param widget: 要添加提示的控件
        :param text: 提示文字
        """
        tooltip = None

        def enter(event):
            nonlocal tooltip
            x = y = 0
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 25
            y += widget.winfo_rooty() + 25

            # 創建提示框
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{x}+{y}")

            label = ttk.Label(
                tooltip,
                text=text,
                background="#ffffe0",
                relief="solid",
                borderwidth=1,
                font=("微軟正黑體", 10),
                padding=(5, 2)
            )
            label.pack()

        def leave(event):
            nonlocal tooltip
            if tooltip:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def create_button_set(self, parent: tk.Widget, button_configs: List[Dict]) -> Dict[str, tk.Label]:
        """創建一組按鈕"""
        buttons = {}

        # 檢查父控件是否還存在
        if hasattr(parent, 'winfo_exists') and not parent.winfo_exists():
            self.logger.warning("父控件已不存在，無法創建按鈕集")
            return buttons

        # 預載入所有圖標
        icon_pairs = [(config['normal_icon'], config['hover_icon'])
                    for config in button_configs
                    if 'normal_icon' in config and 'hover_icon' in config]
        self.load_icons(icon_pairs)


        # 創建所有按鈕
        for config in button_configs:
            button_id = config.get('id', '')
            if not button_id:
                continue

            normal_icon = config.get('normal_icon', '')
            hover_icon = config.get('hover_icon', '')
            command = config.get('command', None)
            tooltip = config.get('tooltip', '')
            side = config.get('side', tk.LEFT)
            padx = config.get('padx', 5)
            pady = config.get('pady', 0)

            # 創建按鈕
            btn = self.create_image_button(
                parent,
                normal_icon,
                hover_icon,
                command,
                tooltip,
                side,
                padx,
                pady
            )

            buttons[button_id] = btn

        return buttons