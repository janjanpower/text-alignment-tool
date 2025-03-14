"""文本對齊工具主界面核心模組"""

import logging
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog

# 避免循環導入
from gui.alignment.tree_manager import TreeManager
from gui.alignment.audio_integration import AudioIntegration
from gui.alignment.word_integration import WordIntegration
from gui.alignment.correction_handler import CorrectionHandler
from gui.alignment.state_handling import StateHandling
from gui.alignment.ui_events import UIEventHandler

from gui.base_window import BaseWindow
from gui.custom_messagebox import show_info, show_warning, show_error, ask_question
from services.config_manager import ConfigManager
from services.correction_state_manager import CorrectionStateManager
from services.state_manager import StateManager

class AlignmentGUI(BaseWindow):
    """文本對齊工具主界面類別"""

    # 定義顯示模式常量
    DISPLAY_MODE_SRT = "srt"                  # 僅 SRT
    DISPLAY_MODE_SRT_WORD = "srt_word"        # SRT + Word
    DISPLAY_MODE_AUDIO_SRT = "audio_srt"      # SRT + Audio
    DISPLAY_MODE_ALL = "all"                  # SRT + Word + Audio

    def __init__(self, master=None):
        """初始化主界面"""
        # 加載配置
        self.config = ConfigManager()
        window_config = self.config.get_window_config()

        # 調用父類初始化
        super().__init__(
            title=window_config.get('title', '文本對齊工具'),
            width=1000,
            height=420,
            master=master
        )

        # 初始化變數
        self._initialize_variables()

        # 設置日誌
        self._setup_logging()

        # 創建界面元素
        self._create_gui_elements()

        # 初始化子模組
        self._initialize_submodules()

        # 綁定事件
        self._bind_all_events()

        # 最後添加窗口大小變化事件綁定
        self.master.bind("<Configure>", self.on_window_resize)

        # 初始化後進行一次列寬調整
        self.master.after(100, lambda: self.on_window_resize(None))

    def _initialize_variables(self):
        """初始化變數"""
        # 基本狀態
        self.display_mode = self.DISPLAY_MODE_SRT
        self.srt_imported = False
        self.audio_imported = False
        self.word_imported = False

        # 文件路徑
        self.srt_file_path = None
        self.audio_file_path = None
        self.word_file_path = None
        self.current_project_path = None

        # 其他狀態變數
        self.audio_notification_shown = False
        self.srt_data = []
        self.database_file = None

        # 界面元素
        self.tree = None
        self.status_var = tk.StringVar()
        self.file_info_var = tk.StringVar(value="尚未載入任何檔案")

        # 列配置
        self.columns = {
            self.DISPLAY_MODE_SRT: ['Index', 'Start', 'End', 'SRT Text', 'V/X'],
            self.DISPLAY_MODE_SRT_WORD: ['Index', 'Start', 'End', 'SRT Text', 'Word Text', 'Match', 'V/X'],
            self.DISPLAY_MODE_AUDIO_SRT: ['V.O', 'Index', 'Start', 'End', 'SRT Text', 'V/X'],
            self.DISPLAY_MODE_ALL: ['V.O', 'Index', 'Start', 'End', 'SRT Text', 'Word Text', 'Match', 'V/X'],
        }

        # 各種標記和索引
        self.use_word_text = {}
        self.edited_text_info = {}
        self.PLAY_ICON = "▶"

        # 定義新的變數
        self.merge_symbol = None
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.current_selected_items = []
        self.time_slider = None
        self.slider_active = False
        self.slider_target = None
        self.slider_start_value = 0

    def _setup_logging(self):
        """設置日誌"""
        self.logger = logging.getLogger(self.__class__.__name__)
        handler = logging.FileHandler('alignment_gui.log', encoding='utf-8')
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def _create_gui_elements(self):
        """創建主要界面元素"""
        # 創建選單列
        self._create_menu()

        # 創建工具列
        self._create_toolbar()

        # 創建主要內容區域
        self._create_main_content()

        # 創建底部檔案信息區域
        self._create_file_info_area()

        # 最後創建狀態欄
        self._create_status_bar()

        # 創建合併符號 ("+")
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
        # 綁定點擊事件
        self.merge_symbol.bind('<Button-1>', lambda e: self.combine_sentences())

    def _create_menu(self):
        """創建選單列"""
        self.menubar = tk.Menu(self.menu_frame)

        # 建立一個 frame 來放置選單按鈕
        menu_buttons_frame = ttk.Frame(self.menu_frame)
        menu_buttons_frame.pack(fill=tk.X)

        # 檔案選單
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_button = ttk.Menubutton(menu_buttons_frame, text="檔案", menu=file_menu)
        file_button.pack(side=tk.LEFT, padx=2)

        file_menu.add_command(label="切換專案", command=self.switch_project)
        file_menu.add_separator()
        file_menu.add_command(label="開啟 SRT", command=self.load_srt)
        file_menu.add_command(label="儲存", command=self.save_srt)
        file_menu.add_command(label="另存新檔", command=self.save_srt_as)
        file_menu.add_separator()
        file_menu.add_command(label="離開", command=self.close_window)

        # 編輯選單
        edit_menu = tk.Menu(self.menubar, tearoff=0)
        edit_button = ttk.Menubutton(menu_buttons_frame, text="編輯", menu=edit_menu)
        edit_button.pack(side=tk.LEFT, padx=2)

        edit_menu.add_command(label="復原 Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="重做 Ctrl+Y", command=self.redo)

    def _create_toolbar(self):
        """創建工具列"""
        self.toolbar_frame = ttk.Frame(self.main_frame)
        self.toolbar_frame.pack(fill=tk.X, padx=5, pady=5)

        # 建立工具列按鈕
        buttons = [
            ("載入 SRT", self.load_srt),
            ("匯入音頻", self.import_audio),
            ("載入 Word", self.import_word_document),
            ("重新比對", self.compare_word_with_srt),
            ("調整時間", self.align_end_times),
            ("匯出 SRT", lambda: self.export_srt(from_toolbar=False))
        ]

        for text, command in buttons:
            btn = ttk.Button(
                self.toolbar_frame,
                text=text,
                command=command,
                width=15,
                style='Custom.TButton'
            )
            btn.pack(side=tk.LEFT, padx=5)

    def _create_main_content(self):
        """創建主要內容區域"""
        # 建立內容框架
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 結果框架
        self.result_frame = ttk.Frame(self.content_frame)
        self.result_frame.pack(fill=tk.BOTH, expand=True)

        # 創建 TreeManager 實例
        self.tree_manager = TreeManager(self)
        self.tree = self.tree_manager.create_treeview(self.result_frame, self.columns[self.display_mode])

    def _create_file_info_area(self):
        """創建檔案資訊顯示區域"""
        # 檔案資訊區域（無外框）
        self.file_info_frame = ttk.Frame(self.main_frame)
        self.file_info_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5, padx=5)

        # 檔案資訊標籤（置中）
        self.file_info_label = ttk.Label(
            self.file_info_frame,
            textvariable=self.file_info_var,
            style='Custom.TLabel',
            anchor='center'
        )
        self.file_info_label.pack(fill=tk.X, pady=5)

    def _create_status_bar(self):
        """創建狀態列"""
        # 檢查並創建狀態變數
        self.status_label = ttk.Label(
            self.main_frame,
            textvariable=self.status_var,
            style='Custom.TLabel'
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=2)

    def _initialize_submodules(self):
        """初始化子模組，包括樹視圖管理、UI事件處理、音頻/Word集成和狀態管理"""
        # 初始化樹視圖管理器
        self.tree_manager = TreeManager(self)
        self.tree = self.tree_manager.create_treeview(self.content_frame, self.columns[self.display_mode])

        # 初始化校正狀態管理器
        self.correction_state_manager = CorrectionStateManager(self.tree)

        # 初始化狀態管理器 - 用於撤銷/重做功能
        self.state_manager = StateManager(max_states=50)

        # 初始化音頻播放器和集成
        self.audio_integration = AudioIntegration(self)
        self.audio_player = self.audio_integration.initialize_audio_player()

        # 初始化 Word 處理和集成
        self.word_processor = WordProcessor()
        self.word_integration = WordIntegration(self, self.word_processor)

        # 初始化校正處理器
        self.correction_handler = CorrectionHandler(self)

        # 初始化狀態處理器 - 處理撤銷/重做邏輯
        self.state_handling = StateHandling(self)

        # 初始化 UI 事件處理器
        self.ui_events = UIEventHandler(self)

        # 設置委派方法 - 將某些方法委派給子模組
        # 撤銷/重做操作
        self.undo = self.state_handling.undo
        self.redo = self.state_handling.redo

        # UI 事件相關
        self.on_tree_click = self.ui_events.on_tree_click
        self.on_double_click = self.ui_events.on_double_click
        self.on_treeview_select = self.ui_events.on_treeview_select
        self.combine_sentences = self.ui_events.combine_sentences

        # 校正相關
        self.load_corrections = self.correction_handler.load_corrections
        self.correct_text = self.correction_handler.correct_text
        self.check_text_correction = self.correction_handler.check_text_correction

        # Word 相關
        self.import_word_document = self.word_integration.import_word_document
        self.compare_word_with_srt = self.word_integration.compare_word_with_srt

        # 音頻相關
        self.import_audio = self.audio_integration.import_audio
        self.play_audio_segment = self.audio_integration.play_audio_segment

        # 綁定所有事件
        self.ui_events.bind_all_events()

    def _bind_all_events(self):
        """綁定所有事件"""
        # 綁定視窗關閉事件
        self.master.protocol("WM_DELETE_WINDOW", self.close_window)

        # 綁定全域快捷鍵
        self.master.bind_all('<Control-s>', lambda e: self.save_srt())
        self.master.bind_all('<Control-o>', lambda e: self.load_srt())
        self.master.bind_all('<Control-z>', lambda e: self.undo())
        self.master.bind_all('<Control-y>', lambda e: self.redo())

        # 綁定 Treeview 特定事件
        self.tree.bind('<Button-1>', self.on_tree_click)
        self.tree.bind('<Double-1>', self._handle_double_click)
        self.tree.bind('<KeyRelease>', self.on_treeview_change)

        # 添加樹狀視圖選擇事件綁定
        self.tree.bind("<<TreeviewSelect>>", self.on_treeview_select)

        # 添加滑鼠移動事件綁定，用於更新合併符號位置
        self.master.bind("<Motion>", self.remember_mouse_position)

    def update_status(self, message=None):
        """
        更新狀態列訊息
        :param message: 狀態訊息（可選）
        """
        if message:
            self.status_var.set(message)

        # 更新檔案狀態
        file_status_parts = []

        # 添加 SRT 文件狀態
        if self.srt_file_path:
            file_status_parts.append(f"SRT檔案：{os.path.basename(self.srt_file_path)}")

        # 添加音頻文件狀態
        if hasattr(self, 'audio_file_path') and self.audio_file_path:
            file_status_parts.append(f"音頻檔案：{os.path.basename(self.audio_file_path)}")

        self.master.update_idletasks()

    def on_window_resize(self, event=None):
        """處理窗口大小變化事件"""
        # 僅在必要時啟用
        return

    def run(self):
        """運行界面"""
        self.master.mainloop()

    # 其他從主類繼承的方法，但在這裡不實現詳細內容，由子模組提供
    def load_srt(self, event=None, file_path=None):
        """由audio_integration模組實現"""
        return self.audio_integration.load_srt(event, file_path)

    def save_srt(self, event=None):
        """由state_handling模組實現"""
        return self.state_handling.save_srt(event)

    def save_srt_as(self):
        """由state_handling模組實現"""
        return self.state_handling.save_srt_as()

    def switch_project(self):
        """由ui_events模組實現"""
        return self.ui_events.switch_project()

    def close_window(self, event=None):
        """由ui_events模組實現"""
        return self.ui_events.close_window(event)

    def on_treeview_change(self, event):
        """由ui_events模組實現"""
        return self.ui_events.on_treeview_change(event)

    def on_tree_click(self, event):
        """由ui_events模組實現"""
        return self.ui_events.on_tree_click(event)

    def _handle_double_click(self, event):
        """由ui_events模組實現"""
        return self.ui_events._handle_double_click(event)

    def on_treeview_select(self, event=None):
        """由ui_events模組實現"""
        return self.ui_events.on_treeview_select(event)

    def remember_mouse_position(self, event):
        """由ui_events模組實現"""
        return self.ui_events.remember_mouse_position(event)

    def import_audio(self):
        """由audio_integration模組實現"""
        return self.audio_integration.import_audio()

    def import_word_document(self):
        """由word_integration模組實現"""
        return self.word_integration.import_word_document()

    def compare_word_with_srt(self):
        """由word_integration模組實現"""
        return self.word_integration.compare_word_with_srt()

    def align_end_times(self):
        """由ui_events模組實現"""
        return self.ui_events.align_end_times()

    def export_srt(self, from_toolbar=False):
        """由state_handling模組實現"""
        return self.state_handling.export_srt(from_toolbar)

    def undo(self, event=None):
        """由state_handling模組實現"""
        return self.state_handling.undo(event)

    def redo(self, event=None):
        """由state_handling模組實現"""
        return self.state_handling.redo(event)

    def combine_sentences(self, event=None):
        """由ui_events模組實現"""
        return self.ui_events.combine_sentences(event)