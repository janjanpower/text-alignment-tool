"""UI 管理器模組，負責處理所有用戶界面元素"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any, Callable

from gui.components.gui_builder import GUIBuilder
from gui.components.tree_view_manager import TreeViewManager
from gui.components.columns import ColumnConfig


class UIManager:
    """管理用戶界面元素和交互"""

    def __init__(self, master, config):
        """
        初始化 UI 管理器
        :param master: 父視窗
        :param config: 配置管理器
        """
        self.master = master
        self.config = config
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

        # GUI 建構器
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
        """設置主要框架"""
        self.menu_frame = ttk.Frame(main_frame)
        self.menu_frame.pack(fill=tk.X, padx=0, pady=0)

        self.toolbar_frame = ttk.Frame(main_frame)
        self.toolbar_frame.pack(fill=tk.X, padx=0, pady=0)

        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2,3))

    def create_menu(self, menu_commands):
        """
        創建選單列
        :param menu_commands: 選單命令字典，格式 {'檔案': {'開啟': open_function, ...}, ...}
        """
        self.gui_builder.create_menu(self.menu_frame, menu_commands)

    def create_toolbar(self, buttons, image_manager=None):
        """
        創建工具列
        :param buttons: 按鈕配置列表
        :param image_manager: 圖片管理器 (可選)
        """
        if image_manager:
            self.create_image_toolbar(buttons, image_manager)
        else:
            self.create_text_toolbar(buttons)

    def create_image_toolbar(self, buttons, image_manager):
        """創建圖片按鈕工具列"""
        # 設置按鈕圖片尺寸（可根據需要調整）
        button_width = 50  # 按鈕寬度
        button_height = 50  # 按鈕高度

        # 預載入所有按鈕圖片，指定尺寸
        image_manager.load_button_images(width=button_width, height=button_height)

        # 創建工具列按鈕
        self.toolbar_buttons = {}
        for btn_info in buttons:
            self.create_image_button(btn_info, image_manager, width=button_width, height=button_height)

    def create_image_button(self, btn_info, image_manager, width=None, height=None):
        """
        創建圖片按鈕
        :param btn_info: 按鈕信息
        :param image_manager: 圖片管理器
        :param width: 按鈕寬度
        :param height: 按鈕高度
        """
        button_id = btn_info["id"]
        command = btn_info["command"]
        tooltip = btn_info.get("tooltip", "")

        # 獲取按鈕圖片
        normal_img, pressed_img = image_manager.get_button_images(button_id, width, height)
        if not normal_img or not pressed_img:
            self.logger.error(f"無法加載按鈕圖片: {button_id}")
            # 如果加載失敗，創建文字按鈕作為備選
            btn = ttk.Button(self.toolbar_frame, text=tooltip, command=command, width=15)
            btn.pack(side=tk.LEFT, padx=5)
            self.toolbar_buttons[button_id] = btn
            return

        # 創建按鈕框架
        btn_frame = ttk.Frame(self.toolbar_frame)
        btn_frame.pack(side=tk.LEFT, padx=5)

        # 創建標籤按鈕 (使用 Label 而不是 Button，以便自定義按下行為)
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

        # 只綁定按下和釋放事件
        btn.bind("<ButtonPress-1>", lambda e, b=btn: self._on_button_press(e, b))
        btn.bind("<ButtonRelease-1>", lambda e, b=btn: self._on_button_release(e, b))

        # 儲存按鈕引用
        self.toolbar_buttons[button_id] = btn

        # 添加提示文字
        if tooltip:
            self._create_tooltip(btn, tooltip)

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

    def _create_tooltip(self, widget, text):
        """為控件創建提示文字"""
        def enter(event):
            x, y, _, _ = widget.bbox("insert")
            x += widget.winfo_rootx() + 0
            y += widget.winfo_rooty() + 60

            # 創建提示框
            self.tooltip = tk.Toplevel(widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")

            label = ttk.Label(self.tooltip, text=text, background="#ffffe0", relief="solid", borderwidth=3 , padding=(5,2))
            label.pack()

        def leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                delattr(self, 'tooltip')

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)

    def create_text_toolbar(self, buttons):
        """創建文字按鈕工具列（備選方案）"""
        # 遍歷按鈕配置並創建文字按鈕
        self.toolbar_buttons = {}
        for i, btn_info in enumerate(buttons):
            btn = ttk.Button(
                self.toolbar_frame,
                text=btn_info["text"],
                command=btn_info["command"],
                width=btn_info.get("width", 0)
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.toolbar_buttons[f"button_{i}"] = btn

    def create_main_content(self):
        """創建主要內容區域"""
        # 建立內容框架
        self.result_frame = ttk.Frame(self.content_frame)
        self.result_frame.pack(fill=tk.BOTH, expand=True)

        # 建立 Treeview
        self.create_treeview()

    def create_treeview(self, font_manager=None):
        """創建 Treeview"""
        # 創建 Treeview
        self.tree = ttk.Treeview(self.result_frame)

        # 設置 TreeView 字型
        if font_manager:
            style = ttk.Style()
            tree_font = font_manager.get_font(size=10)
            style.configure("Treeview", font=tree_font)
            style.configure("Treeview.Heading", font=tree_font)

        # 初始化 TreeView 管理器
        self.tree_manager = TreeViewManager(self.tree)

        # 設置卷軸
        self.setup_treeview_scrollbars()

        # 設置標籤
        self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
        self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

        # 防止使用者調整欄位寬度
        def handle_resize(event):
            if event.widget.identify_region(event.x, event.y) == "separator":
                return "break"

        self.tree.bind('<Button-1>', handle_resize)

        self.logger.debug("Treeview 創建完成")

    def setup_treeview_scrollbars(self):
        """設置 Treeview 卷軸"""
        # 垂直卷軸
        self.tree_scrollbar = ttk.Scrollbar(
            self.result_frame,
            orient='vertical',
            command=self.tree.yview
        )
        self.tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 配置 Treeview 的卷軸命令
        self.tree['yscrollcommand'] = self.tree_scrollbar.set

        # 將 Treeview 放入框架 - 注意順序很重要
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def setup_treeview_columns(self, display_mode, columns):
        """
        設置 Treeview 列配置
        :param display_mode: 顯示模式
        :param columns: 列名列表
        """
        try:
            # 獲取當前模式的列配置
            columns_for_mode = columns.get(display_mode, [])

            # 添加診斷日誌
            self.logger.debug(f"設置樹狀視圖列，顯示模式: {display_mode}, 列: {columns_for_mode}")

            # 更新 Treeview 列
            self.tree["columns"] = columns_for_mode
            self.tree['show'] = 'headings'  # 確保顯示所有列標題

            # 配置每一列
            for col in columns_for_mode:
                config = self.column_config.COLUMNS.get(col, {
                    'width': 100,
                    'stretch': True if col in ['SRT Text', 'Word Text'] else False,
                    'anchor': 'w' if col in ['SRT Text', 'Word Text'] else 'center'
                })

                # 明確設置每列的寬度、拉伸和錨點
                self.tree.column(col, width=config['width'], stretch=config['stretch'], anchor=config['anchor'])
                self.tree.heading(col, text=col, anchor='center')

                # 對於 SRT Text 列，確保它可見並有適當的寬度
                if col == 'SRT Text':
                    self.tree.column(col, width=300, stretch=True, anchor='w')

            # 確保標籤設置
            self.tree.tag_configure('mismatch', background='#FFDDDD')
            self.tree.tag_configure('use_word_text', background='#00BFFF')

            return True
        except Exception as e:
            self.logger.error(f"設置樹狀視圖列時出錯: {str(e)}")
            return False

    def create_merge_symbol(self):
        """創建合併符號"""
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

    def show_merge_symbol(self, x, y):
        """在指定位置顯示合併符號"""
        if hasattr(self, 'merge_symbol'):
            self.merge_symbol.place(x=x, y=y)

    def hide_merge_symbol(self):
        """隱藏合併符號"""
        if hasattr(self, 'merge_symbol'):
            self.merge_symbol.place_forget()

    def create_floating_correction_icon(self):
        """創建浮動校正圖標"""
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

    def show_floating_icon(self, x, y, callback):
        """顯示浮動校正圖標"""
        if not hasattr(self, 'floating_icon'):
            self.create_floating_correction_icon()

        self.floating_icon.bind("<Button-1>", callback)
        self.floating_icon.place(x=x, y=y)

    def hide_floating_icon(self):
        """隱藏浮動校正圖標"""
        if hasattr(self, 'floating_icon') and not self.floating_icon_fixed:
            self.floating_icon.place_forget()

    def fix_floating_icon(self):
        """固定浮動圖標"""
        self.floating_icon_fixed = True

    def unfix_floating_icon(self):
        """取消固定浮動圖標"""
        self.floating_icon_fixed = False
        self.hide_floating_icon()

    def on_window_resize(self, event):
        """處理窗口大小變化事件"""
        # 僅處理主窗口大小變化
        if event and event.widget == self.master:
            try:
                # 獲取當前窗口尺寸
                window_width = self.master.winfo_width()
                window_height = self.master.winfo_height()

                # 記錄窗口大小變化
                self.logger.debug(f"窗口大小變化: {window_width}x{window_height}")

                # 可以在這裡添加列寬調整邏輯
            except Exception as e:
                # 僅記錄錯誤
                self.logger.error(f"處理窗口大小變化時出錯: {e}")