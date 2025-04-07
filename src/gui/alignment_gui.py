"""文本對齊工具主界面模組"""

import logging
import os
import sys
import time
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any

import pysrt
from gui.base_window import BaseWindow
from gui.components.columns import ColumnConfig
from gui.components.gui_builder import GUIBuilder
from gui.components.tree_view_manager import TreeViewManager
from gui.custom_messagebox import (
    show_info,
    show_warning,
    show_error,
    ask_question
)
from gui.quick_correction_dialog import QuickCorrectionDialog
from gui.text_edit_dialog import TextEditDialog
from services.combine_service import CombineService
from services.config_manager import ConfigManager
from services.correction_service import CorrectionService
from services.enhanced_state_manager import EnhancedStateManager
from services.file_manager import FileManager
from services.split_service import SplitService
from services.word_processor import WordProcessor
from utils.image_manager import ImageManager
from utils.text_utils import simplify_to_traditional
from utils.time_utils import parse_time,time_to_milliseconds, milliseconds_to_time, time_to_seconds
from gui.slider_controller import TimeSliderController

# 添加項目根目錄到路徑以確保絕對導入能正常工作
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


class AlignmentGUI(BaseWindow):
    """文本對齊工具主界面類別"""
    def __init__(self, master: Optional[tk.Tk] = None) -> None:
        """初始化主界面"""
        # 加載配置
        self.config = ConfigManager()
        window_config = self.config.get_window_config()

        # 調用父類初始化
        super().__init__(
            title=window_config['title'],
            width=1000,
            height=500,
            master=master
        )

        # 初始化變數
        self.initialize_variables()

        # 設置日誌
        self.setup_logging()

        # 初始化圖片管理器

        self.image_manager = ImageManager()

        # 創建界面元素 (注意這裡的順序很重要)
        self.create_gui_elements()

        # 初始化校正服務
        self.correction_service = CorrectionService()
        # 初始化合併服務
        self.combine_service = CombineService(self)
        self.split_service = SplitService(self)

        # 初始化增強狀態管理器
        self.initialize_state_manager()

        # 在初始化後保存初始狀態
        self.master.after(500, lambda: self.save_initial_state())

        # 初始化檔案管理器
        self.initialize_file_manager()

        # 初始化音頻播放器
        self.initialize_audio_player()

        callback_manager = self._create_slider_callbacks()
        self.slider_controller = TimeSliderController(self.master, self.tree, callback_manager)

        # 綁定事件
        self.bind_all_events()

        self.master.protocol("WM_DELETE_WINDOW", self.close_window)

        # 初始化變數時加入日誌
        self.logger.debug("初始化 AlignmentGUI")
        self.logger.debug(f"初始模式: {self.display_mode}")
        self.logger.debug(f"初始音頻匯入: {self.audio_imported}")

        # 在最後添加窗口大小變化事件綁定
        self.master.bind("<Configure>", self.on_window_resize)

        # 初始化後進行一次列寬調整
        self.master.after(100, lambda: self.on_window_resize(None))

        # 創建但不立即顯示合併符號 ("+")
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

        # 添加樹狀視圖選擇事件綁定
        self.tree.bind("<<TreeviewSelect>>", self.on_treeview_select)
        # 添加滑鼠移動事件綁定，用於更新合併符號位置
        self.master.bind("<Motion>", self.remember_mouse_position)

        self.last_combine_operation = None
        self.last_time_adjust_operation = None

    def initialize_file_manager(self) -> None:
        """初始化檔案管理器"""
        self.logger.debug("開始初始化 FileManager")

        # 創建 FileManager 實例
        self.file_manager = FileManager(self.master)

        # 設置回調函數
        callbacks = {
            'on_srt_loaded': self._on_srt_loaded,
            'on_audio_loaded': self._on_audio_loaded,
            'on_word_loaded': self._on_word_loaded,
            'on_file_info_updated': self.update_file_info,
            'on_status_updated': self.update_status,
            'get_corrections': self.load_corrections,
            'get_srt_data': self._get_current_srt_data,
            'get_tree_data': lambda: self.tree_manager.get_all_items(),
            'show_info': lambda title, msg: show_info(title, msg, self.master),
            'show_warning': lambda title, msg: show_warning(title, msg, self.master),
            'show_error': lambda title, msg: show_error(title, msg, self.master),
            'ask_question': lambda title, msg: ask_question(title, msg, self.master)
        }

        # 設置所有回調
        for name, callback in callbacks.items():
            self.file_manager.set_callback(name, callback)

        # 同步初始檔案狀態
        self.file_manager.srt_imported = self.srt_imported
        self.file_manager.audio_imported = self.audio_imported
        self.file_manager.word_imported = self.word_imported
        self.file_manager.srt_file_path = self.srt_file_path
        self.file_manager.audio_file_path = self.audio_file_path
        self.file_manager.word_file_path = self.word_file_path
        self.file_manager.current_project_path = self.current_project_path
        self.file_manager.database_file = self.database_file

        self.logger.debug("FileManager 初始化完成")

    def set_user_id(self, user_id):
        """設置用戶ID"""
        if user_id:
            self.user_id = user_id
            # 同步到 file_manager
            if hasattr(self, 'file_manager'):
                self.file_manager.user_id = user_id
            self.logger.debug(f"設置用戶ID: {user_id}")
        else:
            self.logger.warning("嘗試設置空的用戶ID")

    def _on_srt_loaded(self, srt_data, file_path, corrections=None) -> None:
        """SRT 載入後的回調"""
        self.logger.debug(f"SRT 數據載入回調開始，檔案: {file_path}")

        try:
            # 清除當前數據
            self.clear_current_data()

            # 設置 SRT 數據和狀態
            self.srt_data = srt_data
            self.srt_imported = True
            self.srt_file_path = file_path

            # 同步 FileManager 的狀態
            if hasattr(self, 'file_manager'):
                self.file_manager.srt_imported = True
                self.file_manager.srt_file_path = file_path

            self.logger.debug(f"SRT 數據已設置，項目數: {len(srt_data) if srt_data else 0}")

            # 更新顯示模式
            self.update_display_mode()

            # 如果沒有提供校正數據，嘗試載入
            if corrections is None:
                self.logger.debug("未提供校正數據，嘗試載入")
                corrections = self.load_corrections()

            # 直接處理 SRT 條目並顯示 - 這是關鍵步驟!
            self.logger.debug("開始處理 SRT 條目")
            self.process_srt_entries(srt_data, corrections)

            # 檢查樹視圖是否更新成功
            items_count = len(self.tree_manager.get_all_items())
            self.logger.debug(f"樹視圖更新完成，當前項目數: {items_count}")

            # 如果有音頻檔案，更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.logger.debug("更新音頻段落")
                self.audio_player.segment_audio(self.srt_data)

            # 如果有 Word 檔案，執行比對
            if self.word_imported and hasattr(self, 'word_processor'):
                self.logger.debug("執行 Word 比對")
                self.compare_word_with_srt()

            # 保存初始狀態
            if hasattr(self, 'state_manager'):
                description = "Loaded SRT file"
                if file_path:
                    description = f"Loaded SRT file: {os.path.basename(file_path)}"

                self.logger.debug("保存初始狀態")
                self.save_operation_state(self.get_current_state(), {
                    'type': 'load_srt',
                    'description': description
                })

            self.logger.debug("SRT 數據載入回調完成")

        except Exception as e:
            self.logger.error(f"處理 SRT 數據時出錯: {e}", exc_info=True)
            show_error("錯誤", f"處理 SRT 數據失敗: {str(e)}", self.master)

    def check_treeview_structure(self):
        """檢查樹視圖結構"""
        columns = self.tree["columns"]
        self.logger.debug(f"樹視圖列設置：{columns}")

        # 確認當前顯示模式
        self.logger.debug(f"當前顯示模式：{self.display_mode}")

        # 確認列配置
        expected_columns = self.columns.get(self.display_mode, [])
        self.logger.debug(f"預期列配置：{expected_columns}")

        # 檢查是否匹配
        if columns != expected_columns:
            self.logger.error(f"樹視圖列配置不匹配！當前：{columns}，預期：{expected_columns}")
            # 嘗試修復
            self.refresh_treeview_structure()
            self.logger.debug("已嘗試修復樹視圖結構")

    def _on_audio_loaded(self, file_path) -> None:
        """音頻載入後的回調"""
        try:
            # 記錄音頻檔案路徑
            self.audio_file_path = file_path
            self.audio_imported = True

            # 添加明確的日誌
            self.logger.info(f"音頻已成功載入，路徑: {file_path}, 匯入狀態: {self.audio_imported}")

            # 確保音頻播放器已初始化
            if not hasattr(self, 'audio_player'):
                self.initialize_audio_player()

            # 直接在這裡載入音頻，而不是依賴於回調
            if self.audio_player:
                # 確保真正加載了音頻
                audio_loaded = self.audio_player.load_audio(file_path)
                if not audio_loaded:
                    self.logger.error(f"音頻加載失敗: {file_path}")
                    self.audio_imported = False  # 重置狀態
                    show_error("錯誤", "音頻加載失敗，請檢查文件格式", self.master)
                    return

                # 如果有 SRT 數據，立即分割音頻
                if hasattr(self, 'srt_data') and self.srt_data:
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.info(f"音頻已分割為 {len(self.audio_player.segment_manager.audio_segments) if hasattr(self.audio_player.segment_manager, 'audio_segments') else 0} 個段落")

            # 保存當前數據狀態
            old_mode = self.display_mode
            self.logger.info(f"音頻已載入，匯入前顯示模式: {old_mode}")

            # 更新顯示模式
            self.update_display_mode()

            # 檢查模式是否已更新
            new_mode = self.display_mode
            if new_mode != old_mode:
                self.logger.info(f"顯示模式已更新: {old_mode} -> {new_mode}")

            # 確保顯示模式的一致性
            self.check_display_mode_consistency()

            # 同步 FileManager 的狀態
            if hasattr(self, 'file_manager'):
                self.file_manager.audio_imported = True
                self.file_manager.audio_file_path = file_path

        except Exception as e:
            self.logger.error(f"處理音頻載入回調時出錯: {e}", exc_info=True)
            self.audio_imported = False  # 確保在出錯時重置狀態
            show_error("錯誤", f"處理音頻載入失敗: {str(e)}", self.master)

    def _on_word_loaded(self, file_path) -> None:
        """Word 文檔載入後的回調"""
        # 確保 Word 處理器已載入文檔
        if self.word_processor.load_document(file_path):
            self.word_imported = True
            self.word_file_path = file_path
            self.logger.info(f"成功載入 Word 文檔: {file_path}")

            # 更新顯示模式
            self.update_display_mode()

            # 如果已有 SRT 數據，執行比對
            if self.srt_data:
                self.logger.info("執行 SRT 與 Word 文本比對")
                self.compare_word_with_srt()

            # 檢查模式切換一致性
            self.check_display_mode_consistency()

    def _get_column_indices_for_mode(self, mode):
        """根據顯示模式獲取各列索引"""
        if mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
            return {
                'index': 1,
                'start': 2,
                'end': 3,
                'text': 4,
                'word_text': 5 if mode == self.DISPLAY_MODE_ALL else None,
                'correction': 7 if mode == self.DISPLAY_MODE_ALL else 5
            }
        else:  # SRT or SRT_WORD modes
            return {
                'index': 0,
                'start': 1,
                'end': 2,
                'text': 3,
                'word_text': 4 if mode == self.DISPLAY_MODE_SRT_WORD else None,
                'correction': 6 if mode == self.DISPLAY_MODE_SRT_WORD else 4
            }

    def _get_current_srt_data(self) -> pysrt.SubRipFile:
        """獲取當前 SRT 數據"""
        # 創建新的 SRT 文件
        new_srt = pysrt.SubRipFile()

        # 載入校正資料庫
        corrections = self.load_corrections()

        # 獲取當前顯示模式的欄位索引
        col_indices = self._get_column_indices_for_mode(self.display_mode)

        self.logger.debug(f"開始從樹視圖獲取 SRT 數據，顯示模式: {self.display_mode}")

        # 遍歷所有項目
        for item in self.tree_manager.get_all_items():
            values = list(self.tree.item(item)['values'])

            # 確保 values 有足夠的元素
            if len(values) <= col_indices['index']:
                self.logger.warning(f"項目 {item} 的值列表長度不足，跳過")
                continue

            # 檢查是否使用 Word 文本 (藍色背景)
            use_word = self.use_word_text.get(item, False)

            # 記錄調試信息
            if use_word:
                self.logger.debug(f"項目 {item} 標記為使用 Word 文本")

            try:
                # 獲取索引值
                index = int(values[col_indices['index']])

                # 獲取時間值
                start = values[col_indices['start']] if col_indices['start'] < len(values) else "00:00:00,000"
                end = values[col_indices['end']] if col_indices['end'] < len(values) else "00:00:10,000"

                # 決定要使用的文本
                final_text = ""

                # 基本文本是 SRT Text 欄位的值
                srt_text = values[col_indices['text']] if col_indices['text'] < len(values) else ""

                # 如果有 Word 文本且設置了藍色背景，則使用 Word 文本
                if use_word and col_indices['word_text'] is not None and col_indices['word_text'] < len(values):
                    word_text = values[col_indices['word_text']]
                    if word_text and word_text.strip():
                        final_text = word_text
                        self.logger.debug(f"項目 {index} 使用 Word 文本: {word_text}")
                    else:
                        final_text = srt_text
                        self.logger.debug(f"項目 {index} 標記為使用 Word 文本，但 Word 文本為空，使用 SRT 文本")
                else:
                    final_text = srt_text

                # 檢查校正狀態
                correction_icon = values[col_indices['correction']] if col_indices['correction'] < len(values) else ""

                # 根據校正狀態決定是否應用校正
                if correction_icon == "✅":  # 只在有勾選的情況下應用校正
                    corrected_text = self.correct_text(final_text, corrections)
                    final_text = corrected_text

                # 解析時間
                start_time = parse_time(start)
                end_time = parse_time(end)

                # 創建字幕項
                sub = pysrt.SubRipItem(
                    index=index,
                    start=start_time,
                    end=end_time,
                    text=final_text
                )
                new_srt.append(sub)

                self.logger.debug(f"已添加項目 {index}，文本: {final_text[:20]}{'...' if len(final_text) > 20 else ''}")

            except (ValueError, IndexError) as e:
                self.logger.error(f"處理項目 {item} 時出錯: {e}")
                continue

        # 排序確保索引順序正確
        new_srt.sort()

        self.logger.info(f"成功生成 SRT 數據，共 {len(new_srt)} 個項目")
        return new_srt

    def _update_tree_data(self, srt_data, corrections) -> None:
        """更新樹視圖數據"""
        self.logger.debug(f"開始更新樹視圖，SRT 項目數：{len(srt_data)}")

        # 清空樹視圖
        self.tree_manager.clear_all()

        self.logger.debug("樹視圖已清空，開始處理 SRT 條目")

        # 更新數據
        self.process_srt_entries(srt_data, corrections)

        # 檢查是否成功更新
        items_count = len(self.tree_manager.get_all_items())
        self.logger.debug(f"樹視圖更新完成，當前項目數：{items_count}")

    def _segment_audio(self, srt_data) -> None:
        """對音頻進行分段"""
        if hasattr(self, 'audio_player') and self.audio_imported:
            self.audio_player.segment_audio(srt_data)

    def load_srt(self, event: Optional[tk.Event] = None, file_path: Optional[str] = None) -> None:
        """載入 SRT 文件"""
        self.file_manager.load_srt(event, file_path)

    def save_srt(self, event: Optional[tk.Event] = None) -> bool:
        """儲存 SRT 文件"""
        return self.file_manager.save_srt(event)

    def save_srt_as(self) -> bool:
        """另存新檔"""
        return self.file_manager.save_srt_as()

    def import_audio(self) -> None:
        """匯入音頻檔案"""
        self.file_manager.import_audio()

    def import_word_document(self) -> None:
        """匯入 Word 文檔"""
        self.file_manager.import_word_document()

    def export_srt(self, from_toolbar: bool = False) -> None:
        """匯出 SRT 檔案"""
        self.file_manager.export_srt(from_toolbar)

    def switch_project(self) -> None:
        """切換專案"""
        def confirm_switch():
            """確認是否可以切換專案"""
            if self.tree_manager.get_all_items():
                response = ask_question("確認切換",
                                    "切換專案前，請確認是否已經儲存當前的文本？\n"
                                    "未儲存的內容將會遺失。",
                                    self.master)
                return response
            return True

        def do_switch():
            """執行專案切換"""
            # 清理當前資源
            self.cleanup()

            # 關閉當前視窗
            self.master.destroy()

            # 獲取用戶ID - 確保從用戶相關的位置獲取
            user_id = None
            if hasattr(self, 'file_manager') and hasattr(self.file_manager, 'user_id'):
                user_id = self.file_manager.user_id
            elif hasattr(self, 'current_user') and self.current_user:
                user_id = self.current_user.id

            # 創建新的應用程式實例並啟動專案管理器
            root = tk.Tk()
            from .project_manager import ProjectManager
            project_manager = ProjectManager(root, user_id=user_id)
            project_manager.master.mainloop()

        self.file_manager.switch_project(confirm_switch, do_switch)

    def _record_time_adjustment(self):
        """記錄時間調整以便撤銷"""
        # 已有紀錄，就不需要重複記錄
        if hasattr(self, 'last_time_adjust_operation') and self.last_time_adjust_operation:
            return

        # 獲取所有項目的時間值
        items = self.tree_manager.get_all_items()
        if not items:
            return

        # 根據顯示模式確定時間列的索引
        if self.display_mode in [self.DISPLAY_MODE_SRT, self.DISPLAY_MODE_SRT_WORD]:
            start_index = 1  # Start 欄位索引
            end_index = 2    # End 欄位索引
        else:  # 其他模式
            start_index = 2  # Start 欄位索引
            end_index = 3    # End 欄位索引

        # 保存所有項目的原始時間值
        original_items_times = []
        for i, item in enumerate(items):
            values = self.tree_manager.get_item_values(item)
            if len(values) > end_index:
                item_data = {
                    'id': item,
                    'index': i,
                    'start': values[start_index] if len(values) > start_index else "",
                    'end': values[end_index] if len(values) > end_index else ""
                }
                original_items_times.append(item_data)

        # 保存操作記錄
        self.last_time_adjust_operation = {
            'timestamp': time.time(),
            'original_items_times': original_items_times,
            'display_mode': self.display_mode,
            'start_index': start_index,
            'end_index': end_index
        }

    def remember_mouse_position(self, event):
        """記錄當前滑鼠位置"""
        self.last_mouse_x = event.x_root - self.tree.winfo_rootx()
        self.last_mouse_y = event.y_root - self.tree.winfo_rooty()

    def on_treeview_select(self, event=None):
        """處理樹狀視圖選擇變化"""
        selected_items = self.tree_manager.get_selected_items()

        # 隱藏合併符號
        self.merge_symbol.place_forget()

        # 檢查是否選擇了至少兩個項目
        if len(selected_items) >= 2:
            # 使用最後記錄的滑鼠位置來放置合併符號
            if hasattr(self, 'last_mouse_x') and hasattr(self, 'last_mouse_y'):
                x = self.last_mouse_x + 15  # 游標右側 15 像素
                y = self.last_mouse_y

                # 確保符號在可視範圍內
                tree_width = self.tree.winfo_width()
                tree_height = self.tree.winfo_height()

                x = min(x, tree_width - 30)  # 避免超出右邊界
                y = min(y, tree_height - 30)  # 避免超出下邊界
                y = max(y, 10)  # 避免超出上邊界

                # 顯示合併符號
                self.merge_symbol.place(x=x, y=y)

                # 儲存目前選中的項目，用於之後的合併操作
                self.current_selected_items = selected_items
            else:
                # 如果沒有滑鼠位置記錄，退化為使用第一個選中項的位置
                item = selected_items[0]
                bbox = self.tree.bbox(item)
                if bbox:
                    self.merge_symbol.place(x=bbox[0] + bbox[2] + 5, y=bbox[1])
                    # 儲存目前選中的項目
                    self.current_selected_items = selected_items
        else:
            # 如果選中項目少於2個，清除儲存的選中項
            if hasattr(self, 'current_selected_items'):
                self.current_selected_items = []


    def cleanup(self) -> None:
        """清理資源"""
        try:
            # 停止音頻播放
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()

            # 清除合併符號
            if hasattr(self, 'merge_symbol'):
                self.merge_symbol.place_forget()
                self.merge_symbol.destroy()

            # 清理滑桿
            self.hide_time_slider()

            # 保存當前狀態
            if hasattr(self, 'state_manager'):
                current_state = self.get_current_state()
                correction_state = self.correction_service.serialize_state()
                self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})

            # 清除所有資料
            self.clear_current_data()

            # 調用父類清理方法
            super().cleanup()

        except Exception as e:
            self.logger.error(f"清理資源時出錯: {e}")

    def initialize_variables(self) -> None:
        """初始化變數"""
        # 現有的常量
        self.PLAY_ICON = "▶"

        # 添加顯示模式常量
        self.DISPLAY_MODE_SRT = "srt"                  # 僅 SRT
        self.DISPLAY_MODE_SRT_WORD = "srt_word"        # SRT + Word
        self.DISPLAY_MODE_AUDIO_SRT = "audio_srt"      # SRT + Audio
        self.DISPLAY_MODE_ALL = "all"                  # SRT + Word + Audio

        # 添加編輯文本信息的存儲
        self.edited_text_info = {}  # {srt_index: {'edited': ['srt', 'word']}}

         # 添加 Word 相關變數
        self.word_processor = WordProcessor()
        self.word_file_path = None
        self.word_comparison_results = {}
        # 添加用於追蹤哪些行使用 Word 文本的字典
        self.use_word_text = {}  # {item_id: True/False}

        # 初始化必要的狀態變數
        self.display_mode = self.DISPLAY_MODE_SRT
        self.srt_imported = False
        self.audio_imported = False
        self.word_imported = False

        # 添加校正圖標相關屬性
        self.floating_icon_fixed = False
        self.current_hovering_text = ""
        self.current_hovering_item = None
        self.current_hovering_column = ""

        # 為每種模式定義列配置
        self.columns = {
            self.DISPLAY_MODE_SRT: ['Index', 'Start', 'End', 'SRT Text', 'V/X'],
            self.DISPLAY_MODE_SRT_WORD: ['Index', 'Start', 'End', 'SRT Text', 'Word Text', 'Match', 'V/X'],
            self.DISPLAY_MODE_AUDIO_SRT: ['V.O', 'Index', 'Start', 'End', 'SRT Text', 'V/X'],
            self.DISPLAY_MODE_ALL: ['V.O', 'Index', 'Start', 'End', 'SRT Text', 'Word Text', 'Match', 'V/X'],
        }
        # 初始化列配置
        self.column_config = ColumnConfig()
        # 定義統一的圖標字符
        self.PLAY_ICON = "▶"
        self.audio_notification_shown = False
        self.correction_states = {}
        self.display_mode = "srt"
        self.srt_data = []
        self.srt_file_path = None
        self.current_project_path = None
        self.database_file = None
        self.audio_file_path = None
        self.current_style = None



    def update_state_manager(self) -> None:
        """更新狀態管理器的參數"""
        if hasattr(self, 'state_manager'):
            self.state_manager.tree = self.tree
            self.state_manager.display_mode = self.display_mode
            self.state_manager.insert_item = self.insert_item
            self.state_manager.update_srt_data = self.update_srt_data_from_treeview
            self.state_manager.update_status = self.update_status
            self.state_manager.segment_audio = None
            if hasattr(self, 'audio_player'):
                self.state_manager.segment_audio = self.audio_player.segment_audio

    def update_display_mode(self) -> None:
        """根據已匯入的檔案更新顯示模式"""
        old_mode = self.display_mode

        # 檢查並設置新的顯示模式
        if not self.srt_imported:
            # SRT 未匯入，保持現有模式但發出警告
            show_warning("警告", "請先匯入 SRT 文件", self.master)
            return

        # 獲取適當的顯示模式
        new_mode = self._get_appropriate_display_mode()

        # 如果模式已經改變，更新界面
        if new_mode != old_mode:
            self.logger.info(f"顯示模式變更: {old_mode} -> {new_mode}")
            self._apply_display_mode_change(old_mode, new_mode)
        else:
            # 即使模式沒變，也需要確保數據同步
            self.update_srt_data_from_treeview()

            # 如果有音頻檔案，仍然需要確保音頻段落與當前顯示同步
            if self.audio_imported and hasattr(self, 'audio_player') and hasattr(self, 'srt_data') and self.srt_data:
                self.audio_player.segment_audio(self.srt_data)
                self.logger.info("已更新音頻段落以匹配當前顯示")

    def _apply_display_mode_change(self, old_mode, new_mode):
        """
        應用顯示模式變更

        Args:
            old_mode: 原顯示模式
            new_mode: 新顯示模式
        """
        # 先更新 SRT 數據，確保所有數據正確同步
        self.update_srt_data_from_treeview()

        # 更新顯示模式
        self.display_mode = new_mode

        # 保存所有校正狀態和相關數據，以便在模式切換後恢復
        correction_states = {}
        for index, state in self.correction_service.correction_states.items():
            correction_states[index] = {
                'state': state,
                'original': self.correction_service.original_texts.get(index, ''),
                'corrected': self.correction_service.corrected_texts.get(index, '')
            }

        # 保存 use_word_text 設置
        use_word_settings = {}
        for item_id, use_word in self.use_word_text.items():
            values = self.tree.item(item_id, 'values')
            if values:
                # 根據顯示模式找到對應的索引
                if old_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                    index = str(values[1]) if len(values) > 1 else ""
                else:
                    index = str(values[0]) if values else ""

                if index:
                    use_word_settings[index] = use_word

        # 更新 Treeview 結構前，先保存現有的數據
        existing_data = []
        for item in self.tree_manager.get_all_items():
            values = self.tree_manager.get_item_values(item)
            tags = self.tree_manager.get_item_tags(item)

            # 找到當前項目的索引
            if old_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                index = str(values[1]) if len(values) > 1 else ""
            else:
                index = str(values[0]) if values else ""

            use_word = self.use_word_text.get(item, False)

            item_data = {
                'index': index,
                'values': values,
                'tags': tags,
                'use_word': use_word
            }

            # 獲取校正狀態
            if index in correction_states:
                item_data['correction'] = correction_states[index]

            existing_data.append(item_data)

        # 清空並重建校正狀態和 use_word_text 字典
        self.correction_service.clear_correction_states()
        self.use_word_text.clear()

        # 更新 Treeview 結構
        self.refresh_treeview_structure()

        # 重新填充數據
        for item_data in existing_data:
            old_index = item_data['index']
            old_values = item_data['values']

            # 調整值以適應新的顯示模式
            new_values = self.adjust_values_for_mode(old_values, old_mode, new_mode)

            # 添加新項目
            new_item = self.insert_item('', 'end', values=tuple(new_values))

            # 恢復標籤
            if item_data['tags']:
                self.tree.item(new_item, tags=item_data['tags'])

            # 恢復 use_word_text 狀態
            if old_index in use_word_settings and use_word_settings[old_index]:
                self.use_word_text[new_item] = True

                # 確保有 use_word_text 標籤
                current_tags = list(self.tree.item(new_item, 'tags') or tuple())
                if 'use_word_text' not in current_tags:
                    current_tags.append('use_word_text')
                    self.tree.item(new_item, tags=tuple(current_tags))

            # 恢復校正狀態
            if 'correction' in item_data:
                # 確定新的索引位置
                if new_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                    new_index = str(new_values[1]) if len(new_values) > 1 else ""
                else:
                    new_index = str(new_values[0]) if new_values else ""

                if new_index:
                    correction_info = item_data['correction']
                    self.correction_service.correction_states[new_index] = correction_info['state']
                    self.correction_service.original_texts[new_index] = correction_info['original']
                    self.correction_service.corrected_texts[new_index] = correction_info['corrected']

                    # 更新顯示的文本和圖標
                    updated_values = list(new_values)

                    # 更新 V/X 列
                    updated_values[-1] = '✅' if correction_info['state'] == 'correct' else '❌'

                    # 更新文本列
                    if new_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                        text_index = 4
                    else:
                        text_index = 3

                    if text_index < len(updated_values):
                        if correction_info['state'] == 'correct':
                            updated_values[text_index] = correction_info['corrected']
                        else:
                            updated_values[text_index] = correction_info['original']

                    # 更新項目值
                    self.tree.item(new_item, values=tuple(updated_values))

        # 設置樣式
        self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
        self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

        # 如果有音頻檔案，確保根據最新的顯示模式重新分割音頻
        if self.audio_imported and hasattr(self, 'audio_player') and hasattr(self, 'srt_data') and self.srt_data:
            self.audio_player.segment_audio(self.srt_data)
            self.logger.info("已根據最新顯示模式重新分割音頻段落")

        # 更新狀態欄
        self.update_status(f"顯示模式: {self.get_mode_description(new_mode)}")

    def update_correction_status_display(self):
        """更新樹視圖中的校正狀態顯示"""
        try:
            # 檢查所需組件是否可用
            if not hasattr(self, 'tree') or not hasattr(self, 'correction_service'):
                self.logger.warning("無法更新校正狀態顯示：所需組件不可用")
                return

            # 直接調用 correction_service 的方法
            self.correction_service.update_display_status(self.tree, self.display_mode)

        except Exception as e:
            self.logger.error(f"更新校正狀態顯示時出錯: {e}", exc_info=True)

    def restore_tree_data(self, data, source_mode="any", target_mode=None):
        """
        統一的樹狀視圖數據恢復方法

        Args:
            data: 之前保存的數據列表
            source_mode: 源模式 ("any" 表示自動檢測)
            target_mode: 目標模式 (None 表示使用當前模式)
        """
        try:
            if target_mode is None:
                target_mode = self.display_mode

            self.logger.debug(f"開始恢復樹狀視圖數據: 源模式={source_mode}, 目標模式={target_mode}")

            # 清空當前樹狀視圖
            self.tree_manager.clear_all()

            # 清空校正狀態
            self.correction_service.clear_correction_states()

            # 逐項恢復數據
            for item_data in data:
                values = item_data.get('values', [])

                # 調整值以適應新的顯示模式
                adjusted_values = self.adjust_values_for_mode(values, source_mode, target_mode)

                # 插入新項目
                item_id = self.insert_item('', 'end', values=tuple(adjusted_values))

                # 恢復標籤
                tags = item_data.get('tags')
                if tags:
                    self.tree.item(item_id, tags=tags)

                # 恢復 use_word_text 狀態
                use_word = item_data.get('use_word', False)
                if use_word:
                    self.use_word_text[item_id] = True

                    # 確保標籤中有 use_word_text
                    current_tags = list(self.tree.item(item_id, "tags") or ())
                    if "use_word_text" not in current_tags:
                        current_tags.append("use_word_text")
                        self.tree.item(item_id, tags=tuple(current_tags))

                # 恢復校正狀態
                correction = item_data.get('correction')
                if correction:
                    # 確定新的索引位置
                    if target_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                        idx = str(adjusted_values[1]) if len(adjusted_values) > 1 else ""
                    else:
                        idx = str(adjusted_values[0]) if adjusted_values else ""

                    if idx and 'state' in correction:
                        # 恢復校正狀態
                        self.correction_service.set_correction_state(
                            idx,
                            correction.get('original', ''),
                            correction.get('corrected', ''),
                            correction.get('state', 'correct')
                        )

            # 設置樣式
            self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

            self.logger.info(f"已恢復 {len(data)} 個項目的數據到 {target_mode} 模式")

        except Exception as e:
            self.logger.error(f"恢復樹狀視圖數據時出錯: {e}", exc_info=True)


    def get_mode_description(self, mode: str) -> str:
        """
        獲取顯示模式的描述文字
        """
        descriptions = {
            self.DISPLAY_MODE_SRT: "SRT 模式",
            self.DISPLAY_MODE_SRT_WORD: "SRT + Word 模式",
            self.DISPLAY_MODE_AUDIO_SRT: "SRT + 音頻模式",
            self.DISPLAY_MODE_ALL: "完整模式 (SRT + Word + 音頻)"
        }
        return descriptions.get(mode, "未知模式")

    def setup_logging(self) -> None:
        """設置日誌"""
        self.logger = logging.getLogger(self.__class__.__name__)
        handler = logging.FileHandler('alignment_gui.log', encoding='utf-8')
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

    def create_gui_elements(self) -> None:
        """創建主要界面元素"""
        # 初始化 GUI 建構器
        self.gui_builder = GUIBuilder(self.master, self.main_frame)

        # 創建選單列
        self.create_menu()

        # 創建工具列
        self.create_toolbar()

        # 創建主要內容區域
        self.create_main_content()

        # 創建底部檔案信息區域
        self.gui_builder.create_file_info_area(self.main_frame)

        # 最後創建狀態欄
        self.gui_builder.create_status_bar(self.main_frame)

    def create_menu(self) -> None:
        """創建選單列"""
        # 定義選單命令
        menu_commands = {
            '檔案': {
                '切換專案': self.switch_project,
                'separator': None,
                '開啟 SRT': self.load_srt,
                '儲存': self.save_srt,
                '另存新檔': self.save_srt_as,
                'separator': None,
                '離開': self.close_window
            },
            '編輯': {
                '復原 Ctrl+Z': self.undo,
                '重做 Ctrl+Y': self.redo
            }
        }

        self.gui_builder.create_menu(self.menu_frame, menu_commands)

    def compare_word_with_srt(self) -> None:
        """比對 SRT 和 Word 文本"""
        try:
            if not self.srt_data or not hasattr(self, 'word_processor') or not self.word_processor.text_content:
                show_warning("警告", "請確保 SRT 和 Word 文件均已加載", self.master)
                return

            # 提取 SRT 文本
            srt_texts = [sub.text for sub in self.srt_data]

            # 比對文本
            self.word_comparison_results = self.word_processor.compare_with_srt(srt_texts)

            # 更新顯示
            self.update_display_with_comparison()

            # 顯示摘要信息
            total_items = len(srt_texts)
            mismatched = sum(1 for result in self.word_comparison_results.values() if not result.get('match', True))

            show_info("比對完成",
                    f"共比對 {total_items} 項字幕\n"
                    f"發現 {mismatched} 項不匹配\n\n"
                    f"不匹配項目以紅色背景標記，差異詳情顯示在 'Match' 欄位",
                    self.master)

            # 更新狀態
            self.update_status(f"已完成 SRT 和 Word 文檔比對: {mismatched}/{total_items} 項不匹配")

        except Exception as e:
            self.logger.error(f"比對 SRT 和 Word 文檔時出錯: {e}", exc_info=True)
            show_error("錯誤", f"比對失敗: {str(e)}", self.master)

    # 添加更新顯示方法
    def update_display_with_comparison(self) -> None:
        """根據比對結果更新顯示"""
        try:
            if not self.word_comparison_results:
                return

            # 備份當前選中和標籤以及值
            selected = self.tree_manager.get_selected_items()
            tags_backup = {}
            values_backup = {}
            use_word_backup = self.use_word_text.copy()  # 備份 use_word_text 狀態

            for item in self.tree_manager.get_all_items():
                tags_backup[item] = self.tree_manager.get_item_tags(item)
                values_backup[item] = self.tree_manager.get_item_values(item)

            # 建立索引到項目ID的映射
            index_to_item = {}
            for item_id, values in values_backup.items():
                try:
                    if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                        if len(values) > 1:
                            index_to_item[str(values[1])] = item_id
                    else:  # self.display_mode in [self.DISPLAY_MODE_SRT, self.DISPLAY_MODE_SRT_WORD]
                        if values:
                            index_to_item[str(values[0])] = item_id
                except Exception as e:
                    self.logger.error(f"處理項目索引映射時出錯: {e}")

            # 清空樹
            self.tree_manager.clear_all()

            # 載入校正數據庫
            corrections = self.load_corrections()

            # 重新載入 SRT 數據，加入比對結果
            for i, sub in enumerate(self.srt_data):
                # 取得比對結果
                comparison = self.word_comparison_results.get(i, {
                    'match': True,
                    'word_text': '',
                    'difference': ''
                })

                # 轉換文本為繁體中文
                text = simplify_to_traditional(sub.text.strip())

                # 檢查校正需求
                needs_correction = False
                corrected_text = text
                if corrections:
                    corrected_text = self.correct_text(text, corrections)
                    needs_correction = corrected_text != text

                # 直接使用原始 Word 文本和差異信息
                match_status = comparison.get('match', True)
                word_text = comparison.get('word_text', '')
                diff_text = comparison.get('difference', '')

                # 檢查是否有先前的 use_word_text 設置
                old_item_id = index_to_item.get(str(sub.index))
                use_word = False
                if old_item_id in use_word_backup:
                    use_word = use_word_backup[old_item_id]

                # 準備標籤
                tags = []
                # 如果使用 Word 文本，添加 use_word_text 標籤
                if use_word:
                    tags.append('use_word_text')
                # 否則如果不匹配，添加 mismatch 標籤
                elif not match_status:
                    tags.append('mismatch')

                # 創建基本值並插入項目
                item_id = self.prepare_and_insert_subtitle_item(
                    sub=sub,
                    corrections=corrections,
                    tags=tuple(tags) if tags else None,
                    use_word=use_word
                )

                # 處理 Word 文本和差異信息
                if item_id and (self.display_mode == self.DISPLAY_MODE_SRT_WORD or self.display_mode == self.DISPLAY_MODE_ALL):
                    values = list(self.tree.item(item_id, 'values'))

                    # 設置 Word 文本
                    word_text_index = 5 if self.display_mode == self.DISPLAY_MODE_ALL else 4
                    if word_text_index < len(values):
                        values[word_text_index] = word_text

                    # 設置差異文本
                    diff_text_index = 6 if self.display_mode == self.DISPLAY_MODE_ALL else 5
                    if diff_text_index < len(values):
                        values[diff_text_index] = diff_text

                    # 更新項目值
                    self.tree.item(item_id, values=tuple(values))

                # 如果使用 Word 文本，更新顯示的文本
                if use_word:
                    values = list(self.tree.item(item_id, 'values'))
                    text_index = 4 if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 3

                    if text_index < len(values) and word_text:
                        values[text_index] = word_text
                        self.tree.item(item_id, values=tuple(values))

            # 恢復選中
            if selected:
                for item in selected:
                    if item in self.tree_manager.get_all_items():
                        self.tree.selection_add(item)

            # 配置標記樣式 - 確保標籤的優先級
            self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.tree.tag_configure("use_word_text", background="#00BFFF")  # 淺藍色背景標記使用 Word 文本的項目

        except Exception as e:
            self.logger.error(f"更新比對顯示時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新比對顯示失敗: {str(e)}", self.master)

    def close_window(self, event: Optional[tk.Event] = None) -> None:
        """關閉視窗"""
        try:
            # 先清理所有子視窗
            for widget in self.master.winfo_children():
                if isinstance(widget, tk.Toplevel):
                    widget.destroy()

            # 停止音頻播放
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()

            # 保存當前狀態
            if hasattr(self, 'state_manager'):
                current_state = self.get_current_state()
                correction_state = self.correction_service.serialize_state()
                self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})
            # 執行清理
            self.cleanup()

            # 確保處理完所有待處理的事件
            self.master.update_idletasks()

            # 關閉主視窗
            self.master.destroy()
            sys.exit(0)

        except Exception as e:
            self.logger.error(f"關閉視窗時出錯: {e}")
            sys.exit(1)

    def create_file_info_area(self) -> None:
        """創建檔案資訊顯示區域"""
        # 檔案資訊區域（無外框）
        self.file_info_frame = ttk.Frame(self.main_frame)
        self.file_info_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=5, padx=5)

        # 檔案資訊標籤（置中）
        self.file_info_var = tk.StringVar(value="尚未載入任何檔案")
        self.file_info_label = ttk.Label(
            self.file_info_frame,
            textvariable=self.file_info_var,
            style='Custom.TLabel',
            anchor='center'  # 文字置中
        )
        self.file_info_label.pack(fill=tk.X, pady=5)

    def update_file_info(self) -> None:
        """更新檔案資訊顯示"""
        info_parts = []

        # 檢查是否有 FileManager，沒有則使用舊方法
        if hasattr(self, 'file_manager'):
            # 添加 SRT 文件資訊
            if self.file_manager.srt_file_path:
                info_parts.append(f"SRT檔案：{os.path.basename(self.file_manager.srt_file_path)}")

            # 添加音頻文件資訊
            if self.file_manager.audio_file_path:
                info_parts.append(f"音頻檔案：{os.path.basename(self.file_manager.audio_file_path)}")

            # 添加 Word 文件資訊
            if self.file_manager.word_file_path:
                info_parts.append(f"Word檔案：{os.path.basename(self.file_manager.word_file_path)}")
        else:
            # 舊的實現方式
            if self.srt_file_path:
                info_parts.append(f"SRT檔案：{os.path.basename(self.srt_file_path)}")

            if hasattr(self, 'audio_file_path') and self.audio_file_path:
                info_parts.append(f"音頻檔案：{os.path.basename(self.audio_file_path)}")

            if hasattr(self, 'word_file_path') and self.word_file_path:
                info_parts.append(f"Word檔案：{os.path.basename(self.word_file_path)}")

        # 更新顯示
        if info_parts:
            self.gui_builder.update_file_info(" | ".join(info_parts))
        else:
            self.gui_builder.update_file_info("尚未載入任何檔案")

    def create_toolbar(self) -> None:
        """創建工具列，使用圖片按鈕"""
        self.toolbar_frame = ttk.Frame(self.main_frame)
        self.toolbar_frame.pack(fill=tk.X, padx=0, pady=0)

        # 確保 PIL/Pillow 已安裝
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self.logger.error("缺少 PIL/Pillow 庫，無法使用圖片按鈕，改用文字按鈕")
            self.create_text_toolbar()
            return

        # 初始化圖片管理器
        try:

            self.image_manager = ImageManager()
        except ImportError:
            self.logger.error("無法導入 ImageManager，改用文字按鈕")
            self.create_text_toolbar()
            return

        # 設置按鈕圖片尺寸（可根據需要調整）
        button_width = 50  # 按鈕寬度
        button_height = 50  # 按鈕高度

        # 預載入所有按鈕圖片，指定尺寸
        self.image_manager.load_button_images(width=button_width, height=button_height)

        # 定義工具列按鈕
        buttons = [
            {"id": "load_srt", "command": self.load_srt, "tooltip": "載入 SRT 檔案"},
            {"id": "import_audio", "command": self.import_audio, "tooltip": "匯入音頻檔案"},
            {"id": "load_word", "command": self.import_word_document, "tooltip": "載入 Word 檔案"},
            {"id": "adjust_time", "command": self.align_end_times, "tooltip": "調整時間軸"},
            {"id": "export_srt", "command": lambda: self.export_srt(from_toolbar=True), "tooltip": "匯出 SRT 檔案"}
        ]

        # 創建工具列按鈕
        self.toolbar_buttons = {}
        for btn_info in buttons:
            self.create_image_button(btn_info, width=button_width, height=button_height)

    def create_image_button(self, btn_info, width=None, height=None):
        """
        創建圖片按鈕
        :param btn_info: 按鈕信息
        :param width: 按鈕寬度
        :param height: 按鈕高度
        """
        button_id = btn_info["id"]
        command = btn_info["command"]
        tooltip = btn_info.get("tooltip", "")

        # 獲取按鈕圖片
        normal_img, pressed_img = self.image_manager.get_button_images(button_id, width, height)
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

    def _on_button_click(self, event, button):
        """按鈕點擊事件處理"""
        if hasattr(button, 'command') and callable(button.command):
            button.command()

    def create_text_toolbar(self):
        """創建文字按鈕工具列（備選方案）"""
        # 定義工具列按鈕
        buttons = [
            {"text": "載入 SRT", "command": self.load_srt, "width": 0},
            {"text": "匯入音頻", "command": self.import_audio, "width": 0},
            {"text": "載入 Word", "command": self.import_word_document, "width": 0},
            {"text": "調整時間", "command": self.align_end_times, "width": 0},
            {"text": "匯出 SRT", "command": lambda: self.export_srt(from_toolbar=True), "width": 0}
        ]

        self.toolbar_buttons = {}
        for i, btn_info in enumerate(buttons):
            btn = ttk.Button(
                self.toolbar_frame,
                text=btn_info["text"],
                command=btn_info["command"],
                width=btn_info["width"]
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.toolbar_buttons[f"button_{i}"] = btn

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

    def create_main_content(self) -> None:
        """創建主要內容區域"""
        # 建立內容框架
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(2,3))

        # 使用 GUI 建構器創建內容容器
        container = self.gui_builder.create_main_content(self.content_frame)

        # 使用容器建立 Treeview
        self.result_frame = container

        # 建立 Treeview
        self.create_treeview()

        # 調試輸出
        self.logger.debug("主要內容區域創建完成")

    def create_treeview(self) -> None:
        """創建 Treeview"""
        # 結果框架
        self.result_frame = ttk.Frame(self.content_frame)
        self.result_frame.pack(fill=tk.BOTH, expand=True)

        # 創建 Treeview
        self.tree = ttk.Treeview(self.result_frame)

        # 設置 TreeView 字型
        style = ttk.Style()
        tree_font = self.font_manager.get_font(size=10)  # 顯式指定較小的字型大小
        style.configure("Treeview", font=tree_font)
        style.configure("Treeview.Heading", font=tree_font)

        # 初始化 TreeView 管理器
        self.tree_manager = TreeViewManager(self.tree)

        # 設置列配置前確保 Treeview 已顯示
        self.setup_treeview_columns()

        # 防止使用者調整欄位寬度
        def handle_resize(event):
            if event.widget.identify_region(event.x, event.y) == "separator":
                return "break"

        self.tree.bind('<Button-1>', handle_resize)

        # 設置卷軸
        self.setup_treeview_scrollbars()

        self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
        self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目
        self.logger.debug("Treeview 創建完成")

    def setup_treeview_columns(self) -> None:
        """設置 Treeview 列配置"""
        try:
            # 獲取當前模式的列配置
            columns = self.columns.get(self.display_mode, [])

            # 添加診斷日誌
            self.logger.debug(f"設置樹狀視圖列，顯示模式: {self.display_mode}, 列: {columns}")

            # 更新 Treeview 列
            self.tree["columns"] = columns
            self.tree['show'] = 'headings'  # 確保顯示所有列標題

            # 配置每一列
            for col in columns:
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
                    self.logger.debug(f"設置 SRT Text 列: width=300, stretch=True")

            # 確保標籤設置
            self.tree.tag_configure('mismatch', background='#FFDDDD')
            self.tree.tag_configure('use_word_text', background='#00BFFF')

        except Exception as e:
            self.logger.error(f"設置樹狀視圖列時出錯: {str(e)}")
            show_error("錯誤", f"設置顯示列時發生錯誤: {str(e)}", self.master)

    def _handle_double_click(self, event):
        """處理雙擊事件，防止編輯 V/X 欄位"""
        region = self.tree.identify("region", event.x, event.y)
        column = self.tree.identify_column(event.x)

        # 如果點擊的是最後一列（Correction），則阻止編輯
        if column == f"#{len(self.tree['columns'])}":
            return "break"

        # 其他列正常處理
        if region == "cell":
            self.on_double_click(event)

    def on_double_click(self, event: tk.Event) -> None:
        """處理雙擊事件"""
        try:
            # 先獲取點擊的區域和列
            region = self.tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            # 獲取點擊的列
            column = self.tree.identify_column(event.x)
            if not column:
                return

            # 獲取列索引
            column_idx = int(column[1:]) - 1
            column_name = self.tree["columns"][column_idx]

            # 獲取選中的項目
            selected_items = self.tree_manager.get_selected_items()
            if not selected_items:
                return

            # 檢查項目是否依然存在
            item = selected_items[0]
            if not self.tree.exists(item):
                return

            values = list(self.tree_manager.get_item_values(item))
            if not values:
                return

            # 根據顯示模式確定正確的索引和文本
            try:
                # 不同模式下獲取 SRT 索引和文本
                if self.display_mode == self.DISPLAY_MODE_ALL:  # ALL 模式
                    srt_index = int(values[1])
                    start_time = values[2]
                    end_time = values[3]

                    # 根據點擊的列決定編輯哪個文本
                    if column_name == "SRT Text":
                        edit_text = values[4] if self.display_mode == self.DISPLAY_MODE_ALL else values[3]  # SRT 文本
                        edit_mode = 'srt'
                        # 使用原有的 TextEditDialog
                        dialog = TextEditDialog(
                            parent=self.master,
                            title="編輯 SRT 文本",
                            initial_text=edit_text,
                            start_time=start_time,
                            end_time=end_time,
                            column_index=column_idx,
                            display_mode=self.display_mode
                        )

                        if dialog.result:
                            self.process_srt_edit_result(dialog.result, item, srt_index, start_time, end_time)

                    elif column_name == "Word Text":
                        edit_text = values[5] if self.display_mode == self.DISPLAY_MODE_ALL else values[4]  # Word 文本
                        edit_mode = 'word'

                        # 使用針對 Word 文本的編輯對話框
                        dialog = TextEditDialog(
                            parent=self.master,
                            title="編輯 Word 文本",
                            initial_text=edit_text,
                            start_time=start_time,
                            end_time=end_time,
                            column_index=column_idx,
                            display_mode=self.display_mode,
                            edit_mode=edit_mode  # 明確指定編輯模式為 Word
                        )

                        if dialog.result:
                            self.process_word_text_edit(dialog.result, item, srt_index)
                    else:
                        # 其他列不進行編輯
                        return

                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:  # SRT_WORD 模式
                    srt_index = int(values[0])
                    start_time = values[1]
                    end_time = values[2]

                    # 根據點擊的列決定編輯哪個文本
                    if column_name == "SRT Text":
                        edit_text = values[3]  # SRT 文本

                        # 使用原有的 TextEditDialog
                        dialog = TextEditDialog(
                            parent=self.master,
                            title="編輯 SRT 文本",
                            initial_text=edit_text,
                            start_time=start_time,
                            end_time=end_time,
                            column_index=column_idx,
                            display_mode=self.display_mode
                        )

                        if dialog.result:
                            self.process_srt_edit_result(dialog.result, item, srt_index, start_time, end_time)

                    elif column_name == "Word Text":
                        edit_text = values[4]  # Word 文本

                        # 使用針對 Word 文本的編輯對話框
                        dialog = TextEditDialog(
                            parent=self.master,
                            title="編輯 Word 文本",
                            initial_text=edit_text,
                            start_time=start_time,
                            end_time=end_time,
                            column_index=column_idx,
                            display_mode=self.display_mode
                        )

                        if dialog.result:
                            self.process_word_text_edit(dialog.result, item, srt_index)

                    else:
                        # 其他列不進行編輯
                        return

                else:  # SRT 或 AUDIO_SRT 模式
                    if self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                        current_index = int(values[1])
                        start_time = values[2]
                        end_time = values[3]
                        initial_text = values[4]
                    else:  # SRT 模式
                        current_index = int(values[0])
                        start_time = values[1]
                        end_time = values[2]
                        initial_text = values[3]

                    # 使用原有的編輯對話框
                    dialog = TextEditDialog(
                        parent=self.master,
                        title="編輯文本",
                        initial_text=initial_text,
                        start_time=start_time,
                        end_time=end_time,
                        column_index=column_idx,
                        display_mode=self.display_mode
                    )

                    # 處理編輯結果
                    if dialog.result:
                        self.process_srt_edit_result(dialog.result, item, current_index, start_time, end_time)

            except (IndexError, ValueError) as e:
                self.logger.error(f"解析項目值時出錯: {e}")
                show_error("錯誤", "無法讀取選中項目的值", self.master)
                return

        except Exception as e:
            self.logger.error(f"處理雙擊事件時出錯: {e}", exc_info=True)
            show_error("錯誤", f"編輯文本失敗: {str(e)}", self.master)

        finally:
            # 確保焦點回到主視窗
            self.master.focus_force()


    def setup_treeview_scrollbars(self) -> None:
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

        # 調試輸出
        self.logger.debug("Treeview 卷軸設置完成")


    def create_status_bar(self) -> None:
        """創建狀態列"""
        # 檢查並創建狀態變數
        if not hasattr(self, 'status_var'):
            self.status_var = tk.StringVar()

        self.status_label = ttk.Label(
            self.main_frame,
            textvariable=self.status_var,
            style='Custom.TLabel'
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, pady=2)

    def on_tree_click(self, event: tk.Event) -> None:
        """處理樹狀圖的點擊事件"""
        try:
            # 獲取點擊區域、欄位和項目信息
            region = self.tree.identify("region", event.x, event.y)
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)

            self.logger.debug(f"樹狀圖點擊事件: region={region}, column={column}, item={item}")

            if not (region and column and item):
                return

            # 檢查是否是選中的項目
            is_selected = item in self.tree_manager.get_selected_items()

            # 獲取列名
            column_idx = int(column[1:]) - 1
            if column_idx >= len(self.tree["columns"]):
                return

            column_name = self.tree["columns"][column_idx]
            self.logger.debug(f"點擊的列名: {column_name}")

            # 處理文本列點擊事件（SRT Text 或 Word Text）
            if region == "cell" and is_selected and column_name in ["SRT Text", "Word Text"]:
                # 檢查是否點擊了與當前懸停文本不同的項目
                if (hasattr(self, 'current_hovering_item') and
                    (self.current_hovering_item != item or self.current_hovering_column != column_name)):
                    # 隱藏之前的圖標
                    if hasattr(self, 'floating_icon'):
                        self.floating_icon.place_forget()
                        self.floating_icon_fixed = False

                # 獲取值
                values = list(self.tree.item(item)["values"])
                if not values or len(values) <= column_idx:
                    return

                selected_text = values[column_idx]
                if not selected_text:
                    return

                # 更新當前懸停信息
                self.current_hovering_text = selected_text
                self.current_hovering_item = item
                self.current_hovering_column = column_name

                # 如果已有圖標，固定它
                if hasattr(self, 'floating_icon'):
                    self.floating_icon_fixed = True
                    # 更新圖標位置（放在點擊位置）
                    self.floating_icon.place(x=event.x + 10, y=event.y - 10)
                else:
                    # 創建新圖標
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
                    self.floating_icon_fixed = True
                    self.floating_icon.bind("<Button-1>", self.on_icon_click)
                    self.floating_icon.place(x=event.x + 10, y=event.y - 10)

            # 隱藏合併符號
            if hasattr(self, 'merge_symbol'):
                self.merge_symbol.place_forget()

            # 隱藏時間滑桿（如果有）
            if hasattr(self, 'slider_controller'):
                self.slider_controller.hide_slider()

            # 處理時間欄位的點擊
            if column_name in ["Start", "End"] and region == "cell":
                # 顯示時間調整滑桿
                if hasattr(self, 'slider_controller'):
                    self.slider_controller.show_slider(event, item, column, column_name)
                return

            # 獲取值
            values = list(self.tree.item(item)["values"])
            if not values:
                return

            # 處理 V/X 列點擊
            if column_name == "V/X":
                # 獲取當前項目的索引
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    display_index = str(values[1])
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    display_index = str(values[1])
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    display_index = str(values[0])
                    text_index = 3
                else:  # SRT 模式
                    display_index = str(values[0])
                    text_index = 3

                # 獲取當前文本
                current_text = values[text_index] if text_index < len(values) else ""

                # 先檢查最後一列的值（校正圖標）
                correction_mark = values[-1] if len(values) > 0 else ""

                # 如果沒有校正圖標，說明這行文本與錯誤字不符，直接返回
                if correction_mark == "":
                    return

                # 檢查是否有校正狀態，這裡簡化判斷：有圖標就表示有校正需求
                if display_index in self.correction_service.correction_states:
                    current_state = self.correction_service.correction_states[display_index]
                    original_text = self.correction_service.original_texts.get(display_index, "")
                    corrected_text = self.correction_service.corrected_texts.get(display_index, "")

                    # 如果原始文本或校正文本記錄為空，嘗試從當前文本重新檢查
                    if not original_text or not corrected_text:
                        _, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(current_text)
                        # 更新校正記錄
                        self.correction_service.original_texts[display_index] = original_text
                        self.correction_service.corrected_texts[display_index] = corrected_text

                    # 根據當前狀態切換
                    if current_state == 'correct':
                        # 從已校正切換到未校正
                        self.correction_service.correction_states[display_index] = 'error'
                        values[text_index] = original_text
                        values[-1] = '❌'
                    else:
                        # 從未校正切換到已校正
                        self.correction_service.correction_states[display_index] = 'correct'
                        values[text_index] = corrected_text
                        values[-1] = '✅'

                    # 更新樹狀圖顯示
                    self.tree_manager.update_item(item, values=tuple(values))

                    # 保存當前狀態
                    if hasattr(self, 'state_manager'):
                        current_state = self.get_current_state()
                        correction_state = self.correction_service.serialize_state()
                        self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})

                    # 更新 SRT 數據
                    self.update_srt_data_from_treeview()
                else:
                    # 如果沒有校正狀態記錄，但有圖標，可能是初始狀態
                    # 直接檢查文本並設置校正狀態
                    needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(current_text)

                    if needs_correction:
                        # 決定當前顯示的是原始文本還是校正後文本
                        is_showing_corrected = (current_text == corrected_text)

                        if is_showing_corrected:
                            # 當前顯示的是校正後文本，切換到原始文本
                            self.correction_service.set_correction_state(
                                display_index,
                                original_text,
                                corrected_text,
                                'error'  # 未校正狀態
                            )
                            values[text_index] = original_text
                            values[-1] = '❌'
                        else:
                            # 當前顯示的是原始文本，切換到校正後文本
                            self.correction_service.set_correction_state(
                                display_index,
                                original_text,
                                corrected_text,
                                'correct'  # 已校正狀態
                            )
                            values[text_index] = corrected_text
                            values[-1] = '✅'

                        # 更新樹狀圖顯示
                        self.tree_manager.update_item(item, values=tuple(values))

                        # 保存當前狀態
                        if hasattr(self, 'state_manager'):
                            current_state = self.get_current_state()
                            correction_state = self.correction_service.serialize_state()
                            self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})

                        # 更新 SRT 數據
                        self.update_srt_data_from_treeview()

            # 處理 Word Text 列點擊 - 切換使用 Word 文本
            if column_name == "Word Text" and self.display_mode in [self.DISPLAY_MODE_SRT_WORD, self.DISPLAY_MODE_ALL]:
                # 檢查項目是否依然存在
                if not self.tree.exists(item):
                    return

                # 保存當前標籤和校正狀態，避免丟失
                current_tags = list(self.tree.item(item, "tags") or tuple())

                # 識別校正狀態相關的標籤
                correction_tags = [tag for tag in current_tags if tag.startswith("correction_")]

                # 檢查當前是否已經使用 Word 文本
                using_word_text = "use_word_text" in current_tags

                # 切換狀態
                if using_word_text:
                    # 如果已使用 Word 文本，則取消
                    self.use_word_text[item] = False
                    if "use_word_text" in current_tags:
                        current_tags.remove("use_word_text")

                    # 如果文本不匹配，添加 mismatch 標籤
                    # 獲取 SRT 文本和 Word 文本
                    if self.display_mode == self.DISPLAY_MODE_ALL:
                        srt_text_idx = 4  # SRT Text 在 ALL 模式下的索引
                        word_text_idx = 5  # Word Text 在 ALL 模式下的索引
                    else:  # SRT_WORD 模式
                        srt_text_idx = 3  # SRT Text
                        word_text_idx = 4  # Word Text

                    # 只有當兩個文本不同時才添加 mismatch 標籤
                    if srt_text_idx < len(values) and word_text_idx < len(values):
                        srt_text = values[srt_text_idx]
                        word_text = values[word_text_idx]
                        if srt_text != word_text and "mismatch" not in current_tags:
                            current_tags.append("mismatch")
                else:
                    # 如果未使用 Word 文本，則開始使用
                    self.use_word_text[item] = True
                    if "use_word_text" not in current_tags:
                        current_tags.append("use_word_text")

                    # 移除 mismatch 標籤
                    if "mismatch" in current_tags:
                        current_tags.remove("mismatch")

                # 確保校正標籤被保留
                for tag in correction_tags:
                    if tag not in current_tags:
                        current_tags.append(tag)

                # 更新標籤
                self.tree.item(item, tags=tuple(current_tags))

                # 確保標籤樣式已設置
                self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景
                self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景

                # 保存當前狀態
                if hasattr(self, 'state_manager'):
                    current_state = self.get_current_state()
                    correction_state = self.correction_service.serialize_state()
                    self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})
                return

            # 處理音頻播放列的點擊
            elif column_name == 'V.O':
                # 先檢查音頻是否已匯入
                if not self.audio_imported:
                    show_warning("警告", "未匯入音頻，請先匯入音頻檔案", self.master)
                    return

                # 檢查音頻播放器是否已初始化
                if not hasattr(self, 'audio_player') or not self.audio_player.audio:
                    show_warning("警告", "音頻播放器未初始化或音頻未載入", self.master)
                    return

                try:
                    if self.display_mode == self.DISPLAY_MODE_ALL:
                        index = int(values[1])
                    elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                        index = int(values[1])
                    else:
                        index = int(values[0])

                    self.play_audio_segment(index)
                except (ValueError, IndexError) as e:
                    self.logger.error(f"處理音頻播放時出錯: {e}")
                    show_warning("警告", "無法播放音頻段落", self.master)

        except Exception as e:
            self.logger.error(f"處理樹狀圖點擊事件時出錯: {e}", exc_info=True)

    def _create_slider_callbacks(self):
        """創建滑桿控制器所需的回調函數"""
        from utils.time_utils import parse_time as parse_time_func

        # 返回一個具有方法屬性的對象，而不是字典
        class CallbackManager:
            def __init__(self, gui):
                self.gui = gui

            def parse_time(self, time_str):
                """解析時間字串的包裝方法"""
                try:
                    return parse_time_func(time_str)
                except Exception as e:
                    self.gui.logger.error(f"解析時間字串時出錯: {e}")
                    return None

            def on_time_change(self):
                """時間變更後的更新操作"""
                self.gui.update_after_time_change()

            def get_display_mode(self):
                """獲取當前顯示模式"""
                return self.gui.display_mode

        return CallbackManager(self)

    def parse_time(self, time_str):
        """解析時間字串的包裝方法"""
        from utils.time_utils import parse_time
        try:
            return parse_time(time_str)
        except Exception as e:
            self.logger.error(f"解析時間字串時出錯: {e}")
            return pysrt.SubRipTime(0, 0, 0, 0)

    def update_after_time_change(self):
        """時間變更後的更新操作"""
        try:
            # 保存當前校正狀態
            correction_states = {}
            for index, state in self.correction_service.correction_states.items():
                correction_states[index] = {
                    'state': state,
                    'original': self.correction_service.original_texts.get(index, ''),
                    'corrected': self.correction_service.corrected_texts.get(index, '')
                }

            # 更新 SRT 數據以反映變更
            self.update_srt_data_from_treeview()

            # 恢復校正狀態
            for index, data in correction_states.items():
                self.correction_service.correction_states[index] = data['state']
                self.correction_service.original_texts[index] = data['original']
                self.correction_service.corrected_texts[index] = data['corrected']

            # 如果有音頻，更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player') and self.audio_player.audio:
                # 創建一份當前時間調整的記錄，用於可能的撤銷操作
                self._record_time_adjustment()

                # 使用 segment_audio 而不是 rebuild_segments 確保完全重建
                self.audio_player.segment_audio(self.srt_data)
                self.logger.info("時間調整後已更新音頻段落")

            # 保存狀態
            self.save_operation_state('time_adjust', '調整時間軸')
        except Exception as e:
            self.logger.error(f"更新時間變更後出錯: {e}")

    def on_icon_click(self, event):
        """當圖標被點擊時的處理，打開添加視窗"""
        try:
            # 顯示添加校正對話框
            if hasattr(self, 'current_hovering_text') and self.current_hovering_text:
                self.show_add_correction_dialog(self.current_hovering_text)
            else:
                self.logger.warning("找不到當前懸停文本，無法打開校正對話框")

        except Exception as e:
            self.logger.error(f"圖標點擊處理時出錯: {e}", exc_info=True)

    def reset_floating_icon_state(self):
        """重置浮動圖標的狀態"""
        if hasattr(self, 'floating_icon'):
            self.floating_icon.place_forget()
            self.floating_icon_fixed = False

    def toggle_correction_icon(self, item: str, index: str, text: str) -> None:
        """交由 CorrectionService 處理"""
        self.correction_service.toggle_correction_icon(self.tree, item, index, text, self.display_mode)

    def get_text_position_in_values(self):
        """獲取文本在值列表中的位置"""
        if self.display_mode == self.DISPLAY_MODE_ALL:
            return 4  # SRT Text 在 ALL 模式下的索引
        elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
            return 4  # SRT Text 在 AUDIO_SRT 模式下的索引
        elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
            return 3  # SRT Text 在 SRT_WORD 模式下的索引
        else:  # SRT 模式
            return 3  # SRT Text 在 SRT 模式下的索引
        return None

    def insert_text_segment(self, insert_position: int, text: str, start: str, end: str,
                   corrections: dict, show_correction_info: bool = True) -> str:
        """
        插入文本段落並建立校正狀態
        返回創建的項目ID
        """
        try:
            # 檢查文本是否需要校正
            needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)
            correction_icon = '✅' if needs_correction and show_correction_info else ''

            # 準備新的值列表
            if self.display_mode == "audio_srt":
                new_values = [
                    self.PLAY_ICON,
                    str(insert_position + 1),  # 暫時的索引
                    start,
                    end,
                    text,
                    correction_icon
                ]
            else:
                new_values = [
                    str(insert_position + 1),  # 暫時的索引
                    start,
                    end,
                    text,
                    correction_icon
                ]

            # 插入新項目
            new_item = self.tree_manager.insert_item('', insert_position, values=tuple(new_values))

            # 如果需要校正，建立校正狀態
            if needs_correction:
                self.correction_service.set_correction_state(
                    str(insert_position + 1),  # 使用暫時的索引
                    original_text,
                    corrected_text,
                    'error'  # 初始狀態為未校正
                )

            return new_item
        except Exception as e:
            self.logger.error(f"插入文本段落時出錯: {e}")
            return ""

    def process_srt_edit_result(self, result, item, srt_index, start_time, end_time):
        """處理 SRT 文本編輯結果 - 轉發到 split_service"""
        self.split_service.process_srt_edit_result(result, item, srt_index, start_time, end_time)


    def process_word_text_edit(self, result, item, srt_index):
        """
        處理 Word 文本編輯結果
        :param result: 編輯結果
        :param item: 樹項目 ID
        :param srt_index: SRT 索引
        """
        try:
            # 保存操作前的狀態供撤銷使用
            original_state = self.get_current_state()
            original_correction = self.correction_service.serialize_state()

            # 檢查結果類型
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], tuple):
                # 這是文本拆分結果 - 獲取當前值
                current_values = self.tree_manager.get_item_values(item)

                # 調用處理 Word 文本斷句的方法
                word_index = -1  # 設置適當的 Word 文檔索引
                if hasattr(self, 'process_word_text_split'):
                    self.process_word_text_split(result, word_index, srt_index, current_values, item)
                else:
                    self.logger.warning("未找到 process_word_text_split 方法，無法處理 Word 文本斷句")
            else:
                # 單一文本編輯結果
                text = result
                if isinstance(text, list):
                    if len(text) > 0:
                        text = str(text[0])
                    else:
                        text = ""

                # 確保文本是字串類型
                text = str(text)

                # 獲取當前值
                values = list(self.tree_manager.get_item_values(item))
                tags = self.tree_manager.get_item_tags(item)

                # 更新 Word 文本
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    values[5] = text  # Word Text 在 ALL 模式下的索引
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    values[4] = text  # Word Text 在 SRT_WORD 模式下的索引

                # 更新樹狀視圖
                self.tree.item(item, values=tuple(values), tags=tags)

                # 標記 Word 欄位被編輯
                i = srt_index - 1
                if i not in self.edited_text_info:
                    self.edited_text_info[i] = {'edited': []}

                if 'word' not in self.edited_text_info[i]['edited']:
                    self.edited_text_info[i]['edited'].append('word')

                # 更新 SRT 數據
                self.update_srt_data_from_treeview()

                # 保存當前狀態
                current_state = self.get_current_state()
                current_correction = self.correction_service.serialize_state()

                self.save_operation_state(current_state, {
                    'type': 'edit_word_text',
                    'description': '編輯 Word 文本',
                    'original_state': original_state,
                    'original_correction': original_correction,
                    'srt_index': srt_index,
                    'item_id': item
                }, current_correction)

                # 更新狀態欄
                self.update_status("已更新 Word 文本")

        except Exception as e:
            self.logger.error(f"處理 Word 編輯結果時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新文本失敗: {str(e)}", self.master)

    def process_word_text_split(self, result, word_index, srt_index, original_values, original_item):
        """處理Word文本的斷句"""
        try:
            # 保存操作前的狀態供撤銷使用
            original_state = self.get_current_state()
            original_correction = self.correction_service.serialize_state()

            # 先獲取項目位置，然後再刪除
            delete_position = self.tree.index(original_item)

            # 儲存原始的標籤狀態
            tags = self.tree.item(original_item, 'tags')

            # 移除不需要的標籤
            if tags and 'mismatch' in tags:
                tags = tuple(tag for tag in tags if tag != 'mismatch')

            # 從樹狀視圖中刪除原項目
            self.tree_manager.delete_item(original_item)

            # 載入校正數據庫
            corrections = self.load_corrections()

            # 處理每個分割後的文本段落
            new_items = []
            for i, (text, new_start, new_end) in enumerate(result):
                # 構建用於插入的值列表
                new_values = list(original_values)
                new_srt_index = srt_index + i if i > 0 else srt_index

                # 更新索引、時間和Word文本，但保留校正狀態不變
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    new_values[1] = str(new_srt_index)  # Index
                    new_values[2] = new_start  # Start
                    new_values[3] = new_end    # End

                    # 為第一個段落保留SRT文本，其他段落使用空白字符串
                    if i > 0:
                        new_values[4] = ""  # 新段落的SRT文本為空白字符串

                    new_values[5] = text  # Word文本
                    new_values[6] = ""  # 清空Match欄位

                    # 重要修改：清空校正圖標，稍後根據校正檢查重新設置
                    new_values[7] = ""

                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    new_values[0] = str(new_srt_index)  # Index
                    new_values[1] = new_start  # Start
                    new_values[2] = new_end    # End

                    # 為第一個段落保留SRT文本，其他段落使用空白字符串
                    if i > 0:
                        new_values[3] = ""  # 新段落的SRT文本為空白字符串

                    new_values[4] = text  # Word文本
                    new_values[5] = ""  # 清空Match欄位

                    # 重要修改：清空校正圖標，稍後根據校正檢查重新設置
                    new_values[6] = ""

                # 確保V.O值保持
                if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                    new_values[0] = self.PLAY_ICON

                # 插入新項目
                new_item = self.tree_manager.insert_item('', delete_position + i, values=tuple(new_values))
                new_items.append(new_item)

                # 應用標籤
                if tags:
                    self.tree.item(new_item, tags=tags)

                # 如果這是第一個項目，保存use_word_text狀態
                if i == 0 and original_item in self.use_word_text:
                    self.use_word_text[new_item] = self.use_word_text[original_item]

                # 重要修改：重新檢查文本是否需要校正，不繼承原校正狀態
                needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

                # 根據校正檢查設置校正圖標和狀態
                if needs_correction:
                    # 獲取校正圖標的位置
                    vx_pos = 7 if self.display_mode == self.DISPLAY_MODE_ALL else 6

                    # 更新值列表中的校正圖標
                    updated_values = list(self.tree.item(new_item, 'values'))
                    updated_values[vx_pos] = '❌'  # 預設為未校正狀態
                    self.tree.item(new_item, values=tuple(updated_values))

                    # 設置校正狀態
                    self.correction_service.set_correction_state(
                        str(new_srt_index),
                        original_text,
                        corrected_text,
                        'error'  # 預設為未校正狀態
                    )

                # 更新Word處理器中的段落
                if hasattr(self, 'word_processor'):
                    try:
                        # 確保索引有效
                        if i == 0:
                            # 第一個段落更新原有的
                            self.word_processor.edit_paragraph(word_index, text)
                        else:
                            # 後續段落需要添加新段落
                            self.word_processor.split_paragraph(word_index, [text])
                    except Exception as e:
                        self.logger.error(f"更新Word段落時出錯: {e}")

            # 重新編號所有項目
            self.renumber_items()

            # 更新音頻段落索引
            if self.audio_imported:
                self.update_audio_segments()

            # 選中新創建的項目
            if new_items:
                self.tree_manager.set_selection(new_items)
                self.tree_manager.select_and_see(new_items[0])

            # 更新 SRT 數據以反映變化
            self.update_srt_data_from_treeview()

            # 保存當前狀態
            current_state = self.get_current_state()
            current_correction = self.correction_service.serialize_state()

            # 保存關鍵的操作信息，包含足夠的信息以便還原
            operation_info = {
                'type': 'split_word_text',
                'description': 'Word 文本斷句',
                'original_item': original_item,
                'word_index': word_index,
                'srt_index': srt_index,
                'new_items': new_items,
                'original_state': original_state,
                'split_count': len(result)
            }

            # 使用 save_state 保存狀態
            if hasattr(self, 'state_manager'):
                self.save_operation_state(current_state, operation_info, current_correction)

            # 更新狀態
            self.update_status("已分割 Word 文本")

        except Exception as e:
            self.logger.error(f"處理 Word 文本分割時出錯: {e}", exc_info=True)
            show_error("錯誤", f"分割 Word 文本失敗: {str(e)}", self.master)

    def bind_all_events(self) -> None:
        """綁定所有事件"""
        # 原有的事件綁定
        # 綁定視窗關閉事件
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 綁定全域快捷鍵
        self.master.bind_all('<Control-s>', lambda e: self.save_srt())
        self.master.bind_all('<Control-o>', lambda e: self.load_srt())
        self.master.bind_all('<Control-z>', lambda e: self.undo())
        self.master.bind_all('<Control-y>', lambda e: self.redo())

        # 綁定 Treeview 特定事件
        if hasattr(self, 'tree'):
            self.tree.bind('<Button-1>', self.on_tree_click)
            self.tree.bind('<Double-1>', self._handle_double_click)
            self.tree.bind('<KeyRelease>', self.on_treeview_change)

            # 添加鼠標移動事件以跟蹤游標位置
            self.tree.bind('<Motion>', self.show_floating_correction_icon)

            # 添加鼠標離開事件
            self.tree.bind('<Leave>', self.on_mouse_leave_tree)

    def initialize_audio_player(self) -> None:
        """初始化音頻服務和播放器"""
        from audio.audio_service import AudioService

        self.audio_service = AudioService(self)  # 傳入 self 作為 gui_reference
        self.audio_player = self.audio_service.initialize_player(self.main_frame)

        # 設置音頻載入回調
        def on_audio_loaded_callback(file_path):
            self.audio_file_path = file_path
            self.audio_imported = True
            self.update_display_mode()
            self.update_file_info()
            # 其他需要的處理...

        self.on_audio_loaded_callback = on_audio_loaded_callback

    def on_treeview_change(self, event: tk.Event) -> None:
        """
        處理 Treeview 變更事件
        :param event: 事件對象
        """
        current_state = self.get_current_state()
        correction_state = self.correction_service.serialize_state()
        self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})
    def on_closing(self) -> None:
        """處理視窗關閉事件"""
        try:
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()
            current_state = self.get_current_state()
            correction_state = self.correction_service.serialize_state()
            self.save_operation_state('操作類型', '操作描述', additional_info={'key': 'value'})

            # 先解除所有事件綁定
            for widget in self.master.winfo_children():
                for binding in widget.bind():
                    widget.unbind(binding)

            self.master.update_idletasks()  # 確保所有待處理的事件都被處理
            self.master.destroy()
            import sys
            sys.exit(0)
        except Exception as e:
            self.logger.error(f"關閉視窗時出錯: {e}")
            self.master.destroy()
            sys.exit(1)

    def play_audio_segment(self, index: int) -> None:
        """播放指定的音頻段落"""
        try:
            self.logger.info(f"===== 嘗試播放索引 {index} 的音頻段落 =====")

            # 檢查音頻播放器是否已初始化
            if not hasattr(self, 'audio_player'):
                self.logger.error("音頻播放器未初始化")
                # 嘗試初始化播放器
                self.initialize_audio_player()
                if not hasattr(self, 'audio_player'):
                    show_error("錯誤", "無法初始化音頻播放器", self.master)
                    return

            # 檢查播放器的音頻是否已載入
            if not hasattr(self.audio_player, 'audio') or self.audio_player.audio is None:
                self.logger.error("播放器音頻未載入")

                # 嘗試重新載入音頻
                if hasattr(self, 'audio_file_path') and self.audio_file_path:
                    self.logger.info(f"嘗試重新載入音頻文件: {self.audio_file_path}")
                    loaded = self.audio_player.load_audio(self.audio_file_path)

                    if not loaded or not self.audio_player.audio:
                        show_warning("警告", "無法載入音頻，請重新匯入音頻檔案", self.master)
                        return
                else:
                    show_warning("警告", "無法播放音訊：音訊未載入或為空", self.master)
                    return

            success = self.audio_player.play_segment(index)

            # 如果播放失敗，記錄錯誤
            if not success:
                self.logger.error(f"播放索引 {index} 的音頻段落失敗")
                show_warning("警告", f"播放索引 {index} 的音頻段落失敗", self.master)

        except Exception as e:
            self.logger.error(f"播放音頻段落時出錯: {e}", exc_info=True)
            show_error("錯誤", f"播放音頻段落失敗: {str(e)}", self.master)

    def insert_item(self, parent: str, position: str, values: tuple) -> str:
        """
        封裝 Treeview 的插入操作，並加入日誌追蹤
        """
        try:
            return self.tree_manager.insert_item(parent, position, values)
        except Exception as e:
            self.logger.error(f"插入項目時出錯: {e}")
            raise

    def handle_audio_loaded(self, event: Optional[tk.Event] = None) -> None:
        """處理音頻載入事件"""
        try:
            if not self.audio_imported:  # 避免重複處理
                self.audio_imported = True
                self.audio_file_path = self.audio_player.audio_file

                # 保存當前數據狀態
                old_mode = self.display_mode
                self.logger.info(f"音頻已載入，匯入前顯示模式: {old_mode}")

                # 保存當前樹視圖數據
                current_data = []
                for item in self.tree_manager.get_all_items():
                    values = self.tree_manager.get_item_values(item)
                    tags = self.tree_manager.get_item_tags(item)
                    use_word = self.use_word_text.get(item, False)

                    # 獲取索引位置
                    index_pos = 1 if old_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 0

                    if values and len(values) > index_pos:
                        index = str(values[index_pos])
                        # 檢查是否有校正狀態
                        correction_info = None
                        if index in self.correction_service.correction_states:
                            correction_info = {
                                'state': self.correction_service.correction_states[index],
                                'original': self.correction_service.original_texts.get(index, ''),
                                'corrected': self.correction_service.corrected_texts.get(index, '')
                            }

                    current_data.append({
                        'values': values,
                        'tags': tags,
                        'use_word': use_word,
                        'correction': correction_info
                    })

                # 先清空當前樹狀視圖
                self.tree_manager.clear_all()

                # 更新顯示模式 (這會改變樹狀視圖的結構)
                self.update_display_mode()

                # 更新文件信息
                self.update_file_info()

                # 如果有 SRT 數據，更新音頻段落
                if hasattr(self, 'srt_data') and self.srt_data:
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.info("已根據 SRT 數據分割音頻段落")

                # 重要：根據舊數據重新填充樹狀視圖
                new_mode = self.display_mode
                for item_data in current_data:
                    values = item_data['values']
                    # 轉換值以適應新的顯示模式
                    adjusted_values = self.adjust_values_for_mode(values, old_mode, new_mode)

                    # 插入到樹狀視圖
                    new_item = self.insert_item('', 'end', values=tuple(adjusted_values))

                    # 恢復標籤
                    if item_data['tags']:
                        self.tree.item(new_item, tags=item_data['tags'])

                    # 恢復 use_word_text 狀態
                    if item_data['use_word']:
                        self.use_word_text[new_item] = True

                    # 恢復校正狀態
                    if 'correction' in item_data and item_data['correction']:
                        correction = item_data['correction']

                        # 獲取新的索引位置
                        index_pos = 1 if new_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 0
                        if len(adjusted_values) > index_pos:
                            new_index = str(adjusted_values[index_pos])

                            # 恢復校正狀態
                            self.correction_service.correction_states[new_index] = correction['state']
                            self.correction_service.original_texts[new_index] = correction['original']
                            self.correction_service.corrected_texts[new_index] = correction['corrected']

                # 如果已加載 Word 文檔，檢查是否需要執行自動比對
                if self.word_imported and hasattr(self, 'word_processor'):
                    # 檢查是否需要重新執行比對
                    if old_mode != self.display_mode:
                        self.logger.info("顯示模式已變更，正在重新執行 Word 比對")
                        self.compare_word_with_srt()
                    else:
                        self.logger.info("顯示模式未變更，保持現有 Word 比對結果")

                # 檢查所有模式切換是否已正確處理
                self.check_display_mode_consistency()

                # 通知使用者（如果尚未顯示過通知）
                if not self.audio_notification_shown:
                    show_info("成功", f"已成功載入音頻檔案：\n{os.path.basename(self.audio_file_path)}", self.master)
                    self.audio_notification_shown = True

        except Exception as e:
            self.logger.error(f"處理音頻載入事件時出錯: {e}")
            show_error("錯誤", f"處理音頻載入失敗: {str(e)}", self.master)

    # 修改 load_corrections 方法，使用 CorrectionService
    def load_corrections(self) -> Dict[str, str]:
        """載入校正數據庫"""
        # 如果尚未設置資料庫檔案，設置它
        if self.current_project_path and not self.correction_service.database_file:
            database_file = os.path.join(self.current_project_path, "corrections.csv")
            self.correction_service.set_database_file(database_file)

        # 載入校正規則
        corrections = self.correction_service.load_corrections()

        # 如果有項目，自動應用校正
        if hasattr(self, 'tree') and self.tree_manager.get_all_items():
            self.update_correction_display()

        return corrections

    # 修改 correct_text 方法，使用 CorrectionService
    def correct_text(self, text: str, corrections: Dict[str, str] = None) -> str:
        """
        根據校正數據庫修正文本
        :param text: 原始文本
        :param corrections: 校正對照表，如果為 None 則使用當前的校正表
        :return: 校正後的文本
        """
        # 使用 correction_service 檢查文本是否需要校正
        if not hasattr(self, 'correction_service') or not self.correction_service:
            return text

        try:
            needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)
            return corrected_text if needs_correction else text
        except ValueError as e:
            self.logger.error(f"校正文本時出錯: {e}")
            return text  # 返回原始文本作為備選

    def prepare_and_insert_subtitle_item(self, sub, corrections=None, tags=None, use_word=False):
        """準備並插入字幕項目到樹狀視圖"""
        return self.split_service.prepare_and_insert_subtitle_item(sub, corrections, tags, use_word)

    def process_srt_entries(self, srt_data, corrections):
        """處理 SRT 條目"""
        self.split_service.process_srt_entries(srt_data, corrections)

    def update_audio_segments(self) -> None:
        """完全重建音頻段落映射，確保與當前 SRT 數據一致"""
        if not hasattr(self, 'audio_player') or not self.audio_player or not self.audio_player.audio:
            return

        try:
            # 使用現有的 segment_audio 方法重新分割整個音頻
            if hasattr(self, 'srt_data') and self.srt_data:
                self.audio_player.segment_audio(self.srt_data)
                self.logger.info(f"音頻段落重建完成，共 {len(self.srt_data)} 個段落")
        except Exception as e:
            self.logger.error(f"更新音頻段落時出錯: {e}")

    # 在修改 Treeview 數據的同時更新 SRT 數據
    def update_srt_data_from_treeview(self) -> None:
        """從 Treeview 更新 SRT 數據"""
        # 添加遞歸保護
        if hasattr(self, '_updating_srt_data') and self._updating_srt_data:
            return

        try:
            self._updating_srt_data = True
            # 創建新的 SRT 數據
            new_srt_data = pysrt.SubRipFile()

            # 獲取當前顯示模式下的索引列
            if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                index_col = 1
                start_col = 2
                end_col = 3
                text_col = 4
            else:  # SRT 或 SRT_WORD 模式
                index_col = 0
                start_col = 1
                end_col = 2
                text_col = 3

            for i, item in enumerate(self.tree_manager.get_all_items(), 1):
                try:
                    values = self.tree_manager.get_item_values(item)

                    # 安全地獲取數據，避免索引錯誤
                    if len(values) <= index_col:
                        continue  # 跳過無效的值

                    # 獲取索引、時間和文本，使用預設值避免錯誤
                    try:
                        index = int(values[index_col]) if values[index_col].isdigit() else i
                    except (ValueError, TypeError, AttributeError):
                        index = i

                    # 獲取時間
                    start_time = values[start_col] if len(values) > start_col else "00:00:00,000"
                    end_time = values[end_col] if len(values) > end_col else "00:00:10,000"

                    # 獲取文本
                    text = values[text_col] if len(values) > text_col else ""

                    # 考慮 use_word_text 設置
                    if self.display_mode in [self.DISPLAY_MODE_SRT_WORD, self.DISPLAY_MODE_ALL] and self.use_word_text.get(item, False):
                        # 獲取 Word 文本列的索引
                        word_text_col = 5 if self.display_mode == self.DISPLAY_MODE_ALL else 4
                        if len(values) > word_text_col and values[word_text_col]:
                            text = values[word_text_col]

                    # 考慮校正狀態
                    try:
                        item_index = str(values[index_col])
                        if item_index in self.correction_service.correction_states:
                            state = self.correction_service.correction_states[item_index]
                            if state == 'correct' and item_index in self.correction_service.corrected_texts:
                                text = self.correction_service.corrected_texts[item_index]
                    except Exception as e:
                        self.logger.warning(f"處理校正狀態時出錯: {e}")

                    # 安全解析時間
                    try:
                        start = parse_time(start_time) if isinstance(start_time, str) else start_time
                        end = parse_time(end_time) if isinstance(end_time, str) else end_time
                    except ValueError as e:
                        self.logger.warning(f"解析時間失敗: {e}, 使用默認時間")
                        start = pysrt.SubRipTime(0, 0, 0, 0)
                        end = pysrt.SubRipTime(0, 0, 10, 0)  # 默認10秒

                    # 創建 SRT 項目
                    sub = pysrt.SubRipItem(
                        index=i,  # 使用連續的索引
                        start=start,
                        end=end,
                        text=text if text is not None else ""
                    )
                    new_srt_data.append(sub)
                except Exception as e:
                    self.logger.warning(f"處理項目 {i} 時出錯: {e}, 跳過該項目")
                    continue

            # 更新 SRT 數據
            self.srt_data = new_srt_data
            self.logger.info(f"從 Treeview 更新 SRT 數據，共 {len(new_srt_data)} 個項目")

            # 更新音頻段落時，禁止觸發校正狀態更新
            skip_correction_update = True
            if self.audio_imported and hasattr(self, 'audio_player') and self.srt_data:
                if hasattr(self.audio_player.segment_manager, 'rebuild_segments'):
                    self.audio_player.segment_manager.rebuild_segments(self.srt_data)
                else:
                    self.audio_player.segment_audio(self.srt_data)

        finally:
            self._updating_srt_data = False

    def combine_sentences(self, event=None):
        """合併字幕"""
        self.combine_service.combine_sentences(event)

    def get_column_indices_for_current_mode(self) -> Dict[str, int]:
        """
        獲取當前顯示模式下各種列的索引位置
        :return: 列名稱到索引的映射
        """
        if self.display_mode == self.DISPLAY_MODE_SRT:
            return {
                'index': 0,
                'start': 1,
                'end': 2,
                'text': 3,
                'vx': 4,
                'vo': None,
                'word_text': None,
                'match': None
            }
        elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
            return {
                'index': 0,
                'start': 1,
                'end': 2,
                'text': 3,
                'word_text': 4,
                'match': 5,
                'vx': 6,
                'vo': None
            }
        elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
            return {
                'vo': 0,
                'index': 1,
                'start': 2,
                'end': 3,
                'text': 4,
                'vx': 5,
                'word_text': None,
                'match': None
            }
        else:  # self.DISPLAY_MODE_ALL
            return {
                'vo': 0,
                'index': 1,
                'start': 2,
                'end': 3,
                'text': 4,
                'word_text': 5,
                'match': 6,
                'vx': 7
            }

    def _combine_item_values(self, sorted_items, column_indices, base_values):
        """合併所有選中項的值"""
        # 載入校正數據庫
        corrections = self.load_corrections()

        # 基礎值
        combined_values = list(base_values)

        # 獲取合併後的文本
        combined_text = ""
        combined_word_text = ""
        combined_match = ""

        # 收集所有文本和Word文本
        all_srt_texts = []
        all_word_texts = []

        # 從所有項目獲取文本內容
        for i, item in enumerate(sorted_items):
            item_values = self.tree_manager.get_item_values(item)

            # 獲取SRT文本
            if column_indices['text'] < len(item_values) and item_values[column_indices['text']].strip():
                all_srt_texts.append(item_values[column_indices['text']])

            # 獲取Word文本（如果有）
            if column_indices['word_text'] is not None and column_indices['word_text'] < len(item_values) and item_values[column_indices['word_text']].strip():
                all_word_texts.append(item_values[column_indices['word_text']])

        # 合併所有文本（使用空格連接）
        combined_text = " ".join(all_srt_texts)

        # 合併所有Word文本（如果有）
        if all_word_texts:
            combined_word_text = " ".join(all_word_texts)

        # 使用最後一個項目的結束時間
        last_item_values = self.tree.item(sorted_items[-1], 'values')
        end_time = ""
        if column_indices['end'] < len(last_item_values):
            end_time = last_item_values[column_indices['end']]
        else:
            end_time = base_values[column_indices['end']] if column_indices['end'] < len(base_values) else ""

        # 更新合併後的值
        combined_values[column_indices['end']] = end_time
        combined_values[column_indices['text']] = combined_text

        if column_indices['vo'] is not None:
            combined_values[column_indices['vo']] = self.PLAY_ICON

        if column_indices['word_text'] is not None:
            combined_values[column_indices['word_text']] = combined_word_text

        # 更新Match欄位（如果需要）
        if column_indices['match'] is not None:
            # 可能需要根據文本內容重新計算Match狀態
            combined_values[column_indices['match']] = ""

        self.logger.debug(f"合併文本: {combined_text}")
        self.logger.debug(f"合併Word文本: {combined_word_text}")

        return combined_values

    def _create_merged_item(self, sorted_items, combined_values, needs_correction, corrected_text, base_tags, column_indices) -> tuple:
        """創建新的合併項目"""
        # 設置校正狀態圖標
        combined_values[column_indices['vx']] = '✅' if needs_correction else ''

        # 檢查是否有任一項使用 Word 文本
        use_word_text = False
        for item in sorted_items:
            if self.use_word_text.get(item, False):
                use_word_text = True
                break

        # 刪除所有原始項目
        insert_position = self.tree.index(sorted_items[0])
        for item in sorted_items:
            self.tree_manager.delete_item(item)

        # 插入新合併項目
        new_item = self.insert_item('', insert_position, values=tuple(combined_values))

        # 確保 new_item_index 被定義
        if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
            new_item_index = str(combined_values[1])
        else:
            new_item_index = str(combined_values[0])

        # 設置標籤
        if base_tags:
            self.tree.item(new_item, tags=base_tags)

        # 設置 use_word_text 狀態
        if use_word_text:
            self.use_word_text[new_item] = True
            current_tags = list(self.tree.item(new_item, "tags") or ())
            if "use_word_text" not in current_tags:
                current_tags.append("use_word_text")
            if "mismatch" in current_tags:
                current_tags.remove("mismatch")
            self.tree.item(new_item, tags=tuple(current_tags))

        # 保存校正狀態處理 - 根據實際檢查結果設置
        if needs_correction:
            # 明確設置校正狀態
            self.correction_service.set_correction_state(
                new_item_index,
                combined_values[column_indices['text']],  # 原始文本
                corrected_text,  # 校正後文本
                'correct'  # 默認為已校正狀態
            )

            # 更新顯示，確保校正圖標顯示正確
            if column_indices['vx'] < len(combined_values):
                new_values_list = list(combined_values)
                new_values_list[column_indices['vx']] = '✅'
                self.tree.item(new_item, values=tuple(new_values_list))
        else:
            # 如果不需要校正，確保沒有校正狀態
            if hasattr(self.correction_service, 'remove_correction_state'):
                self.correction_service.remove_correction_state(new_item_index)

        return new_item, new_item_index

    def _update_srt_and_audio(self, sorted_items, new_item_index):
        """更新 SRT 數據和音頻段落"""
        # 首先獲取所有需要合併的索引
        indices_to_merge = []
        for item in sorted_items:
            item_values = self.tree_manager.get_item_values(item)
            if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                if len(item_values) > 1:
                    try:
                        idx = int(item_values[1])  # 索引在第2列
                        indices_to_merge.append(idx)
                    except (ValueError, TypeError):
                        pass
            else:
                if item_values:
                    try:
                        idx = int(item_values[0])  # 索引在第1列
                        indices_to_merge.append(idx)
                    except (ValueError, TypeError):
                        pass

        # 對索引排序，確保按順序處理
        indices_to_merge.sort()

        # 如果沒有找到有效索引，無法處理
        if not indices_to_merge:
            self.logger.warning("找不到要合併的有效索引")
            return

        # 合併SRT數據
        try:
            # 保留第一個索引的項目
            first_idx = indices_to_merge[0]
            if first_idx <= len(self.srt_data):
                # 獲取合併後的文本 - 從樹狀視圖中獲取，確保與顯示一致
                merged_text = ""
                for item in sorted_items:
                    values = self.tree_manager.get_item_values(item)
                    text_index = 4 if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 3
                    if text_index < len(values) and values[text_index]:
                        if merged_text:
                            merged_text += " "
                        merged_text += values[text_index]

                # 獲取開始時間和結束時間
                start_time = self.srt_data[first_idx - 1].start
                last_idx = indices_to_merge[-1]
                end_time = self.srt_data[last_idx - 1].end if last_idx <= len(self.srt_data) else start_time

                # 更新第一個項目
                self.srt_data[first_idx - 1].text = merged_text
                self.srt_data[first_idx - 1].end = end_time

                # 刪除其他被合併的項目
                self.srt_data = [sub for sub in self.srt_data if sub.index not in indices_to_merge[1:]]

                # 重新編號
                for i, sub in enumerate(self.srt_data, 1):
                    sub.index = i

                self.logger.info(f"已更新SRT數據，合併 {len(indices_to_merge)} 個項目")
        except Exception as e:
            self.logger.error(f"更新SRT數據時出錯: {e}", exc_info=True)

            # 更新項目編號
            self.renumber_items()

            # 更新 SRT 數據
            self.update_srt_data_from_treeview()

            # 如果有音頻，處理音頻段落
            if self.audio_imported and hasattr(self, 'audio_player'):
                # 由於原始項目已被刪除，使用索引而非項目ID來處理音頻段落
                try:
                    # 直接使用新的合併項目索引
                    new_index = int(new_item_index)

                    # 重新對整個 SRT 數據進行分割以確保一致性
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.info(f"已重新分割全部音頻段落，確保與 SRT 同步")
                except Exception as e:
                    self.logger.error(f"處理音頻段落時出錯: {e}", exc_info=True)
                    # 即使出錯，也嘗試重新分割所有音頻
                    if hasattr(self.audio_player, 'segment_audio'):
                        self.audio_player.segment_audio(self.srt_data)

            # 刷新所有校正狀態，確保它們基於最新的文本內容
            if hasattr(self.correction_service, 'refresh_all_correction_states'):
                self.correction_service.refresh_all_correction_states()
                self.logger.debug("已刷新所有校正狀態")

            # 更新校正狀態顯示
            self.update_correction_status_display()

        except Exception as e:
            self.logger.error(f"更新 SRT 數據和音頻段落時出錯: {e}", exc_info=True)

    def _merge_audio_segments(self, sorted_items, new_item_index) -> None:
        """合併音頻段落"""
        try:
            # 獲取所有被合併項目的確切索引
            indices_to_merge = []
            for item in sorted_items:
                item_values = self.tree_manager.get_item_values(item)
                if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                    if len(item_values) > 1:
                        try:
                            idx = int(item_values[1])  # 索引在第2列
                            indices_to_merge.append(idx)
                        except (ValueError, TypeError):
                            pass
                else:
                    if item_values:
                        try:
                            idx = int(item_values[0])  # 索引在第1列
                            indices_to_merge.append(idx)
                        except (ValueError, TypeError):
                            pass

            self.logger.info(f"準備合併音頻段落，選中的索引: {indices_to_merge}")

            # 確保只使用選中的索引的音頻段落
            valid_segments = []
            for idx in indices_to_merge:
                segment = None
                # 嘗試獲取音頻段落
                if idx in self.audio_player.segment_manager.audio_segments:
                    segment = self.audio_player.segment_manager.audio_segments[idx]
                elif str(idx) in self.audio_player.segment_manager.audio_segments:
                    segment = self.audio_player.segment_manager.audio_segments[str(idx)]

                if segment:
                    valid_segments.append((idx, segment))
                else:
                    self.logger.warning(f"索引 {idx} 的音頻段落不存在，跳過")

            if valid_segments:
                # 按照選取順序排序
                ordered_segments = []
                for idx in indices_to_merge:
                    for seg_idx, segment in valid_segments:
                        if seg_idx == idx:
                            ordered_segments.append(segment)
                            break

                # 合併音頻段落
                if ordered_segments:
                    combined_segment = ordered_segments[0]
                    for segment in ordered_segments[1:]:
                        combined_segment = combined_segment + segment

                    # 獲取新的索引
                    new_index = int(new_item_index)

                    # 保存合併後的段落
                    self.audio_player.segment_manager.audio_segments[new_index] = combined_segment
                    self.logger.info(f"成功合併音頻段落，新索引: {new_index}")

                    # 刪除被合併的舊段落（除了新索引本身）
                    for idx in indices_to_merge:
                        if idx != new_index:
                            # 嘗試刪除索引
                            if idx in self.audio_player.segment_manager.audio_segments:
                                del self.audio_player.segment_manager.audio_segments[idx]
                            elif str(idx) in self.audio_player.segment_manager.audio_segments:
                                del self.audio_player.segment_manager.audio_segments[str(idx)]
                else:
                    self.logger.warning("沒有有效的音頻段落可排序")
            else:
                self.logger.warning("沒有找到有效的音頻段落可合併")

            if self.audio_imported and hasattr(self, 'audio_player'):
                # 使用全部音頻段落重新分割
                self.audio_player.segment_audio(self.srt_data)
                self.logger.info(f"已根據更新後的 SRT 數據重新分割音頻段落")
        except Exception as e:
            self.logger.error(f"合併音頻段落時出錯: {e}", exc_info=True)

    def _finalize_combine(self, original_state, original_correction, original_items_data, new_item, new_item_index) -> None:
        """完成合併操作，保存狀態並更新顯示"""
        # 保存操作後的狀態
        current_state = self.get_current_state()
        current_correction = self.correction_service.serialize_state()

        # 獲取所有選中項目的詳細信息（用於還原）
        selected_items_details = []
        for item_data in original_items_data:
            selected_items_details.append({
                'id': item_data.get('id'),
                'values': item_data.get('values'),
                'tags': item_data.get('tags'),
                'position': item_data.get('position'),
                'use_word': item_data.get('use_word', False)
            })

        # 保存更完整的操作信息
        operation_info = {
            'type': 'combine_sentences',
            'description': '合併字幕',
            'original_state': original_state,
            'original_correction': original_correction,
            'items': [item_data.get('id') for item_data in original_items_data],
            'selected_items_details': selected_items_details,
            'is_first_operation': len(self.state_manager.states) <= 1,
            'new_item': new_item,  # 保存新合併項的ID
            'new_item_index': new_item_index  # 保存新合併項的索引
        }

        self.logger.debug(f"正在保存合併操作狀態: 原狀態項數={len(original_state)}, 新狀態項數={len(current_state)}")
        self.save_operation_state(current_state, operation_info, current_correction)

        # 選中新合併的項目
        self.tree_manager.set_selection(new_item)
        self.tree_manager.select_and_see(new_item)

        self.save_operation_state(
            'combine_sentences',
            '合併字幕',
            {
                'original_state': original_state,
                'original_correction': original_correction,
                'items': [item_data.get('id') for item_data in original_items_data],
                'selected_items_details': selected_items_details
            }
        )

        # 隱藏合併符號
        if hasattr(self, 'merge_symbol'):
            self.merge_symbol.place_forget()

        self.update_status("已合併所選字幕")

    def align_end_times(self) -> None:
        """調整結束時間"""
        items = self.tree_manager.get_all_items()
        if not items:
            show_warning("警告", "沒有可調整的字幕項目", self.master)
            return

        try:
            # 保存調整前的狀態供撤銷使用
            original_state = self.get_current_state()
            original_correction = self.correction_service.serialize_state()

            # 根據顯示模式確定時間列的索引
            if self.display_mode in [self.DISPLAY_MODE_SRT, self.DISPLAY_MODE_SRT_WORD]:
                start_index = 1  # Start 欄位索引
                end_index = 2    # End 欄位索引
            else:  # self.display_mode in [self.DISPLAY_MODE_AUDIO_SRT, self.DISPLAY_MODE_ALL]:
                start_index = 2  # Start 欄位索引
                end_index = 3    # End 欄位索引

            self.logger.info(f"開始調整結束時間，顯示模式: {self.display_mode}，時間欄位索引: 開始={start_index}, 結束={end_index}")

            # 保存所有項目的原始時間值
            original_items_times = []
            for i, item in enumerate(items):
                values = self.tree_manager.get_item_values(item)
                if len(values) > end_index:
                    item_data = {
                        'id': item,
                        'index': i,
                        'start': values[start_index] if len(values) > start_index else "",
                        'end': values[end_index] if len(values) > end_index else ""
                    }
                    original_items_times.append(item_data)

            # 保存操作記錄
            self.last_time_adjust_operation = {
                'timestamp': time.time(),
                'original_items_times': original_items_times,
                'display_mode': self.display_mode,
                'start_index': start_index,
                'end_index': end_index
            }

            # 創建備份以便還原
            backup_values = {}
            for item in items:
                backup_values[item] = list(self.tree_manager.get_item_values(item))

            # 逐項調整結束時間
            for i in range(len(items) - 1):
                current_item = items[i]
                next_item = items[i + 1]

                current_values = list(self.tree.item(current_item, 'values'))
                next_values = list(self.tree.item(next_item, 'values'))

                # 確保索引在有效範圍內
                if len(current_values) <= end_index or len(next_values) <= start_index:
                    self.logger.warning(f"項目 {i} 或 {i+1} 的值列表長度不足，跳過調整")
                    continue

                # 將當前項目的結束時間設為下一項目的開始時間
                current_values[end_index] = next_values[start_index]
                self.tree.item(current_item, values=tuple(current_values))

            # 更新 SRT 數據以反映變更
            self.update_srt_data_from_treeview()

            # 更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)

            # 保存操作狀態
            self.save_operation_state(
                'align_end_times',
                '調整結束時間',
                {
                    'original_state': original_state,
                    'original_correction': original_correction,
                    'backup_values': backup_values
                }
            )

            self.update_status("已完成結束時間調整")
            show_info("完成", "均將時間軸前後對齊填滿", self.master)

        except Exception as e:
            self.logger.error(f"調整結束時間時出錯: {e}", exc_info=True)
            show_error("錯誤", f"調整結束時間失敗: {str(e)}", self.master)

    def undo_time_adjust_operation(self):
        """
        專門處理時間軸調整的撤銷
        """
        try:
            # 檢查是否有時間調整操作記錄
            if not hasattr(self, 'last_time_adjust_operation') or not self.last_time_adjust_operation:
                self.logger.warning("沒有時間調整操作記錄，無法撤銷")
                return False

            # 獲取時間調整操作記錄
            time_op = self.last_time_adjust_operation
            original_items_times = time_op.get('original_items_times', [])

            if not original_items_times:
                self.logger.warning("時間調整操作記錄不完整，無法撤銷")
                return False

            self.logger.debug(f"執行時間調整操作撤銷，原始項目數: {len(original_items_times)}")

            # 獲取顯示模式的時間列索引
            start_index = time_op.get('start_index', 1)
            end_index = time_op.get('end_index', 2)

            # 恢復所有項目的原始時間
            for item_data in original_items_times:
                item_index = item_data.get('index', -1)
                original_start = item_data.get('start', '')
                original_end = item_data.get('end', '')

                # 獲取當前項目
                items = self.tree_manager.get_all_items()
                if 0 <= item_index < len(items):
                    current_item = items[item_index]
                    values = list(self.tree.item(current_item, 'values'))

                    # 恢復時間值
                    if len(values) > start_index:
                        values[start_index] = original_start
                    if len(values) > end_index:
                        values[end_index] = original_end

                    # 更新項目
                    self.tree.item(current_item, values=tuple(values))

            # 更新 SRT 數據
            self.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)

            # 清除時間調整操作記錄
            self.last_time_adjust_operation = None

            # 更新狀態
            self.update_status("已撤銷時間調整操作")
            return True

        except Exception as e:
            self.logger.error(f"撤銷時間調整操作時出錯: {e}", exc_info=True)
            show_error("錯誤", f"撤銷時間調整操作失敗: {str(e)}", self.master)
            return False

    # 在 renumber_items 函數中，確保校正狀態正確轉移
    def renumber_items(self, skip_correction_update=False) -> None:
        """重新編號項目並保持校正狀態"""
        try:
            items = self.tree_manager.get_all_items()
            if not items:
                return

            # 獲取索引欄位位置
            if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                index_pos = 1  # 第二欄
            else:  # self.DISPLAY_MODE_SRT, self.DISPLAY_MODE_SRT_WORD
                index_pos = 0  # 第一欄

            # 創建舊索引到新索引的完整映射
            index_mapping = {}

            # 如果不跳過校正狀態更新，則備份當前校正狀態
            old_correction_states = {}
            old_original_texts = {}
            old_corrected_texts = {}

            if not skip_correction_update and hasattr(self, 'correction_service'):
                for key, value in self.correction_service.correction_states.items():
                    old_correction_states[key] = value

                for key, value in self.correction_service.original_texts.items():
                    old_original_texts[key] = value

                for key, value in self.correction_service.corrected_texts.items():
                    old_corrected_texts[key] = value

                # 清除當前所有校正狀態 - 稍後會根據映射恢復
                self.correction_service.clear_correction_states()

            # 先建立舊索引到新索引的映射
            for i, item in enumerate(items, 1):
                if not self.tree.exists(item):
                    continue

                values = list(self.tree.item(item)['values'])
                if not values or len(values) <= index_pos:
                    continue

                # 獲取當前索引
                old_index = str(values[index_pos])

                # 保存舊索引到新索引的映射
                index_mapping[old_index] = str(i)

            # 然後更新值並恢復校正狀態
            for i, item in enumerate(items, 1):
                if not self.tree.exists(item):
                    continue

                values = list(self.tree.item(item)['values'])
                if not values or len(values) <= index_pos:
                    continue

                # 獲取當前索引
                old_index = str(values[index_pos])

                # 更新值中的索引
                values[index_pos] = str(i)
                self.tree_manager.update_item(item, values=tuple(values))

                # 如果不跳過校正狀態更新，則檢查是否需要更新校正狀態
                if not skip_correction_update:
                    if old_index in old_correction_states:
                        # 獲取該項目的原始校正信息
                        correction_state = old_correction_states[old_index]
                        original_text = old_original_texts.get(old_index, "")
                        corrected_text = old_corrected_texts.get(old_index, "")

                        # 使用新索引設置校正狀態
                        self.correction_service.set_correction_state(
                            str(i),
                            original_text,
                            corrected_text,
                            correction_state
                        )

            self.logger.info(f"重新編號完成: {len(items)} 個項目, {len(index_mapping)} 個索引映射")

        except Exception as e:
            self.logger.error(f"重新編號項目時出錯: {e}", exc_info=True)
            show_error("錯誤", f"重新編號失敗: {str(e)}", self.master)

    # 最後，修改 get_current_state 方法，以保存 use_word_text 的狀態
    def get_current_state(self) -> Dict[str, Any]:
        """
        獲取當前應用狀態，增強版
        :return: 當前應用狀態字典
        """
        try:
            state = {
                'tree_items': [],
                'display_mode': self.display_mode,
                'use_word_text': {},
                'srt_data': self.get_serialized_srt_data(),
                'item_id_mapping': {}  # 新增: 保存項目 ID 映射
            }

            # 收集樹狀視圖數據
            for item in self.tree_manager.get_all_items():
                values = self.tree_manager.get_item_values(item)
                tags = self.tree_manager.get_item_tags(item)
                position = self.tree_manager.get_item_position(item)

                # 獲取索引值
                index_position = 1 if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 0
                index = str(values[index_position]) if len(values) > index_position else str(position)

                item_state = {
                    'values': values,
                    'tags': tags,
                    'position': position,
                    'index': index,
                    'original_id': item  # 保存原始項目 ID
                }

                # 保存使用 Word 文本的標記
                if item in self.use_word_text:
                    state['use_word_text'][index] = self.use_word_text[item]
                    item_state['use_word_text'] = self.use_word_text[item]

                # 保存項目 ID 映射
                state['item_id_mapping'][item] = index

                state['tree_items'].append(item_state)

            return state
        except Exception as e:
            self.logger.error(f"獲取當前狀態時出錯: {e}")
            return {'tree_items': [], 'display_mode': self.display_mode}


    def get_serialized_srt_data(self) -> List[Dict[str, Any]]:
        """
        將 SRT 數據序列化為可保存的格式
        :return: 序列化後的 SRT 數據
        """
        result = []
        if hasattr(self, 'srt_data'):
            for sub in self.srt_data:
                result.append({
                    'index': sub.index,
                    'start': str(sub.start),
                    'end': str(sub.end),
                    'text': sub.text
                })
        return result

    def update_status(self, message: Optional[str] = None) -> None:
        """
        更新狀態列訊息
        :param message: 狀態訊息（可選）
        """
        if message:
            self.gui_builder.update_status(message)

        # 更新檔案狀態
        self.update_file_info()

        self.master.update_idletasks()

    def initialize_state_manager(self) -> None:
        """初始化狀態管理器和回調函數"""
        self.state_manager = EnhancedStateManager()

        # 設置對 GUI 的引用，使狀態管理器能夠操作界面元素
        self.state_manager.set_gui_reference(self)

        # 設置回調函數
        self.state_manager.set_callback('on_state_change', self.on_state_change)
        self.state_manager.set_callback('on_undo', self.on_undo_state)
        self.state_manager.set_callback('on_redo', self.on_redo_state)
        self.state_manager.set_callback('on_state_applied', self.on_state_applied)

        # 記錄初始化完成
        self.logger.info("狀態管理器初始化完成，已設置所有回調函數")

    def get_tree_data(self) -> List[Dict[str, Any]]:
        """獲取樹狀視圖數據"""
        tree_data = []
        for item in self.tree_manager.get_all_items():
            values = self.tree_manager.get_item_values(item)
            tags = self.tree_manager.get_item_tags(item)
            position = self.tree_manager.get_item_position(item)
            use_word = self.use_word_text.get(item, False)

            tree_data.append({
                'values': values,
                'tags': tags,
                'position': position,
                'use_word_text': use_word
            })
        return tree_data

    def apply_state(self, state, correction_state, operation):
        """
        完全應用狀態到應用程序 - 統一的狀態恢復接口

        Args:
            state: 要應用的狀態
            correction_state: 校正狀態
            operation: 操作信息
        """
        try:
            # 保存可能有效的可見項目
            visible_item = self.get_visible_item()
            self.logger.debug(f"開始應用狀態，可見項目: {visible_item}")

            # 獲取操作類型
            op_type = operation.get('type', '')
            self.logger.debug(f"處理操作類型: {op_type}")

            # 根據操作類型選擇不同的處理方式
            if op_type == 'split_srt':
                # 使用專門的方法處理拆分操作
                success = self._apply_split_operation(state, correction_state, operation)
                if not success:
                    self.logger.warning(f"應用拆分操作失敗")
                    return False
            elif op_type == 'combine_sentences':
                # 使用專門的方法處理合併操作
                success = self._apply_combine_operation(state, correction_state, operation)
                if not success:
                    self.logger.warning(f"應用合併操作失敗")
                    return False
            elif op_type == 'align_end_times':
                # 使用專門的方法處理時間調整操作
                success = self._apply_time_adjustment(state, correction_state, operation)
                if not success:
                    self.logger.warning(f"應用時間調整操作失敗")
                    return False
            else:
                # 一般操作：標準處理流程

                # 1. 清除當前狀態
                self.clear_current_state()

                # 2. 設置顯示模式
                old_mode = self.display_mode
                new_mode = state.get('display_mode', self.display_mode)
                if old_mode != new_mode:
                    self.logger.debug(f"顯示模式變更: {old_mode} -> {new_mode}")
                    self.display_mode = new_mode
                    self.refresh_treeview_structure()

                # 3. 保存要恢復的項目 ID 映射
                id_mapping = {}
                if 'item_id_mapping' in state:
                    id_mapping = state.get('item_id_mapping', {})

                # 4. 恢復樹狀視圖
                self._restore_tree_items(state, id_mapping)

                # 5. 恢復 SRT 數據
                self._restore_srt_data(state)

                # 6. 恢復使用 Word 文本的標記
                if 'use_word_text' in state:
                    self.restore_use_word_flags(state['use_word_text'], id_mapping)
                    self.logger.debug(f"已恢復 Word 文本標記，數量: {len(state['use_word_text'])}")

                # 7. 恢復校正狀態
                if correction_state and hasattr(self, 'correction_service'):
                    self.correction_service.deserialize_state(correction_state, id_mapping)
                    self.logger.debug("已恢復校正狀態")

                # 8. 更新音頻段落
                self._update_audio_segments()

            # 恢復視圖位置
            self._restore_view_position(visible_item, id_mapping, operation)

            # 觸發狀態應用完成回調
            if hasattr(self, 'state_manager'):
                self.state_manager.trigger_callback('on_state_applied')

            # 更新狀態欄
            op_desc = "恢復狀態"
            if operation and 'description' in operation:
                op_desc = operation['description']
            self.update_status(f"已{op_desc}")
            self.logger.debug(f"狀態應用完成: {op_desc}")

            # 強制更新界面
            self.master.update_idletasks()

            return True
        except Exception as e:
            self.logger.error(f"應用狀態時出錯: {e}", exc_info=True)
            show_error("錯誤", f"恢復狀態失敗: {str(e)}", self.master)
            return False

    def _restore_tree_items(self, state, id_mapping):
        """恢復樹狀視圖項目"""
        new_items = []  # 收集新的項目 ID
        if 'tree_items' in state:
            for item_data in state['tree_items']:
                values = item_data.get('values', [])
                position = item_data.get('position', 'end')
                tags = item_data.get('tags')
                original_id = item_data.get('original_id')  # 原始項目 ID

                # 插入項目
                new_id = self.insert_item('', position, values=tuple(values))
                new_items.append(new_id)

                # 保存 ID 映射
                if original_id:
                    id_mapping[original_id] = new_id

                # 恢復標籤
                if tags:
                    self.tree.item(new_id, tags=tags)

            self.logger.debug(f"已恢復樹狀視圖，項目數: {len(state['tree_items'])}")

    def _restore_srt_data(self, state):
        """恢復 SRT 數據"""
        if 'srt_data' in state and state['srt_data']:
            self.restore_srt_data(state['srt_data'])
            self.logger.debug(f"已恢復 SRT 數據，項目數: {len(state['srt_data'])}")
        else:
            # 如果沒有 SRT 數據，從樹狀視圖重建
            self.update_srt_data_from_treeview()
            self.logger.debug("從樹狀視圖重建 SRT 數據")

    def _update_audio_segments(self):
        """更新音頻段落"""
        if self.audio_imported and hasattr(self, 'audio_player'):
            self.audio_player.segment_audio(self.srt_data)
            self.logger.debug("已更新音頻段落")

    def on_state_change(self):
        """狀態變更事件處理"""
        # 添加保護標記
        if hasattr(self, '_handling_state_change') and self._handling_state_change:
            return

        try:
            self._handling_state_change = True
            # 更新撤銷/重做按鈕狀態
            self.update_undo_redo_buttons()
            self.update_status("狀態已更新")
        finally:
            self._handling_state_change = False

    def update_undo_redo_buttons(self):
        """更新撤銷/重做按鈕狀態"""
        # 如果您有撤銷/重做按鈕，可以在這裡更新它們的啟用/禁用狀態
        try:
            if hasattr(self, 'state_manager'):
                can_undo = self.state_manager.can_undo()
                can_redo = self.state_manager.can_redo()

                # 如果有撤銷/重做按鈕，更新它們的狀態
                if hasattr(self, 'undo_button'):
                    self.undo_button['state'] = 'normal' if can_undo else 'disabled'
                if hasattr(self, 'redo_button'):
                    self.redo_button['state'] = 'normal' if can_redo else 'disabled'
        except Exception as e:
            self.logger.error(f"更新撤銷/重做按鈕狀態時出錯: {e}")

    def on_undo_state(self, state, correction_state, operation):
        """撤銷狀態回調處理"""
        try:
            # 獲取操作類型
            op_type = operation.get('type', '')
            self.logger.debug(f"執行撤銷操作: {op_type} - {operation.get('description', '未知操作')}")

            # 根據操作類型分別處理
            if op_type == 'split_srt':
                self.restore_from_split_operation(operation)

            elif op_type == 'combine_sentences':
                # 使用保存的原始樹狀態還原
                if 'original_tree_state' in operation:
                    self.clear_current_treeview()
                    self.restore_tree_data(operation.get('original_tree_state', []))
                    self.update_srt_data_from_treeview()
                    # 更新音頻段落
                    if self.audio_imported and hasattr(self, 'audio_player'):
                        self.audio_player.segment_audio(self.srt_data)
            elif op_type == 'align_end_times':
                # 處理時間調整操作的撤銷
                if 'backup_values' in operation:
                    backup_values = operation.get('backup_values', {})
                    for item, values in backup_values.items():
                        if self.tree.exists(item):
                            self.tree.item(item, values=values)
                    self.update_srt_data_from_treeview()
                    # 更新音頻段落
                    if self.audio_imported and hasattr(self, 'audio_player'):
                        self.audio_player.segment_audio(self.srt_data)
            else:
                # 其他類型的操作使用一般方法處理
                self.apply_state(state, correction_state, operation)

            self.update_status(f"已撤銷：{operation.get('description', '未知操作')}")
            # 強制更新界面
            self.master.update_idletasks()
        except Exception as e:
            self.logger.error(f"撤銷狀態時出錯: {e}", exc_info=True)
            show_error("錯誤", f"撤銷操作失敗: {str(e)}", self.master)

    def on_redo_state(self, state, correction_state, operation):
        """
        重做狀態回調處理
        """
        try:
            self.logger.debug(f"執行重做操作: {operation.get('type', '')} - {operation.get('description', '未知操作')}")

            # 直接執行狀態恢復邏輯，而不是調用 apply_state
            # 這裡實現核心邏輯，與 apply_state 類似但不調用它
            self._apply_state_internal(state, correction_state, operation)

            self.update_status(f"已重做：{operation.get('description', '未知操作')}")

        except Exception as e:
            self.logger.error(f"重做狀態時出錯: {e}", exc_info=True)
            show_error("錯誤", f"重做操作失敗: {str(e)}", self.master)

    def restore_from_split_operation(self, operation):
        """從拆分操作恢復狀態 - 基於完整原始狀態的復原"""
        self.split_service.restore_from_split_operation(operation)

    def clear_current_treeview(self):
        """清除當前樹狀視圖 - 簡化版，僅清除樹狀視圖項目"""
        try:
            # 清除樹狀視圖項目
            self.tree_manager.clear_all()
            self.logger.debug("已清除當前樹狀視圖")
        except Exception as e:
            self.logger.error(f"清除樹狀視圖時出錯: {e}")

    def on_state_applied(self):
        """
        狀態應用完成回調
        """
        try:
            # 更新撤銷/重做按鈕狀態
            self.update_undo_redo_buttons()

            # 更新 SRT 數據
            self.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)

            self.logger.debug("狀態應用完成")
        except Exception as e:
            self.logger.error(f"處理狀態應用完成回調時出錯: {e}")

    def save_initial_state(self):
        """
        保存初始狀態
        """
        try:
            if hasattr(self, 'state_manager'):
                # 檢查是否有任何內容可保存
                if not self.tree_manager.get_all_items():
                    self.logger.debug("樹為空，跳過初始狀態保存")
                    return

                current_state = self.get_current_state()
                correction_state = self.correction_service.serialize_state() if hasattr(self, 'correction_service') else None

                # 診斷日誌
                self.logger.debug(f"保存初始狀態，樹項目數: {len(self.tree_manager.get_all_items())}")

                # 保存狀態
                self.save_operation_state(current_state, {
                    'type': 'initial',
                    'description': '初始狀態'
                }, correction_state)

                # 再次診斷
                self.logger.debug(f"初始狀態已保存，當前索引: {self.state_manager.current_state_index}, 狀態數: {len(self.state_manager.states)}")

                # 更新按鈕狀態
                self.update_undo_redo_buttons()
            else:
                self.logger.warning("無法保存初始狀態：狀態管理器未初始化")
        except Exception as e:
            self.logger.error(f"保存初始狀態時出錯: {e}", exc_info=True)

    def undo(self, event=None):
        """撤銷操作"""
        try:
            if hasattr(self, 'state_manager'):
                return self.state_manager.undo()
            else:
                self.logger.warning("無法撤銷：狀態管理器未初始化")
                return False
        except Exception as e:
            self.logger.error(f"撤銷操作時出錯: {e}", exc_info=True)
            show_error("錯誤", f"撤銷操作失敗: {str(e)}", self.master)
            return False

    def redo(self, event=None):
        """
        重做操作 - 使用 EnhancedStateManager 的重做功能
        """
        try:
            if hasattr(self, 'state_manager'):
                success = self.state_manager.redo()
                if success:
                    self.update_status("已重做操作")
                return success
            else:
                self.logger.warning("無法重做：狀態管理器未初始化")
                return False
        except Exception as e:
            self.logger.error(f"重做操作時出錯: {e}", exc_info=True)
            show_error("錯誤", f"重做操作失敗: {str(e)}", self.master)
            return False

    def redo_split_operation(self, state, operation):
        """處理拆分操作的重做"""
        try:
            # 獲取操作信息
            split_info = operation.get('split_result', [])
            srt_index = operation.get('srt_index')

            if not split_info or not srt_index:
                self.logger.warning("重做拆分操作失敗：缺少必要信息")
                return False

            # 清除當前狀態
            self.gui.clear_current_treeview()

            # 恢復拆分後的樹狀視圖
            if 'tree_items' in state.state:
                for item_data in state.state['tree_items']:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')
                    tags = item_data.get('tags')

                    # 插入項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

                    # 恢復使用 Word 文本的標記
                    if item_data.get('use_word', False):
                        self.gui.use_word_text[new_id] = True

            # 恢復 SRT 數據
            if 'srt_data' in state.state:
                self.gui.restore_srt_data(state.state['srt_data'])

            # 恢復校正狀態
            if state.correction_state and hasattr(self.gui, 'correction_service'):
                self.gui.correction_service.deserialize_state(state.correction_state)

            # 選中拆分後的第一個項目
            items = self.gui.tree.get_children()
            if items:
                first_position = operation.get('first_position', 0)
                if 0 <= first_position < len(items):
                    self.gui.tree.selection_set(items[first_position])
                    self.gui.tree.see(items[first_position])

            return True

        except Exception as e:
            self.logger.error(f"重做拆分操作時出錯: {e}", exc_info=True)
            return False

    def _redo_split_operation(self, state, operation):
        """重做拆分操作"""
        try:
            # 獲取操作信息
            split_result = operation.get('split_result', [])
            srt_index = operation.get('srt_index')

            if not split_result or not srt_index:
                self.logger.warning("無法重做拆分操作: 缺少必要信息")
                return False

            # 清空樹視圖並恢復 state 中的樹視圖狀態
            self.gui.clear_current_treeview()

            # 從狀態數據中還原完整樹視圖
            if 'tree_items' in state.state:
                # 保存項目 ID 映射
                id_mapping = {}

                for item_data in state.state['tree_items']:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')
                    tags = item_data.get('tags')
                    use_word = item_data.get('use_word', False)
                    original_id = item_data.get('original_id')

                    # 插入新項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))

                    # 保存 ID 映射
                    if original_id:
                        id_mapping[original_id] = new_id

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

                    # 恢復使用 Word 文本標記
                    if use_word:
                        self.gui.use_word_text[new_id] = True

            # 恢復 SRT 數據
            if 'srt_data' in state.state and state.state['srt_data']:
                self.gui.restore_srt_data(state.state['srt_data'])

            # 恢復校正狀態
            if state.correction_state and hasattr(self.gui, 'correction_service'):
                self.gui.correction_service.deserialize_state(state.correction_state, id_mapping)

            # 如果有目標項目，選中它
            target_item_id = operation.get('target_item_id')
            if target_item_id and target_item_id in id_mapping:
                mapped_id = id_mapping[target_item_id]
                if self.gui.tree.exists(mapped_id):
                    self.gui.tree.selection_set(mapped_id)
                    self.gui.tree.see(mapped_id)
            else:
                # 選中第一個拆分項目
                items = self.gui.tree.get_children()
                if items:
                    first_item = None
                    for item in items:
                        values = self.gui.tree.item(item, 'values')
                        index_pos = 1 if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT] else 0
                        if len(values) > index_pos and str(values[index_pos]) == str(srt_index):
                            first_item = item
                            break

                    if first_item:
                        self.gui.tree.selection_set(first_item)
                        self.gui.tree.see(first_item)

            # 如果有音頻，確保更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            return True

        except Exception as e:
            self.logger.error(f"重做拆分操作時出錯: {e}", exc_info=True)
            return False

    def _redo_combine_operation(self, state, operation):
        """重做合併操作"""
        try:
            # 清空樹視圖並恢復 state 中的樹視圖狀態
            self.gui.clear_current_treeview()

            # 恢復合併後的數據
            if 'tree_items' in state.state:
                # 保存項目 ID 映射
                id_mapping = {}

                for item_data in state.state['tree_items']:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')
                    tags = item_data.get('tags')
                    use_word = item_data.get('use_word', False)
                    original_id = item_data.get('original_id')

                    # 插入新項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))

                    # 保存 ID 映射
                    if original_id:
                        id_mapping[original_id] = new_id

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

                    # 恢復使用 Word 文本標記
                    if use_word:
                        self.gui.use_word_text[new_id] = True

            # 恢復 SRT 數據
            if 'srt_data' in state.state and state.state['srt_data']:
                self.gui.restore_srt_data(state.state['srt_data'])

            # 恢復校正狀態
            if state.correction_state and hasattr(self.gui, 'correction_service'):
                self.gui.correction_service.deserialize_state(state.correction_state, id_mapping)

            # 如果有合併後的項目 ID，選中它
            new_item = operation.get('new_item')
            if new_item and new_item in id_mapping:
                mapped_id = id_mapping[new_item]
                if self.gui.tree.exists(mapped_id):
                    self.gui.tree.selection_set(mapped_id)
                    self.gui.tree.see(mapped_id)

            # 如果有音頻，確保更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            return True

        except Exception as e:
            self.logger.error(f"重做合併操作時出錯: {e}", exc_info=True)
            return False

    # 在 AlignmentGUI 類中保留這個統一的接口
    def save_operation_state(self, operation_type, operation_description, additional_info=None):
        """
        統一保存操作狀態的方法 - 透過狀態管理器
        """
        if hasattr(self, '_saving_state') and self._saving_state:
            return

        try:
            self._saving_state = True
            # 獲取當前完整狀態
            current_state = self.get_current_state()

            # 獲取校正狀態
            correction_state = None
            if hasattr(self, 'correction_service'):
                correction_state = self.correction_service.serialize_state()

            # 構建操作信息
            operation_info = {
                'type': operation_type,
                'description': operation_description,
                'timestamp': time.time(),
                'display_mode': self.display_mode,
                'tree_items_count': len(self.tree_manager.get_all_items())
            }

            # 添加附加信息
            if additional_info:
                for key, value in additional_info.items():
                    if key not in operation_info:
                        operation_info[key] = value

            # 保存狀態
            self.save_operation_state(current_state, operation_info, correction_state)

            # 保存後再次診斷
            self.logger.debug(f"狀態已保存，當前狀態索引: {self.state_manager.current_index}, 總狀態數: {len(self.state_manager.states)}")

        finally:
            self._saving_state = False

    def _get_appropriate_display_mode(self):
        """根據已匯入的檔案類型確定適當的顯示模式"""
        if self.srt_imported and self.word_imported and self.audio_imported:
            return self.DISPLAY_MODE_ALL
        elif self.srt_imported and self.word_imported:
            return self.DISPLAY_MODE_SRT_WORD
        elif self.srt_imported and self.audio_imported:
            return self.DISPLAY_MODE_AUDIO_SRT
        elif self.srt_imported:
            return self.DISPLAY_MODE_SRT
        else:
            # 默認模式
            return self.DISPLAY_MODE_SRT

    def check_display_mode_consistency(self):
        """檢查顯示模式是否與實際狀態一致"""
        expected_mode = self._get_appropriate_display_mode()

        self.logger.debug(f"檢查顯示模式：當前={self.display_mode}, 預期={expected_mode}")

        if expected_mode and expected_mode != self.display_mode:
            self.logger.warning(f"顯示模式不一致: 當前={self.display_mode}, 預期={expected_mode}，正在修正...")

            # 使用統一的方法切換顯示模式
            self._apply_display_mode_change(self.display_mode, expected_mode)

    def refresh_treeview_structure(self) -> None:
        """
        根據當前的顯示模式重新配置 Treeview 結構
        """
        try:
            self.logger.info(f"開始刷新樹狀視圖結構，目標模式: {self.display_mode}")

            # 保存當前樹中的數據
            current_data = []

            for item in self.tree_manager.get_all_items():
                values = list(self.tree.item(item)['values'])
                tags = self.tree.item(item)['tags']
                use_word = self.use_word_text.get(item, False)

                # 獲取校正狀態
                correction_info = {}
                try:
                    # 根據不同顯示模式確定索引位置
                    if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                        idx = str(values[1]) if len(values) > 1 else ""
                    else:
                        idx = str(values[0]) if values else ""

                    if idx in self.correction_service.correction_states:
                        correction_info = {
                            'state': self.correction_service.correction_states[idx],
                            'original': self.correction_service.original_texts.get(idx, ""),
                            'corrected': self.correction_service.corrected_texts.get(idx, "")
                        }
                except Exception as e:
                    self.logger.error(f"獲取項目 {item} 的校正狀態時出錯: {e}")

                current_data.append({
                    'values': values,
                    'tags': tags,
                    'use_word': use_word,
                    'correction': correction_info if correction_info else None
                })

            # 清空樹狀視圖項目
            self.tree_manager.clear_all()

            # 更新列配置
            columns = self.columns[self.display_mode]
            self.tree["columns"] = columns
            self.tree['show'] = 'headings'

            # 配置每列
            for col in columns:
                config = self.column_config.COLUMNS.get(col, {
                    'width': 100,
                    'stretch': True if col in ['SRT Text', 'Word Text'] else False,
                    'anchor': 'w' if col in ['SRT Text', 'Word Text'] else 'center'
                })

                self.tree_manager.set_column_config(col,
                    width=config['width'],
                    stretch=config['stretch'],
                    anchor=config['anchor'])
                self.tree_manager.set_heading(col, text=col, anchor='center')

            # 恢復數據到樹狀視圖
            old_mode = "any"  # 使用通用模式檢測
            self.restore_tree_data(current_data, old_mode, self.display_mode)

            # 綁定窗口大小變化事件
            self.master.bind("<Configure>", self.on_window_resize)

            # 設置標籤樣式
            self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

            self.logger.info(f"樹狀視圖結構刷新完成，共恢復 {len(current_data)} 項數據")

        except Exception as e:
            self.logger.error(f"刷新 Treeview 結構時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新顯示結構失敗: {str(e)}", self.master)

    def on_window_resize(self, event=None) -> None:
        """
        處理窗口大小變化事件 - 簡化版，不調整列寬
        僅用於記錄窗口大小變化
        """
        # 僅在必要時啟用
        return

        # 以下代碼暫時禁用，直到解決顯示問題
        """
        # 僅處理主窗口大小變化
        if event and event.widget == self.master:
            try:
                # 獲取當前窗口尺寸
                window_width = self.master.winfo_width()
                window_height = self.master.winfo_height()

                # 記錄窗口大小變化
                self.logger.debug(f"窗口大小變化: {window_width}x{window_height}")

            except Exception as e:
                # 僅記錄錯誤
                self.logger.error(f"處理窗口大小變化時出錯: {e}")
        """

    def adjust_values_for_mode(self, values, source_mode, target_mode):
        """
        調整值列表以適應不同的顯示模式

        Args:
            values: 原始值列表
            source_mode: 原始顯示模式 ("any" 表示自動檢測)
            target_mode: 目標顯示模式

        Returns:
            調整後的值列表
        """
        try:
            # 確保 values 是列表
            values = list(values)

            # 如果源模式和目標模式相同，直接返回原始值
            if source_mode == target_mode:
                return values

            # 如果 source_mode 是 "any"，嘗試自動檢測模式
            if source_mode == "any":
                # 根據值的長度嘗試判斷源模式
                length = len(values)
                if length == 5:  # [Index, Start, End, SRT Text, V/X]
                    source_mode = self.DISPLAY_MODE_SRT
                elif length == 6:  # [V.O, Index, Start, End, SRT Text, V/X]
                    source_mode = self.DISPLAY_MODE_AUDIO_SRT
                elif length == 7:  # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                    source_mode = self.DISPLAY_MODE_SRT_WORD
                elif length == 8:  # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                    source_mode = self.DISPLAY_MODE_ALL
                else:
                    # 無法檢測，嘗試通用方法
                    self.logger.warning(f"無法根據值的長度 ({length}) 檢測源模式，使用通用處理")
                    return self._apply_generic_adjustment(values, target_mode)

            # 使用正確的列數填充值列表
            expected_columns = len(self.columns[target_mode])

            # 提取關鍵值用於重建
            extracted = self._extract_key_values(values, source_mode)

            # 根據目標模式重新構建值列表
            rebuilt_values = self._build_values_for_mode(extracted, target_mode)

            # 確保長度正確
            if len(rebuilt_values) > expected_columns:
                rebuilt_values = rebuilt_values[:expected_columns]
            elif len(rebuilt_values) < expected_columns:
                rebuilt_values = list(rebuilt_values) + [''] * (expected_columns - len(rebuilt_values))

            return rebuilt_values

        except Exception as e:
            self.logger.error(f"調整值列表以適應不同的顯示模式時出錯: {e}")
            # 返回原始值，避免錯誤傳播
            return values


    def _extract_key_values(self, values, mode):
        """從給定模式和值中提取關鍵數據"""
        result = {
            'index': '',
            'start': '',
            'end': '',
            'srt_text': '',
            'word_text': '',
            'match': '',
            'vx': '',
            'vo': self.PLAY_ICON  # 預設的播放圖標
        }

        try:
            if mode == self.DISPLAY_MODE_SRT:
                # [Index, Start, End, SRT Text, V/X]
                if len(values) >= 1: result['index'] = values[0]
                if len(values) >= 2: result['start'] = values[1]
                if len(values) >= 3: result['end'] = values[2]
                if len(values) >= 4: result['srt_text'] = values[3]
                if len(values) >= 5: result['vx'] = values[4]

            elif mode == self.DISPLAY_MODE_SRT_WORD:
                # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                if len(values) >= 1: result['index'] = values[0]
                if len(values) >= 2: result['start'] = values[1]
                if len(values) >= 3: result['end'] = values[2]
                if len(values) >= 4: result['srt_text'] = values[3]
                if len(values) >= 5: result['word_text'] = values[4]
                if len(values) >= 6: result['match'] = values[5]
                if len(values) >= 7: result['vx'] = values[6]

            elif mode == self.DISPLAY_MODE_AUDIO_SRT:
                # [V.O, Index, Start, End, SRT Text, V/X]
                if len(values) >= 1: result['vo'] = values[0]
                if len(values) >= 2: result['index'] = values[1]
                if len(values) >= 3: result['start'] = values[2]
                if len(values) >= 4: result['end'] = values[3]
                if len(values) >= 5: result['srt_text'] = values[4]
                if len(values) >= 6: result['vx'] = values[5]

            elif mode == self.DISPLAY_MODE_ALL:
                # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                if len(values) >= 1: result['vo'] = values[0]
                if len(values) >= 2: result['index'] = values[1]
                if len(values) >= 3: result['start'] = values[2]
                if len(values) >= 4: result['end'] = values[3]
                if len(values) >= 5: result['srt_text'] = values[4]
                if len(values) >= 6: result['word_text'] = values[5]
                if len(values) >= 7: result['match'] = values[6]
                if len(values) >= 8: result['vx'] = values[7]
        except Exception as e:
            self.logger.error(f"提取關鍵值時出錯: {e}")

        return result

    def _build_values_for_mode(self, extracted, mode):
        """根據提取的關鍵值和目標模式構建值列表"""
        if mode == self.DISPLAY_MODE_SRT:
            # [Index, Start, End, SRT Text, V/X]
            return [
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['vx']
            ]
        elif mode == self.DISPLAY_MODE_SRT_WORD:
            # [Index, Start, End, SRT Text, Word Text, Match, V/X]
            return [
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['word_text'],
                extracted['match'],
                extracted['vx']
            ]
        elif mode == self.DISPLAY_MODE_AUDIO_SRT:
            # [V.O, Index, Start, End, SRT Text, V/X]
            return [
                extracted['vo'],
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['vx']
            ]
        elif mode == self.DISPLAY_MODE_ALL:
            # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
            return [
                extracted['vo'],
                extracted['index'],
                extracted['start'],
                extracted['end'],
                extracted['srt_text'],
                extracted['word_text'],
                extracted['match'],
                extracted['vx']
            ]
        else:
            # 不應該發生，返回空列表
            self.logger.error(f"未知的顯示模式: {mode}")
            return []

    def _apply_generic_adjustment(self, values, target_mode):
        """通用的值調整方法，用於無法確定源模式的情況"""
        # 首先嘗試提取所有可能值
        extracted = {}

        # 根據值的長度和位置嘗試提取
        length = len(values)

        # 提取索引 (通常在第1-2項)
        if length >= 2:
            extracted['index'] = values[0] if not values[0] == self.PLAY_ICON else values[1]
        elif length >= 1:
            extracted['index'] = values[0]
        else:
            extracted['index'] = ""

        # 提取時間 (通常在第2-4項)
        if length >= 4:
            start_idx = 1 if values[0] == self.PLAY_ICON else 0
            extracted['start'] = values[start_idx + 1]
            extracted['end'] = values[start_idx + 2]
        elif length >= 3:
            extracted['start'] = values[1]
            extracted['end'] = values[2]
        else:
            extracted['start'] = ""
            extracted['end'] = ""

        # 提取文本 (通常在索引和時間之後)
        if length >= 5:
            text_idx = 4 if values[0] == self.PLAY_ICON else 3
            extracted['srt_text'] = values[text_idx] if text_idx < length else ""
        elif length >= 4:
            extracted['srt_text'] = values[3]
        else:
            extracted['srt_text'] = ""

        # 檢查是否有Word文本
        if target_mode in [self.DISPLAY_MODE_SRT_WORD, self.DISPLAY_MODE_ALL]:
            extracted['word_text'] = ""
            extracted['match'] = ""

        # 提取校正標記
        extracted['vx'] = values[-1] if values and (values[-1] in ['✅', '❌', '']) else ""

        # 設置播放圖標
        extracted['vo'] = self.PLAY_ICON

        # 根據目標模式構建結果
        result = []

        if target_mode == self.DISPLAY_MODE_SRT:
            result = [extracted.get('index', ''), extracted.get('start', ''),
                    extracted.get('end', ''), extracted.get('srt_text', ''),
                    extracted.get('vx', '')]
        elif target_mode == self.DISPLAY_MODE_SRT_WORD:
            result = [extracted.get('index', ''), extracted.get('start', ''),
                    extracted.get('end', ''), extracted.get('srt_text', ''),
                    extracted.get('word_text', ''), extracted.get('match', ''),
                    extracted.get('vx', '')]
        elif target_mode == self.DISPLAY_MODE_AUDIO_SRT:
            result = [extracted.get('vo', self.PLAY_ICON), extracted.get('index', ''),
                    extracted.get('start', ''), extracted.get('end', ''),
                    extracted.get('srt_text', ''), extracted.get('vx', '')]
        elif target_mode == self.DISPLAY_MODE_ALL:
            result = [extracted.get('vo', self.PLAY_ICON), extracted.get('index', ''),
                    extracted.get('start', ''), extracted.get('end', ''),
                    extracted.get('srt_text', ''), extracted.get('word_text', ''),
                    extracted.get('match', ''), extracted.get('vx', '')]

        # 確保結果長度正確
        expected_len = len(self.columns[target_mode])
        if len(result) > expected_len:
            result = result[:expected_len]
        elif len(result) < expected_len:
            result = result + [''] * (expected_len - len(result))

        return result

    def clear_current_data(self) -> None:
        """統一的數據清理函數 - 清除所有數據和狀態"""
        try:
            self.logger.debug("開始清除所有數據和狀態")

            # 1. 清除狀態管理器的狀態
            if hasattr(self, 'state_manager'):
                self.state_manager.clear_states()

            # 2. 清除樹狀視圖的所有項目
            if hasattr(self, 'tree'):
                self.tree_manager.clear_all()

            # 3. 清除校正狀態
            if hasattr(self, 'correction_service'):
                self.correction_service.clear_correction_states()

            # 4. 清除使用 Word 文本的標記
            if hasattr(self, 'use_word_text'):
                self.use_word_text.clear()

            # 5. 清除編輯文本信息
            if hasattr(self, 'edited_text_info'):
                self.edited_text_info.clear()

            # 6. 清除 Word 比對結果
            if hasattr(self, 'word_comparison_results'):
                self.word_comparison_results = {}

            # 7. 清除檔案狀態 - 使用 FileManager 進行清理
            if hasattr(self, 'file_manager'):
                self.file_manager.clear_file_status()

            # 8. 同步本地狀態變數
            self.srt_imported = False
            self.audio_imported = False
            self.word_imported = False
            self.srt_file_path = None
            self.audio_file_path = None
            self.word_file_path = None
            self.srt_data = []

            # 9. 清理音頻資源
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()

            # 10. 重置顯示模式
            self.display_mode = self.DISPLAY_MODE_SRT

            # 11. 確保介面一致
            self.refresh_treeview_structure()
            self.update_file_info()
            self.update_status("已清除所有數據")

            self.logger.debug("所有數據清理完成")

        except Exception as e:
            self.logger.error(f"清除數據時出錯: {e}")
            show_error("錯誤", f"清除數據失敗: {str(e)}", self.master)

    def clear_current_state(self):
        """清除當前狀態 - 樹狀視圖和相關狀態"""
        try:
            # 在清除前記錄當前狀態
            tree_items_count = len(self.tree_manager.get_all_items() if hasattr(self, 'tree') else [])
            self.logger.debug(f"開始清除當前狀態，當前樹項目數: {tree_items_count}")

            # 清空樹狀視圖
            if hasattr(self, 'tree'):
                self.tree_manager.clear_all()

            # 清空相關狀態
            if hasattr(self, 'use_word_text'):
                self.use_word_text.clear()

            # 清空校正狀態
            if hasattr(self, 'correction_service'):
                self.correction_service.clear_correction_states()

            self.logger.debug("已清除當前狀態")
        except Exception as e:
            self.logger.error(f"清除當前狀態時出錯: {e}", exc_info=True)

    def restore_srt_data(self, serialized_data):
        """
        從序列化數據恢復 SRT 數據

        Args:
            serialized_data: 序列化的 SRT 數據
        """
        try:
            if not serialized_data:
                self.logger.warning("無法恢復 SRT 數據：序列化數據為空")
                return

            if not isinstance(serialized_data, list):
                self.logger.error("無法恢復 SRT 數據：非法的數據格式")
                return

            # 進一步檢查數據結構
            for item in serialized_data:
                required_keys = ['index', 'start', 'end', 'text']
                if not all(key in item for key in required_keys):
                    self.logger.warning(f"數據項缺少必要欄位: {item}")
                    continue

            new_srt = pysrt.SubRipFile()
            for item in serialized_data:
                try:
                    sub = pysrt.SubRipItem(
                        index=item['index'],
                        start=parse_time(item['start']),
                        end=parse_time(item['end']),
                        text=item['text']
                    )
                    new_srt.append(sub)
                except Exception as e:
                    self.logger.error(f"解析 SRT 項目時出錯: {e}")
                    continue

            self.srt_data = new_srt
            self.logger.debug(f"已從序列化數據恢復 SRT 數據，項目數: {len(new_srt)}")
        except Exception as e:
            self.logger.error(f"恢復 SRT 數據時出錯: {e}")


    def restore_use_word_flags(self, use_word_flags, id_mapping=None):
        """
        恢復使用 Word 文本的標記，支持 ID 映射

        Args:
            use_word_flags: 使用 Word 文本的標記
            id_mapping: ID 映射表 {原始ID: 新ID}
        """
        try:
            if not use_word_flags:
                return

            # 首先，建立一個從索引到樹項目 ID 的映射
            index_to_item = {}
            for item in self.tree_manager.get_all_items():
                values = self.tree_manager.get_item_values(item)
                index_position = 1 if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 0
                if len(values) > index_position:
                    index = str(values[index_position])
                    index_to_item[index] = item

            # 然後，根據保存的標記設置 use_word_text
            for index, use_word in use_word_flags.items():
                if index in index_to_item:
                    item_id = index_to_item[index]

                    # 如果有 ID 映射，使用映射後的 ID
                    if id_mapping and item_id in id_mapping:
                        item_id = id_mapping[item_id]

                    if self.tree.exists(item_id):  # 確保項目存在
                        if use_word:
                            self.use_word_text[item_id] = True

                            # 確保標籤中有 use_word_text
                            current_tags = list(self.tree.item(item_id, "tags") or ())
                            if "use_word_text" not in current_tags:
                                current_tags.append("use_word_text")
                                self.tree.item(item_id, tags=tuple(current_tags))

            self.logger.debug(f"已恢復 {len(use_word_flags)} 個 Word 文本標記")
        except Exception as e:
            self.logger.error(f"恢復使用 Word 文本標記時出錯: {e}")

    def get_visible_item(self):
        """
        獲取當前可見的項目
        :return: 當前可見項目的 ID
        """
        try:
            current_selection = self.tree_manager.get_selected_items()
            if current_selection:
                return current_selection[0]

            # 如果沒有選中項，獲取頂部項目
            visible_items = self.tree.identify_row(10)
            if visible_items:
                return visible_items

            # 如果沒有可見項目，返回第一個項目
            all_items = self.tree_manager.get_all_items()
            if all_items:
                return all_items[0]
        except Exception as e:
            self.logger.error(f"獲取可見項目時出錯: {e}")

        return None



    def _create_restored_values(self, text, start, end, srt_index):
        """
        為拆分還原創建值列表
        """
        # 檢查文本是否需要校正
        needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)
        correction_icon = '✅' if needs_correction else ''

        # 根據顯示模式準備值
        if self.display_mode == self.DISPLAY_MODE_ALL:
            values = [
                self.PLAY_ICON,
                str(srt_index),
                start,
                end,
                text,
                "",  # Word文本
                "",  # Match
                correction_icon
            ]
        elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
            values = [
                str(srt_index),
                start,
                end,
                text,
                "",  # Word文本
                "",  # Match
                correction_icon
            ]
        elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
            values = [
                self.PLAY_ICON,
                str(srt_index),
                start,
                end,
                text,
                correction_icon
            ]
        else:  # SRT模式
            values = [
                str(srt_index),
                start,
                end,
                text,
                correction_icon
            ]

        # 如果需要校正，設置校正狀態
        if needs_correction:
            self.correction_service.set_correction_state(
                str(srt_index),
                original_text,
                corrected_text,
                'correct'  # 默認為已校正狀態
            )

        return values



    def show_floating_correction_icon(self, event):
        """顯示跟隨游標的校正圖標，但只在選中的文本項目上"""
        try:
            # 獲取游標所在位置的區域和欄位
            region = self.tree.identify("region", event.x, event.y)
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)

            # 如果游標移到新的項目或列，且之前有固定的圖標，則隱藏它
            if hasattr(self, 'current_hovering_item') and hasattr(self, 'current_hovering_column'):
                if (item != self.current_hovering_item or
                    (column and int(column[1:]) - 1 != self.get_column_index(self.current_hovering_column))):
                    if hasattr(self, 'floating_icon'):
                        self.floating_icon.place_forget()
                        self.floating_icon_fixed = False

            # 如果圖標已固定，不再移動
            if hasattr(self, 'floating_icon_fixed') and self.floating_icon_fixed:
                return

            # 檢查是否為選中的項目
            is_selected = item in self.tree_manager.get_selected_items()

            # 只有在文本欄位上且是被選中的項目才顯示圖標
            is_text_column = False
            if region == "cell" and column and item and is_selected:
                column_idx = int(column[1:]) - 1
                if column_idx >= 0 and column_idx < len(self.tree["columns"]):
                    column_name = self.tree["columns"][column_idx]
                    if column_name in ["SRT Text", "Word Text"]:
                        is_text_column = True

            # 如果不在文本欄位上或不是被選中的項目，隱藏圖標
            if not is_text_column or not is_selected:
                if hasattr(self, 'floating_icon') and not self.floating_icon_fixed:
                    self.floating_icon.place_forget()
                return

            # 獲取文本內容
            values = self.tree.item(item, "values")
            if not values or len(values) <= column_idx:
                return

            selected_text = values[column_idx]
            if not selected_text:
                return

            # 保存相關信息
            self.current_hovering_text = selected_text
            self.current_hovering_item = item
            self.current_hovering_column = column_name

            # 創建或更新浮動圖標
            if not hasattr(self, 'floating_icon'):
                # 創建一個表示"添加"的圖標，使用統一的樣式
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
                # 初始化圖標固定狀態
                self.floating_icon_fixed = False
                # 添加點擊事件
                self.floating_icon.bind("<Button-1>", self.on_icon_click)

            # 更新圖標位置跟隨游標
            self.floating_icon.place(x=event.x + 10, y=event.y - 10)

        except Exception as e:
            self.logger.error(f"顯示浮動校正圖標時出錯: {e}", exc_info=True)

    def get_column_index(self, column_name):
        """獲取列名對應的索引"""
        for i, col in enumerate(self.tree["columns"]):
            if col == column_name:
                return i
        return -1

    def apply_new_correction(self, error: str, correction: str) -> None:
        """
        應用新添加的校正規則並更新界面

        Args:
            error: 錯誤字
            correction: 校正字
        """
        if not hasattr(self, 'correction_service'):
            return

        # 應用新的校正規則
        updated_count = self.correction_service.apply_new_correction(error, correction)

        # 更新界面顯示
        self.update_correction_display()

        # 更新 SRT 數據
        self.update_srt_data_from_treeview()

        # 如果有音頻，更新音頻段落
        if self.audio_imported and hasattr(self, 'audio_player'):
            self.audio_player.segment_audio(self.srt_data)

        # 更新狀態欄
        self.update_status(f"已添加新校正規則並更新 {updated_count} 個項目")

    def show_add_correction_dialog(self, text):
        """顯示添加校正對話框"""
        try:
            dialog = QuickCorrectionDialog(self.master, text, self.current_project_path)
            result = dialog.run()

            if result:
                error, correction = result

                # 立即檢查所有項目並應用新的校正規則
                self.apply_correction_to_all_items(error, correction)

            # 重置圖標狀態，使其能夠再次跟隨游標
            self.reset_floating_icon_state()

        except Exception as e:
            self.logger.error(f"顯示添加校正對話框時出錯: {e}", exc_info=True)
            # 確保即使發生錯誤也重置圖標狀態
            self.reset_floating_icon_state()

    def apply_correction_to_all_items(self, error, correction):
        """
        對所有項目應用特定的校正規則

        Args:
            error: 錯誤字
            correction: 校正字
        """
        try:
            if not hasattr(self, 'tree') or not self.tree:
                self.logger.warning("樹狀視圖不可用，無法應用校正")
                return

            # 獲取文本位置索引
            text_index = self.get_text_position_in_values()
            if text_index is None:
                self.logger.warning("無法獲取文本位置索引")
                return

            # 遍歷所有樹項目
            updated_items = []
            for item in self.tree_manager.get_all_items():
                values = list(self.tree.item(item, "values"))

                # 確保索引有效
                if len(values) <= text_index:
                    continue

                # 獲取文本
                text = values[text_index]

                # 檢查文本是否含有錯誤字
                if error in text:
                    # 獲取當前模式下的索引位置
                    index_pos = 1 if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 0
                    item_index = str(values[index_pos]) if len(values) > index_pos else ""

                    # 應用校正
                    corrected_text = text.replace(error, correction)

                    # 更新顯示文本
                    values[text_index] = corrected_text

                    # 設置校正圖標
                    values[-1] = '✅'

                    # 更新樹項目
                    self.tree.item(item, values=tuple(values))

                    # 設置校正狀態
                    if hasattr(self, 'correction_service') and item_index:
                        self.correction_service.set_correction_state(
                            item_index,
                            text,  # 原始文本
                            corrected_text,  # 校正後文本
                            'correct'  # 已校正狀態
                        )

                    updated_items.append(item)

            # 如果有更新項目，需要同步更新其他資料
            if updated_items:
                # 更新 SRT 數據
                self.update_srt_data_from_treeview()

                # 更新音頻段落
                if self.audio_imported and hasattr(self, 'audio_player'):
                    self.audio_player.segment_audio(self.srt_data)

                # 更新狀態欄
                self.update_status(f"已添加校正規則 '{error}→{correction}' 並更新 {len(updated_items)} 個項目")

                # 保存操作狀態
                if hasattr(self, 'state_manager'):
                    current_state = self.get_current_state()
                    current_correction = self.correction_service.serialize_state()

                    self.save_operation_state(current_state, {
                        'type': 'add_and_apply_correction',
                        'description': f"添加並應用校正規則：{error}→{correction}",
                        'error': error,
                        'correction': correction,
                        'updated_items_count': len(updated_items)
                    }, current_correction)

            else:
                self.update_status(f"已添加校正規則 '{error}→{correction}'，但沒有找到需要更新的項目")

        except Exception as e:
            self.logger.error(f"應用校正規則到所有項目時出錯: {e}", exc_info=True)
            self.update_status("應用校正規則失敗")

    def on_mouse_leave_tree(self, event):
        """當鼠標離開樹狀視圖時的處理"""
        # 如果圖標未固定，則隱藏
        if hasattr(self, 'floating_icon') and not (hasattr(self, 'floating_icon_fixed') and self.floating_icon_fixed):
            self.floating_icon.place_forget()

    def update_correction_display(self):
        """更新校正顯示，並立即應用校正"""
        try:
            # 檢查所需組件是否可用
            if not hasattr(self, 'tree') or not hasattr(self, 'correction_service'):
                self.logger.warning("無法更新校正狀態顯示：所需組件不可用")
                return

            # 直接調用 correction_service 的方法
            self.correction_service.update_display_status(self.tree, self.display_mode)

            # 更新 SRT 數據以反映變化
            self.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)

            # 更新狀態欄
            self.update_status("已應用最新校正規則")

        except Exception as e:
            self.logger.error(f"更新校正狀態顯示時出錯: {e}", exc_info=True)