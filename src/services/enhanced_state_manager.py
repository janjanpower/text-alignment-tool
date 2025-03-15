# 將 AlignmentGUI 的 undo 和 redo 功能完整地整合到 EnhancedStateManager 中

import copy
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from gui.custom_messagebox import show_info, show_warning, show_error


@dataclass
class StateRecord:
    """狀態記錄數據類別"""
    state: Any
    operation: Dict[str, Any]
    timestamp: float
    correction_state: Optional[Dict[str, Any]] = None  # 校正狀態

class EnhancedStateManager:
    """增強狀態管理類別，整合原有 AlignmentGUI 的 undo/redo 功能"""

    def __init__(self, max_states: int = 50) -> None:
        """
        初始化狀態管理器
        :param max_states: 最大狀態數量
        """
        self.states: List[StateRecord] = []
        self.current_state_index: int = -1
        self.last_undo_time: float = 0
        self.undo_counter: int = 0
        self.max_states = max_states
        self.logger = logging.getLogger(self.__class__.__name__)

        # 添加 alignment_gui 屬性，初始值為 None
        self.alignment_gui = None

        # 用於追蹤變更的項目
        self.changed_items: Set[str] = set()

        # 添加回調函數字典
        self.callbacks = {
            'on_state_change': None,
            'on_undo': None,
            'on_redo': None
        }

    def set_callback(self, event_name: str, callback_func) -> None:
        """
        設置回調函數
        :param event_name: 事件名稱
        :param callback_func: 回調函數
        """
        if event_name in self.callbacks:
            self.callbacks[event_name] = callback_func
        else:
            self.logger.warning(f"嘗試設置未知事件 '{event_name}' 的回調")


    def save_state(self, current_state: Any, operation_info: Optional[Dict] = None,
                 correction_state: Optional[Dict] = None) -> None:
        """
        保存新的狀態
        :param current_state: 當前狀態
        :param operation_info: 操作信息（可選）
        :param correction_state: 校正狀態（可選）
        """
        # 如果當前狀態與最後一個狀態相同，不保存
        if (self.current_state_index >= 0 and
            self.current_state_index < len(self.states) and
            self._states_equal(current_state, self.states[self.current_state_index].state)):
            # 但如果校正狀態變更了，仍然要保存
            if correction_state != self.states[self.current_state_index].correction_state:
                self._update_current_state_correction(correction_state)
            return

        # 如果不是在最後一個狀態，刪除之後的狀態
        if self.current_state_index < len(self.states) - 1:
            self.states = self.states[:self.current_state_index + 1]

        # 創建狀態記錄
        state_record = StateRecord(
            state=copy.deepcopy(current_state),
            operation=operation_info or {'type': 'unknown', 'description': 'Unknown operation'},
            timestamp=time.time(),
            correction_state=copy.deepcopy(correction_state) if correction_state else None
        )

        # 添加新狀態
        self.states.append(state_record)

        # 如果超過最大狀態數，刪除最舊的狀態
        if len(self.states) > self.max_states:
            self.states.pop(0)
            self.current_state_index -= 1

        self.current_state_index = len(self.states) - 1
        self.logger.debug(f"保存狀態：索引 {self.current_state_index}")

    def _update_current_state_correction(self, correction_state: Optional[Dict]) -> None:
        """更新當前狀態的校正狀態"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            self.states[self.current_state_index].correction_state = copy.deepcopy(correction_state)
            self.logger.debug(f"更新狀態 {self.current_state_index} 的校正狀態")

    def _states_equal(self, state1: Any, state2: Any) -> bool:
        """
        比較兩個狀態是否相等
        實現簡單的深度比較
        """
        try:
            if isinstance(state1, list) and isinstance(state2, list):
                if len(state1) != len(state2):
                    return False

                for i in range(len(state1)):
                    if i >= len(state2) or not self._states_equal(state1[i], state2[i]):
                        return False
                return True

            elif isinstance(state1, dict) and isinstance(state2, dict):
                if set(state1.keys()) != set(state2.keys()):
                    return False

                for key in state1:
                    if key not in state2 or not self._states_equal(state1[key], state2[key]):
                        return False
                return True

            else:
                return state1 == state2

        except Exception as e:
            self.logger.error(f"比較狀態時出錯: {e}")
            # 比較失敗時視為不相等
            return False

    def get_current_operation(self) -> Optional[Dict[str, Any]]:
        """獲取當前操作的信息"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].operation
        return None

    def get_current_correction_state(self) -> Optional[Dict[str, Any]]:
        """獲取當前狀態的校正狀態"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].correction_state
        return None

    def can_undo(self) -> bool:
        """
        檢查是否可以撤銷
        :return: 是否可以撤銷
        """
        return self.current_state_index > 0

    def can_redo(self) -> bool:
        """
        檢查是否可以重做
        :return: 是否可以重做
        """
        return self.current_state_index < len(self.states) - 1

    def get_previous_operation(self) -> Optional[Dict[str, Any]]:
        """獲取前一個操作的信息"""
        if self.current_state_index > 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index - 1].operation
        return None

    def set_alignment_gui(self, alignment_gui) -> None:
        """設置對 AlignmentGUI 的引用

        :param alignment_gui: AlignmentGUI 實例
        """
        self.alignment_gui = alignment_gui
        self.logger.debug("已設置 AlignmentGUI 引用")

    def rebuild_correction_states_from_ui(self):
        """完全從當前 UI 重建校正狀態"""
        if not hasattr(self, 'alignment_gui'):
            self.logger.error("無法重建校正狀態: alignment_gui 屬性不存在")
            return

        # 清空現有的校正狀態
        self.alignment_gui.correction_service.clear_correction_states()

        # 遍歷所有樹視圖項目
        for item_id in self.alignment_gui.tree.get_children():
            values = self.alignment_gui.tree.item(item_id, 'values')

            # 獲取索引位置
            index_pos = 1 if self.alignment_gui.display_mode in [
                self.alignment_gui.DISPLAY_MODE_ALL,
                self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
            ] else 0

            if len(values) <= index_pos:
                continue  # 跳過無效的值

            item_index = str(values[index_pos])

            # 獲取校正圖標
            correction_mark = values[-1] if values else ''

            if correction_mark in ['✅', '❌']:
                # 確定文本位置
                text_pos = 4 if self.alignment_gui.display_mode in [
                    self.alignment_gui.DISPLAY_MODE_ALL,
                    self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                ] else 3

                if len(values) > text_pos:
                    text = values[text_pos]

                    # 檢查文本是否需要校正
                    needs_correction, corrected_text, original_text, _ = \
                        self.alignment_gui.correction_service.check_text_for_correction(text)

                    if needs_correction:
                        state = 'correct' if correction_mark == '✅' else 'error'
                        self.alignment_gui.correction_service.set_correction_state(
                            item_index,
                            text,  # 原始文本
                            corrected_text,  # 校正後文本
                            state  # 校正狀態
                        )

        # 記錄重建的校正狀態數量
        self.logger.info(f"已從 UI 重建 {len(self.alignment_gui.correction_service.correction_states)} 個校正狀態")

    def verify_state_indices(self):
        """驗證並修正狀態索引"""
        if self.current_state_index < 0:
            self.logger.warning(f"狀態索引 {self.current_state_index} 小於 0，重置為 0")
            self.current_state_index = 0

        if len(self.states) > 0 and self.current_state_index >= len(self.states):
            self.logger.warning(f"狀態索引 {self.current_state_index} 超出範圍，設置為 {len(self.states) - 1}")
            self.current_state_index = len(self.states) - 1


    def undo(self, event=None) -> bool:
        """撤銷操作 - 整合自 AlignmentGUI"""
        try:
            # 驗證狀態索引
            self.verify_state_indices()

            # 調試信息
            self.logger.debug(f"嘗試撤銷: 狀態數量={len(self.states)}, 目前索引={self.current_state_index}")

            # 獲取操作信息
            previous_operation = None
            if self.current_state_index > 0 and self.current_state_index < len(self.states):
                previous_operation = self.states[self.current_state_index].operation
                operation_type = previous_operation.get('type', '') if previous_operation else ''
                self.logger.debug(f"上一操作類型: {operation_type}")

            # 呼叫狀態管理器的撤銷方法
            if not self.can_undo():
                self.logger.debug("無法撤銷：已經是最初狀態")
                if hasattr(self, 'alignment_gui'):
                    self.alignment_gui.update_status("已到達最初狀態，無法再撤銷")
                return False

            # 獲取前一個狀態的索引
            prev_index = self.current_state_index - 1

            # 再次檢查索引有效性
            if prev_index < 0 or prev_index >= len(self.states):
                self.logger.debug(f"無效的前一個狀態索引: {prev_index}")
                return False

            # 獲取前一個狀態
            previous_state = self.states[prev_index].state
            previous_correction = self.states[prev_index].correction_state

            # 然後更新索引
            self.current_state_index = prev_index
            self.last_undo_time = time.time()
            self.undo_counter += 1

            # 清空變更項目集合
            self.changed_items.clear()

            # 下面是整合自 AlignmentGUI 的恢復邏輯
            if hasattr(self, 'alignment_gui'):
                # 清空當前狀態
                self.alignment_gui.tree.delete(*self.alignment_gui.tree.get_children())
                self.alignment_gui.use_word_text.clear()

                # 清空校正狀態
                self.alignment_gui.correction_service.clear_correction_states()

                # 使用集合記錄已處理的索引，避免重複
                processed_indices = set()

                # 專門處理合併操作
                if previous_operation and previous_operation.get('type') == 'combine_sentences':
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        # 從原始合併前的狀態恢復
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                # 獲取索引位置
                                index_pos = 1 if self.alignment_gui.display_mode in [
                                    self.alignment_gui.DISPLAY_MODE_ALL,
                                    self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                                ] else 0

                                if len(values) <= index_pos:
                                    continue  # 跳過無效的值

                                item_index = str(values[index_pos])

                                # 檢查索引是否已處理過，避免重複
                                if item_index in processed_indices:
                                    self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                                    continue

                                processed_indices.add(item_index)

                                item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.alignment_gui.use_word_text[item_id] = True

                        # 重建校正狀態
                        self.rebuild_correction_states_from_ui()

                        # 更新 SRT 數據和音頻
                        self.alignment_gui.update_srt_data_from_treeview()
                        if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                            self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                        # 嘗試選中之前合併的項目
                        if 'items' in previous_operation and previous_operation['items']:
                            try:
                                items_to_select = []
                                for i, item_id in enumerate(self.alignment_gui.tree.get_children()):
                                    if i < len(previous_operation['items']):
                                        items_to_select.append(item_id)

                                if items_to_select:
                                    self.alignment_gui.tree.selection_set(items_to_select)
                                    self.alignment_gui.tree.see(items_to_select[0])
                            except Exception as select_error:
                                self.logger.warning(f"恢復選擇時出錯: {select_error}")

                        self.alignment_gui.update_correction_status_display()
                        self.alignment_gui.update_status("已復原合併字幕操作")
                        return True

                    # 特別處理第一個合併操作
                    elif self.current_state_index == 0:
                        self.logger.info("正在處理第一個合併操作的撤銷")
                        # 如果是第一個操作且為合併操作，嘗試恢復到最初狀態
                        initial_state = self.states[0].state if self.states else None

                        if initial_state:
                            for item_data in initial_state:
                                values = item_data.get('values', [])
                                if values:
                                    # 獲取索引位置
                                    index_pos = 1 if self.alignment_gui.display_mode in [
                                        self.alignment_gui.DISPLAY_MODE_ALL,
                                        self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                                    ] else 0

                                    if len(values) <= index_pos:
                                        continue  # 跳過無效的值

                                    item_index = str(values[index_pos])

                                    # 檢查索引是否已處理過，避免重複
                                    if item_index in processed_indices:
                                        self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                                        continue

                                    processed_indices.add(item_index)

                                    item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                                    # 恢復標籤
                                    if 'tags' in item_data and item_data['tags']:
                                        self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                                    # 恢復 use_word_text 狀態
                                    if item_data.get('use_word_text', False):
                                        self.alignment_gui.use_word_text[item_id] = True

                            # 重建校正狀態
                            self.rebuild_correction_states_from_ui()

                            # 更新 SRT 數據和音頻
                            self.alignment_gui.update_srt_data_from_treeview()
                            if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                                self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                            self.alignment_gui.update_correction_status_display()
                            self.alignment_gui.update_status("已恢復到初始狀態")
                            return True

                # 處理斷句操作
                elif previous_operation and previous_operation.get('type') in ['split_srt', 'split_word_text']:
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                # 獲取索引位置
                                index_pos = 1 if self.alignment_gui.display_mode in [
                                    self.alignment_gui.DISPLAY_MODE_ALL,
                                    self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                                ] else 0

                                if len(values) <= index_pos:
                                    continue  # 跳過無效的值

                                item_index = str(values[index_pos])

                                # 檢查索引是否已處理過，避免重複
                                if item_index in processed_indices:
                                    self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                                    continue

                                processed_indices.add(item_index)

                                item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.alignment_gui.use_word_text[item_id] = True

                        # 重建校正狀態
                        self.rebuild_correction_states_from_ui()

                        # 更新 SRT 數據和音頻
                        self.alignment_gui.update_srt_data_from_treeview()
                        if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                            self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                        # 選中相關項目
                        if 'srt_index' in previous_operation:
                            for item_id in self.alignment_gui.tree.get_children():
                                item_values = self.alignment_gui.tree.item(item_id, 'values')
                                if self.alignment_gui.display_mode in [self.alignment_gui.DISPLAY_MODE_ALL, self.alignment_gui.DISPLAY_MODE_AUDIO_SRT]:
                                    if len(item_values) > 1 and str(item_values[1]) == str(previous_operation['srt_index']):
                                        self.alignment_gui.tree.selection_set(item_id)
                                        self.alignment_gui.tree.see(item_id)
                                        break
                                else:
                                    if item_values and str(item_values[0]) == str(previous_operation['srt_index']):
                                        self.alignment_gui.tree.selection_set(item_id)
                                        self.alignment_gui.tree.see(item_id)
                                        break

                        # 更新校正狀態顯示
                        self.alignment_gui.update_correction_status_display()

                        self.alignment_gui.update_status(f"已復原{previous_operation.get('description', '拆分操作')}")
                        return True

                # 處理時間調整操作
                elif previous_operation and previous_operation.get('type') == 'align_end_times':
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                # 獲取索引位置
                                index_pos = 1 if self.alignment_gui.display_mode in [
                                    self.alignment_gui.DISPLAY_MODE_ALL,
                                    self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                                ] else 0

                                if len(values) <= index_pos:
                                    continue  # 跳過無效的值

                                item_index = str(values[index_pos])

                                # 檢查索引是否已處理過，避免重複
                                if item_index in processed_indices:
                                    self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                                    continue

                                processed_indices.add(item_index)

                                item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.alignment_gui.use_word_text[item_id] = True

                        # 重建校正狀態
                        self.rebuild_correction_states_from_ui()

                        # 更新 SRT 數據和音頻
                        self.alignment_gui.update_srt_data_from_treeview()
                        if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                            self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                        # 更新校正狀態顯示
                        self.alignment_gui.update_correction_status_display()

                        self.alignment_gui.update_status("已復原時間調整操作")
                        return True

                # 處理文本編輯操作
                elif previous_operation and previous_operation.get('type') == 'edit_text':
                    original_state = previous_operation.get('original_state')
                    if original_state:
                        for item_data in original_state:
                            values = item_data.get('values', [])
                            if values:
                                # 獲取索引位置
                                index_pos = 1 if self.alignment_gui.display_mode in [
                                    self.alignment_gui.DISPLAY_MODE_ALL,
                                    self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                                ] else 0

                                if len(values) <= index_pos:
                                    continue  # 跳過無效的值

                                item_index = str(values[index_pos])

                                # 檢查索引是否已處理過，避免重複
                                if item_index in processed_indices:
                                    self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                                    continue

                                processed_indices.add(item_index)

                                item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                                # 恢復標籤
                                if 'tags' in item_data and item_data['tags']:
                                    self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                                # 恢復 use_word_text 狀態
                                if item_data.get('use_word_text', False):
                                    self.alignment_gui.use_word_text[item_id] = True

                        # 重建校正狀態
                        self.rebuild_correction_states_from_ui()

                        # 選中編輯過的項目
                        if 'item_id' in previous_operation:
                            target_index = previous_operation.get('item_index')
                            if target_index:
                                for item_id in self.alignment_gui.tree.get_children():
                                    item_values = self.alignment_gui.tree.item(item_id, 'values')
                                    index_pos = 1 if self.alignment_gui.display_mode in [self.alignment_gui.DISPLAY_MODE_ALL, self.alignment_gui.DISPLAY_MODE_AUDIO_SRT] else 0
                                    if len(item_values) > index_pos and str(item_values[index_pos]) == str(target_index):
                                        self.alignment_gui.tree.selection_set(item_id)
                                        self.alignment_gui.tree.see(item_id)
                                        break

                        # 更新 SRT 數據和音頻
                        self.alignment_gui.update_srt_data_from_treeview()
                        if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                            self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                        # 更新校正狀態顯示
                        self.alignment_gui.update_correction_status_display()

                        self.alignment_gui.update_status("已復原文本編輯操作")
                        return True

                # 非特殊操作的標準恢復流程
                if previous_state:
                    # 從前一個狀態恢復
                    for item_data in previous_state:
                        values = item_data.get('values', [])
                        if values:
                            # 獲取索引位置
                            index_pos = 1 if self.alignment_gui.display_mode in [
                                self.alignment_gui.DISPLAY_MODE_ALL,
                                self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                            ] else 0

                            if len(values) <= index_pos:
                                continue  # 跳過無效的值

                            item_index = str(values[index_pos])

                            # 檢查索引是否已處理過，避免重複
                            if item_index in processed_indices:
                                self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                                continue

                            processed_indices.add(item_index)

                            item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                            # 恢復標籤
                            if 'tags' in item_data and item_data['tags']:
                                self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                            # 恢復 use_word_text 狀態
                            if item_data.get('use_word_text', False):
                                self.alignment_gui.use_word_text[item_id] = True

                    # 恢復校正狀態
                    if previous_correction:
                        self.alignment_gui.correction_service.deserialize_state(previous_correction)

                    # 重建校正狀態以確保一致性
                    self.rebuild_correction_states_from_ui()

                    # 更新校正狀態顯示
                    self.alignment_gui.update_correction_status_display()

                    # 更新 SRT 數據和音頻
                    self.alignment_gui.update_srt_data_from_treeview()
                    if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                        self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                    self.alignment_gui.update_status("已復原上一步操作")
                    return True
                else:
                    self.alignment_gui.update_status("已到達最初狀態，無法再撤銷")
                    return False

            return False

        except Exception as e:
            self.logger.error(f"撤銷操作時出錯: {e}", exc_info=True)
            if hasattr(self, 'alignment_gui'):
                from gui.custom_messagebox import show_error
                show_error("錯誤", f"撤銷失敗: {str(e)}", self.alignment_gui.master)
            return False


    def redo(self, event=None) -> bool:
        """重做操作 - 整合自 AlignmentGUI"""
        try:
            # 驗證狀態索引
            self.verify_state_indices()

            # 檢查是否可以重做
            if not self.can_redo():
                self.logger.debug("無法重做：已經是最新狀態")
                if hasattr(self, 'alignment_gui'):
                    self.alignment_gui.update_status("已到達最新狀態，無法再重做")
                return False

            # 獲取下一個狀態索引
            next_index = self.current_state_index + 1

            # 驗證索引有效性
            if next_index < 0 or next_index >= len(self.states):
                self.logger.error(f"無效的下一個狀態索引: {next_index}")
                return False

            # 獲取下一個狀態
            next_state_record = self.states[next_index]
            next_state = next_state_record.state
            next_correction = next_state_record.correction_state

            # 獲取操作類型，可能需要特殊處理
            operation_type = ""
            if hasattr(next_state_record, 'operation') and next_state_record.operation:
                operation_type = next_state_record.operation.get('type', '')
                self.logger.debug(f"當前重做操作類型: {operation_type}")

            # 更新索引
            self.current_state_index = next_index

            # 清空變更項目集合
            self.changed_items.clear()

            if hasattr(self, 'alignment_gui'):
                # 完全清空現有狀態
                self.alignment_gui.tree.delete(*self.alignment_gui.tree.get_children())
                self.alignment_gui.use_word_text.clear()
                self.alignment_gui.correction_service.clear_correction_states()

                # 使用集合記錄已處理的索引，避免重複
                processed_indices = set()

                # 從下一個狀態恢復所有項目
                for item_data in next_state:
                    values = item_data.get('values', [])
                    if not values:
                        continue

                    # 獲取索引位置
                    index_pos = 1 if self.alignment_gui.display_mode in [
                        self.alignment_gui.DISPLAY_MODE_ALL,
                        self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                    ] else 0

                    if len(values) <= index_pos:
                        continue  # 跳過無效的值

                    item_index = str(values[index_pos])

                    # 檢查索引是否已處理過，避免重複
                    if item_index in processed_indices:
                        self.logger.warning(f"索引 {item_index} 已經處理過，跳過重複項")
                        continue

                    processed_indices.add(item_index)

                    # 插入新項目
                    item_id = self.alignment_gui.insert_item('', 'end', values=tuple(values))

                    # 恢復標籤
                    if 'tags' in item_data and item_data['tags']:
                        self.alignment_gui.tree.item(item_id, tags=item_data['tags'])

                    # 恢復 use_word_text 狀態
                    if item_data.get('use_word_text', False):
                        self.alignment_gui.use_word_text[item_id] = True

                # 恢復校正狀態
                if next_correction:
                    self.alignment_gui.correction_service.deserialize_state(next_correction)

                # 重建校正狀態以確保一致性
                self.rebuild_correction_states_from_ui()

                # 更新校正狀態顯示
                self.alignment_gui.update_correction_status_display()

                # 更新 SRT 數據和音頻
                self.alignment_gui.update_srt_data_from_treeview()
                if self.alignment_gui.audio_imported and hasattr(self.alignment_gui, 'audio_player'):
                    self.alignment_gui.audio_player.segment_audio(self.alignment_gui.srt_data)

                self.alignment_gui.update_status("已重做操作")
                return True

            return False

        except Exception as e:
            self.logger.error(f"重做操作時出錯: {e}", exc_info=True)
            if hasattr(self, 'alignment_gui'):
                from gui.custom_messagebox import show_error
                show_error("錯誤", f"重做失敗: {str(e)}", self.alignment_gui.master)
            return False
    def clear_states(self) -> None:
        """清除所有狀態"""
        self.states.clear()
        self.current_state_index = -1
        self.last_undo_time = 0
        self.undo_counter = 0
        self.changed_items.clear()
        self.logger.debug("清除所有狀態")

    def get_current_state(self) -> Optional[Any]:
        """
        獲取當前狀態
        :return: 當前狀態，如果沒有狀態則返回 None
        """
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].state
        return None

    def get_state_history(self) -> List[Dict[str, Any]]:
        """
        獲取狀態歷史摘要
        :return: 狀態歷史摘要列表
        """
        history = []
        for i, state in enumerate(self.states):
            history.append({
                'index': i,
                'timestamp': state.timestamp,
                'operation_type': state.operation.get('type', 'unknown'),
                'description': state.operation.get('description', ''),
                'is_current': i == self.current_state_index,
                'has_correction': state.correction_state is not None
            })
        return history

    def mark_item_changed(self, item_id: str) -> None:
        """
        標記項目已變更
        :param item_id: 項目標識符
        """
        self.changed_items.add(item_id)

    def is_item_changed(self, item_id: str) -> bool:
        """
        檢查項目是否已變更
        :param item_id: 項目標識符
        :return: 項目是否已變更
        """
        return item_id in self.changed_items

    def clear_changed_items(self) -> None:
        """清除已變更項目集合"""
        self.changed_items.clear()

    def get_changed_items(self) -> Set[str]:
        """
        獲取已變更項目集合
        :return: 已變更項目集合
        """
        return self.changed_items.copy()

    def create_snapshot(self) -> Dict[str, Any]:
        """
        創建當前狀態的快照，用於保存
        :return: 狀態快照
        """
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            current = self.states[self.current_state_index]
            return {
                'state': copy.deepcopy(current.state),
                'operation': copy.deepcopy(current.operation),
                'timestamp': current.timestamp,
                'correction_state': copy.deepcopy(current.correction_state)
                                  if current.correction_state else None
            }
        return {
            'state': None,
            'operation': {'type': 'unknown', 'description': 'No state available'},
            'timestamp': time.time(),
            'correction_state': None
        }

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> bool:
        """
        從快照恢復狀態
        :param snapshot: 狀態快照
        :return: 是否成功恢復
        """
        try:
            # 清除當前狀態
            self.clear_states()

            # 創建新的狀態記錄
            state_record = StateRecord(
                state=copy.deepcopy(snapshot.get('state')),
                operation=copy.deepcopy(snapshot.get('operation',
                             {'type': 'restore', 'description': 'Restored from snapshot'})),
                timestamp=snapshot.get('timestamp', time.time()),
                correction_state=copy.deepcopy(snapshot.get('correction_state'))
            )

            # 添加狀態
            self.states.append(state_record)
            self.current_state_index = 0

            # 通過回調函數恢復 UI 狀態
            if self.callbacks['clear_ui_state']:
                self.callbacks['clear_ui_state']()

            if self.callbacks['restore_ui_state']:
                self.callbacks['restore_ui_state'](state_record.state)

            if self.callbacks['on_correction_restore'] and state_record.correction_state:
                self.callbacks['on_correction_restore'](state_record.correction_state)

            if self.callbacks['update_ui']:
                self.callbacks['update_ui']("已從快照恢復狀態")

            self.logger.info("成功從快照恢復狀態")
            return True

        except Exception as e:
            self.logger.error(f"從快照恢復狀態時出錯: {e}")
            if self.callbacks['on_error']:
                self.callbacks['on_error']("恢復失敗", str(e))
            return False