"""文本合併服務模組，負責處理字幕合併相關操作"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple


class CombineService:
    """字幕合併服務，處理文本合併相關操作"""

    def __init__(self, alignment_gui):
        """
        初始化合併服務
        :param alignment_gui: 對齊工具實例，用於訪問必要的GUI元素
        """
        self.gui = alignment_gui
        self.logger = logging.getLogger(self.__class__.__name__)
        self.last_combine_operation = None

    def combine_sentences(self, event=None):
        """合併字幕"""
        try:
            # 檢查是否有足夠的選中項
            if not self._validate_combine_selection():
                return

            # 記錄合併前的狀態
            self.logger.info("=== 開始合併字幕 ===")

            # 保存合併前的狀態
            original_state, original_correction, original_items_data, selected_indices = self._prepare_combine_state()

            # 執行實際的合併操作 - 包含所有後續處理
            success, new_item, new_item_index = self._execute_combine(original_items_data, selected_indices)

            if not success:
                return

            # 保存操作後的狀態
            self._save_combine_operation_state(original_state, original_correction, original_items_data, new_item, new_item_index)

            # 隱藏合併符號
            if hasattr(self.gui, 'merge_symbol'):
                self.gui.merge_symbol.place_forget()

            self.gui.update_status("已合併所選字幕")
        except Exception as e:
            self.logger.error(f"合併字幕時出錯: {e}", exc_info=True)
            self.gui.show_error("錯誤", f"合併字幕失敗: {str(e)}")

    def _validate_combine_selection(self) -> bool:
        """驗證是否有足夠的選中項用於合併"""
        if not hasattr(self.gui, 'current_selected_items') or len(self.gui.current_selected_items) < 2:
            self.gui.show_warning("警告", "請選擇至少兩個字幕項目")
            return False
        return True

    def _prepare_combine_state(self) -> tuple:
        """準備合併操作的狀態數據"""
        # 保存操作前的完整狀態
        original_state = self.gui.get_current_state()
        original_correction = self.gui.correction_service.serialize_state()

        # 保存合併前所有選中項目的完整信息
        original_items_data = []
        selected_indices = []  # 記錄要被合併的索引

        # 根據索引排序項目
        sorted_items = sorted(self.gui.current_selected_items, key=self.gui.tree.index)

        # 獲取所有選中項目的詳細信息
        for sel_item in sorted_items:
            values = self.gui.tree.item(sel_item, 'values')
            tags = self.gui.tree.item(sel_item, 'tags')
            position = self.gui.tree.index(sel_item)

            # 獲取索引
            index_pos = 1 if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT] else 0
            item_index = str(values[index_pos]) if len(values) > index_pos else ""
            selected_indices.append(item_index)  # 記錄索引

            # 獲取校正狀態
            correction_info = None
            if item_index and item_index in self.gui.correction_service.correction_states:
                correction_info = {
                    'state': self.gui.correction_service.correction_states[item_index],
                    'original': self.gui.correction_service.original_texts.get(item_index, ''),
                    'corrected': self.gui.correction_service.corrected_texts.get(item_index, '')
                }

            original_items_data.append({
                'id': sel_item,
                'values': values,
                'tags': tags,
                'position': position,
                'use_word': self.gui.use_word_text.get(sel_item, False),
                'correction': correction_info
            })

        # 記錄這是一次合併操作
        self.last_combine_operation = {
            'timestamp': time.time(),
            'original_items_data': original_items_data,
            'display_mode': self.gui.display_mode
        }

        if hasattr(self.gui, 'state_manager') and hasattr(self.gui.state_manager, 'last_combine_operation'):
            self.gui.state_manager.last_combine_operation = self.last_combine_operation

        return original_state, original_correction, original_items_data, selected_indices

    def _execute_combine(self, original_items_data, selected_indices):
        """執行實際的合併操作"""
        try:
            # 使用所有選中的項目進行合併
            selected_items = self.gui.current_selected_items

            # 根據索引排序項目
            sorted_items = sorted(selected_items, key=self.gui.tree.index)

            # 獲取列索引配置
            column_indices = self.gui.get_column_indices_for_current_mode()

            # 第一個項目作為基礎
            base_item = sorted_items[0]
            base_values = list(self.gui.tree.item(base_item, 'values'))
            base_tags = self.gui.tree.item(base_item, 'tags')
            base_position = self.gui.tree.index(base_item)

            # 收集合併前的信息
            all_texts = []
            all_word_texts = []
            for item in sorted_items:
                values = self.gui.tree_manager.get_item_values(item)
                if column_indices['text'] < len(values):
                    all_texts.append(values[column_indices['text']])
                if column_indices['word_text'] is not None and column_indices['word_text'] < len(values):
                    all_word_texts.append(values[column_indices['word_text']])

            # 合併文本
            combined_text = " ".join(text for text in all_texts if text)
            combined_word_text = " ".join(text for text in all_word_texts if text)

            # 獲取時間範圍
            first_start = base_values[column_indices['start']]
            last_item = sorted_items[-1]
            last_values = self.gui.tree.item(last_item, 'values')
            last_end = last_values[column_indices['end']] if column_indices['end'] < len(last_values) else ""

            # 清除被合併項目的校正狀態
            for item_index in selected_indices:
                if item_index and item_index in self.gui.correction_service.correction_states:
                    self.gui.correction_service.remove_correction_state(item_index)
                    self.logger.debug(f"已清除索引 {item_index} 的校正狀態")

            # 檢查合併後的文本是否需要校正
            needs_correction, corrected_text, original_text, _ = self._check_combined_text_correction(combined_text)

            # 刪除所有原始項目
            for item in sorted_items:
                self.gui.tree_manager.delete_item(item)

            # 構建合併後的值
            combined_values = base_values.copy()
            combined_values[column_indices['text']] = combined_text
            combined_values[column_indices['end']] = last_end
            if column_indices['word_text'] is not None:
                combined_values[column_indices['word_text']] = combined_word_text
            if column_indices['match'] is not None:
                combined_values[column_indices['match']] = ""

            # 設置校正圖標
            combined_values[column_indices['vx']] = '✅' if needs_correction else ''

            # 插入新合併項目
            new_item = self.gui.insert_item('', base_position, values=tuple(combined_values))

            # 確定新項目的索引
            if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT]:
                new_item_index = str(combined_values[1])
            else:
                new_item_index = str(combined_values[0])

            # 設置標籤
            if base_tags:
                self.gui.tree.item(new_item, tags=base_tags)

            # 設置校正狀態
            if needs_correction:
                self.gui.correction_service.set_correction_state(
                    new_item_index,
                    original_text,
                    corrected_text,
                    'correct'  # 默認為已校正狀態
                )

            # 更新 SRT 數據
            self.gui.update_srt_data_from_treeview()

            # 更新音頻段落 - 不再使用原始項目
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                # 直接更新整個 SRT 數據的音頻段落
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            # 重新編號
            self.gui.renumber_items()

            # 選中新合併的項目
            self.gui.tree_manager.set_selection(new_item)
            self.gui.tree_manager.select_and_see(new_item)

            return True, new_item, new_item_index

        except Exception as e:
            self.logger.error(f"執行合併操作時出錯: {e}", exc_info=True)
            self.gui.show_error("錯誤", f"合併操作失敗: {str(e)}")
            return False, None, None

    def _check_combined_text_correction(self, text):
        """
        檢查合併後的文本是否需要校正
        """
        # 使用 correction_service 檢查文本是否需要校正
        return self.gui.correction_service.check_text_for_correction(text)

    def _save_combine_operation_state(self, original_state, original_correction, original_items_data, new_item, new_item_index):
        """保存合併操作的狀態"""
        # 獲取當前狀態
        current_state = self.gui.get_current_state()
        current_correction = self.gui.correction_service.serialize_state()

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

        # 保存操作狀態
        self.gui.save_operation_state(
            'combine_sentences',
            '合併字幕',
            {
                'original_state': original_state,
                'original_correction': original_correction,
                'selected_items_details': selected_items_details,
                'new_item': new_item,
                'new_item_index': new_item_index
            }
        )