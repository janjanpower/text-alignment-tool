"""GUI 建構器模組，負責基礎UI元素的創建"""

import logging
import os
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional, Callable, Tuple


class GUIBuilder:
    """處理基礎 GUI 元素的建構，如菜單、工具列、內容區域等"""

    def __init__(self, parent, main_frame):
        """
        初始化 GUI 建構器
        :param parent: 父視窗
        :param main_frame: 主要框架
        """
        self.parent = parent
        self.main_frame = main_frame
        self.logger = logging.getLogger(self.__class__.__name__)

        # 共享變數
        self.file_info_var = None
        self.file_info_label = None
        self.status_var = None
        self.status_label = None

        # 保存創建的工具提示彈窗
        self.tooltip = None

        # 圖片管理器引用，稍後可以設置
        self.image_manager = None

    def set_image_manager(self, image_manager):
        """設置圖片管理器"""
        self.image_manager = image_manager

    def create_menu(self, menu_frame, menu_commands: Dict[str, Dict[str, Callable]]) -> None:
        """
        創建選單列
        :param menu_frame: 選單框架
        :param menu_commands: 選單命令字典，格式 {'檔案': {'開啟': open_function, ...}, ...}
        """
        try:
            menubar = tk.Menu(menu_frame)

            # 建立一個 frame 來放置選單按鈕
            menu_buttons_frame = ttk.Frame(menu_frame)
            menu_buttons_frame.pack(fill=tk.X)

            # 創建各個選單
            for menu_name, commands in menu_commands.items():
                menu = tk.Menu(menubar, tearoff=0)
                menu_button = ttk.Menubutton(menu_buttons_frame, text=menu_name, menu=menu)
                menu_button.pack(side=tk.LEFT, padx=2)

                # 添加各個命令
                for command_name, command_func in commands.items():
                    if command_name == "separator":
                        menu.add_separator()
                    else:
                        menu.add_command(label=command_name, command=command_func)
        except Exception as e:
            self.logger.error(f"創建選單時出錯: {e}")

    def create_toolbar(self, toolbar_frame, buttons: List[Dict[str, Any]]) -> Dict[str, tk.Widget]:
        """
        創建工具列，支援文字或圖片按鈕
        :param toolbar_frame: 工具列框架
        :param buttons: 按鈕配置列表
        :return: 創建的按鈕字典 {button_id: button_widget}
        """
        created_buttons = {}

        try:
            # 使用 enumerate 來追蹤每個按鈕的位置
            for index, button_config in enumerate(buttons):
                button_id = button_config.get('id', f'button_{index}')
                text = button_config.get('text', '')
                command = button_config.get('command', None)
                width = button_config.get('width', 15)
                tooltip = button_config.get('tooltip', text)
                icon_id = button_config.get('icon_id', None)
                side = button_config.get('side', tk.LEFT)

                # 判斷是否使用圖示按鈕
                if icon_id and self.image_manager:
                    # 創建圖示按鈕
                    btn = self.image_manager.create_image_button(
                        toolbar_frame,
                        icon_id,
                        command,
                        tooltip=tooltip
                    )
                    btn.pack(side=side, padx=5)
                else:
                    # 創建文字按鈕
                    btn = ttk.Button(
                        toolbar_frame,
                        text=text,
                        command=command,
                        width=width,
                        style='Custom.TButton'
                    )
                    btn.pack(side=side, padx=5)

                    # 添加提示文字
                    if tooltip:
                        self.create_tooltip(btn, tooltip)

                # 保存創建的按鈕
                created_buttons[button_id] = btn

            return created_buttons

        except Exception as e:
            self.logger.error(f"創建工具列時出錯: {e}")
            return created_buttons

    def create_image_button(self, toolbar_frame, button_config: Dict, normal_img, pressed_img) -> tk.Label:
        """
        創建圖像按鈕
        :param toolbar_frame: 工具列框架
        :param button_config: 按鈕配置
        :param normal_img: 正常狀態的圖像
        :param pressed_img: 按下狀態的圖像
        :return: 創建的按鈕
        """
        try:
            command = button_config.get('command', None)
            tooltip = button_config.get('tooltip', '')
            side = button_config.get('side', tk.LEFT)

            # 創建按鈕框架
            btn_frame = ttk.Frame(toolbar_frame)
            btn_frame.pack(side=side, padx=5)

            # 創建標籤按鈕
            btn = tk.Label(
                btn_frame,
                image=normal_img,
                cursor="hand2"
            )
            btn.normal_image = normal_img  # 保存引用以避免垃圾回收
            btn.pressed_image = pressed_img  # 保存引用以避免垃圾回收
            btn.pack()

            # 儲存原始命令
            btn.command = command

            # 綁定按下和釋放事件
            btn.bind("<ButtonPress-1>", lambda e, b=btn: self._on_button_press(e, b))
            btn.bind("<ButtonRelease-1>", lambda e, b=btn: self._on_button_release(e, b))

            # 添加提示文字
            if tooltip:
                self.create_tooltip(btn, tooltip)

            return btn
        except Exception as e:
            self.logger.error(f"創建圖像按鈕時出錯: {e}")
            return None

    def _on_button_press(self, event, button):
        """滑鼠按下按鈕事件處理"""
        if hasattr(button, 'pressed_image'):
            button.configure(image=button.pressed_image)
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

    def create_tooltip(self, widget, text: str) -> None:
        """
        為控件創建提示文字
        :param widget: 要添加提示的控件
        :param text: 提示文字
        """
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 20
            y += widget.winfo_rooty() - 20

            # 創建提示框
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")

            label = ttk.Label(self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=1, padding=(5,2))
            label.pack()

        def leave(event):
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def create_main_content(self, content_frame) -> ttk.Frame:
        """
        創建主要內容區域
        :param content_frame: 內容框架
        :return: 創建的框架
        """
        try:
            # 創建個在內容框架中的容器，用於存放樹狀視圖等控件
            container = ttk.Frame(content_frame)
            container.pack(fill=tk.BOTH, expand=True, padx=5, pady=0)

            return container
        except Exception as e:
            self.logger.error(f"創建主要內容區域時出錯: {e}")
            return ttk.Frame(content_frame)  # 傳回一個空的框架避免程式崩潰

    def create_file_info_area(self, frame) -> None:
        """
        創建檔案資訊顯示區域
        :param frame: 父框架
        """
        try:
            # 檔案資訊區域（無外框）
            self.file_info_frame = ttk.Frame(frame)
            self.file_info_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5, padx=5)

            # 檔案資訊標籤（置中）
            self.file_info_var = tk.StringVar(value="尚未載入任何檔案")
            self.file_info_label = ttk.Label(
                self.file_info_frame,
                textvariable=self.file_info_var,
                style='Custom.TLabel',
                anchor='center'  # 文字置中
            )
            self.file_info_label.pack(fill=tk.X, pady=0)
        except Exception as e:
            self.logger.error(f"創建檔案資訊區域時出錯: {e}")

    def create_status_bar(self, frame) -> None:
        """
        創建狀態列
        :param frame: 父框架
        """
        try:
            self.status_var = tk.StringVar()
            self.status_label = ttk.Label(
                frame,
                textvariable=self.status_var,
                style='Custom.TLabel'
            )
            self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=0)
        except Exception as e:
            self.logger.error(f"創建狀態列時出錯: {e}")

    def create_treeview_with_scrollbar(self, frame) -> Tuple[ttk.Treeview, ttk.Scrollbar]:
        """
        創建帶捲軸的樹狀視圖
        :param frame: 父框架
        :return: (樹狀視圖, 捲軸)
        """
        try:
            # 創建樹狀視圖
            tree = ttk.Treeview(frame)

            # 垂直捲軸
            scrollbar = ttk.Scrollbar(
                frame,
                orient='vertical',
                command=tree.yview
            )
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            # 配置樹狀視圖的捲軸命令
            tree['yscrollcommand'] = scrollbar.set

            # 樹狀視圖放入框架
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            return tree, scrollbar
        except Exception as e:
            self.logger.error(f"創建帶捲軸的樹狀視圖時出錯: {e}")
            # 返回空的樹狀視圖和捲軸，避免程式崩潰
            empty_tree = ttk.Treeview(frame)
            empty_scrollbar = ttk.Scrollbar(frame)
            return empty_tree, empty_scrollbar

    def update_file_info(self, info_text: str) -> None:
        """
        更新檔案資訊顯示
        :param info_text: 要顯示的資訊文字
        """
        if self.file_info_var:
            self.file_info_var.set(info_text)

    def update_status(self, status_text: str) -> None:
        """
        更新狀態列訊息
        :param status_text: 狀態訊息
        """
        if self.status_var:
            self.status_var.set(status_text)

    def create_button_set(self, frame, button_configs, image_manager=None):
        """
        創建一組按鈕，支援圖示按鈕和文字按鈕

        :param frame: 父框架
        :param button_configs: 按鈕配置列表
        :param image_manager: 圖片管理器 (可選)
        :return: 創建的按鈕字典 {button_id: button_widget}
        """
        buttons = {}

        for config in button_configs:
            button_id = config.get('id', f'btn_{len(buttons)}')
            text = config.get('text', '')
            command = config.get('command')
            icon_id = config.get('icon_id')
            tooltip = config.get('tooltip', text)
            width = config.get('width', 10)
            side = config.get('side', tk.LEFT)
            padx = config.get('padx', 5)
            pady = config.get('pady', 0)

            # 判斷是使用圖示按鈕還是文字按鈕
            if icon_id and image_manager:
                # 建立圖示按鈕
                btn = image_manager.create_image_button(
                    frame,
                    icon_id,
                    command,
                    tooltip=tooltip
                )
            else:
                # 建立文字按鈕
                btn = ttk.Button(
                    frame,
                    text=text,
                    command=command,
                    width=width
                )
                # 添加提示文字
                if tooltip:
                    self.create_tooltip(btn, tooltip)

            # 放置按鈕
            btn.pack(side=side, padx=padx, pady=pady)

            # 保存按鈕引用
            buttons[button_id] = btn

        return buttons