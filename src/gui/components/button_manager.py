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

            # 構建可能的路徑
            components_dir = current_dir
            gui_dir = os.path.dirname(components_dir)
            src_dir = os.path.dirname(gui_dir)
            project_root = os.path.dirname(src_dir)

            # 調試信息
            self.logger.debug(f"當前目錄: {current_dir}")
            self.logger.debug(f"GUI 目錄: {gui_dir}")
            self.logger.debug(f"SRC 目錄: {src_dir}")
            self.logger.debug(f"專案根目錄: {project_root}")

            # 可能的按鈕圖標目錄路徑
            possible_paths = [
                os.path.join(project_root, "assets", "buttons"),
                os.path.join(src_dir, "assets", "buttons"),
                os.path.join(project_root, "src", "assets", "buttons"),
                os.path.join(gui_dir, "assets", "buttons"),
                os.path.join(project_root, "assets", "icons"),  # 嘗試使用 icons 目錄
                os.path.join(src_dir, "assets", "icons"),
                os.path.join(current_dir, "assets", "buttons"),
                os.path.join(current_dir, "assets", "icons")
            ]

            # 嘗試每個路徑
            for path in possible_paths:
                if os.path.exists(path):
                    self.logger.info(f"找到按鈕圖標目錄: {path}")
                    return path

            # 如果所有路徑都不存在，嘗試創建默認路徑
            default_path = os.path.join(project_root, "assets", "buttons")
            try:
                os.makedirs(default_path, exist_ok=True)
                self.logger.info(f"已創建按鈕圖標目錄: {default_path}")
                return default_path
            except Exception as e:
                self.logger.error(f"創建按鈕圖標目錄失敗: {e}")

            # 如果創建失敗，返回 src/assets/buttons 作為最後嘗試
            return os.path.join(src_dir, "assets", "buttons")
        except Exception as e:
            self.logger.error(f"獲取圖標路徑時出錯: {e}")
            return ""

    def get_standard_icon_names(self) -> dict:
        """獲取標準化的圖標名稱對應關係"""
        return {
            # 登入相關
            'login': ('login_icon.png', 'login_hover.png'),
            'register': ('register_icon.png', 'register_hover.png'),
            'logout': ('loginout_icon.png', 'loginout_hover.png'),

            # 校正資料庫相關
            'add_data': ('adddata_icon.png', 'adddata_hover.png'),
            'delete_data': ('deletedata_icon.png', 'deletedata_hover.png'),
            'text_management': ('text_icon.png', 'text_hover.png'),

            # 通用按鈕
            'ok': ('ok_icon.png', 'ok_hover.png'),
            'cancel': ('cancel.png', 'cancel_hover.png'),
        }

    def load_icons(self, icon_names: List[Tuple[str, str]], size: Tuple[int, int] = None) -> None:
        """
        載入指定的圖標
        :param icon_names: 圖標名稱列表，每項為 (normal_icon, hover_icon) 元組
        :param size: 圖標大小，格式為 (寬, 高)
        """
        if size is None:
            size = (self.default_width, self.default_height)

        try:
            # 檢查圖標目錄
            if not self.icon_base_path or not os.path.exists(self.icon_base_path):
                self.icon_base_path = self._get_icon_path()

            # 嘗試多個可能的按鈕目錄
            possible_icon_dirs = [
                self.icon_base_path,
                os.path.join(os.path.dirname(self.icon_base_path), "icons"),
                os.path.join(os.path.dirname(os.path.dirname(self.icon_base_path)), "assets", "icons")
            ]

            for normal_icon, hover_icon in icon_names:
                loaded = False

                # 嘗試從多個目錄載入
                for icon_dir in possible_icon_dirs:
                    if not os.path.exists(icon_dir):
                        continue

                    # 載入正常狀態圖標
                    normal_path = self._find_icon_file(icon_dir, normal_icon)
                    hover_path = self._find_icon_file(icon_dir, hover_icon)

                    if normal_path and os.path.exists(normal_path):
                        try:
                            img = Image.open(normal_path)
                            img = img.resize(size, Image.LANCZOS)
                            self.button_icons[normal_icon] = ImageTk.PhotoImage(img)
                            self.logger.debug(f"已載入圖標: {normal_icon} ({normal_path})")

                            # 載入懸停狀態圖標
                            if hover_path and os.path.exists(hover_path):
                                img = Image.open(hover_path)
                                img = img.resize(size, Image.LANCZOS)
                                self.button_icons[hover_icon] = ImageTk.PhotoImage(img)
                                self.logger.debug(f"已載入圖標: {hover_icon} ({hover_path})")
                            else:
                                # 如果找不到懸停圖標，使用正常圖標作為替代
                                self.button_icons[hover_icon] = self.button_icons[normal_icon]
                                self.logger.warning(f"找不到懸停圖標 {hover_icon}，使用 {normal_icon} 替代")

                            loaded = True
                            break
                        except Exception as e:
                            self.logger.error(f"載入圖標 {normal_icon} 時出錯: {e}")

                # 如果所有目錄都找不到圖標，創建空白圖標
                if not loaded:
                    self.logger.warning(f"找不到圖標: {normal_icon} 和 {hover_icon}，使用空白圖標")
                    try:
                        # 創建一個簡單的空白圖標
                        blank_img = self._create_blank_icon(size)
                        self.button_icons[normal_icon] = blank_img
                        self.button_icons[hover_icon] = blank_img
                    except Exception as e:
                        self.logger.error(f"創建空白圖標時出錯: {e}")

        except Exception as e:
            self.logger.error(f"載入圖標時出錯: {e}")

    def _find_icon_file(self, directory: str, icon_name: str) -> str:
        """
        在目錄中尋找圖標文件
        :param directory: 要搜索的目錄
        :param icon_name: 圖標名稱
        :return: 圖標文件的完整路徑，如果找不到則返回空字符串
        """
        # 如果已經包含文件擴展名，直接檢查
        if '.' in icon_name:
            full_path = os.path.join(directory, icon_name)
            if os.path.exists(full_path):
                return full_path

        # 嘗試各種常見擴展名
        for ext in ['.png', '.jpg', '.gif', '.bmp', '.ico']:
            full_path = os.path.join(directory, icon_name + ext)
            if os.path.exists(full_path):
                return full_path

        # 找不到圖標
        return ""

    def _create_blank_icon(self, size: Tuple[int, int]) -> ImageTk.PhotoImage:
        """
        創建空白圖標
        :param size: 圖標尺寸
        :return: 空白圖標
        """
        try:
            img = Image.new('RGBA', size, (200, 200, 200, 128))  # 半透明灰色
            return ImageTk.PhotoImage(img)
        except Exception as e:
            self.logger.error(f"創建空白圖標時出錯: {e}")
            # 創建最小的可能圖像
            return ImageTk.PhotoImage(Image.new('RGB', (1, 1), color='#cccccc'))

    # src/gui/components/button_manager.py 添加

    def get_standard_button_configs(self) -> dict:
        """
        獲取標準化的按鈕配置
        :return: 按鈕配置字典
        """
        return {
            'ok': {
                'normal_icon': 'ok_icon.png',
                'hover_icon': 'ok_hover.png',
                'tooltip': '確認'
            },
            'cancel': {
                'normal_icon': 'cancel.png',
                'hover_icon': 'cancel_hover.png',
                'tooltip': '取消'
            },
            'login': {
                'normal_icon': 'login_icon.png',
                'hover_icon': 'login_hover.png',
                'tooltip': '登入系統'
            },
            'register': {
                'normal_icon': 'register_icon.png',
                'hover_icon': 'register_hover.png',
                'tooltip': '註冊帳號'
            },
            'logout': {
                'normal_icon': 'loginout_icon.png',
                'hover_icon': 'loginout_hover.png',
                'tooltip': '登出系統'
            },
            'add_data': {
                'normal_icon': 'adddata_icon.png',
                'hover_icon': 'adddata_hover.png',
                'tooltip': '新增資料'
            },
            'delete_data': {
                'normal_icon': 'deletedata_icon.png',
                'hover_icon': 'deletedata_hover.png',
                'tooltip': '刪除資料'
            },
            'text_management': {
                'normal_icon': 'text_icon.png',
                'hover_icon': 'text_hover.png',
                'tooltip': '文本管理'
            }
        }

    def get_button_config(self, button_id: str, **overrides) -> dict:
        """
        獲取指定ID的按鈕配置，並應用覆蓋設置
        :param button_id: 按鈕ID
        :param overrides: 覆蓋設置
        :return: 按鈕配置字典
        """
        # 獲取標準配置
        std_configs = self.get_standard_button_configs()

        if button_id in std_configs:
            # 創建配置的副本
            config = std_configs[button_id].copy()

            # 添加按鈕ID
            config['id'] = button_id

            # 應用覆蓋設置
            for key, value in overrides.items():
                config[key] = value

            return config
        else:
            # 返回基本配置
            config = {
                'id': button_id,
                'normal_icon': 'default_icon.png',
                'hover_icon': 'default_hover.png',
                'tooltip': button_id
            }

            # 應用覆蓋設置
            for key, value in overrides.items():
                config[key] = value

            return config

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