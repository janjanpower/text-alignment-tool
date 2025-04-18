"""UI 管理器模組，負責管理所有用戶界面元素"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any, Callable, Tuple

from gui.components.gui_builder import GUIBuilder
from gui.components.tree_view_manager import TreeViewManager
from gui.components.columns import ColumnConfig


class UIManager:
    """管理用戶界面元素和交互，基於 GUIBuilder 提供高層次的界面管理"""

    def __init__(self, master, config, font_manager=None):
        """
        初始化 UI 管理器
        :param master: 父視窗
        :param config: 配置管理器
        :param font_manager: 字體管理器
        """
        self.master = master
        self.config = config
        self.font_manager = font_manager
        self.logger = logging.getLogger(self.__class__.__name__)

        # 基本 UI 元素
        self.menu_frame = None
        self.toolbar_frame = None
        self.content_frame = None
        self.result_frame = None

        # 樹狀視圖相關
        self.tree = None
        self.tree_manager = None
        self.tree_scrollbar = None

        # 直接使用 GUIBuilder 進行基礎元素創建
        self.gui_builder = GUIBuilder(self.master, self.master)

        # 按鈕和圖標
        self.toolbar_buttons = {}
        self.floating_icon = None
        self.floating_icon_fixed = False
        self.merge_symbol = None

        # 顯示模式和列配置
        self.PLAY_ICON = "▶"
        self.column_config = ColumnConfig()

    def setup_frames(self, main_frame):
        """
        設置主要框架
        :param main_frame: 主框架
        """
        # 創建菜單框架
        self.menu_frame = ttk.Frame(main_frame)
        self.menu_frame.pack(fill=tk.X, padx=0, pady=0)

        # 創建工具列框架
        self.toolbar_frame = ttk.Frame(main_frame)
        self.toolbar_frame.pack(fill=tk.X, padx=5, pady=5)

        # 創建內容框架
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2,3))

        # 創建文件信息區域和狀態欄
        self.gui_builder.create_file_info_area(main_frame)
        self.gui_builder.create_status_bar(main_frame)

    def create_menu(self, menu_commands):
        """
        創建選單列 - 使用 GUIBuilder
        :param menu_commands: 選單命令字典
        """
        self.gui_builder.create_menu(self.menu_frame, menu_commands)

    def create_toolbar(self, buttons, image_manager=None):
        """
        創建工具列 - 根據是否提供圖片管理器決定創建圖片或文字工具列
        :param buttons: 按鈕配置列表
        :param image_manager: 圖片管理器 (可選)
        """
        if image_manager:
            self.create_image_toolbar(buttons, image_manager)
        else:
            self.create_text_toolbar(buttons)

    def create_image_toolbar(self, buttons, image_manager):
        """
        創建圖片按鈕工具列
        :param buttons: 按鈕配置列表
        :param image_manager: 圖片管理器
        """
        # 設置按鈕圖片尺寸
        button_width = 108
        button_height = 30

        # 預載入所有按鈕圖片
        image_manager.load_button_images(width=button_width, height=button_height)

        # 創建工具列按鈕
        self.toolbar_buttons = {}
        for btn_info in buttons:
            button_id = btn_info["id"]
            command = btn_info["command"]
            tooltip = btn_info.get("tooltip", "")

            # 獲取按鈕圖片
            normal_img, pressed_img = image_manager.get_button_images(button_id, width=button_width, height=button_height)

            if normal_img and pressed_img:
                # 使用 GUIBuilder 創建圖像按鈕
                btn = self.gui_builder.create_image_button(
                    self.toolbar_frame,
                    btn_info,
                    normal_img,
                    pressed_img
                )
                if btn:
                    self.toolbar_buttons[button_id] = btn
            else:
                # 圖片加載失敗，創建文字按鈕作為備選
                self.logger.warning(f"無法加載按鈕圖片: {button_id}，使用文字按鈕代替")
                btn = ttk.Button(self.toolbar_frame, text=tooltip, command=command, width=15)
                btn.pack(side=tk.LEFT, padx=5)
                self.toolbar_buttons[button_id] = btn

    def create_text_toolbar(self, buttons):
        """
        創建文字按鈕工具列
        :param buttons: 按鈕配置列表
        """
        # 調用 GUIBuilder 創建基本工具列
        tool_buttons = []
        for i, btn_info in enumerate(buttons):
            tool_buttons.append({
                'text': btn_info.get("text", f"Button {i}"),
                'command': btn_info.get("command"),
                'width': btn_info.get("width", 15)
            })

        self.gui_builder.create_toolbar(self.toolbar_frame, tool_buttons)

    def create_main_content(self):
        """創建主要內容區域並初始化樹狀視圖"""
        # 使用 GUIBuilder 創建內容容器
        self.result_frame = self.gui_builder.create_main_content(self.content_frame)

        # 創建樹狀視圖
        self.create_treeview()

    def create_treeview(self):
        """創建樹狀視圖及其管理器"""
        # 使用 GUIBuilder 創建樹狀視圖和捲軸
        self.tree, self.tree_scrollbar = self.gui_builder.create_treeview_with_scrollbar(self.result_frame)

        # 設置樹狀視圖字型
        if self.font_manager:
            style = ttk.Style()
            tree_font = self.font_manager.get_font(size=10)
            style.configure("Treeview", font=tree_font)
            style.configure("Treeview.Heading", font=tree_font)

        # 初始化 TreeView 管理器
        self.tree_manager = TreeViewManager(self.tree)

        # 設置標籤
        self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
        self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

        # 防止使用者調整欄位寬度
        def handle_resize(event):
            if event.widget.identify_region(event.x, event.y) == "separator":
                return "break"

        self.tree.bind('<Button-1>', handle_resize)

        self.logger.debug("Treeview 創建完成")

    def setup_treeview_columns(self, display_mode, columns_config):
        """
        設置樹狀視圖列配置
        :param display_mode: 顯示模式
        :param columns_config: 列配置字典，格式: {模式: [列名列表]}
        :return: 是否成功
        """
        try:
            # 獲取當前模式的列配置
            columns = columns_config.get(display_mode, [])
            if not columns:
                self.logger.warning(f"未找到顯示模式 {display_mode} 的列配置")
                return False

            # 更新樹狀視圖列
            self.tree["columns"] = columns
            self.tree['show'] = 'headings'  # 確保顯示所有列標題

            # 配置每一列
            for col in columns:
                config = self.column_config.COLUMNS.get(col, {
                    'width': 100,
                    'stretch': True if col in ['SRT Text', 'Word Text'] else False,
                    'anchor': 'w' if col in ['SRT Text', 'Word Text'] else 'center'
                })

                self.tree_manager.set_column_config(
                    col,
                    width=config['width'],
                    stretch=config['stretch'],
                    anchor=config['anchor']
                )
                self.tree_manager.set_heading(col, text=col, anchor='center')

            return True

        except Exception as e:
            self.logger.error(f"設置樹狀視圖列時出錯: {e}")
            return False

    def create_merge_symbol(self):
        """創建用於合併操作的加號符號"""
        if not hasattr(self, 'merge_symbol') or self.merge_symbol is None:
            self.merge_symbol = tk.Label(
                self.tree,
                text="+",
                font=("Arial", 16, "bold"),
                bg="#4CAF50",
                fg="white",
                width=2,
                height=1,
                relief="raised"
            )

        return self.merge_symbol

    def show_merge_symbol(self, x, y, callback=None):
        """
        在指定位置顯示合併符號
        :param x: X坐標
        :param y: Y坐標
        :param callback: 點擊回調
        """
        if not hasattr(self, 'merge_symbol') or self.merge_symbol is None:
            self.create_merge_symbol()

        # 如果提供了回調，綁定點擊事件
        if callback and callable(callback):
            self.merge_symbol.bind('<Button-1>', callback)

        # 確保合併符號在可視範圍內
        tree_width = self.tree.winfo_width()
        tree_height = self.tree.winfo_height()

        x = min(x, tree_width - 30)  # 避免超出右邊界
        y = min(y, tree_height - 30)  # 避免超出下邊界
        y = max(y, 10)  # 避免超出上邊界

        self.merge_symbol.place(x=x, y=y)

    def hide_merge_symbol(self):
        """隱藏合併符號"""
        if hasattr(self, 'merge_symbol') and self.merge_symbol:
            self.merge_symbol.place_forget()

    def create_floating_correction_icon(self, callback=None):
        """
        創建浮動校正圖標
        :param callback: 點擊回調
        :return: 創建的圖標
        """
        if not hasattr(self, 'floating_icon') or self.floating_icon is None:
            self.floating_icon = tk.Label(
                self.tree,
                text="✚",  # 使用十字形加號
                bg="#E0F7FA",  # 淺藍色背景
                fg="#00796B",  # 深綠色前景
                font=("Arial", 12),
                cursor="hand2",
                relief=tk.RAISED,  # 突起的外觀
                borderwidth=1,  # 添加邊框
                padx=3,  # 水平內邊距
                pady=1   # 垂直內邊距
            )
            self.floating_icon_fixed = False

            # 如果提供了回調，綁定點擊事件
            if callback and callable(callback):
                self.floating_icon.bind("<Button-1>", callback)

        return self.floating_icon

    def show_floating_icon(self, x, y, callback=None):
        """
        顯示浮動校正圖標
        :param x: X坐標
        :param y: Y坐標
        :param callback: 點擊回調
        """
        if not hasattr(self, 'floating_icon') or self.floating_icon is None:
            self.create_floating_correction_icon(callback)
        elif callback and callable(callback):
            # 更新現有圖標的回調
            self.floating_icon.bind("<Button-1>", callback)

        self.floating_icon.place(x=x, y=y)

    def hide_floating_icon(self):
        """隱藏浮動校正圖標"""
        if hasattr(self, 'floating_icon') and self.floating_icon and not self.floating_icon_fixed:
            self.floating_icon.place_forget()

    def fix_floating_icon(self):
        """固定浮動圖標，防止被自動隱藏"""
        self.floating_icon_fixed = True

    def unfix_floating_icon(self):
        """取消固定浮動圖標"""
        self.floating_icon_fixed = False
        self.hide_floating_icon()

    def update_file_info(self, info_text):
        """
        更新文件信息區域
        :param info_text: 要顯示的信息
        """
        self.gui_builder.update_file_info(info_text)

    def update_status(self, status_text):
        """
        更新狀態欄
        :param status_text: 狀態信息
        """
        self.gui_builder.update_status(status_text)

    def clear_treeview(self):
        """清空樹狀視圖內容"""
        if self.tree_manager:
            self.tree_manager.clear_all()

    def get_all_items(self):
        """獲取樹狀視圖中的所有項目"""
        if self.tree_manager:
            return self.tree_manager.get_all_items()
        return []

    def on_window_resize(self, event):
        """
        處理窗口大小變化事件
        :param event: 窗口大小變化事件
        """
        # 僅處理主窗口大小變化
        if event and event.widget == self.master:
            try:
                # 獲取當前窗口尺寸
                window_width = self.master.winfo_width()
                window_height = self.master.winfo_height()

                # 記錄窗口大小變化
                self.logger.debug(f"窗口大小變化: {window_width}x{window_height}")

                # 可以在這裡添加根據窗口大小動態調整列寬的邏輯

            except Exception as e:
                self.logger.error(f"處理窗口大小變化時出錯: {e}")