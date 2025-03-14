"""Word文檔集成模組"""

import os
import logging
import tkinter as tk
from tkinter import filedialog

from gui.custom_messagebox import show_info, show_warning, show_error
from services.word_processor import WordProcessor
from utils.text_utils import simplify_to_traditional

class WordIntegration:
    """處理Word文檔相關功能的集成"""

    def __init__(self, parent):
        """
        初始化Word集成
        :param parent: 父物件 (AlignmentGUI 實例)
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

        # 初始化Word處理器
        self.parent.word_processor = WordProcessor()
        self.parent.word_comparison_results = {}

    def import_word_document(self):
        """匯入 Word 文檔"""
        try:
            # 檢查是否已匯入 SRT
            if not self.parent.srt_imported:
                show_warning("警告", "請先匯入 SRT 文件", self.parent.master)
                return

            file_path = filedialog.askopenfilename(
                filetypes=[("Word files", "*.docx")],
                parent=self.parent.master
            )

            if not file_path:
                return

            # 保存當前顯示模式和狀態
            old_mode = self.parent.display_mode
            self.logger.info(f"即將匯入 Word 文檔，匯入前顯示模式: {old_mode}")

            # 保存當前樹狀視圖的狀態（如果需要）
            current_state = None
            if old_mode != self.parent.DISPLAY_MODE_SRT and old_mode != self.parent.DISPLAY_MODE_SRT_WORD:
                current_state = self.parent.state_handling.get_current_state()

            # 載入 Word 文檔
            if self.parent.word_processor.load_document(file_path):
                self.parent.word_imported = True
                self.parent.word_file_path = file_path
                self.logger.info(f"成功載入 Word 文檔: {file_path}")

                # 更新顯示模式 - 這裡我們會根據匯入狀態切換模式
                self.parent.update_display_mode()

                # 更新界面和狀態
                self.parent.update_file_info()
                self.parent.update_status(f"已載入 Word 文檔: {os.path.basename(file_path)}")

                # 如果已有 SRT 數據，執行比對
                if self.parent.srt_data:
                    self.logger.info("執行 SRT 與 Word 文本比對")
                    self.compare_word_with_srt()

                # 通知使用者
                show_info("成功", f"已成功載入 Word 文檔：\n{os.path.basename(file_path)}", self.parent.master)
                return True
            else:
                show_error("錯誤", "無法載入 Word 文檔", self.parent.master)
                return False

        except Exception as e:
            self.logger.error(f"匯入 Word 文檔時出錯: {e}", exc_info=True)
            show_error("錯誤", f"匯入 Word 文檔失敗: {str(e)}", self.parent.master)
            return False

    def compare_word_with_srt(self):
        """比對 SRT 和 Word 文本"""
        try:
            if not self.parent.srt_data or not hasattr(self.parent, 'word_processor') or not self.parent.word_processor.text_content:
                show_warning("警告", "請確保 SRT 和 Word 文件均已加載", self.parent.master)
                return

            # 提取 SRT 文本
            srt_texts = [sub.text for sub in self.parent.srt_data]

            # 比對文本
            self.parent.word_comparison_results = self.parent.word_processor.compare_with_srt(srt_texts)

            # 更新顯示
            self.update_display_with_comparison()

            # 顯示摘要信息
            total_items = len(srt_texts)
            mismatched = sum(1 for result in self.parent.word_comparison_results.values() if not result.get('match', True))

            show_info("比對完成",
                    f"共比對 {total_items} 項字幕\n"
                    f"發現 {mismatched} 項不匹配\n\n"
                    f"不匹配項目以紅色背景標記，差異詳情顯示在 'Match' 欄位",
                    self.parent.master)

            # 更新狀態
            self.parent.update_status(f"已完成 SRT 和 Word 文檔比對: {mismatched}/{total_items} 項不匹配")

            return True

        except Exception as e:
            self.logger.error(f"比對 SRT 和 Word 文檔時出錯: {e}", exc_info=True)
            show_error("錯誤", f"比對失敗: {str(e)}", self.parent.master)
            return False

    def update_display_with_comparison(self):
        """根據比對結果更新顯示"""
        try:
            if not self.parent.word_comparison_results:
                return

            # 備份當前選中和標籤以及值
            selected = self.parent.tree.selection()
            tags_backup = {}
            values_backup = {}
            use_word_backup = self.parent.use_word_text.copy()  # 備份 use_word_text 狀態

            for item in self.parent.tree.get_children():
                tags_backup[item] = self.parent.tree.item(item, 'tags')
                values_backup[item] = self.parent.tree.item(item, 'values')

            # 建立索引到項目ID的映射
            index_to_item = {}
            for item_id, values in values_backup.items():
                try:
                    if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT]:
                        if len(values) > 1:
                            index_to_item[str(values[1])] = item_id
                    else:  # self.display_mode in [self.DISPLAY_MODE_SRT, self.DISPLAY_MODE_SRT_WORD]
                        if values:
                            index_to_item[str(values[0])] = item_id
                except Exception as e:
                    self.logger.error(f"處理項目索引映射時出錯: {e}")

            # 清空樹
            for item in self.parent.tree.get_children():
                self.parent.tree.delete(item)

            # 載入校正數據庫
            corrections = self.parent.correction_handler.load_corrections()

            # 重新載入 SRT 數據，加入比對結果
            for i, sub in enumerate(self.parent.srt_data):
                # 取得比對結果
                comparison = self.parent.word_comparison_results.get(i, {
                    'match': True,
                    'word_text': '',
                    'difference': ''
                })

                # 轉換文本為繁體中文
                text = simplify_to_traditional(sub.text.strip())

                # 檢查校正需求
                corrected_text = self.parent.correction_handler.correct_text(text, corrections)
                needs_correction = corrected_text != text

                # 直接使用原始 Word 文本和差異信息
                match_status = comparison.get('match', True)
                word_text = comparison.get('word_text', '')
                diff_text = comparison.get('difference', '')

                # 準備值 - 根據不同模式創建適當的值列表
                values = self.prepare_values_for_mode(
                    self.parent.display_mode, sub,
                    corrected_text if needs_correction else text,
                    word_text, diff_text, needs_correction
                )

                # 插入到樹狀視圖
                item_id = self.parent.tree_manager.insert_item('', 'end', values=tuple(values))

                # 設置標籤
                tags = []

                # 檢查是否有先前的 use_word_text 設置
                old_item_id = index_to_item.get(str(sub.index))

                # 檢查是否使用 Word 文本
                use_word = False
                if old_item_id in use_word_backup:
                    use_word = use_word_backup[old_item_id]
                    self.parent.use_word_text[item_id] = use_word

                # 如果使用 Word 文本，添加 use_word_text 標籤
                if use_word:
                    tags.append('use_word_text')
                # 否則如果不匹配，添加 mismatch 標籤
                elif not match_status:
                    tags.append('mismatch')

                # 如果需要校正，添加校正標籤
                if needs_correction:
                    self.parent.correction_state_manager.add_correction_state(
                        str(sub.index),
                        text,
                        corrected_text,
                        'correct'
                    )

                # 應用標籤
                if tags:
                    self.parent.tree.item(item_id, tags=tuple(tags))

            # 恢復選中
            if selected:
                for item in selected:
                    if item in self.parent.tree.get_children():
                        self.parent.tree.selection_add(item)

            # 配置標記樣式 - 確保標籤的優先級
            self.parent.tree.tag_configure('mismatch', background='#FFDDDD')  # 淺紅色背景標記不匹配項目
            self.parent.tree.tag_configure("use_word_text", background="#00BFFF")  # 淺藍色背景標記使用 Word 文本的項目

            return True

        except Exception as e:
            self.logger.error(f"更新比對顯示時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新比對顯示失敗: {str(e)}", self.parent.master)
            return False

    def prepare_values_for_mode(self, mode, sub, text, word_text, diff_text, needs_correction):
        """根據顯示模式準備值列表"""
        if mode == self.parent.DISPLAY_MODE_ALL:  # ALL 模式
            return [
                self.parent.PLAY_ICON,
                str(sub.index),
                str(sub.start),
                str(sub.end),
                text,
                word_text,
                diff_text,
                '✅' if needs_correction else ''
            ]
        elif mode == self.parent.DISPLAY_MODE_SRT_WORD:  # SRT_WORD 模式
            return [
                str(sub.index),
                str(sub.start),
                str(sub.end),
                text,
                word_text,
                diff_text,
                '✅' if needs_correction else ''
            ]
        elif mode == self.parent.DISPLAY_MODE_AUDIO_SRT:  # AUDIO_SRT 模式
            return [
                self.parent.PLAY_ICON,
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

    def process_word_edit_result(self, result, item, srt_index):
        """處理 Word 文本編輯結果"""
        try:
            # 獲取當前值
            values = list(self.parent.tree.item(item, 'values'))

            # 保存當前標籤狀態
            tags = self.parent.tree.item(item, 'tags')

            # 獲取 Word 段落索引
            word_index = srt_index - 1

            # 檢查結果類型
            if isinstance(result, list) and len(result) > 0:
                # 檢查是否為斷句結果 (返回的是文本、開始時間、結束時間的列表)
                if isinstance(result[0], tuple) and len(result[0]) >= 3:
                    # 處理 Word 文本斷句
                    self.handle_word_text_split(result, word_index, srt_index, values, item)
                    return
                # 如果只是普通列表，使用第一個元素
                elif len(result) > 0:
                    result = str(result[0])
            # 確保結果是字串
            result = str(result)

            # 更新 Word 文本
            if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                values[5] = result
            elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
                values[4] = result

            # 更新 Word 處理器中的段落
            if hasattr(self.parent, 'word_processor') and word_index >= 0:
                self.parent.word_processor.edit_paragraph(word_index, result)

            # 更新樹狀視圖，保留原有標籤
            self.parent.tree.item(item, values=tuple(values), tags=tags)

            # 標記 Word 欄位被編輯
            i = srt_index - 1
            if i not in self.parent.edited_text_info:
                self.parent.edited_text_info[i] = {'edited': []}

            if 'word' not in self.parent.edited_text_info[i]['edited']:
                self.parent.edited_text_info[i]['edited'].append('word')

            # 保存當前狀態
            self.parent.state_manager.save_state(self.parent.state_handling.get_current_state())
            self.parent.update_status("已更新 Word 文本")

            return True

        except Exception as e:
            self.logger.error(f"更新 Word 文本時出錯: {e}", exc_info=True)
            show_error("錯誤", f"更新文本失敗: {str(e)}", self.parent.master)
            return False

    def handle_word_text_split(self, result, word_index, srt_index, original_values, original_item):
        """處理Word文本的斷句"""
        try:
            # 保存操作前的狀態供撤銷使用
            original_state = self.parent.state_handling.get_current_state()

            # 先獲取項目位置，然後再刪除
            delete_position = self.parent.tree.index(original_item)

            # 儲存原始的標籤狀態
            tags = self.parent.tree.item(original_item, 'tags')

            # 移除不需要的標籤
            if tags and 'mismatch' in tags:
                tags = tuple(tag for tag in tags if tag != 'mismatch')

            # 檢查原始項目的校正狀態
            values = self.parent.tree.item(original_item)['values']
            correction_state = ''
            if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL and len(values) > 7:
                correction_state = values[7]
            elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD and len(values) > 6:
                correction_state = values[6]

            # 取得原始SRT文本
            srt_text = ""
            if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                srt_text = values[4] if len(values) > 4 else ""
            elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
                srt_text = values[3] if len(values) > 3 else ""

            # 從樹狀視圖中刪除原項目
            self.parent.tree.delete(original_item)

            # 載入校正數據庫
            corrections = self.parent.correction_handler.load_corrections()

            # 處理每個分割後的文本段落
            new_items = []
            for i, (text, new_start, new_end) in enumerate(result):
                # 構建用於插入的值列表
                new_values = list(original_values)
                new_srt_index = srt_index + i if i > 0 else srt_index

                # 更新索引、時間和Word文本，但保留校正狀態不變
                if self.parent.display_mode == self.parent.DISPLAY_MODE_ALL:
                    new_values[1] = str(new_srt_index)  # Index
                    new_values[2] = new_start  # Start
                    new_values[3] = new_end    # End

                    # 為第一個段落保留SRT文本，其他段落使用空白字符串但不是None
                    if i > 0:
                        new_values[4] = ""  # 新段落的SRT文本為空白字符串

                    new_values[5] = text  # Word文本
                    new_values[6] = ""  # 清空Match欄位
                    # 不修改校正狀態 (V/X)，保留原始值

                elif self.parent.display_mode == self.parent.DISPLAY_MODE_SRT_WORD:
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
                if self.parent.display_mode in [self.parent.DISPLAY_MODE_ALL, self.parent.DISPLAY_MODE_AUDIO_SRT]:
                    new_values[0] = self.parent.PLAY_ICON

                # 插入新項目
                new_item = self.parent.tree_manager.insert_item('', delete_position + i, values=tuple(new_values))
                new_items.append(new_item)

                # 應用標籤
                if tags:
                    self.parent.tree.item(new_item, tags=tags)

                # 如果這是第一個項目，保存use_word_text狀態
                if i == 0 and original_item in self.parent.use_word_text:
                    self.parent.use_word_text[new_item] = self.parent.use_word_text[original_item]

                # 更新Word處理器中的段落
                if hasattr(self.parent, 'word_processor'):
                    try:
                        # 確保索引有效
                        if i == 0:
                            # 第一個段落更新原有的
                            self.parent.word_processor.edit_paragraph(word_index, text)
                        else:
                            # 後續段落需要添加新段落
                            self.parent.word_processor.split_paragraph(word_index, [text])
                    except Exception as e:
                        self.logger.error(f"更新Word段落時出錯: {e}")

            # 重新編號所有項目
            self.parent.ui_events.renumber_items()

            # 更新音頻段落索引
            if self.parent.audio_imported:
                self.parent.audio_integration.update_audio_segments()

            # 選中新創建的項目
            if new_items:
                self.parent.tree.selection_set(new_items)
                self.parent.tree.see(new_items[0])

            # 更新 SRT 數據以反映變化 - 這是關鍵，確保 SRT 數據與界面同步
            self.parent.state_handling.update_srt_data_from_treeview()

            # 保存當前狀態 - 這裡是關鍵，我們要正確保存當前斷句後的狀態
            current_state = self.parent.state_handling.get_current_state()

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
            if hasattr(self.parent, 'state_manager'):
                self.parent.state_manager.save_state(current_state, operation_info)

            # 更新狀態
            self.parent.update_status("已分割 Word 文本")

            return True

        except Exception as e:
            self.logger.error(f"處理 Word 文本分割時出錯: {e}", exc_info=True)
            show_error("錯誤", f"分割 Word 文本失敗: {str(e)}", self.parent.master)
            return False