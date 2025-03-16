# src/services/enhanced_state_manager.py

import copy
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from gui.custom_messagebox import (
    show_info,
    show_warning,
    show_error,
    ask_question
)
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

    def _apply_correction_state(self, correction_state):
        """確保正確應用校正狀態"""
        if not hasattr(self, 'alignment_gui') or not self.alignment_gui:
            self.logger.warning("無法應用校正狀態：alignment_gui 不可用")
            return False

        gui = self.alignment_gui

        if not hasattr(gui, 'correction_service'):
            self.logger.warning("無法應用校正狀態：correction_service 不可用")
            return False

        try:
            # 先清除現有校正狀態
            gui.correction_service.clear_correction_states()

            # 如果沒有校正狀態，只清除即可
            if not correction_state:
                self.logger.debug("沒有校正狀態需要應用")
                return True

            # 使用反序列化方法應用校正狀態
            gui.correction_service.deserialize_state(correction_state)

            # 主動更新顯示 - 這是關鍵步驟
            gui.update_correction_status_display()

            # 日誌記錄已應用的校正狀態數量
            self.logger.debug(f"已應用 {len(correction_state)} 個校正狀態")

            return True
        except Exception as e:
            self.logger.error(f"應用校正狀態時出錯: {e}", exc_info=True)
            return False

    def save_state(self, current_state: Any, operation_info: Optional[Dict] = None,
             correction_state: Optional[Dict] = None) -> None:
        """
        保存新的狀態
        :param current_state: 當前狀態
        :param operation_info: 操作信息（可選）
        :param correction_state: 校正狀態（可選）
        """
        # 深拷貝當前狀態和校正狀態，確保不會被後續操作修改
        copied_state = copy.deepcopy(current_state)

        # 如果未提供校正狀態，但 alignment_gui 可用，從中獲取
        if correction_state is None and hasattr(self, 'alignment_gui') and self.alignment_gui:
            if hasattr(self.alignment_gui, 'correction_service'):
                correction_state = self.alignment_gui.correction_service.serialize_state()

        copied_correction = copy.deepcopy(correction_state)

        # 如果當前狀態索引小於狀態列表長度-1，刪除後面的狀態
        if self.current_state_index < len(self.states) - 1:
            self.states = self.states[:self.current_state_index + 1]

        # 創建狀態記錄
        state_record = StateRecord(
            state=copied_state,
            operation=operation_info or {'type': 'unknown', 'description': 'Unknown operation'},
            timestamp=time.time(),
            correction_state=copied_correction
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
        """設置對 AlignmentGUI 的引用"""
        self.alignment_gui = alignment_gui
        self.logger.debug("已設置 AlignmentGUI 引用")

    def verify_state_indices(self):
        """驗證並修正狀態索引"""
        if self.current_state_index < 0:
            self.logger.warning(f"狀態索引 {self.current_state_index} 小於 0，重置為 0")
            self.current_state_index = 0

        if len(self.states) > 0 and self.current_state_index >= len(self.states):
            self.logger.warning(f"狀態索引 {self.current_state_index} 超出範圍，設置為 {len(self.states) - 1}")
            self.current_state_index = len(self.states) - 1

    def _clear_current_ui_state(self):
        """清理當前界面狀態"""
        if not hasattr(self, 'alignment_gui') or self.alignment_gui is None:
            return

        # 清空樹狀視圖
        for item in self.alignment_gui.tree.get_children():
            self.alignment_gui.tree.delete(item)

        # 清空 use_word_text 字典
        self.alignment_gui.use_word_text.clear()

        # 清空校正狀態
        self.alignment_gui.correction_service.clear_correction_states()

    # 在 undo/redo 方法中，確保完整重建 UI 和校正狀態
    def _restore_state_to_ui(self, state, correction_state=None):
        """完整重建 UI 和狀態"""
        if not hasattr(self, 'alignment_gui') or self.alignment_gui is None:
            return

        gui = self.alignment_gui

        # 1. 先完全清空當前狀態
        gui.clear_current_ui_state()  # 確保此方法清除所有相關狀態

        # 2. 恢復樹狀視圖
        for item_data in state:
            values = item_data.get('values', [])
            position = item_data.get('position', 'end')

            # 插入新項目
            new_id = gui.insert_item('', position, values=tuple(values))

            # 恢復標籤
            tags = item_data.get('tags')
            if tags:
                gui.tree.item(new_id, tags=tags)

            # 恢復 use_word_text 狀態
            if item_data.get('use_word_text', False):
                gui.use_word_text[new_id] = True

        # 3. 恢復校正狀態 - 這是關鍵
        if correction_state:
            gui.correction_service.deserialize_state(correction_state)

        # 4. 更新介面顯示
        gui.update_correction_status_display()  # 確保此方法正確反映校正狀態

        # 5. 更新底層數據
        gui.update_srt_data_from_treeview()

        # 6. 更新音頻段落
        if gui.audio_imported and hasattr(gui, 'audio_player'):
            gui.audio_player.segment_audio(gui.srt_data)

    # 在關鍵操作（如分割、合併、切換校正狀態）後，保存完整的狀態快照
    def save_complete_state(self, operation_type, description, **extra_info):
        # 獲取完整的介面狀態
        ui_state = self.get_current_state()

        # 獲取完整的校正狀態
        correction_state = self.correction_service.serialize_state()

        # 創建操作信息
        operation_info = {
            'type': operation_type,
            'description': description,
            'timestamp': time.time(),
            'display_mode': self.display_mode,
            **extra_info
        }

        # 保存狀態
        self.state_manager.save_state(ui_state, operation_info, correction_state)

        self.logger.debug(f"已保存完整狀態: {operation_type}")

    def _try_select_items(self, item_ids):
        """嘗試選中指定的項目列表"""
        if not hasattr(self, 'alignment_gui') or self.alignment_gui is None:
            return

        try:
            items_to_select = []
            all_items = self.alignment_gui.tree.get_children()

            # 確保不超出範圍
            for i, item_id in enumerate(item_ids):
                if i < len(all_items):
                    items_to_select.append(all_items[i])

            if items_to_select:
                self.alignment_gui.tree.selection_set(items_to_select)
                self.alignment_gui.tree.see(items_to_select[0])
        except Exception as e:
            self.logger.warning(f"選中項目時出錯: {e}")

    def _try_select_item_by_index(self, index):
        """嘗試根據索引選中項目"""
        if not hasattr(self, 'alignment_gui') or self.alignment_gui is None:
            return

        try:
            for item_id in self.alignment_gui.tree.get_children():
                values = self.alignment_gui.tree.item(item_id, 'values')

                # 根據不同顯示模式獲取索引
                idx_pos = 1 if self.alignment_gui.display_mode in [
                    self.alignment_gui.DISPLAY_MODE_ALL,
                    self.alignment_gui.DISPLAY_MODE_AUDIO_SRT
                ] else 0

                if len(values) > idx_pos and str(values[idx_pos]) == str(index):
                    self.alignment_gui.tree.selection_set(item_id)
                    self.alignment_gui.tree.see(item_id)
                    break
        except Exception as e:
            self.logger.warning(f"根據索引選中項目時出錯: {e}")

    def _handle_special_operation_undo(self, operation):
        """處理特殊操作的撤銷"""
        operation_type = operation.get('type', '')

        # 依據操作類型進行特殊處理
        if operation_type == 'toggle_correction':
            # 獲取操作信息
            item_id = operation.get('item_id')
            display_index = operation.get('display_index')
            previous_mark = operation.get('previous_mark')

            # 如果有實際的項目，嘗試反轉圖標狀態
            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                gui = self.alignment_gui

                # 嘗試找到對應的項目
                for current_item in gui.tree.get_children():
                    values = gui.tree.item(current_item, 'values')

                    # 根據顯示模式確定索引位置
                    index_pos = 1 if gui.display_mode in [
                        gui.DISPLAY_MODE_ALL,
                        gui.DISPLAY_MODE_AUDIO_SRT
                    ] else 0

                    if len(values) > index_pos and str(values[index_pos]) == str(display_index):
                        # 找到對應項目，恢復圖標
                        current_values = list(values)
                        current_values[-1] = previous_mark

                        # 更新樹狀視圖
                        gui.tree.item(current_item, values=tuple(current_values))

                        # 確保選擇該項目
                        gui.tree.selection_set(current_item)
                        gui.tree.see(current_item)
                        break

        elif operation_type == 'combine_sentences':
            # 可能需要選中被合併的項目
            if 'items' in operation:
                self._try_select_items(operation['items'])

        elif operation_type in ['split_srt', 'split_word_text']:
            # 可能需要選中被分割的項目
            if 'srt_index' in operation:
                self._try_select_item_by_index(operation['srt_index'])

        elif operation_type == 'edit_text':
            # 可能需要選中被編輯的項目
            if 'item_index' in operation:
                self._try_select_item_by_index(operation['item_index'])

    def _handle_special_operation_redo(self, operation):
        """處理特殊操作的重做"""
        operation_type = operation.get('type', '')

        # 在重做時，通常不需要特別處理，因為重做是按照當前狀態直接恢復
        # 但如果有需要，可以在這裡添加特殊處理邏輯

    # 在 EnhancedStateManager 類中添加的輔助方法

    def _undo_split_operation(self, operation, previous_state, previous_correction):
        """專門處理分割操作的撤銷"""
        if not hasattr(self, 'alignment_gui') or not self.alignment_gui:
            self.logger.error("無法執行撤銷分割：alignment_gui 不可用")
            return False

        gui = self.alignment_gui

        try:
            # 1. 從操作信息中獲取原始狀態
            original_state = operation.get('original_state')

            if not original_state and previous_state:
                # 如果沒有特殊保存的原始狀態，使用前一個狀態
                original_state = previous_state

            if not original_state:
                self.logger.error("無法找到分割前的狀態")
                return False

            # 2. 完全清空當前樹狀視圖
            for item in gui.tree.get_children():
                gui.tree.delete(item)

            # 3. 清空相關狀態
            gui.use_word_text.clear()
            gui.correction_service.clear_correction_states()

            # 4. 從保存的狀態重建樹狀視圖
            for item_data in original_state:
                values = item_data.get('values', [])
                position = item_data.get('position', 'end')

                # 插入項目
                new_id = gui.insert_item('', position, values=tuple(values))

                # 恢復標籤
                tags = item_data.get('tags')
                if tags:
                    gui.tree.item(new_id, tags=tags)

                # 恢復 use_word_text 狀態
                if item_data.get('use_word', False):
                    gui.use_word_text[new_id] = True

            # 5. 嘗試選中原被分割的項目
            split_item_details = operation.get('split_item_details', {})
            if split_item_details:
                position = split_item_details.get('position')
                if position is not None:
                    try:
                        all_items = gui.tree.get_children()
                        if 0 <= position < len(all_items):
                            gui.tree.selection_set(all_items[position])
                            gui.tree.see(all_items[position])
                    except Exception as e:
                        self.logger.error(f"選中原始項目時出錯: {e}")

            # 6. 恢復校正狀態
            if previous_correction:
                gui.correction_service.deserialize_state(previous_correction)

            # 7. 更新 SRT 數據
            gui.update_srt_data_from_treeview()

            # 8. 更新音頻段落
            if gui.audio_imported and hasattr(gui, 'audio_player'):
                gui.audio_player.segment_audio(gui.srt_data)

            # 9. 更新校正狀態顯示
            gui.update_correction_status_display()

            # 10. 更新狀態欄
            gui.update_status("已復原拆分操作")

            return True

        except Exception as e:
            self.logger.error(f"撤銷分割操作時出錯: {e}", exc_info=True)
            return False

    def _undo_combine_operation(self, operation, previous_state, previous_correction):
        """處理合併操作的撤銷"""
        if not hasattr(self, 'alignment_gui') or not self.alignment_gui:
            return False

        gui = self.alignment_gui

        try:
            # 從操作信息中獲取原始狀態
            original_state = operation.get('original_state')

            if not original_state and previous_state:
                # 如果沒有特殊保存的原始狀態，使用前一個狀態
                original_state = previous_state

            if not original_state:
                self.logger.error("無法找到合併前的狀態")
                return False

            # 完全清空當前樹狀視圖
            for item in gui.tree.get_children():
                gui.tree.delete(item)

            # 清空相關狀態
            gui.use_word_text.clear()
            gui.correction_service.clear_correction_states()

            # 重建樹狀視圖
            for item_data in original_state:
                values = item_data.get('values', [])
                position = item_data.get('position', 'end')

                # 插入項目
                new_id = gui.insert_item('', position, values=tuple(values))

                # 恢復標籤
                tags = item_data.get('tags')
                if tags:
                    gui.tree.item(new_id, tags=tags)

                # 恢復 use_word_text 狀態
                if item_data.get('use_word', False):
                    gui.use_word_text[new_id] = True

            # 恢復校正狀態
            if previous_correction:
                gui.correction_service.deserialize_state(previous_correction)

            # 更新 SRT 數據
            gui.update_srt_data_from_treeview()

            # 更新音頻段落
            if gui.audio_imported and hasattr(gui, 'audio_player'):
                gui.audio_player.segment_audio(gui.srt_data)

            # 更新校正狀態顯示
            gui.update_correction_status_display()

            # 更新狀態欄
            gui.update_status("已復原合併操作")

            return True

        except Exception as e:
            self.logger.error(f"撤銷合併操作時出錯: {e}", exc_info=True)
            return False

    def _undo_normal_operation(self, previous_state, previous_correction):
        """處理一般操作的撤銷"""
        if not hasattr(self, 'alignment_gui') or not self.alignment_gui:
            return False

        gui = self.alignment_gui

        try:
            # 清空當前樹狀視圖
            for item in gui.tree.get_children():
                gui.tree.delete(item)

            # 清空相關狀態
            gui.use_word_text.clear()
            gui.correction_service.clear_correction_states()

            # 從前一個狀態恢復
            for item_data in previous_state:
                values = item_data.get('values', [])
                position = item_data.get('position', 'end')

                # 插入項目
                new_id = gui.insert_item('', position, values=tuple(values))

                # 恢復標籤
                tags = item_data.get('tags')
                if tags:
                    gui.tree.item(new_id, tags=tags)

                # 恢復 use_word_text 狀態
                if item_data.get('use_word_text', False):
                    gui.use_word_text[new_id] = True

            # 恢復校正狀態
            if previous_correction:
                gui.correction_service.deserialize_state(previous_correction)

            # 更新 SRT 數據
            gui.update_srt_data_from_treeview()

            # 更新音頻段落
            if gui.audio_imported and hasattr(gui, 'audio_player'):
                gui.audio_player.segment_audio(gui.srt_data)

            # 更新校正狀態顯示
            gui.update_correction_status_display()

            # 更新狀態欄
            gui.update_status("已復原操作")

            return True

        except Exception as e:
            self.logger.error(f"撤銷一般操作時出錯: {e}", exc_info=True)
            return False

    def undo(self, event=None) -> bool:
        """撤銷操作"""
        try:
            # 驗證狀態索引
            self.verify_state_indices()

            # 檢查是否可以撤銷
            if not self.can_undo():
                if hasattr(self, 'alignment_gui'):
                    self.alignment_gui.update_status("已到達最初狀態，無法再撤銷")
                return False

            # 獲取當前操作信息，用於特殊處理
            current_operation = None
            if self.current_state_index >= 0 and self.current_state_index < len(self.states):
                current_operation = self.states[self.current_state_index].operation

            # 獲取前一個狀態
            prev_index = self.current_state_index - 1

            if prev_index < 0 or prev_index >= len(self.states):
                self.logger.error(f"無效的前一個狀態索引: {prev_index}")
                return False

            # 獲取前一個狀態
            previous_state = self.states[prev_index].state
            previous_correction = self.states[prev_index].correction_state

            # 更新索引
            self.current_state_index = prev_index
            self.last_undo_time = time.time()
            self.undo_counter += 1

            # 清空變更項目集合
            self.changed_items.clear()

            # 保存可見性狀態，以便恢復
            visible_item, visible_y = None, None
            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                visible_item, visible_y = self._save_scroll_position()

            # 處理特殊操作類型
            operation_type = current_operation.get('type', '') if current_operation else ''

            if operation_type == 'split_srt':
                result = self._undo_split_operation(current_operation, previous_state, previous_correction)
            elif operation_type == 'combine_sentences':
                result = self._undo_combine_operation(current_operation, previous_state, previous_correction)
            else:
                # 普通操作的撤銷
                result = self._undo_normal_operation(previous_state, previous_correction)

            # 恢復滾動位置
            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                self._restore_scroll_position(visible_y, visible_item)

            # 處理特殊操作的額外邏輯
            if result and current_operation:
                self._handle_special_operation_undo(current_operation)

            # 更新狀態
            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                self.alignment_gui.update_status("已撤銷操作")

            return result

        except Exception as e:
            self.logger.error(f"撤銷操作時出錯: {e}", exc_info=True)
            if hasattr(self, 'alignment_gui'):
                show_error("錯誤", f"撤銷失敗: {str(e)}", self.alignment_gui.master)
            return False

    def _save_scroll_position(self):
        """保存滾動位置狀態"""
        try:
            gui = self.alignment_gui
            if not gui or not hasattr(gui, 'tree'):
                return None, None

            current_selection = gui.tree.selection()
            visible_item = None
            if current_selection:
                visible_item = current_selection[0]
            else:
                # 如果沒有選中項，獲取可見區域中的第一個項目
                visible_items = gui.tree.identify_row(10)  # 嘗試獲取頂部附近的項目
                if visible_items:
                    visible_item = visible_items

            # 如果找到了可見項目，獲取其Y坐標
            visible_y = None
            if visible_item:
                bbox = gui.tree.bbox(visible_item)
                if bbox:
                    visible_y = bbox[1]  # Y坐標

            return visible_item, visible_y

        except Exception as e:
            self.logger.error(f"保存滾動位置時出錯: {e}")
            return None, None

    def _restore_scroll_position(self, y_position, reference_item=None):
        """嘗試恢復滾動位置"""
        try:
            gui = self.alignment_gui
            if not gui or not hasattr(gui, 'tree'):
                return

            if reference_item and gui.tree.exists(reference_item):
                # 如果引用項目仍然存在，直接使其可見
                gui.tree.see(reference_item)
            elif y_position is not None:
                # 嘗試找到類似位置的項目
                for item in gui.tree.get_children():
                    bbox = gui.tree.bbox(item)
                    if bbox and abs(bbox[1] - y_position) < 30:  # 接近原始Y坐標
                        gui.tree.see(item)
                        break
        except Exception as e:
            self.logger.error(f"恢復滾動位置時出錯: {e}")

    def redo(self, event=None) -> bool:
        """重做操作"""
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

            # 保存滾動位置
            visible_item, visible_y = None, None
            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                visible_item, visible_y = self._save_scroll_position()

            # 獲取下一個狀態
            next_state = self.states[next_index].state
            next_correction = self.states[next_index].correction_state
            next_operation = self.states[next_index].operation

            # 更新索引
            self.current_state_index = next_index

            # 清空變更項目集合
            self.changed_items.clear()

            # 操作類型特殊處理
            operation_type = next_operation.get('type', '') if next_operation else ''

            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                gui = self.alignment_gui

                # 完全清空當前樹狀視圖
                for item in gui.tree.get_children():
                    gui.tree.delete(item)

                # 清空相關狀態
                gui.use_word_text.clear()
                gui.correction_service.clear_correction_states()

                # 恢復下一個狀態
                for item_data in next_state:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')

                    # 插入項目
                    new_id = gui.insert_item('', position, values=tuple(values))

                    # 恢復標籤
                    tags = item_data.get('tags')
                    if tags:
                        gui.tree.item(new_id, tags=tags)

                    # 恢復 use_word_text 狀態
                    if item_data.get('use_word_text', False):
                        gui.use_word_text[new_id] = True

                # 恢復校正狀態
                if next_correction:
                    gui.correction_service.deserialize_state(next_correction)

                # 更新 SRT 數據
                gui.update_srt_data_from_treeview()

                # 更新音頻段落
                if gui.audio_imported and hasattr(gui, 'audio_player'):
                    gui.audio_player.segment_audio(gui.srt_data)

                # 更新校正狀態顯示
                gui.update_correction_status_display()

                # 恢復滾動位置
                self._restore_scroll_position(visible_y, visible_item)

                # 如果是特殊操作，可能需要額外的處理
                if operation_type in ['combine_sentences', 'split_srt', 'split_word_text', 'edit_text', 'align_end_times']:
                    self._handle_special_operation_redo(next_operation)

                gui.update_status("已重做操作")
                return True

            return False

        except Exception as e:
            self.logger.error(f"重做操作時出錯: {e}", exc_info=True)
            if hasattr(self, 'alignment_gui'):
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
        """獲取當前狀態"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].state
        return None

    def get_state_history(self) -> List[Dict[str, Any]]:
        """獲取狀態歷史摘要"""
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
        """標記項目已變更"""
        self.changed_items.add(item_id)

    def is_item_changed(self, item_id: str) -> bool:
        """檢查項目是否已變更"""
        return item_id in self.changed_items

    def clear_changed_items(self) -> None:
        """清除已變更項目集合"""
        self.changed_items.clear()

    def get_changed_items(self) -> Set[str]:
        """獲取已變更項目集合"""
        return self.changed_items.copy()

    def create_snapshot(self) -> Dict[str, Any]:
        """創建當前狀態的快照，用於保存"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            current = self.states[self.current_state_index]
            # 接續前面的 create_snapshot 方法
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
            if hasattr(self, 'alignment_gui') and self.alignment_gui:
                # 清理當前 UI 狀態
                self._clear_current_ui_state()

                # 恢復狀態
                self._restore_state_to_ui(state_record.state, state_record.correction_state)

                self.alignment_gui.update_status("已從快照恢復狀態")

            self.logger.info("成功從快照恢復狀態")
            return True

        except Exception as e:
            self.logger.error(f"從快照恢復狀態時出錯: {e}")
            if hasattr(self, 'alignment_gui'):
                show_error("錯誤", f"從快照恢復失敗: {str(e)}", self.alignment_gui.master)
            return False

    def rebuild_correction_states_from_ui(self):
        """完全從當前 UI 重建校正狀態"""
        if not hasattr(self, 'alignment_gui') or not self.alignment_gui:
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

    def handle_text_split_operation(self, operation, is_undo=True):
        """專門處理文本拆分操作的撤銷/重做

        Args:
            operation: 操作信息
            is_undo: 是否是撤銷操作

        Returns:
            bool: 處理是否成功
        """
        if not hasattr(self, 'alignment_gui') or not self.alignment_gui:
            return False

        gui = self.alignment_gui

        try:
            if is_undo:
                # 撤銷文本拆分
                # 獲取原始狀態
                original_state = operation.get('original_state')
                original_correction = operation.get('original_correction')

                if not original_state:
                    self.logger.error("無法撤銷：找不到原始狀態")
                    return False

                # 從原始狀態恢復
                return self._restore_state_fully(original_state, original_correction)
            else:
                # 重做文本拆分
                # 獲取結果狀態
                current_state = self.states[self.current_state_index].state
                current_correction = self.states[self.current_state_index].correction_state

                if not current_state:
                    self.logger.error("無法重做：找不到結果狀態")
                    return False

                # 從結果狀態恢復
                return self._restore_state_fully(current_state, current_correction)

        except Exception as e:
            self.logger.error(f"處理文本拆分操作時出錯: {e}", exc_info=True)
            return False

    def _restore_state_fully(self, state, correction_state):
        """完整恢復狀態，包括樹視圖和校正狀態"""
        gui = self.alignment_gui

        # 清空當前樹狀視圖
        for item in gui.tree.get_children():
            gui.tree.delete(item)

        # 清空相關狀態
        gui.use_word_text.clear()
        gui.correction_service.clear_correction_states()

        # 恢復樹狀視圖項目
        for item_data in state:
            values = item_data.get('values', [])
            position = item_data.get('position', 'end')

            # 插入項目
            new_id = gui.insert_item('', position, values=tuple(values))

            # 恢復標籤
            tags = item_data.get('tags')
            if tags:
                gui.tree.item(new_id, tags=tags)

            # 恢復 use_word_text 狀態
            if item_data.get('use_word_text', False):
                gui.use_word_text[new_id] = True

        # 恢復校正狀態
        if correction_state:
            gui.correction_service.deserialize_state(correction_state)

        # 更新 SRT 數據
        gui.update_srt_data_from_treeview()

        # 更新音頻段落
        if gui.audio_imported and hasattr(gui, 'audio_player'):
            gui.audio_player.segment_audio(gui.srt_data)

        # 更新校正狀態顯示
        gui.update_correction_status_display()

        return True