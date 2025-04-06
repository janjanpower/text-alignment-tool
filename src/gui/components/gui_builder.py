"""GUI 建構器模組，負責創建各種界面元素"""

import os
import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional, Callable, Tuple

from gui.components.columns import ColumnConfig


class GUIBuilder:
    """處理 GUI 元素的建構，如菜單、工具列、內容區域等"""

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

    def create_toolbar(self, toolbar_frame, buttons: List[Dict[str, Any]]) -> None:
        """
        創建工具列
        :param toolbar_frame: 工具列框架
        :param buttons: 按鈕配置列表，格式 [{'text': '按鈕文字', 'command': 按鈕命令, 'width': 寬度}, ...]
        """
        try:
            # 使用 enumerate 來追蹤每個按鈕的位置
            for index, button_config in enumerate(buttons):
                text = button_config.get('text', '')
                command = button_config.get('command', None)
                width = button_config.get('width', 15)

                btn = ttk.Button(
                    toolbar_frame,
                    text=text,
                    command=command,
                    width=width,
                    style='Custom.TButton'
                )
                btn.pack(side=tk.LEFT, padx=5)
        except Exception as e:
            self.logger.error(f"創建工具列時出錯: {e}")

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

    def setup_treeview_columns(self, tree, display_mode, columns_config):
        """
        設置樹狀視圖的列
        :param tree: 樹狀視圖
        :param display_mode: 顯示模式
        :param columns_config: 列配置
        """
        try:
            # 獲取當前模式的列配置
            columns = columns_config.get(display_mode, [])

            # 更新樹狀視圖列
            tree["columns"] = columns
            tree['show'] = 'headings'

            # 配置每一列
            for col in columns:
                config = ColumnConfig.COLUMNS.get(col, {
                    'width': 100,
                    'stretch': True if col in ['SRT Text', 'Word Text'] else False,
                    'anchor': 'w' if col in ['SRT Text', 'Word Text'] else 'center'
                })

                tree.column(col,
                    width=config['width'],
                    stretch=config['stretch'],
                    anchor=config['anchor'])
                tree.heading(col, text=col, anchor='center')

            # 設置標籤樣式
            tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

            return True
        except Exception as e:
            self.logger.error(f"設置樹狀視圖列時出錯: {e}")
            return False

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