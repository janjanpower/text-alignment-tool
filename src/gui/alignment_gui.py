"""文本對齊工具主界面模組"""

import csv
import logging
import os
import sys
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Any, Tuple

import pysrt
from audio.audio_player import AudioPlayer
from gui.base_window import BaseWindow
from gui.components.columns import ColumnConfig
from gui.custom_messagebox import (
    show_info,
    show_warning,
    show_error,
    ask_question
)
from gui.text_edit_dialog import TextEditDialog
from services.config_manager import ConfigManager
from services.word_processor import WordProcessor
from services.file_manager import FileManager
from services.correction_service import CorrectionService
from services.enhanced_state_manager import EnhancedStateManager
from utils.text_utils import simplify_to_traditional
from utils.time_utils import parse_time


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
            height=420,
            master=master
        )

        # 初始化變數
        self.initialize_variables()

        # 設置日誌
        self.setup_logging()

        # 創建界面元素
        self.create_gui_elements()

        # 初始化校正服務
        self.correction_service = CorrectionService()

        # 初始化增強狀態管理器
        self.state_manager = EnhancedStateManager()
        self.state_manager.set_alignment_gui(self)

        # 設置狀態管理器的回調函數
        self.setup_state_manager_callbacks()

        # 初始化檔案管理器
        self.initialize_file_manager()

        # 初始化音頻播放器
        self.initialize_audio_player()

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

        # 添加時間調整滑桿相關變量
        self.time_slider = None  # 滑桿控件
        self.slider_active = False  # 滑桿是否激活
        self.slider_target = None  # 滑桿調整的目標項目和欄位
        self.slider_start_value = 0  # 滑桿開始值

    def setup_state_manager_callbacks(self) -> None:
        """設置狀態管理器的回調函數"""
        if not hasattr(self, 'state_manager'):
            return

        self.state_manager.set_callback('on_state_change', lambda: self.update_status("狀態已改變"))
        self.state_manager.set_callback('on_undo', lambda: self.update_status("已撤銷"))
        self.state_manager.set_callback('on_redo', lambda: self.update_status("已重做"))

        # 設置 alignment_gui 參考，確保狀態管理器可以訪問 UI
        self.state_manager.alignment_gui = self

    def rebuild_ui_from_state(self, state, correction_state=None):
        """從保存的狀態重建 UI"""
        try:
            # 先清空當前狀態
            for item in self.tree.get_children():
                self.tree.delete(item)

            self.use_word_text.clear()
            self.correction_service.clear_correction_states()

            # 按順序重建項目
            for item_data in state:
                values = item_data.get('values')
                position = item_data.get('position', 'end')

                # 插入新項目
                new_id = self.insert_item('', position, values=tuple(values))

                # 恢復標籤
                tags = item_data.get('tags')
                if tags:
                    self.tree.item(new_id, tags=tags)

                # 恢復 use_word_text 狀態
                if item_data.get('use_word_text', False):
                    self.use_word_text[new_id] = True

            # 恢復校正狀態
            if correction_state:
                self.correction_service.deserialize_state(correction_state)

            # 更新 SRT
            self.update_srt_data_from_treeview()

            # 更新音頻
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)

            # 更新校正狀態顯示
            self.update_correction_status_display()

            return True
        except Exception as e:
            self.logger.error(f"重建 UI 時出錯: {e}", exc_info=True)
            return False

    def initialize_file_manager(self) -> None:
        """初始化檔案管理器"""
        self.logger.debug("開始初始化 FileManager")

        self.file_manager = FileManager(self.master)

        # 設置回調函數
        callbacks = {
            'on_srt_loaded': self._on_srt_loaded,
            'on_audio_loaded': self._on_audio_loaded,
            'on_word_loaded': self._on_word_loaded,
            'on_file_info_updated': self.update_file_info,
            'on_status_updated': self.update_status,
            'get_corrections': self.load_corrections,
            'get_srt_data': self._get_current_srt_data,  # 添加這個回調
            'get_tree_data': lambda: self.tree.get_children(),
            'show_info': lambda title, msg: show_info(title, msg, self.master),
            'show_warning': lambda title, msg: show_warning(title, msg, self.master),
            'show_error': lambda title, msg: show_error(title, msg, self.master), # 添加這個回調
            'ask_question': lambda title, msg: ask_question(title, msg, self.master)
        }

        # 設置所有回調
        for name, callback in callbacks.items():
            self.file_manager.set_callback(name, callback)

        # 同步初始檔案狀態 - 這是關鍵步驟
        self.file_manager.srt_imported = self.srt_imported
        self.file_manager.audio_imported = self.audio_imported
        self.file_manager.word_imported = self.word_imported
        self.file_manager.srt_file_path = self.srt_file_path
        self.file_manager.audio_file_path = self.audio_file_path
        self.file_manager.word_file_path = self.word_file_path
        self.file_manager.current_project_path = self.current_project_path
        self.file_manager.database_file = self.database_file

        self.logger.debug("FileManager 初始化完成")

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
            items_count = len(self.tree.get_children())
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
                self.state_manager.save_state(self.get_current_state(), {
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

            # 確保音頻播放器已初始化
            if not hasattr(self, 'audio_player'):
                self.initialize_audio_player()

            # 直接在這裡載入音頻，而不是依賴於回調
            if self.audio_player:
                # 確保真正加載了音頻
                audio_loaded = self.audio_player.load_audio(file_path)
                if not audio_loaded:
                    self.logger.error(f"音頻加載失敗: {file_path}")
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

        except Exception as e:
            self.logger.error(f"處理音頻載入回調時出錯: {e}", exc_info=True)
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

    def _get_current_srt_data(self) -> pysrt.SubRipFile:
        """獲取當前 SRT 數據"""
        # 創建新的 SRT 文件
        new_srt = pysrt.SubRipFile()

        # 載入校正資料庫
        corrections = self.load_corrections()

        # 遍歷所有項目
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']

            # 檢查是否使用 Word 文本
            use_word = self.use_word_text.get(item, False)

            # 根據顯示模式解析值
            if self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                index = int(values[1])
                start = values[2]
                end = values[3]
                text = values[4]  # SRT 文本
                # 音頻 SRT 模式下沒有 Word 文本
                word_text = None
                # 檢查校正狀態 - V/X 列
                correction_state = values[5] if len(values) > 5 else ""
            elif self.display_mode in [self.DISPLAY_MODE_SRT_WORD, self.DISPLAY_MODE_ALL]:
                # 對於包含 Word 的模式
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    index = int(values[1])
                    start = values[2]
                    end = values[3]
                    srt_text = values[4]
                    word_text = values[5]
                    # 檢查校正狀態 - V/X 列
                    correction_state = values[7] if len(values) > 7 else ""
                else:  # SRT_WORD 模式
                    index = int(values[0])
                    start = values[1]
                    end = values[2]
                    srt_text = values[3]
                    word_text = values[4]
                    # 檢查校正狀態 - V/X 列
                    correction_state = values[6] if len(values) > 6 else ""

                # 根據標記決定使用哪個文本，不受 mismatch 標記的影響
                if use_word and word_text:
                    text = word_text  # 使用 Word 文本
                    self.logger.debug(f"項目 {index} 使用 Word 文本: {word_text}")
                else:
                    text = srt_text  # 使用 SRT 文本
            else:  # SRT 模式
                index = int(values[0])
                start = values[1]
                end = values[2]
                text = values[3]
                word_text = None
                # 檢查校正狀態 - V/X 列
                correction_state = values[4] if len(values) > 4 else ""

            # 解析時間
            start_time = parse_time(start)
            end_time = parse_time(end)

            # 根據校正狀態決定是否應用校正
            final_text = text
            if correction_state == "✅":  # 只在有勾選的情況下應用校正
                final_text = self.correct_text(text, corrections)

            # 創建字幕項
            sub = pysrt.SubRipItem(
                index=index,
                start=start_time,
                end=end_time,
                text=final_text
            )
            new_srt.append(sub)

        return new_srt

    def _update_tree_data(self, srt_data, corrections) -> None:
        """更新樹視圖數據"""
        self.logger.debug(f"開始更新樹視圖，SRT 項目數：{len(srt_data)}")

        # 清空樹視圖
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.logger.debug("樹視圖已清空，開始處理 SRT 條目")

        # 更新數據
        self.process_srt_entries(srt_data, corrections)

        # 檢查是否成功更新
        items_count = len(self.tree.get_children())
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
            if self.tree.get_children():
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

            # 創建新的應用程式實例並啟動專案管理器
            root = tk.Tk()
            from .project_manager import ProjectManager
            project_manager = ProjectManager(root)
            project_manager.master.mainloop()

        self.file_manager.switch_project(confirm_switch, do_switch)


    def show_time_slider(self, event, item, column, column_name):
        """顯示時間調整滑桿"""
        # 獲取單元格的位置和大小
        bbox = self.tree.bbox(item, column)
        if not bbox:
            return

        x, y, width, height = bbox

        # 獲取當前值和相關項目
        values = self.tree.item(item, "values")

        # 獲取樹狀視圖中的所有項目
        all_items = self.tree.get_children()
        item_index = all_items.index(item)

        # 根據不同模式確定索引、開始時間和結束時間的位置
        if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
            index_pos = 1
            start_pos = 2
            end_pos = 3
        else:  # SRT 或 SRT_WORD 模式
            index_pos = 0
            start_pos = 1
            end_pos = 2

        # 創建滑桿控件
        self.create_time_slider(
            x, y, width, height,
            item, column_name,
            values, item_index, all_items,
            index_pos, start_pos, end_pos
        )

    def create_time_slider(self, x, y, width, height, item, column_name, values,
                        item_index, all_items, index_pos, start_pos, end_pos):
        """創建時間調整滑桿"""
        # 創建滑桿框架
        slider_frame = tk.Frame(self.tree, bg="lightgray", bd=1, relief="raised")
        slider_frame.place(x=x + width, y=y, width=150, height=height)

        # 獲取當前時間值
        current_time_str = values[start_pos if column_name == "Start" else end_pos]
        current_time = parse_time(current_time_str)

        # 計算滑桿範圍
        # 對於 Start 列，最小值是 0，最大值是當前 End 時間
        # 對於 End 列，最小值是當前 Start 時間，最大值可以適當增加
        if column_name == "Start":
            min_value = 0
            max_value = self.time_to_seconds(parse_time(values[end_pos])) * 1000

            # 如果有上一行，則最小值是上一行的結束時間
            if item_index > 0:
                prev_item = all_items[item_index - 1]
                prev_values = self.tree.item(prev_item, "values")
                prev_end_time = parse_time(prev_values[end_pos])
                min_value = self.time_to_milliseconds(prev_end_time)
        else:  # End 欄位
            min_value = self.time_to_milliseconds(parse_time(values[start_pos]))
            max_value = min_value + 10000  # 增加10秒

            # 如果有下一行，則最大值是下一行的開始時間
            if item_index < len(all_items) - 1:
                next_item = all_items[item_index + 1]
                next_values = self.tree.item(next_item, "values")
                next_start_time = parse_time(next_values[start_pos])
                max_value = self.time_to_milliseconds(next_start_time)

        # 當前值
        current_value = self.time_to_milliseconds(current_time)

        # 創建滑桿
        self.slider_active = True
        self.slider_target = {
            "item": item,
            "column": column_name,
            "index": values[index_pos],
            "item_index": item_index,
            "all_items": all_items,
            "index_pos": index_pos,
            "start_pos": start_pos,
            "end_pos": end_pos
        }
        self.slider_start_value = current_value

        # 創建滑桿和確認按鈕
        self.time_slider = ttk.Scale(
            slider_frame,
            from_=min_value,
            to=max_value,
            orient=tk.HORIZONTAL,
            value=current_value,
            command=self.on_slider_change
        )
        self.time_slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # 綁定事件，點擊其他區域時隱藏滑桿
        self.master.bind("<Button-1>", self.check_slider_focus)

    def time_to_seconds(self, time_obj):
        """將時間對象轉換為秒數"""
        return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000

    def time_to_milliseconds(self, time_obj):
        """將時間對象轉換為毫秒"""
        return ((time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds) * 1000 +
                time_obj.milliseconds)

    def on_slider_change(self, value):
        """滑桿值變化時更新時間顯示"""
        if not self.slider_active or not self.slider_target:
            return

        # 獲取新的時間值（毫秒）
        new_value = float(value)

        # 將毫秒轉換為 SubRipTime 對象
        new_time = self.milliseconds_to_time(new_value)

        # 更新樹狀視圖中的顯示
        item = self.slider_target["item"]
        column_name = self.slider_target["column"]
        values = list(self.tree.item(item, "values"))

        # 更新相應的值
        if column_name == "Start":
            values[self.slider_target["start_pos"]] = str(new_time)

            # 如果有上一行，同時更新上一行的結束時間
            item_index = self.slider_target["item_index"]
            if item_index > 0:
                prev_item = self.slider_target["all_items"][item_index - 1]
                prev_values = list(self.tree.item(prev_item, "values"))
                prev_values[self.slider_target["end_pos"]] = str(new_time)
                self.tree.item(prev_item, values=tuple(prev_values))
        else:  # End 欄位
            values[self.slider_target["end_pos"]] = str(new_time)

            # 如果有下一行，同時更新下一行的開始時間
            item_index = self.slider_target["item_index"]
            if item_index < len(self.slider_target["all_items"]) - 1:
                next_item = self.slider_target["all_items"][item_index + 1]
                next_values = list(self.tree.item(next_item, "values"))
                next_values[self.slider_target["start_pos"]] = str(new_time)
                self.tree.item(next_item, values=tuple(next_values))

        # 更新當前項目的值
        self.tree.item(item, values=tuple(values))

    def milliseconds_to_time(self, milliseconds):
        """將毫秒轉換為 SubRipTime 對象"""
        total_seconds = milliseconds / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        ms = int((total_seconds - int(total_seconds)) * 1000)
        return pysrt.SubRipTime(hours, minutes, seconds, ms)

    def apply_time_change(self):
        """應用時間變更並隱藏滑桿"""
        if not self.slider_active:
            return

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
        if self.audio_imported and hasattr(self, 'audio_player'):
            self.audio_player.segment_audio(self.srt_data)

        # 保存狀態
        self.state_manager.save_state(self.get_current_state(), {
            'type': 'time_adjust',
            'description': '調整時間軸'
        })

        # 隱藏滑桿
        self.hide_time_slider()

    def check_slider_focus(self, event):
        """檢查點擊是否在滑桿外部，如果是則隱藏滑桿"""
        if not self.slider_active or not self.time_slider:
            return

        # 獲取滑桿的位置
        slider_x = self.time_slider.winfo_rootx()
        slider_y = self.time_slider.winfo_rooty()
        slider_width = self.time_slider.winfo_width()
        slider_height = self.time_slider.winfo_height()

        # 檢查點擊是否在滑桿區域外
        if (event.x_root < slider_x or event.x_root > slider_x + slider_width or
            event.y_root < slider_y or event.y_root > slider_y + slider_height):
            # 應用變更並隱藏滑桿
            self.apply_time_change()

    def hide_time_slider(self):
        """隱藏時間調整滑桿"""
        if hasattr(self, 'time_slider') and self.time_slider:
            # 獲取滑桿的父框架
            parent = self.time_slider.master
            parent.place_forget()
            parent.destroy()
            self.time_slider = None

        self.slider_active = False
        self.slider_target = None

        # 解除綁定
        try:
            self.master.unbind("<Button-1>")  # 移除特定的回調函數標識符
        except:
            pass

    def remember_mouse_position(self, event):
        """記錄當前滑鼠位置"""
        self.last_mouse_x = event.x_root - self.tree.winfo_rootx()
        self.last_mouse_y = event.y_root - self.tree.winfo_rooty()

    def on_treeview_select(self, event=None):
        """處理樹狀視圖選擇變化"""
        selected_items = self.tree.selection()

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
                self.state_manager.save_state(self.get_current_state())

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
        elif self.srt_imported and self.word_imported and self.audio_imported:
            new_mode = self.DISPLAY_MODE_ALL
        elif self.srt_imported and self.word_imported:
            new_mode = self.DISPLAY_MODE_SRT_WORD
        elif self.srt_imported and self.audio_imported:
            new_mode = self.DISPLAY_MODE_AUDIO_SRT
        else:  # 只有 SRT
            new_mode = self.DISPLAY_MODE_SRT

        # 如果模式已經改變，更新界面
        if new_mode != old_mode:
            self.logger.info(f"顯示模式變更: {old_mode} -> {new_mode}")

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
            for item in self.tree.get_children():
                values = self.tree.item(item, 'values')
                tags = self.tree.item(item, 'tags')

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

            # 清空並重建校正狀態
            self.correction_service.correction_states.clear()
            self.correction_service.original_texts.clear()
            self.correction_service.corrected_texts.clear()

            # 清空 use_word_text 字典
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
        else:
            # 即使模式沒變，也需要確保數據同步
            self.update_srt_data_from_treeview()

            # 如果有音頻檔案，仍然需要確保音頻段落與當前顯示同步
            if self.audio_imported and hasattr(self, 'audio_player') and hasattr(self, 'srt_data') and self.srt_data:
                self.audio_player.segment_audio(self.srt_data)
                self.logger.info("已更新音頻段落以匹配當前顯示")

    def update_correction_status_display(self):
        """更新樹視圖中的校正狀態顯示"""
        for item in self.tree.get_children():
            values = list(self.tree.item(item, 'values'))

            # 獲取索引
            if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                index_pos = 1
                text_pos = 4
            else:  # SRT 或 SRT_WORD 模式
                index_pos = 0
                text_pos = 3

            # 確保索引位置有效
            if len(values) <= index_pos:
                continue

            index = str(values[index_pos])

            # 檢查是否有校正狀態
            state = self.correction_service.get_correction_state(index)

            # 即使沒有顯式的校正狀態，也檢查是否需要校正
            if not state and index in self.correction_service.original_texts and index in self.correction_service.corrected_texts:
                # 比較原始文本和校正文本
                original = self.correction_service.original_texts[index]
                corrected = self.correction_service.corrected_texts[index]

                if original != corrected:
                    # 如果需要校正但沒有狀態，設置為可切換的狀態
                    state = 'correct'  # 默認為已校正
                    self.correction_service.correction_states[index] = state

            # 根據校正狀態更新顯示
            if state:
                # 更新 V/X 列
                mark = '✅' if state == 'correct' else '❌'
                values[-1] = mark

                # 根據狀態更新文本
                display_text = self.correction_service.get_text_for_display(index)
                if display_text and text_pos < len(values):
                    values[text_pos] = display_text

                # 更新項目
                self.tree.item(item, values=tuple(values))

    def restore_tree_data(self, data):
        """
        恢復先前保存的樹狀視圖數據
        :param data: 之前保存的數據列表
        """
        try:
            # 清空當前樹狀視圖
            for item in self.tree.get_children():
                self.tree.delete(item)

            # 清空校正狀態
            self.correction_service.clear_correction_states()

            # 逐項恢復數據
            for item_data in data:
                values = item_data.get('values', [])

                # 調整值以適應新的顯示模式
                adjusted_values = self.adjust_values_for_mode(values, "any", self.display_mode)

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

                # 恢復校正狀態
                correction = item_data.get('correction')
                if correction and 'state' in correction and correction['state']:
                    # 確定新的索引位置
                    if self.display_mode == self.DISPLAY_MODE_ALL or self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                        idx = str(adjusted_values[1])
                    else:
                        idx = str(adjusted_values[0])

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

            self.logger.info(f"已恢復 {len(data)} 個項目的數據到 {self.display_mode} 模式")

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
        # 創建選單列
        self.create_menu()

        # 創建工具列
        self.create_toolbar()

        # 創建主要內容區域
        self.create_main_content()

        # 創建底部檔案信息區域
        self.create_file_info_area()

        # 最後創建狀態欄
        self.create_status_bar()

    def create_menu(self) -> None:
        """創建選單列"""
        self.menubar = tk.Menu(self.menu_frame)

        # 建立一個 frame 來放置選單按鈕
        menu_buttons_frame = ttk.Frame(self.menu_frame)
        menu_buttons_frame.pack(fill=tk.X)

        #檔案選單
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_button = ttk.Menubutton(menu_buttons_frame, text="檔案", menu=file_menu)
        file_button.pack(side=tk.LEFT, padx=2)

        file_menu.add_command(label="切換專案", command=self.switch_project)
        file_menu.add_separator()  # 分隔線
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
            selected = self.tree.selection()
            tags_backup = {}
            values_backup = {}
            use_word_backup = self.use_word_text.copy()  # 備份 use_word_text 狀態

            for item in self.tree.get_children():
                tags_backup[item] = self.tree.item(item, 'tags')
                values_backup[item] = self.tree.item(item, 'values')

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
            for item in self.tree.get_children():
                self.tree.delete(item)

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
                corrected_text = self.correct_text(text, corrections)
                needs_correction = corrected_text != text

                # 直接使用原始 Word 文本和差異信息
                match_status = comparison.get('match', True)
                word_text = comparison.get('word_text', '')
                diff_text = comparison.get('difference', '')

                # 準備值 - 根據不同模式創建適當的值列表
                values = self.prepare_values_for_mode(
                    self.display_mode, sub,
                    corrected_text if needs_correction else text,
                    word_text, diff_text, needs_correction
                )

                # 插入到樹狀視圖
                item_id = self.insert_item('', 'end', values=tuple(values))

                # 設置標籤
                tags = []

                # 檢查是否有先前的 use_word_text 設置
                old_item_id = index_to_item.get(str(sub.index))

                # 檢查是否使用 Word 文本
                use_word = False
                if old_item_id in use_word_backup:
                    use_word = use_word_backup[old_item_id]
                    self.use_word_text[item_id] = use_word

                # 如果使用 Word 文本，添加 use_word_text 標籤
                if use_word:
                    tags.append('use_word_text')
                # 否則如果不匹配，添加 mismatch 標籤
                elif not match_status:
                    tags.append('mismatch')

                # 如果需要校正，添加校正標籤
                if needs_correction:
                    self.correction_service.set_correction_state(
                        str(sub.index),
                        text,
                        corrected_text,
                        'correct'
                    )

                # 應用標籤
                if tags:
                    self.tree.item(item_id, tags=tuple(tags))

            # 恢復選中
            if selected:
                for item in selected:
                    if item in self.tree.get_children():
                        self.tree.selection_add(item)

            # 配置標記樣式 - 確保標籤的優先級
            self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.tree.tag_configure("use_word_text", background="#00BFFF")  # 淺藍色背景標記使用 Word 文本的項目

        except Exception as e:
            self.logger.error(f"更新比對顯示時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新比對顯示失敗: {str(e)}", self.master)


    def prepare_values_for_mode(self, mode, sub, text, word_text, diff_text, needs_correction):
        """根據顯示模式準備值列表"""
        if mode == self.DISPLAY_MODE_ALL:  # ALL 模式
            return [
                self.PLAY_ICON,
                str(sub.index),
                str(sub.start),
                str(sub.end),
                text,
                word_text,
                diff_text,
                '✅' if needs_correction else ''
            ]
        elif mode == self.DISPLAY_MODE_SRT_WORD:  # SRT_WORD 模式
            return [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                text,
                word_text,
                diff_text,
                '✅' if needs_correction else ''
            ]
        elif mode == self.DISPLAY_MODE_AUDIO_SRT:  # AUDIO_SRT 模式
            return [
                self.PLAY_ICON,
                str(sub.index),
                str(sub.start),
                str(sub.end),
                text,
                '✅' if needs_correction else ''
            ]
        else:  # SRT 模式
            return [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                text,
                '✅' if needs_correction else ''
            ]

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
                self.state_manager.save_state(self.get_current_state())

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
            self.file_info_var.set(" | ".join(info_parts))
        else:
            self.file_info_var.set("尚未載入任何檔案")

    def create_toolbar(self) -> None:
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
            ("匯出 SRT", lambda: self.export_srt(from_toolbar=True))
        ]

        # 使用 enumerate 來追蹤每個按鈕的位置
        for index, (text, command) in enumerate(buttons):
            btn = ttk.Button(
                self.toolbar_frame,
                text=text,
                command=command,
                width=15,
                style='Custom.TButton'
            )
            btn.pack(side=tk.LEFT, padx=5)

    def create_main_content(self) -> None:
        """創建主要內容區域"""
        # 建立內容框架
        self.content_frame = ttk.Frame(self.main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 計算總固定寬度
        total_width = sum(config['width'] for config in ColumnConfig.COLUMNS.values()) + 20  # 20 為卷軸寬度

        # 設定固定寬度的容器
        container = ttk.Frame(self.content_frame, width=total_width)
        container.pack(expand=False)
        container.pack_propagate(False)  # 防止自動調整大小

        self.content_frame.pack(fill=tk.BOTH, expand=False)

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
        """設置 Treeview 列配置 - 簡化版"""
        try:
            # 獲取當前模式的列配置
            columns = self.columns.get(self.display_mode, [])

            # 更新 Treeview 列
            self.tree["columns"] = columns
            self.tree['show'] = 'headings'

            # 配置每一列 - 使用預設配置，不計算列寬
            for col in columns:
                config = self.column_config.COLUMNS.get(col, {
                    'width': 100,
                    'stretch': True if col in ['SRT Text', 'Word Text'] else False,
                    'anchor': 'w' if col in ['SRT Text', 'Word Text'] else 'center'
                })

                self.tree.column(col,
                    width=config['width'],
                    stretch=config['stretch'],
                    anchor=config['anchor'])
                self.tree.heading(col, text=col, anchor='center')

            # 調試輸出
            self.logger.debug(f"Treeview 列配置完成，顯示模式: {self.display_mode}, 列: {columns}")

            self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

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

    def on_tree_scroll(self, *args):
        """处理树视图滚动 - 简化版"""
        try:
            # 更新滚动条位置
            self.tree_scrollbar.set(*args)
        except Exception as e:
            # 仅记录错误，不弹出错误对话框
            self.logger.error(f"滚动处理出错: {str(e)}")

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
            region = self.tree.identify("region", event.x, event.y)
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)

            self.logger.debug(f"樹狀圖點擊事件: region={region}, column={column}, item={item}")

            if not (region and column and item):
                return

            # 獲取列名
            column_idx = int(column[1:]) - 1
            if column_idx >= len(self.tree["columns"]):
                return

            column_name = self.tree["columns"][column_idx]
            self.logger.debug(f"點擊的列名: {column_name}")

            # 隱藏合併符號
            if hasattr(self, 'merge_symbol'):
                self.merge_symbol.place_forget()

            # 隱藏時間滑桿（如果有）
            if hasattr(self, 'hide_time_slider'):
                self.hide_time_slider()

            # 處理時間欄位的點擊
            if column_name in ["Start", "End"] and region == "cell":
                # 顯示時間調整滑桿
                if hasattr(self, 'show_time_slider'):
                    self.show_time_slider(event, item, column, column_name)
                return

            # 獲取值
            values = list(self.tree.item(item)["values"])
            if not values:
                return

            # 處理 V/X 列點擊 (校正狀態切換)
            if column_name == "V/X":
                self.logger.debug(f"點擊 V/X 列: item={item}, values={values}")

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

                # 直接檢查文本是否需要校正
                text = values[text_index]
                needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

                self.logger.debug(f"校正檢查: 需要校正={needs_correction}, 原文={original_text}, 校正後={corrected_text}")

                if not needs_correction:
                    self.logger.debug("文本不需要校正，忽略點擊")
                    return  # 如果不需要校正，不處理點擊

                # 獲取當前校正圖標
                correction_mark = values[-1] if values else ''
                self.logger.debug(f"當前校正標記: {correction_mark}")

                # 切換校正狀態
                if correction_mark == '✅':
                    # 從已校正切換到未校正
                    values[-1] = '❌'
                    values[text_index] = original_text
                    state = 'error'
                    self.logger.debug("切換到未校正狀態")
                else:  # correction_mark == '❌' 或空白
                    # 從未校正或無狀態切換到已校正
                    values[-1] = '✅'
                    values[text_index] = corrected_text
                    state = 'correct'
                    self.logger.debug("切換到已校正狀態")

                # 更新校正狀態
                self.correction_service.set_correction_state(
                    display_index,
                    original_text,
                    corrected_text,
                    state
                )

                # 更新樹狀圖顯示
                self.tree.item(item, values=tuple(values))
                self.logger.debug(f"更新後的樹狀圖值: {values}")

                # 保存當前狀態
                current_state = self.get_current_state()
                correction_state = self.correction_service.serialize_state()
                self.state_manager.save_state(
                    current_state,
                    {
                        'type': 'toggle_correction',
                        'display_index': display_index,
                        'description': '切換校正狀態'
                    },
                    correction_state
                )

                # 更新 SRT 數據
                self.update_srt_data_from_treeview()

                return

                # 日誌記錄
                self.logger.debug(f"校正狀態已切換: {current_state} -> {new_state}")
                self.logger.debug(f"更新後的值: {values}")
                self.logger.debug(f"校正狀態: {self.correction_service.correction_states.get(display_index)}")

                return

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
                    self.state_manager.save_state(self.get_current_state())

                return

            # 處理音頻播放列的點擊
            elif column_name == 'V.O' and self.audio_imported:
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

    def update_correction_status_display(self):
        """更新樹視圖中的校正狀態顯示"""
        for item in self.tree.get_children():
            values = list(self.tree.item(item, 'values'))

            # 獲取索引
            if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                index_pos = 1
                text_pos = 4
            else:  # SRT 或 SRT_WORD 模式
                index_pos = 0
                text_pos = 3

            # 確保索引位置有效
            if len(values) <= index_pos:
                continue

            index = str(values[index_pos])

            # 檢查是否有校正狀態
            state = self.correction_service.get_correction_state(index)

            # 即使沒有顯式的校正狀態，也檢查是否需要校正
            if not state and text_pos < len(values):
                text = values[text_pos]
                needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

                if needs_correction:
                    # 這裡不自動設置校正狀態，只檢查現有狀態
                    # 文本需要校正但沒有狀態時，確保圖標為空（等待用戶決定）
                    if values[-1] not in ['✅', '❌']:
                        values[-1] = ''
                        self.tree.item(item, values=tuple(values))
                else:
                    # 文本不需要校正，確保圖標為空
                    if values[-1] != '':
                        values[-1] = ''
                        self.tree.item(item, values=tuple(values))
            elif state:
                # 根據校正狀態更新圖標
                mark = '✅' if state == 'correct' else '❌'

                # 只有當圖標與狀態不一致時才更新
                if values[-1] != mark:
                    values[-1] = mark
                    self.tree.item(item, values=tuple(values))

    def toggle_correction_icon(self, item: str, index: str, text: str) -> None:
        """
        切換校正圖標狀態

        Args:
            item: 樹狀視圖項目ID
            index: 項目索引
            text: 當前文本
        """
        try:
            self.logger.debug(f"切換校正圖標開始: 索引={index}, 項目ID={item}")

            # 保存操作前的狀態
            original_state = self.get_current_state()
            original_correction = self.correction_service.serialize_state()

            # 記錄切換前的校正狀態
            before_state = self.correction_service.get_correction_state(index)
            self.logger.debug(f"切換前校正狀態: {before_state}")

            # 獲取當前項目的值
            values = list(self.tree.item(item, "values"))
            if not values:
                self.logger.warning(f"項目 {item} 沒有值，無法切換校正狀態")
                return

            # 檢查文本是否需要校正
            needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

            if not needs_correction:
                self.logger.debug(f"文本不需要校正，不做任何更改: {text}")
                return

            # 獲取當前校正圖標
            correction_mark = values[-1] if values else ''

            # 切換校正狀態
            if correction_mark == '✅':
                # 從已校正切換到未校正
                values[-1] = '❌'

                # 獲取文本位置索引
                text_index = None
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    text_index = 3
                else:  # SRT 模式
                    text_index = 3

                # 更新顯示文本為原始文本
                if text_index is not None and text_index < len(values):
                    values[text_index] = original_text

                # 更新校正狀態
                self.correction_service.set_correction_state(
                    index,
                    original_text,
                    corrected_text,
                    'error'  # 設置為未校正狀態
                )
            else:  # correction_mark == '❌' 或空白
                # 從未校正或無狀態切換到已校正
                values[-1] = '✅'

                # 獲取文本位置索引
                text_index = None
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    text_index = 4
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    text_index = 3
                else:  # SRT 模式
                    text_index = 3

                # 更新顯示文本為校正後文本
                if text_index is not None and text_index < len(values):
                    values[text_index] = corrected_text

                # 更新校正狀態
                self.correction_service.set_correction_state(
                    index,
                    original_text,
                    corrected_text,
                    'correct'  # 設置為已校正狀態
                )

            # 更新樹狀圖顯示
            self.tree.item(item, values=tuple(values))

            # 記錄切換後的校正狀態
            after_state = self.correction_service.get_correction_state(index)
            self.logger.debug(f"切換後校正狀態: {after_state}")

            # 更新 SRT 數據
            self.update_srt_data_from_treeview()

            # 保存當前狀態，包含完整的操作信息和校正狀態
            current_state = self.get_current_state()
            current_correction = self.correction_service.serialize_state()

            # 創建操作信息
            operation_info = {
                'type': 'toggle_correction',
                'description': '切換校正狀態',
                'item_id': item,
                'index': index,
                'before_state': before_state,
                'after_state': after_state,
                'original_state': original_state,
                'original_correction': original_correction
            }

            # 保存到狀態管理器
            self.state_manager.save_state(current_state, operation_info, current_correction)

            self.logger.debug(f"校正圖標切換完成: 索引={index}, 項目ID={item}")

        except Exception as e:
            self.logger.error(f"切換校正圖標時出錯: {e}", exc_info=True)


    def check_text_correction(self, text: str, corrections: dict) -> Tuple[bool, str, str]:
        """
        檢查文本是否需要校正並返回相關信息
        Args:
            text: 要檢查的文本
            corrections: 校正對照表
        Returns:
            (需要校正, 原始文本, 校正後文本)
        """
        needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)
        return needs_correction, original_text, corrected_text

    def insert_text_segment(self, insert_position: int, text: str, start: str, end: str,
                   corrections: dict, show_correction_info: bool = True) -> str:
        """
        插入文本段落並建立校正狀態
        返回創建的項目ID
        """
        try:
            # 檢查文本是否需要校正
            needs_correction, original_text, corrected_text = self.check_text_correction(text, corrections)
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
            new_item = self.tree.insert('', insert_position, values=tuple(new_values))

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
            selected_items = self.tree.selection()
            if not selected_items:
                return

            # 檢查項目是否依然存在
            item = selected_items[0]
            if not self.tree.exists(item):
                return

            values = list(self.tree.item(item, 'values'))
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
                            self.process_word_edit_result(dialog.result, item, srt_index)
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
                            self.process_word_edit_result(dialog.result, item, srt_index)

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

    # 修改在處理分割文本時的校正狀態邏輯
    def process_srt_edit_result(self, result, item, srt_index, start_time, end_time):
        """處理 SRT 文本編輯結果"""
        try:
            # 保存操作前的完整狀態
            original_state = self.get_current_state()
            original_correction = self.correction_service.serialize_state()

            # 檢查結果類型 - 分割操作
            if isinstance(result, list) and len(result) > 0 and isinstance(result[0], tuple):
                # 獲取當前樹狀視圖的完整快照，包括所有項目和它們的位置
                tree_items = list(self.tree.get_children())
                current_tree_state = []

                for tree_item in tree_items:
                    item_values = self.tree.item(tree_item, 'values')
                    item_tags = self.tree.item(tree_item, 'tags')
                    item_position = self.tree.index(tree_item)

                    current_tree_state.append({
                        'id': tree_item,
                        'values': item_values,
                        'tags': item_tags,
                        'position': item_position,
                        'use_word': self.use_word_text.get(tree_item, False)
                    })

                # 保存被分割項目的詳細信息
                split_item_index = self.tree.index(item)
                split_item_details = {
                    'id': item,
                    'values': self.tree.item(item, 'values'),
                    'tags': self.tree.item(item, 'tags'),
                    'position': split_item_index,
                    'use_word': self.use_word_text.get(item, False)
                }

                # 載入校正數據庫
                corrections = self.load_corrections()

                # 先檢查項目是否存在
                if not self.tree.exists(item):
                    self.logger.error(f"項目 {item} 不存在")
                    return

                # 保存當前標籤狀態和刪除位置
                try:
                    tags = self.tree.item(item, 'tags')
                    delete_position = self.tree.index(item)
                    values = self.tree.item(item)['values']

                    # 獲取當前 Word 文本和 Match 狀態（如果有）
                    word_text = ""
                    match_status = ""

                    if self.display_mode in [self.DISPLAY_MODE_SRT_WORD, self.DISPLAY_MODE_ALL]:
                        word_text_index = 5 if self.display_mode == self.DISPLAY_MODE_ALL else 4
                        match_index = 6 if self.display_mode == self.DISPLAY_MODE_ALL else 5

                        if len(values) > word_text_index:
                            word_text = values[word_text_index]
                        if len(values) > match_index:
                            match_status = values[match_index]

                except Exception as e:
                    self.logger.error(f"獲取項目信息失敗: {e}")
                    return

                # 準備新的時間列表
                new_start_times = []
                new_end_times = []

                # 將結果轉換為列表，避免 tuple 可能引起的問題
                result_list = list(result)

                # 輸出日誌，查看分割結果
                self.logger.debug(f"分割結果數量: {len(result_list)}")
                for i, (text, new_start, new_end) in enumerate(result_list):
                    self.logger.debug(f"分割結果 {i}: text={text}, start={new_start}, end={new_end}")

                # 刪除原始項目 - 在刪除後不再使用 item 引用
                try:
                    self.tree.delete(item)
                except Exception as e:
                    self.logger.error(f"刪除項目失敗: {e}")
                    return

                # 根據顯示模式確定文本位置和V/X位置
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    text_index = 4
                    vx_index = 7
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    text_index = 3
                    vx_index = 6
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    text_index = 4
                    vx_index = 5
                else:  # SRT 模式
                    text_index = 3
                    vx_index = 4

                # 處理每個分割後的文本段落
                new_items = []
                for i, (text, new_start, new_end) in enumerate(result_list):
                    # 收集新的時間
                    new_start_times.append(new_start)
                    new_end_times.append(new_end)

                    try:
                        # 創建新的索引 - 只有新生成的項目才改變索引
                        new_index = str(srt_index + i if i > 0 else srt_index)

                        # 檢查文本是否有需要校正的部分
                        needs_correction, corrected_text, original_text, actual_corrections = self.correction_service.check_text_for_correction(text)

                        # 初始化顯示文本和校正圖標
                        display_text = text
                        correction_icon = ''

                        # 處理校正邏輯
                        if needs_correction:
                            # 如果需要校正，顯示未校正圖標
                            correction_icon = '❌'

                            # 保存校正狀態
                            self.correction_service.set_correction_state(
                                new_index,
                                text,  # 原始文本
                                corrected_text,  # 校正後文本
                                'error'  # 未校正狀態
                            )

                            self.logger.debug(f"文本 '{text}' 包含錯誤字，設置索引 {new_index} 為未校正狀態")
                        else:
                            # 如果不需要校正，不顯示圖標，清除校正狀態
                            correction_icon = ''

                            # 清除校正狀態
                            if hasattr(self.correction_service, 'remove_correction_state'):
                                self.correction_service.remove_correction_state(new_index)

                            self.logger.debug(f"文本 '{text}' 沒有錯誤字，清除索引 {new_index} 的校正狀態")

                        # 為每個分割段落處理Word文本 - 只有第一個段落保留原始Word文本，其他段落為空
                        current_word_text = word_text if i == 0 else ""
                        current_match = "" if i > 0 else match_status  # 第一個段落保留Match狀態，其他清空

                        # 根據顯示模式構建值列表
                        if self.display_mode == self.DISPLAY_MODE_ALL:
                            # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                            values = [
                                self.PLAY_ICON,
                                new_index,
                                new_start,
                                new_end,
                                display_text,
                                current_word_text,  # 只有第一個段落保留Word文本
                                current_match,      # 只有第一個段落保留Match狀態
                                correction_icon     # V/X 根據校正需要設置
                            ]
                        elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                            # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                            values = [
                                new_index,
                                new_start,
                                new_end,
                                display_text,
                                current_word_text,  # 只有第一個段落保留Word文本
                                current_match,      # 只有第一個段落保留Match狀態
                                correction_icon     # V/X 根據校正需要設置
                            ]
                        elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                            # [V.O, Index, Start, End, SRT Text, V/X]
                            values = [
                                self.PLAY_ICON,
                                new_index,
                                new_start,
                                new_end,
                                display_text,
                                correction_icon   # V/X 根據校正需要設置
                            ]
                        else:  # SRT 模式
                            # [Index, Start, End, SRT Text, V/X]
                            values = [
                                new_index,
                                new_start,
                                new_end,
                                display_text,
                                correction_icon   # V/X 根據校正需要設置
                            ]

                        # 使用安全的插入方法
                        pos = delete_position + i
                        self.logger.debug(f"插入項目於位置 {pos}，索引 {new_index}，文本 {display_text}")
                        new_item = self.insert_item('', pos, values=tuple(values))
                        new_items.append(new_item)

                        # 如果有標籤，應用到新項目，但移除不需要的標籤如 'mismatch'
                        if tags:
                            clean_tags = tuple(tag for tag in tags if tag != 'mismatch')
                            self.tree.item(new_item, tags=clean_tags)

                        # 更新 SRT 數據以反映變化
                        if i == 0:
                            # 更新原有項目
                            if srt_index - 1 < len(self.srt_data):
                                self.srt_data[srt_index - 1].text = display_text
                                self.srt_data[srt_index - 1].start = parse_time(new_start)
                                self.srt_data[srt_index - 1].end = parse_time(new_end)
                        else:
                            # 創建新的 SRT 項目
                            try:
                                # 嘗試將索引轉換為整數
                                new_srt_index = int(new_index)
                            except ValueError:
                                # 如果轉換失敗，使用計算的索引
                                new_srt_index = srt_index + i

                            new_srt_item = pysrt.SubRipItem(
                                index=new_srt_index,
                                start=parse_time(new_start),
                                end=parse_time(new_end),
                                text=display_text
                            )

                            # 確定正確的插入位置
                            # 應該是在原始項目的後面，所以基於原始索引計算
                            insert_position = srt_index - 1 + i
                            if insert_position < len(self.srt_data):
                                self.srt_data.insert(insert_position, new_srt_item)
                            else:
                                self.srt_data.append(new_srt_item)

                            self.logger.debug(f"插入新 SRT 項目: 索引={new_srt_index}, 位置={insert_position}, 文本={display_text}")

                    except Exception as e:
                        self.logger.error(f"插入新項目失敗: {e}")
                        continue

                # 如果有音頻，更新音頻段落
                if self.audio_imported and hasattr(self, 'audio_player'):
                    # 首先嘗試使用單個區域切分方法
                    self.audio_player.segment_single_audio(
                        parse_time(start_time),
                        parse_time(end_time),
                        new_start_times,
                        new_end_times,
                        srt_index
                    )

                    # 然後重新對整個 SRT 數據進行分割以確保一致性
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.info(f"已重新分割全部音頻段落，確保與 SRT 同步")

                # 重新編號
                self.renumber_items()

                # 選中新創建的項目
                if new_items:
                    self.tree.selection_set(new_items)
                    self.tree.see(new_items[0])

                # 操作完成後保存更完整的狀態信息
                operation_info = {
                    'type': 'split_srt',
                    'description': '拆分 SRT 文本',
                    'original_state': original_state,
                    'original_correction': original_correction,
                    'split_item_details': split_item_details,
                    'tree_state_before_split': current_tree_state,
                    'full_tree_state': current_tree_state,  # 保存完整的樹狀視圖狀態
                    'srt_index': srt_index,
                    'start_time': start_time,
                    'end_time': end_time,
                    'result_count': len(result_list)
                }

                current_state = self.get_current_state()
                current_correction = self.correction_service.serialize_state()

                self.state_manager.save_state(current_state, operation_info, current_correction)

                # 重新綁定事件
                self.bind_all_events()

                # 更新介面
                self.update_status("已更新並拆分文本")

            else:
                # 處理單一文本編輯（非拆分）結果
                # 這是單一文本字串結果
                text = result
                if isinstance(text, list):
                    if len(text) > 0:
                        text = str(text[0])
                    else:
                        text = ""

                # 確保文本是字串類型
                text = str(text)

                # 獲取當前值
                values = list(self.tree.item(item, 'values'))

                # 檢查文本是否需要校正
                needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

                # 獲取原始項目的校正狀態（如果有）
                original_correction_state = ''
                if str(srt_index) in self.correction_service.correction_states:
                    original_correction_state = self.correction_service.correction_states[str(srt_index)]

                # 新的索引
                new_index = str(srt_index + i if i > 0 else srt_index)

                # 初始化校正圖標
                if needs_correction:
                    # 如果原始項目有校正狀態，使用相同的狀態
                    if original_correction_state:
                        correction_icon = '✅' if original_correction_state == 'correct' else '❌'
                        state = original_correction_state
                    else:
                        # 否則默認為未校正
                        correction_icon = '❌'
                        state = 'error'

                    # 保存校正狀態
                    self.correction_service.set_correction_state(
                        new_index,
                        text,
                        corrected_text,
                        state
                    )
                else:
                    # 不需要校正，不顯示圖標
                    correction_icon = ''
                    # 確保清除校正狀態
                    if hasattr(self.correction_service, 'remove_correction_state'):
                        self.correction_service.remove_correction_state(new_index)

                # 更新 SRT 文本
                if self.display_mode == self.DISPLAY_MODE_ALL:
                    values[4] = text
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    values[3] = text
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    values[4] = text
                else:  # SRT 模式
                    values[3] = text

                # 如果需要校正，更新圖標和設置校正狀態
                if needs_correction:
                    # 設置校正圖標 - 未校正狀態
                    values[-1] = '❌'

                    # 保存校正狀態
                    self.correction_service.set_correction_state(
                        str(srt_index),
                        text,  # 使用原始文本，不引入任何修改
                        corrected_text,
                        'error'  # 未校正狀態
                    )
                else:
                    # 如果不需要校正，清除圖標
                    values[-1] = ''

                    # 清除校正狀態
                    if hasattr(self.correction_service, 'remove_correction_state'):
                        self.correction_service.remove_correction_state(str(srt_index))

                # 更新 SRT 數據
                if 0 <= srt_index - 1 < len(self.srt_data):
                    self.srt_data[srt_index - 1].text = text

                # 更新樹狀視圖，保留原有標籤
                tags = self.tree.item(item, 'tags')
                self.tree.item(item, values=tuple(values), tags=tags)

                # 標記 SRT 欄位被編輯
                i = srt_index - 1
                if i not in self.edited_text_info:
                    self.edited_text_info[i] = {'edited': []}

                if 'srt' not in self.edited_text_info[i]['edited']:
                    self.edited_text_info[i]['edited'].append('srt')

                # 更新音頻段落
                if self.audio_imported and hasattr(self, 'audio_player'):
                    # 即使只修改了文本，也重新同步音頻段落，以確保一致性
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.debug("文本編輯後更新音頻段落")

                # 保存當前狀態，包含完整的操作信息和校正狀態
                current_state = self.get_current_state()
                correction_state = self.correction_service.serialize_state()

                self.state_manager.save_state(current_state, {
                    'type': 'edit_text',
                    'description': '編輯 SRT 文本',
                    'srt_index': srt_index,
                    'item_id': item,
                    'item_index': srt_index,
                    'original_state': original_state
                }, correction_state)

                # 更新狀態
                self.update_status("已更新 SRT 文本")
                self.update_srt_data_from_treeview()

                if hasattr(self.state_manager, 'rebuild_correction_states_from_ui'):
                    self.state_manager.rebuild_correction_states_from_ui()

        except Exception as e:
            self.logger.error(f"處理 SRT 編輯結果時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新文本失敗: {str(e)}", self.master)

    def handle_word_text_split(self, result, word_index, srt_index, original_values, original_item):
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

            # 檢查原始項目的校正狀態
            values = self.tree.item(original_item)['values']
            correction_state = ''
            if self.display_mode == self.DISPLAY_MODE_ALL and len(values) > 7:
                correction_state = values[7]
            elif self.display_mode == self.DISPLAY_MODE_SRT_WORD and len(values) > 6:
                correction_state = values[6]

            # 取得原始SRT文本
            srt_text = ""
            if self.display_mode == self.DISPLAY_MODE_ALL:
                srt_text = values[4] if len(values) > 4 else ""
            elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                srt_text = values[3] if len(values) > 3 else ""

            # 從樹狀視圖中刪除原項目
            self.tree.delete(original_item)

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

                    # 為第一個段落保留SRT文本，其他段落使用空白字符串但不是None
                    if i > 0:
                        new_values[4] = ""  # 新段落的SRT文本為空白字符串

                    new_values[5] = text  # Word文本
                    new_values[6] = ""  # 清空Match欄位
                    # 不修改校正狀態 (V/X)，保留原始值

                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    new_values[0] = str(new_srt_index)  # Index
                    new_values[1] = new_start  # Start
                    new_values[2] = new_end    # End

                    # 為第一個段落保留SRT文本，其他段落使用空白字符串但不是None
                    if i > 0:
                        new_values[3] = ""  # 新段落的SRT文本為空白字符串

                    new_values[4] = text  # Word文本
                    new_values[5] = ""  # 清空Match欄位
                    # 不修改校正狀態 (V/X)，保留原始值

                # 確保V.O值保持
                if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                    new_values[0] = self.PLAY_ICON

                # 插入新項目
                new_item = self.tree.insert('', delete_position + i, values=tuple(new_values))
                new_items.append(new_item)

                # 應用標籤
                if tags:
                    self.tree.item(new_item, tags=tags)

                # 如果這是第一個項目，保存use_word_text狀態
                if i == 0 and original_item in self.use_word_text:
                    self.use_word_text[new_item] = self.use_word_text[original_item]

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
                self.tree.selection_set(new_items)
                self.tree.see(new_items[0])

            # 更新 SRT 數據以反映變化 - 這是關鍵，確保 SRT 數據與界面同步
            self.update_srt_data_from_treeview()

            # 保存當前狀態 - 這裡是關鍵，我們要正確保存當前斷句後的狀態
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
                self.state_manager.save_state(current_state, operation_info, current_correction)

            # 更新狀態
            self.update_status("已分割 Word 文本")

        except Exception as e:
            self.logger.error(f"處理 Word 文本分割時出錯: {e}", exc_info=True)
            show_error("錯誤", f"分割 Word 文本失敗: {str(e)}", self.master)
    def bind_all_events(self) -> None:
        """綁定所有事件"""
        # 綁定視窗關閉事件
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 綁定全域快捷鍵
        self.master.bind_all('<Control-s>', lambda e: self.save_srt())
        self.master.bind_all('<Control-o>', lambda e: self.load_srt())
        self.master.bind_all('<Control-z>', lambda e: self.undo())
        self.master.bind_all('<Control-y>', lambda e: self.redo())

        # 綁定 Treeview 特定事件
        if hasattr(self, 'tree'):
            self.tree.bind('<Button-1>', self.on_tree_click)  # 使用新的統一點擊處理方法
            self.tree.bind('<Double-1>', self._handle_double_click)
            self.tree.bind('<KeyRelease>', self.on_treeview_change)

    def initialize_audio_player(self) -> None:
        """初始化音頻播放器"""
        self.audio_player = AudioPlayer(self.main_frame)
        self.master.bind("<<AudioLoaded>>", self.handle_audio_loaded)

    def on_treeview_change(self, event: tk.Event) -> None:
        """
        處理 Treeview 變更事件
        :param event: 事件對象
        """
        self.state_manager.save_state(self.get_current_state())

    def on_closing(self) -> None:
        """處理視窗關閉事件"""
        try:
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()
            self.state_manager.save_state(self.get_current_state())

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

            # 檢查音頻是否已匯入
            if not self.audio_imported:
                show_warning("警告", "未匯入音頻，請先匯入音頻檔案", self.master)
                return

            # 檢查音頻播放器是否已初始化
            if not hasattr(self, 'audio_player'):
                self.logger.error("音頻播放器未初始化")
                show_error("錯誤", "音頻播放器未初始化", self.master)
                return

            # 檢查播放器的音頻是否已載入
            if not hasattr(self.audio_player, 'audio') or self.audio_player.audio is None:
                self.logger.error("播放器音頻未載入")

                # 嘗試重新載入音頻
                if hasattr(self, 'audio_file_path') and self.audio_file_path:
                    self.logger.info(f"嘗試重新載入音頻文件: {self.audio_file_path}")
                    self.audio_player.load_audio(self.audio_file_path)

                    # 再次檢查
                    if not hasattr(self.audio_player, 'audio') or self.audio_player.audio is None:
                        show_warning("警告", "無法播放音訊：音訊未載入或為空", self.master)
                        return
                else:
                    show_warning("警告", "無法播放音訊：音訊未載入或為空", self.master)
                    return

            # 嘗試播放指定段落
            success = self.audio_player.play_segment(index)

            # 如果播放失敗，記錄錯誤
            if not success:
                self.logger.error(f"播放索引 {index} 的音頻段落失敗")

        except Exception as e:
            self.logger.error(f"播放音頻段落時出錯: {e}", exc_info=True)
            show_error("錯誤", f"播放音頻段落失敗: {str(e)}", self.master)

    def insert_item(self, parent: str, position: str, values: tuple) -> str:
        """
        封裝 Treeview 的插入操作，並加入日誌追蹤

        Args:
            parent: 父項目的 ID
            position: 插入位置 ('', 'end' 等)
            values: 要插入的值的元組

        Returns:
            插入項目的 ID
        """
        try:
            item_id = self.tree.insert(parent, position, values=values)
            return item_id
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
                for item in self.tree.get_children():
                    values = self.tree.item(item, 'values')
                    tags = self.tree.item(item, 'tags')
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
                for item in self.tree.get_children():
                    self.tree.delete(item)

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
        return self.correction_service.load_corrections()

    # 修改 correct_text 方法，使用 CorrectionService
    def correct_text(self, text: str, corrections: Dict[str, str]) -> str:
        """根據校正數據庫修正文本"""
        needs_correction, corrected_text, _ = self.correction_service.correct_text(text)
        return corrected_text if needs_correction else text

    # 修改 check_text_for_correction 方法，使用 CorrectionService
    def check_text_for_correction(self, text: str, corrections: dict) -> tuple[bool, str, str, list]:
        """檢查文本是否需要校正，並返回校正資訊"""
        return self.correction_service.check_text_for_correction(text)

    # 修改 process_srt_entries 方法中的校正相關代碼
    def process_srt_entries(self, srt_data, corrections):
        """處理 SRT 條目"""
        self.logger.debug(f"開始處理 SRT 條目，數量: {len(srt_data) if srt_data else 0}")

        if not srt_data:
            self.logger.warning("SRT 數據為空，無法處理")
            return

        for sub in srt_data:
            # 轉換文本為繁體中文
            text = simplify_to_traditional(sub.text.strip())

            # 檢查校正需求
            needs_correction, corrected_text, original_text, _ = self.correction_service.check_text_for_correction(text)

            # 準備值
            values = [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                corrected_text if needs_correction else text,
                '✅' if needs_correction else ''
            ]

            # 如果已經有音頻，在開頭加入播放圖標
            if self.audio_imported:
                values.insert(0, self.PLAY_ICON)

            # 插入到樹狀視圖
            item_id = self.insert_item('', 'end', values=tuple(values))

            # 如果需要校正，保存校正狀態
            if needs_correction:
                self.correction_service.set_correction_state(
                    str(sub.index),
                    original_text,
                    corrected_text,
                    'correct'  # 默認為已校正狀態
                )

    def process_subtitle_item(self, sub, corrections):
        """處理單個字幕項目，安全地處理索引"""
        try:
            # 確保所有必要屬性存在
            if not hasattr(sub, 'index') or not hasattr(sub, 'start') or \
            not hasattr(sub, 'end') or not hasattr(sub, 'text'):
                self.logger.warning(f"字幕項目缺少必要屬性: {sub}")
                return None

            # 確保 index 是有效的整數
            try:
                index = int(sub.index)
            except (ValueError, TypeError):
                self.logger.warning(f"無效的字幕索引: {sub.index}")
                return None

            # 轉換文本
            traditional_text = simplify_to_traditional(sub.text)
            corrected_text = traditional_text
            has_corrections = False
            correction_details = None

            # 檢查校正
            for error, correction in corrections.items():
                if error in traditional_text:
                    corrected_text = corrected_text.replace(error, correction)
                    has_corrections = True
                    correction_details = (error, correction)
                    break

            # 準備基本值
            base_values = [
                index,                    # 索引
                str(sub.start),          # 開始時間
                str(sub.end),            # 結束時間
                corrected_text,          # 文本
                '✅' if has_corrections else ''  # 校正標記
            ]

            # 根據顯示模式添加額外值
            if self.display_mode == "audio_srt":
                values = ["▶"] + base_values
            else:
                values = base_values

            # 如果有校正，保存校正狀態
            if has_corrections and correction_details:
                error, correction = correction_details
                self.correction_service.set_correction_state(
                    str(index),
                    traditional_text,
                    corrected_text,
                    'correct'
                )

            return tuple(values)

        except Exception as e:
            self.logger.error(f"處理字幕項目時出錯: {str(e)}", exc_info=True)
            return None

    # 修改 save_srt_file 方法，考慮 use_word_text 標記
    def save_srt_file(self, file_path: str) -> None:
        """
        保存 SRT 文件
        :param file_path: 文件路徑
        """
        try:
            # 創建新的 SRT 文件
            new_srt = pysrt.SubRipFile()

            # 載入校正資料庫
            corrections = self.load_corrections()

            # 遍歷所有項目
            for item in self.tree.get_children():
                values = self.tree.item(item)['values']

                # 檢查是否使用 Word 文本
                use_word = self.use_word_text.get(item, False)

                # 根據顯示模式解析值
                if self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    index = int(values[1])
                    start = values[2]
                    end = values[3]
                    text = values[4]  # SRT 文本
                    # 音頻 SRT 模式下沒有 Word 文本
                    word_text = None
                    # 檢查校正狀態 - V/X 列
                    correction_state = values[5] if len(values) > 5 else ""
                elif self.display_mode in [self.DISPLAY_MODE_SRT_WORD, self.DISPLAY_MODE_ALL]:
                    # 對於包含 Word 的模式
                    if self.display_mode == self.DISPLAY_MODE_ALL:
                        index = int(values[1])
                        start = values[2]
                        end = values[3]
                        srt_text = values[4]
                        word_text = values[5]
                        # 檢查校正狀態 - V/X 列
                        correction_state = values[7] if len(values) > 7 else ""
                    else:  # SRT_WORD 模式
                        index = int(values[0])
                        start = values[1]
                        end = values[2]
                        srt_text = values[3]
                        word_text = values[4]
                        # 檢查校正狀態 - V/X 列
                        correction_state = values[6] if len(values) > 6 else ""

                    # 根據標記決定使用哪個文本，不受 mismatch 標記的影響
                    if use_word and word_text:
                        text = word_text  # 使用 Word 文本
                        self.logger.debug(f"項目 {index} 使用 Word 文本: {word_text}")
                    else:
                        text = srt_text  # 使用 SRT 文本
                else:  # SRT 模式
                    index = int(values[0])
                    start = values[1]
                    end = values[2]
                    text = values[3]
                    word_text = None
                    # 檢查校正狀態 - V/X 列
                    correction_state = values[4] if len(values) > 4 else ""

                # 解析時間
                start_time = parse_time(start)
                end_time = parse_time(end)

                # 根據校正狀態決定是否應用校正
                final_text = text
                if correction_state == "✅" and str(index) in self.correction_service.correction_states:
                    # 獲取校正後的文本
                    corrected_text = self.correction_service.corrected_texts.get(str(index), '')
                    if corrected_text:
                        final_text = corrected_text

                # 創建字幕項
                sub = pysrt.SubRipItem(
                    index=index,
                    start=start_time,
                    end=end_time,
                    text=final_text
                )
                new_srt.append(sub)

            # 保存文件
            new_srt.save(file_path, encoding='utf-8')

            # 更新界面顯示
            self.update_file_info()
            self.update_status(f"已儲存至：{os.path.basename(file_path)}")

        except Exception as e:
            self.logger.error(f"保存 SRT 檔案時出錯: {e}")
            show_error("錯誤", f"保存檔案失敗: {str(e)}", self.master)


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
        try:
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

            for i, item in enumerate(self.tree.get_children(), 1):
                try:
                    values = self.tree.item(item, 'values')

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

            # 更新音頻段落
            if self.audio_imported and hasattr(self, 'audio_player') and self.srt_data:
                self.logger.info("SRT 數據已更新，正在同步音頻段落...")
                # 完全重建音頻段落
                if hasattr(self.audio_player.segment_manager, 'rebuild_segments'):
                    self.audio_player.segment_manager.rebuild_segments(self.srt_data)
                else:
                    # 如果沒有重建方法，則使用標準方法
                    self.audio_player.segment_audio(self.srt_data)

        except Exception as e:
            self.logger.error(f"從 Treeview 更新 SRT 數據時出錯: {e}")
            show_error("錯誤", f"更新 SRT 數據失敗: {str(e)}", self.master)

    def combine_sentences(self, event=None) -> None:
        """合併字幕"""
        try:
            # 檢查是否有儲存的選中項
            if not hasattr(self, 'current_selected_items') or len(self.current_selected_items) < 2:
                show_warning("警告", "請選擇至少兩個字幕項目", self.master)
                return

            # 保存操作前的完整狀態
            original_state = self.get_current_state()
            # 獲取當前校正狀態
            original_correction = self.correction_service.serialize_state()
            self.logger.debug(f"合併前狀態包含 {len(original_state)} 項目")

            try:
                # 使用所有選中的項目進行合併
                selected_items = self.current_selected_items

                # 根據索引排序項目
                sorted_items = sorted(selected_items, key=self.tree.index)

                # 第一個項目作為基礎
                base_item = sorted_items[0]
                base_values = list(self.tree.item(base_item, 'values'))
                base_tags = self.tree.item(base_item, 'tags')

                # 獲取所有選中項目的詳細信息（用於還原）
                selected_items_details = []
                for sel_item in sorted_items:
                    item_values = self.tree.item(sel_item, 'values')
                    item_tags = self.tree.item(sel_item, 'tags')
                    item_position = self.tree.index(sel_item)

                    selected_items_details.append({
                        'id': sel_item,
                        'values': item_values,
                        'tags': item_tags,
                        'position': item_position,
                        'use_word': self.use_word_text.get(sel_item, False)
                    })

                # 根據顯示模式確定正確的列索引
                if self.display_mode == self.DISPLAY_MODE_SRT:
                    # [Index, Start, End, SRT Text, V/X]
                    index_index = 0
                    start_index = 1
                    end_index = 2
                    text_index = 3
                    vx_index = 4
                    vo_index = None
                    word_text_index = None
                    match_index = None
                elif self.display_mode == self.DISPLAY_MODE_SRT_WORD:
                    # [Index, Start, End, SRT Text, Word Text, Match, V/X]
                    index_index = 0
                    start_index = 1
                    end_index = 2
                    text_index = 3
                    word_text_index = 4
                    match_index = 5
                    vx_index = 6
                    vo_index = None
                elif self.display_mode == self.DISPLAY_MODE_AUDIO_SRT:
                    # [V.O, Index, Start, End, SRT Text, V/X]
                    vo_index = 0
                    index_index = 1
                    start_index = 2
                    end_index = 3
                    text_index = 4
                    vx_index = 5
                    word_text_index = None
                    match_index = None
                else:  # self.DISPLAY_MODE_ALL
                    # [V.O, Index, Start, End, SRT Text, Word Text, Match, V/X]
                    vo_index = 0
                    index_index = 1
                    start_index = 2
                    end_index = 3
                    text_index = 4
                    word_text_index = 5
                    match_index = 6
                    vx_index = 7

                # 載入校正數據庫
                corrections = self.load_corrections()

                # 合併文本
                combined_text = base_values[text_index] if text_index < len(base_values) else ""
                combined_word_text = ""
                combined_match = ""

                # 初始化 Word 文本和 Match 相關變數
                if word_text_index is not None and word_text_index < len(base_values):
                    combined_word_text = base_values[word_text_index]
                if match_index is not None and match_index < len(base_values):
                    combined_match = base_values[match_index]

                # 使用最後一個項目的結束時間
                last_item_values = self.tree.item(sorted_items[-1], 'values')
                if end_index < len(last_item_values):
                    end_time = last_item_values[end_index]
                else:
                    # 如果找不到結束時間，使用基礎項目的結束時間
                    end_time = base_values[end_index] if end_index < len(base_values) else ""

                # 合併所有選中項的文本
                for item in sorted_items[1:]:
                    item_values = self.tree.item(item, 'values')
                    # 合併文本
                    if text_index < len(item_values) and item_values[text_index].strip():  # 只有當文本不為空白時才合併
                        combined_text += f" {item_values[text_index]}"

                    # 合併 Word 文本 (如果存在)
                    if word_text_index is not None and word_text_index < len(item_values) and item_values[word_text_index].strip():
                        combined_word_text += f" {item_values[word_text_index]}"

                    # 合併 Match 狀態 (如果存在)
                    if match_index is not None and match_index < len(item_values):
                        current_match = item_values[match_index]
                        if current_match and combined_match:
                            combined_match += f" | {current_match}"
                        elif current_match:
                            combined_match = current_match

                # 檢查合併後的文本是否需要校正
                needs_correction, corrected_text, original_text, actual_corrections = self.correction_service.check_text_for_correction(combined_text)

                # 新的值設置部分
                new_values = list(base_values)
                new_values[end_index] = end_time  # 使用最後一項的結束時間
                new_values[text_index] = combined_text  # 合併後的文本

                # 處理特定欄位
                if vo_index is not None:
                    new_values[vo_index] = self.PLAY_ICON  # 確保播放圖標存在

                if word_text_index is not None:
                    new_values[word_text_index] = combined_word_text  # 合併後的 Word 文本

                if match_index is not None:
                    new_values[match_index] = combined_match  # 合併後的比對狀態

                # 初始化校正狀態圖標 - 根據實際檢查結果設置
                new_values[vx_index] = '✅' if needs_correction else ''

                # 檢查是否有任一項使用 Word 文本
                use_word_text = False
                for item in sorted_items:
                    if self.use_word_text.get(item, False):
                        use_word_text = True
                        break

                # 刪除所有原始項目
                insert_position = self.tree.index(sorted_items[0])
                for item in sorted_items:
                    self.tree.delete(item)

                # 插入新合併項目
                new_item = self.insert_item('', insert_position, values=tuple(new_values))

                # 確保 new_item_index 被定義
                if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                    new_item_index = str(new_values[1])
                else:
                    new_item_index = str(new_values[0])

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
                        combined_text,  # 原始文本
                        corrected_text,  # 校正後文本
                        'correct'  # 默認為已校正狀態
                    )

                    # 更新顯示，確保校正圖標顯示正確
                    if vx_index < len(new_values):
                        new_values_list = list(new_values)
                        new_values_list[vx_index] = '✅'
                        self.tree.item(new_item, values=tuple(new_values_list))
                else:
                    # 如果不需要校正，確保沒有校正狀態
                    if hasattr(self.correction_service, 'remove_correction_state'):
                        self.correction_service.remove_correction_state(new_item_index)

                # 更新項目編號
                self.renumber_items()

                # 更新 SRT 數據
                self.update_srt_data_from_treeview()

                # 如果有音頻，處理音頻段落
                if self.audio_imported and hasattr(self, 'audio_player'):
                    try:
                        # 獲取所有被合併項目的確切索引
                        indices_to_merge = []
                        for item_data in selected_items_details:
                            item_values = item_data.get('values', [])
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

                    except Exception as e:
                        self.logger.error(f"合併音頻段落時出錯: {e}")
                        import traceback
                        self.logger.error(traceback.format_exc())

                    # 然後重新對整個 SRT 數據進行分割以確保一致性
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.info(f"已重新分割全部音頻段落，確保與 SRT 同步")

                # 刷新所有校正狀態，確保它們基於最新的文本內容
                if hasattr(self.correction_service, 'refresh_all_correction_states'):
                    self.correction_service.refresh_all_correction_states()

                # 更新校正狀態顯示
                self.update_correction_status_display()

                # 保存操作後的狀態
                current_state = self.get_current_state()
                current_correction = self.correction_service.serialize_state()

                # 保存狀態，包含完整的操作信息和校正狀態
                operation_info = {
                    'type': 'combine_sentences',
                    'description': '合併字幕',
                    'original_state': original_state,
                    'original_correction': original_correction,
                    'items': [item for item in sorted_items],
                    'selected_items_details': selected_items_details,
                    'is_first_operation': len(self.state_manager.states) <= 1
                }

                self.logger.debug(f"正在保存合併操作狀態: 原狀態項數={len(original_state)}, 新狀態項數={len(current_state)}")
                self.state_manager.save_state(current_state, operation_info, current_correction)

                # 選中新合併的項目
                self.tree.selection_set(new_item)
                self.tree.see(new_item)

                # 隱藏合併符號
                if hasattr(self, 'merge_symbol'):
                    self.merge_symbol.place_forget()

                self.update_status("已合併所選字幕")

            except Exception as e:
                self.logger.error(f"合併字幕時出錯: {e}", exc_info=True)
                show_error("錯誤", f"合併字幕失敗: {str(e)}", self.master)

        except Exception as e:
            self.logger.error(f"合併字幕時出錯: {e}", exc_info=True)
            show_error("錯誤", f"合併字幕失敗: {str(e)}", self.master)

    def _check_text_match(self, srt_text: str, word_text: str) -> str:
        """
        檢查 SRT 文本和 Word 文本的差異字
        :param srt_text: SRT 文本
        :param word_text: Word 文本
        :return: 差異描述
        """
        try:
            # 清理文本（移除多餘空格）
            srt_text = ' '.join(srt_text.split())
            word_text = ' '.join(word_text.split())

            # 如果完全相同則沒有差異
            if srt_text == word_text:
                return ""

            # 字符級別的差異比較
            import difflib
            d = difflib.SequenceMatcher(None, srt_text, word_text)

            # 找出不同的部分
            srt_only = []
            word_only = []

            for tag, i1, i2, j1, j2 in d.get_opcodes():
                if tag == 'replace' or tag == 'delete':
                    # SRT 中有但 Word 中沒有或不同的部分
                    srt_only.append(srt_text[i1:i2])
                if tag == 'replace' or tag == 'insert':
                    # Word 中有但 SRT 中沒有或不同的部分
                    word_only.append(word_text[j1:j2])

            # 組合結果
            result = []
            if srt_only:
                result.append(f"SRT={' '.join(srt_only)}")
            if word_only:
                result.append(f"WORD={' '.join(word_only)}")

            return "｜".join(result) if result else "文本不完全匹配"
        except Exception as e:
            self.logger.error(f"檢查文本差異時出錯: {e}")
            return "檢查差異出錯"

    def align_end_times(self) -> None:
        """調整結束時間"""
        items = self.tree.get_children()
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

            # 創建備份以便還原
            backup_values = {}
            for item in items:
                backup_values[item] = list(self.tree.item(item, 'values'))

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

            # 保存操作後的狀態
            current_state = self.get_current_state()
            current_correction = self.correction_service.serialize_state()

            # 保存狀態，包含完整的操作信息和校正狀態
            self.state_manager.save_state(current_state, {
                'type': 'align_end_times',
                'description': '調整結束時間',
                'original_state': original_state
            }, current_correction)

            self.update_status("已完成結束時間調整")
            show_info("完成", "均將時間軸前後對齊填滿", self.master)

        except Exception as e:
            self.logger.error(f"調整結束時間時出錯: {e}", exc_info=True)
            show_error("錯誤", f"調整結束時間失敗: {str(e)}", self.master)

    # 在 renumber_items 函數中，確保校正狀態正確轉移
    def renumber_items(self) -> None:
        """重新編號項目並保持校正狀態"""
        try:
            items = self.tree.get_children()
            if not items:
                return

            # 獲取索引欄位位置
            if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT]:
                index_pos = 1  # 第二欄
            else:  # self.DISPLAY_MODE_SRT, self.DISPLAY_MODE_SRT_WORD
                index_pos = 0  # 第一欄

            self.logger.debug(f"重新編號項目，顯示模式: {self.display_mode}，索引欄位位置: {index_pos}")

            # 創建舊索引到新索引的映射
            index_mapping = {}

            for i, item in enumerate(items, 1):
                if not self.tree.exists(item):
                    continue

                try:
                    values = list(self.tree.item(item)['values'])
                    if not values or len(values) <= index_pos:
                        self.logger.warning(f"項目 {item} 的值列表無效或長度不足，跳過")
                        continue

                    # 獲取當前索引和標籤
                    old_index = str(values[index_pos])
                    tags = list(self.tree.item(item, 'tags') or ())

                    # 更新索引
                    values[index_pos] = str(i)

                    # 更新樹狀視圖，保留原有標籤
                    self.tree.item(item, values=tuple(values), tags=tuple(tags) if tags else ())

                    # 記錄索引映射
                    index_mapping[old_index] = str(i)

                except Exception as e:
                    self.logger.error(f"處理項目 {item} 編號時出錯: {e}")
                    continue

            # 轉移校正狀態 - 使用 correction_service
            if hasattr(self, 'correction_service') and index_mapping:
                self.logger.debug(f"轉移校正狀態，映射: {index_mapping}")
                self.correction_service.transfer_correction_states(index_mapping)

            # 更新 SRT 數據，確保數據與界面同步
            self.update_srt_data_from_treeview()

            # 更新音頻段落的索引
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)
                self.logger.debug("重新編號後更新音頻段落")

            self.logger.info(f"重新編號完成，共處理 {len(items)} 個項目")

        except Exception as e:
            self.logger.error(f"重新編號項目時出錯: {e}")
            # 不向用戶顯示錯誤，靜默失敗

    # 最後，修改 get_current_state 方法，以保存 use_word_text 的狀態
    def get_current_state(self) -> List[Dict[str, Any]]:
        """獲取當前界面狀態，確保保存所有必要信息"""
        state = []

        for item in self.tree.get_children():
            try:
                values = self.tree.item(item, 'values')
                tags = self.tree.item(item, 'tags')
                position = self.tree.index(item)

                # 確保獲得有效的索引
                index_position = 1 if self.display_mode in [self.DISPLAY_MODE_ALL, self.DISPLAY_MODE_AUDIO_SRT] else 0

                if not values or len(values) <= index_position:
                    continue

                index = str(values[index_position])

                # 獲取校正狀態
                correction_info = {}
                if index in self.correction_service.correction_states:
                    correction_info = {
                        'state': self.correction_service.correction_states[index],
                        'original': self.correction_service.original_texts.get(index, ''),
                        'corrected': self.correction_service.corrected_texts.get(index, '')
                    }

                # 構建完整的項目信息
                item_state = {
                    'id': item,
                    'values': values,
                    'tags': tags,
                    'position': position,
                    'use_word_text': self.use_word_text.get(item, False),
                    'correction': correction_info if correction_info else None,
                    'display_mode': self.display_mode  # 保存當前顯示模式
                }

                state.append(item_state)
            except Exception as e:
                self.logger.error(f"獲取項目 {item} 的狀態時出錯: {e}")

        # 按位置排序，確保恢復時順序正確
        state.sort(key=lambda x: x.get('position', 0))

        return state

    def update_status(self, message: Optional[str] = None) -> None:
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



    def undo(self, event=None) -> bool:
        """撤銷操作"""
        if hasattr(self, 'state_manager'):
            # 先保存當前狀態，以便稍後可以恢復
            current_state = self.get_current_state()
            current_correction = self.correction_service.serialize_state()

            # 調用狀態管理器的 undo 方法
            result = self.state_manager.undo()

            # 如果 undo 失敗且當前操作是分割操作，嘗試特殊處理
            if not result:
                current_operation = self.state_manager.get_current_operation()
                if current_operation and current_operation.get('type') == 'split_srt':
                    self.logger.debug("嘗試特殊處理分割操作的撤銷")

                    # 獲取原始狀態
                    original_state = current_operation.get('original_state')
                    original_correction = current_operation.get('original_correction')

                    if original_state:
                        # 嘗試恢復到分割前的狀態
                        self.rebuild_ui_from_state(original_state, original_correction)
                        self.update_status("已撤銷拆分操作")
                        return True

                # 如果上面的恢復嘗試失敗，恢復到當前狀態
                self.rebuild_ui_from_state(current_state, current_correction)

            return result
        return False

    def redo(self, event=None) -> bool:
        """重做操作"""
        if hasattr(self, 'state_manager'):
            # 調用狀態管理器的 redo 方法
            return self.state_manager.redo()
        return False

    def check_display_mode_consistency(self):
        """檢查顯示模式是否與實際狀態一致"""
        expected_mode = None

        if self.srt_imported and self.word_imported and self.audio_imported:
            expected_mode = self.DISPLAY_MODE_ALL
        elif self.srt_imported and self.word_imported:
            expected_mode = self.DISPLAY_MODE_SRT_WORD
        elif self.srt_imported and self.audio_imported:
            expected_mode = self.DISPLAY_MODE_AUDIO_SRT
        elif self.srt_imported:
            expected_mode = self.DISPLAY_MODE_SRT

        self.logger.debug(f"檢查顯示模式：當前={self.display_mode}, 預期={expected_mode}")

        if expected_mode and expected_mode != self.display_mode:
            self.logger.warning(f"顯示模式不一致: 當前={self.display_mode}, 預期={expected_mode}，正在修正...")

            # 保存當前狀態
            current_state = self.get_current_state()

            # 更新顯示模式
            old_mode = self.display_mode
            self.display_mode = expected_mode

            # 需要重新配置樹狀視圖結構
            self.refresh_treeview_structure()

            # 將數據從舊模式轉換為新模式並恢復
            converted_state = []
            for item_data in current_state:
                values = item_data.get('values', [])
                # 調整值以適應新的顯示模式
                adjusted_values = self.adjust_values_for_mode(values, old_mode, expected_mode)

                new_item_data = item_data.copy()
                new_item_data['values'] = adjusted_values
                converted_state.append(new_item_data)

            # 使用轉換後的狀態恢復界面
            self.restore_tree_data(converted_state)

            # 更新相關狀態
            if self.audio_imported and hasattr(self, 'audio_player'):
                self.audio_player.segment_audio(self.srt_data)
                self.logger.info("已重新分割音頻以符合新的顯示模式")

            # 如果有Word比對結果，確保它們與新模式兼容
            if self.word_imported and hasattr(self, 'word_comparison_results') and self.word_comparison_results:
                self.update_display_with_comparison()
                self.logger.info("已更新Word比對顯示以符合新的顯示模式")

            # 更新狀態欄
            self.update_status(f"顯示模式已調整為: {self.get_mode_description(expected_mode)}")

    def refresh_treeview_structure(self) -> None:
        """
        根據當前的顯示模式重新配置 Treeview 結構
        """
        try:
            self.logger.info(f"開始刷新樹狀視圖結構，目標模式: {self.display_mode}")

            # 保存當前樹中的數據
            current_data = []

            for item in self.tree.get_children():
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
            self.tree.delete(*self.tree.get_children())

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

                self.tree.column(col,
                    width=config['width'],
                    stretch=config['stretch'],
                    anchor=config['anchor'])
                self.tree.heading(col, text=col, anchor='center')

            # 恢復數據到樹狀視圖
            old_mode = "any"  # 使用通用模式檢測
            self.restore_tree_data_with_mode(current_data, old_mode, self.display_mode)

            # 綁定窗口大小變化事件
            self.master.bind("<Configure>", self.on_window_resize)

            # 設置標籤樣式
            self.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.tree.tag_configure('use_word_text', background='#00BFFF')  # 淺藍色背景標記使用 Word 文本的項目

            self.logger.info(f"樹狀視圖結構刷新完成，共恢復 {len(current_data)} 項數據")

        except Exception as e:
            self.logger.error(f"刷新 Treeview 結構時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新顯示結構失敗: {str(e)}", self.master)

    def restore_tree_data_with_mode(self, data, source_mode, target_mode):
        """
        根據指定的源模式和目標模式恢復樹狀視圖數據
        :param data: 之前保存的數據列表
        :param source_mode: 源模式
        :param target_mode: 目標模式
        """
        try:
            # 清空當前樹狀視圖
            for item in self.tree.get_children():
                self.tree.delete(item)

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

            self.logger.info(f"已從 {source_mode} 模式恢復 {len(data)} 個項目的數據到 {target_mode} 模式")

        except Exception as e:
            self.logger.error(f"恢復樹狀視圖數據時出錯: {e}", exc_info=True)

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


    def restore_data_to_treeview(self, data) -> None:
        """
        將數據恢復到 Treeview，並根據當前模式調整
        """
        try:
            for values, tags in data:
                # 根據不同模式調整數據
                new_values = self.adjust_values_for_mode(values)

                # 插入調整後的數據
                item_id = self.insert_item('', 'end', values=new_values)

                # 如果有標籤，也恢復
                if tags:
                    # 確保標籤是一個元組
                    if isinstance(tags, list):
                        tags = tuple(tags)
                    elif not isinstance(tags, tuple):
                        tags = (tags,) if tags else tuple()

                    self.tree.item(item_id, tags=tags)

                    # 如果有 use_word_text 標籤，更新 self.use_word_text 字典
                    if 'use_word_text' in tags:
                        self.use_word_text[item_id] = True

        except Exception as e:
            self.logger.error(f"恢復數據到 Treeview 時出錯: {e}", exc_info=True)

    def adjust_values_for_mode(self, values, source_mode, target_mode):
        """
        調整值列表以適應不同的顯示模式
        :param values: 原始值列表
        :param source_mode: 原始顯示模式 ("any" 表示自動檢測)
        :param target_mode: 目標顯示模式
        :return: 調整後的值列表
        """
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
        """清除當前數據"""
        try:
            if hasattr(self, 'state_manager'):
                self.state_manager.clear_states()

            if hasattr(self, 'tree'):
                for item in self.tree.get_children():
                    self.tree.delete(item)

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

            # 清除檔案狀態 - 使用 FileManager 進行清理
            if hasattr(self, 'file_manager'):
                self.file_manager.clear_file_status()

            # 同步本地狀態變數
            self.srt_imported = False
            self.audio_imported = False
            self.word_imported = False
            self.srt_file_path = None
            self.audio_file_path = None
            self.word_file_path = None
            self.srt_data = []

            # 清理音頻資源
            if hasattr(self, 'audio_player'):
                self.audio_player.cleanup()

            # 重置顯示模式
            self.display_mode = self.DISPLAY_MODE_SRT

            # 確保介面一致
            self.refresh_treeview_structure()
            self.update_file_info()
            self.update_status("已清除所有數據")

        except Exception as e:
            self.logger.error(f"清除數據時出錯: {e}")
            show_error("錯誤", f"清除數據失敗: {str(e)}", self.master)