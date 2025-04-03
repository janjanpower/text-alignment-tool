"""增強狀態管理模組"""

import copy
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
import pysrt

@dataclass
class StateRecord:
    """狀態記錄數據類別"""
    state: Dict[str, Any]  # 樹狀視圖和應用狀態
    operation: Dict[str, Any]  # 操作信息
    timestamp: float  # 時間戳
    correction_state: Optional[Dict[str, Any]] = None  # 校正狀態
    display_mode: Optional[str] = None  # 顯示模式

class ApplicationState:
    """完整的應用狀態模型"""

    def __init__(self):
        self.tree_items = []  # 樹狀視圖項目
        self.display_mode = None  # 顯示模式
        self.srt_data = []  # SRT數據
        self.correction_states = {}  # 校正狀態
        self.use_word_flags = {}  # 使用Word文本的標記

    def from_current_state(self, alignment_gui):
        """從當前應用狀態創建狀態對象"""
        # 收集樹狀視圖數據
        self.tree_items = []
        for item in alignment_gui.tree.get_children():
            values = alignment_gui.tree.item(item, 'values')
            tags = alignment_gui.tree.item(item, 'tags')
            use_word = alignment_gui.use_word_text.get(item, False)

            # 獲取索引值
            index_position = 1 if alignment_gui.display_mode in [alignment_gui.DISPLAY_MODE_ALL, alignment_gui.DISPLAY_MODE_AUDIO_SRT] else 0
            index = str(values[index_position]) if len(values) > index_position else ""

            self.tree_items.append({
                'values': values,
                'tags': tags,
                'position': alignment_gui.tree.index(item),
                'index': index,
                'use_word': use_word
            })

            # 保存使用Word文本標記
            if use_word:
                self.use_word_flags[index] = True

        # 保存其他狀態
        self.display_mode = alignment_gui.display_mode
        self.srt_data = alignment_gui.get_serialized_srt_data()

        # 保存校正狀態
        if hasattr(alignment_gui, 'correction_service'):
            self.correction_states = alignment_gui.correction_service.serialize_state()

        return self

    def apply_to(self, alignment_gui):
        """將狀態應用到應用程序"""
        # 首先清空當前狀態
        alignment_gui.clear_current_state()

        # 設置顯示模式
        if self.display_mode != alignment_gui.display_mode:
            alignment_gui.display_mode = self.display_mode
            alignment_gui.refresh_treeview_structure()

        # 恢復SRT數據
        if self.srt_data:
            alignment_gui.restore_srt_data(self.srt_data)

        # 恢復樹狀視圖
        for item_data in self.tree_items:
            values = item_data.get('values', [])
            position = item_data.get('position', 'end')
            tags = item_data.get('tags')
            use_word = item_data.get('use_word', False)

            # 插入項目
            new_id = alignment_gui.insert_item('', position, values=tuple(values))

            # 恢復標籤
            if tags:
                alignment_gui.tree.item(new_id, tags=tags)

            # 恢復使用Word文本標記
            if use_word:
                alignment_gui.use_word_text[new_id] = True

        # 恢復校正狀態
        if self.correction_states and hasattr(alignment_gui, 'correction_service'):
            alignment_gui.correction_service.deserialize_state(self.correction_states)

        # 更新音頻段落
        if alignment_gui.audio_imported and hasattr(alignment_gui, 'audio_player'):
            alignment_gui.audio_player.segment_audio(alignment_gui.srt_data)

class EnhancedStateManager:
    """增強狀態管理類別，提供狀態保存、撤銷和重做功能"""

    def __init__(self, max_states=50):
        self.states = []  # 狀態列表
        self.current_index = -1  # 當前狀態索引
        self.max_states = max_states
        self.logger = logging.getLogger(self.__class__.__name__)
        self.callbacks = {
            'on_state_change': None,
            'on_undo': None,
            'on_redo': None
        }

        # 添加對特殊操作的追蹤
        self.last_split_operation = None
        self.last_combine_operation = None
        self.last_time_adjust_operation = None

        # 存儲對 GUI 的引用，使其能操作實際的界面元素
        self.gui = None

    def set_gui_reference(self, gui):
        """設置對 GUI 的引用，使狀態管理器能夠操作界面元素"""
        self.gui = gui

    def set_callback(self, event_name: str, callback_func: Callable) -> None:
        """
        設置回調函數
        :param event_name: 事件名稱
        :param callback_func: 回調函數
        """
        if event_name in self.callbacks:
            self.callbacks[event_name] = callback_func
        else:
            self.logger.warning(f"嘗試設置未知事件 '{event_name}' 的回調")

    def trigger_callback(self, event_name: str, *args, **kwargs) -> None:
        """
        觸發回調函數
        :param event_name: 事件名稱
        :param args: 位置參數
        :param kwargs: 關鍵字參數
        """
        if event_name in self.callbacks and callable(self.callbacks[event_name]):
            try:
                self.callbacks[event_name](*args, **kwargs)
            except Exception as e:
                self.logger.error(f"執行 '{event_name}' 回調時出錯: {e}")
        else:
            self.logger.debug(f"未找到事件 '{event_name}' 的回調或回調不可調用")

    def save_state(self, current_state: Dict[str, Any], operation_info: Dict[str, Any],
              correction_state: Optional[Dict[str, Any]] = None) -> None:
        """
        保存應用狀態
        :param current_state: 當前狀態
        :param operation_info: 操作信息
        :param correction_state: 校正狀態
        """
        try:
            # 深拷貝當前狀態和校正狀態，確保不會被後續操作修改
            copied_state = copy.deepcopy(current_state)
            copied_correction = copy.deepcopy(correction_state)
            copied_operation = copy.deepcopy(operation_info or {'type': 'unknown', 'description': 'Unknown operation'})

            # 如果當前狀態索引小於狀態列表長度-1，刪除後面的狀態
            if self.current_index < len(self.states) - 1:
                self.states = self.states[:self.current_index + 1]

            # 嘗試壓縮連續的相似操作
            skip_save = self.try_compress_similar_operations(copied_operation, copied_state)
            if skip_save:
                self.logger.debug("跳過保存，已合併至上一個狀態")
                return

            # 檢查和保存特定操作的信息
            self.record_special_operation(copied_operation)

            # 創建狀態記錄
            state_record = StateRecord(
                state=copied_state,
                operation=copied_operation,
                timestamp=time.time(),
                correction_state=copied_correction,
                display_mode=current_state.get('display_mode')
            )

            # 添加新狀態
            self.states.append(state_record)

            # 如果超過最大狀態數，刪除最舊的狀態
            if len(self.states) > self.max_states:
                self.states.pop(0)
                self.current_index -= 1

            self.current_index = len(self.states) - 1

            # 記錄更詳細的信息
            op_type = operation_info.get('type', 'unknown')
            op_desc = operation_info.get('description', 'Unknown operation')
            tree_items_count = current_state.get('tree_items_count', 0)
            if isinstance(current_state.get('tree_items', []), list):
                tree_items_count = len(current_state.get('tree_items', []))

            self.logger.debug(f"保存狀態：索引 {self.current_index}, 操作: {op_desc} ({op_type}), "
                        f"項目數: {tree_items_count}, "
                        f"有校正狀態: {correction_state is not None}")

            # 觸發狀態變更回調
            self.trigger_callback('on_state_change')
        except Exception as e:
            self.logger.error(f"保存狀態時出錯: {e}")

    def record_special_operation(self, operation):
        """記錄特殊操作，以便進行特定的撤銷處理"""
        op_type = operation.get('type', '')

        # 記錄拆分操作
        if op_type == 'split_srt' and 'split_result' in operation:
            self.last_split_operation = operation
            self.logger.debug("已記錄拆分操作")

        # 記錄合併操作
        elif op_type == 'combine_sentences' and 'original_items_data' in operation:
            self.last_combine_operation = operation
            self.logger.debug("已記錄合併操作")

        # 記錄時間調整操作
        elif op_type == 'align_end_times' and 'original_items_times' in operation:
            self.last_time_adjust_operation = operation
            self.logger.debug("已記錄時間調整操作")

    def try_compress_similar_operations(self, operation: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """
        嘗試壓縮連續的相似操作
        :param operation: 當前操作
        :param state: 當前狀態
        :return: 是否跳過保存
        """
        # 如果沒有先前狀態或操作類型不是可合併的，則不壓縮
        if self.current_index < 0 or self.current_index >= len(self.states):
            return False

        # 獲取上一個操作
        prev_op = self.states[self.current_index].operation

        # 檢查操作類型是否相同且時間間隔較短
        current_time = time.time()
        prev_time = self.states[self.current_index].timestamp
        time_diff = current_time - prev_time

        # 可合併的操作類型和最大時間間隔
        mergeable_types = ['edit_text', 'edit_word_text', 'toggle_correction']
        max_merge_interval = 2.0  # 2秒內的相同操作可合併

        if (prev_op.get('type') == operation.get('type') and
            prev_op.get('type') in mergeable_types and
            time_diff < max_merge_interval):

            # 更新上一個狀態的時間戳和狀態數據
            self.states[self.current_index].timestamp = current_time
            self.states[self.current_index].state = state

            # 如果是編輯操作，更新操作描述
            if 'edit' in prev_op.get('type', ''):
                prev_op['description'] = f"{prev_op.get('description', '編輯')} (多次)"

            return True

        return False

    def get_current_operation(self) -> Optional[Dict[str, Any]]:
        """獲取當前操作的信息"""
        if self.current_index >= 0 and self.current_index < len(self.states):
            return self.states[self.current_index].operation
        return None

    def can_undo(self) -> bool:
        """檢查是否可以撤銷"""
        return self.current_index > 0

    def can_redo(self) -> bool:
        """檢查是否可以重做"""
        return self.current_index < len(self.states) - 1

    def get_operation_to_undo(self):
        """獲取要撤銷的操作信息"""
        if not self.can_undo():
            return None
        return self.states[self.current_index]['operation']

    def undo(self) -> bool:
        """
        執行撤銷操作
        :return: 是否成功撤銷
        """
        try:
            # 檢查 GUI 引用是否可用
            if not self.gui:
                self.logger.error("無法執行撤銷：缺少 GUI 引用")
                return False

            self.logger.debug("開始執行撤銷操作")

            # 嘗試特殊操作的撤銷
            if self.last_split_operation:
                self.logger.debug("檢測到拆分操作，使用專用撤銷機制")
                if self.undo_split_operation():
                    return True

            if self.last_combine_operation:
                self.logger.debug("檢測到合併操作，使用專用撤銷機制")
                if self.undo_combine_operation():
                    return True

            if self.last_time_adjust_operation:
                self.logger.debug("檢測到時間調整操作，使用專用撤銷機制")
                if self.undo_time_adjust_operation():
                    return True

            # 一般撤銷邏輯
            if not self.can_undo():
                self.logger.debug("無法撤銷：已經是最初狀態")
                return False

            # 獲取目標狀態
            prev_index = self.current_index - 1
            prev_state = self.states[prev_index]

            # 更新索引
            self.current_index = prev_index

            # 記錄撤銷操作
            self.logger.debug(f"撤銷到狀態索引: {self.current_index}")

            # 觸發撤銷回調
            try:
                if self.callbacks['on_undo']:
                    self.callbacks['on_undo'](prev_state.state, prev_state.correction_state, prev_state.operation)
                    self.logger.debug("撤銷回調執行完成")
                else:
                    self.logger.warning("撤銷回調未設置")
            except Exception as e:
                self.logger.error(f"撤銷回調執行失敗: {e}", exc_info=True)
                return False

            # 觸發狀態變更回調
            self.trigger_callback('on_state_change')

            # 確保修改後更新 SRT 數據和音頻段落
            self.gui.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            self.gui.update_status("已撤銷操作")
            return True

        except Exception as e:
            self.logger.error(f"執行撤銷操作時出錯: {e}", exc_info=True)
            return False

    def redo(self) -> bool:
        """
        執行重做操作
        :return: 是否成功重做
        """
        try:
            # 檢查 GUI 引用是否可用
            if not self.gui:
                self.logger.error("無法執行重做：缺少 GUI 引用")
                return False

            self.logger.debug("開始執行重做操作")

            if not self.can_redo():
                self.logger.debug("無法重做：已經是最新狀態")
                return False

            # 保存操作前數據的完整備份
            original_tree_data = self._backup_current_tree_data()
            original_correction_state = None
            if hasattr(self.gui, 'correction_service'):
                original_correction_state = self.gui.correction_service.serialize_state()

            # 更新索引
            self.current_index += 1
            next_state = self.states[self.current_index]

            # 獲取操作類型
            operation = next_state.operation
            op_type = operation.get('type', '')

            self.logger.debug(f"重做操作: {op_type} - {operation.get('description', '未知操作')}")

            # 標記已進行編號的狀態，避免重複編號
            renumbering_done = False

            try:
                # 根據操作類型處理重做
                if op_type == 'split_srt':
                    # 使用專門的方法處理拆分操作重做
                    result = self._redo_split_operation(next_state, operation)
                    renumbering_done = True  # 標記拆分操作中已完成編號
                elif op_type == 'combine_sentences':
                    # 使用專門的方法處理合併操作重做
                    result = self._redo_combine_operation(next_state, operation)
                    renumbering_done = True  # 標記合併操作中已完成編號
                elif op_type == 'align_end_times':
                    # 使用專門的方法處理時間調整操作重做
                    result = self._redo_time_adjustment(next_state, operation)
                else:
                    # 一般操作使用通用方法處理
                    result = self.apply_state_safely(next_state.state, next_state.correction_state, operation)
            except Exception as e:
                # 如果重做過程出錯，嘗試還原到原始狀態
                self.logger.error(f"執行重做操作時出錯: {e}", exc_info=True)
                self._restore_backup_data(original_tree_data, original_correction_state)
                self.current_index -= 1  # 恢復索引
                return False

            # 只有在尚未完成編號的情況下才執行編號
            if not renumbering_done:
                # 確保項目編號正確
                self.gui.renumber_items(skip_correction_update=False)  # 確保更新校正狀態

            # 觸發重做回調
            if self.callbacks['on_redo']:
                try:
                    self.callbacks['on_redo'](next_state.state, next_state.correction_state, operation)
                except Exception as e:
                    self.logger.error(f"執行重做回調時出錯: {e}", exc_info=True)

            # 觸發狀態變更回調
            self.trigger_callback('on_state_change')

            # 確保修改後更新 SRT 數據
            self.gui.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            self.gui.update_status(f"已重做操作: {operation.get('description', '未知操作')}")
            return True

        except Exception as e:
            self.logger.error(f"執行重做操作時出錯: {e}", exc_info=True)
            return False

    def apply_state_safely(self, state, correction_state, operation):
        """
        安全地應用狀態，處理可能的錯誤
        """
        try:
            # 保存可能有效的可見項目
            visible_item = None
            if hasattr(self.gui, 'tree'):
                selected = self.gui.tree.selection()
                if selected:
                    visible_item = selected[0]

            # 清除當前狀態
            self.gui.clear_current_state()

            # 設置顯示模式
            if 'display_mode' in state:
                old_mode = self.gui.display_mode
                new_mode = state.get('display_mode')
                if old_mode != new_mode:
                    self.gui.display_mode = new_mode
                    self.gui.refresh_treeview_structure()

            # 保存要恢復的項目 ID 映射
            id_mapping = {}
            if 'item_id_mapping' in state:
                id_mapping = state.get('item_id_mapping', {})

            # 恢復樹狀視圖
            new_items = []  # 收集新的項目 ID
            if 'tree_items' in state:
                for item_data in state['tree_items']:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')
                    tags = item_data.get('tags')
                    original_id = item_data.get('original_id')

                    # 插入項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))
                    new_items.append(new_id)

                    # 保存 ID 映射
                    if original_id:
                        id_mapping[original_id] = new_id

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

            # 恢復 SRT 數據
            if 'srt_data' in state and state['srt_data']:
                self.gui.restore_srt_data(state['srt_data'])

            # 恢復使用 Word 文本的標記
            if 'use_word_text' in state:
                self.gui.restore_use_word_flags(state['use_word_text'], id_mapping)

            # 恢復校正狀態
            if correction_state and hasattr(self.gui, 'correction_service'):
                self.gui.correction_service.deserialize_state(correction_state, id_mapping)

            # 恢復視圖位置
            if visible_item:
                # 嘗試1: 使用 ID 映射
                if visible_item in id_mapping:
                    mapped_id = id_mapping[visible_item]
                    if self.gui.tree.exists(mapped_id):
                        self.gui.tree.see(mapped_id)
                        self.gui.tree.selection_set(mapped_id)
                # 嘗試2: 使用操作中的目標項目 ID
                elif 'target_item_id' in operation:
                    target_id = operation['target_item_id']
                    if target_id and self.gui.tree.exists(target_id):
                        self.gui.tree.see(target_id)
                        self.gui.tree.selection_set(target_id)
                # 嘗試3: 使用第一個新項目
                elif new_items:
                    self.gui.tree.see(new_items[0])
                    self.gui.tree.selection_set(new_items[0])

            return True

        except Exception as e:
            self.logger.error(f"安全應用狀態時出錯: {e}", exc_info=True)
            return False

    def _backup_current_tree_data(self):
        """備份當前樹視圖數據"""
        backup_data = []
        if hasattr(self.gui, 'tree'):
            for item in self.gui.tree.get_children():
                values = self.gui.tree.item(item, 'values')
                tags = self.gui.tree.item(item, 'tags')
                position = self.gui.tree.index(item)
                use_word = self.gui.use_word_text.get(item, False)

                # 獲取索引值
                index_pos = 1 if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT] else 0
                index = str(values[index_pos]) if len(values) > index_pos else ""

                correction_info = None
                if hasattr(self.gui, 'correction_service') and index:
                    if index in self.gui.correction_service.correction_states:
                        correction_info = {
                            'state': self.gui.correction_service.correction_states[index],
                            'original': self.gui.correction_service.original_texts.get(index, ''),
                            'corrected': self.gui.correction_service.corrected_texts.get(index, '')
                        }

                backup_data.append({
                    'id': item,
                    'values': values,
                    'tags': tags,
                    'position': position,
                    'use_word': use_word,
                    'index': index,
                    'correction': correction_info
                })
        return backup_data

    def _restore_backup_data(self, backup_data, correction_state=None):
        """從備份還原樹視圖數據"""
        if not backup_data:
            return

        # 清空當前樹視圖
        if hasattr(self.gui, 'tree'):
            for item in self.gui.tree.get_children():
                self.gui.tree.delete(item)

        # 清空校正狀態
        if hasattr(self.gui, 'correction_service'):
            self.gui.correction_service.clear_correction_states()

        # 清空 Word 文本標記
        if hasattr(self.gui, 'use_word_text'):
            self.gui.use_word_text.clear()

        # 恢復數據
        for item_data in backup_data:
            values = item_data.get('values', [])
            position = item_data.get('position', 'end')
            tags = item_data.get('tags')
            use_word = item_data.get('use_word', False)

            # 插入項目
            new_id = self.gui.insert_item('', position, values=tuple(values))

            # 恢復標籤
            if tags:
                self.gui.tree.item(new_id, tags=tags)

            # 恢復使用 Word 文本標記
            if use_word:
                self.gui.use_word_text[new_id] = True

        # 恢復校正狀態 - 優先使用傳入的校正狀態
        if correction_state and hasattr(self.gui, 'correction_service'):
            self.gui.correction_service.deserialize_state(correction_state)
        else:
            # 從備份數據中恢復校正狀態
            for item_data in backup_data:
                if 'correction' in item_data and item_data['correction'] and 'index' in item_data:
                    index = item_data['index']
                    correction = item_data['correction']
                    if hasattr(self.gui, 'correction_service') and 'state' in correction:
                        self.gui.correction_service.set_correction_state(
                            index,
                            correction.get('original', ''),
                            correction.get('corrected', ''),
                            correction.get('state', 'correct')
                        )

        # 更新 SRT 數據
        self.gui.update_srt_data_from_treeview()

    def clear_states(self) -> None:
        """清除所有狀態"""
        self.states.clear()
        self.current_index = -1
        self.last_split_operation = None
        self.last_combine_operation = None
        self.last_time_adjust_operation = None
        self.logger.debug("清除所有狀態")

    def get_current_state(self) -> Optional[Dict[str, Any]]:
        """
        獲取當前狀態
        :return: 當前狀態，如果沒有狀態則返回 None
        """
        if self.current_index >= 0 and self.current_index < len(self.states):
            return self.states[self.current_index].state
        return None

    def get_state_history(self) -> List[Dict[str, Any]]:
        """
        獲取狀態歷史摘要
        """
        history = []
        for i, state in enumerate(self.states):
            history.append({
                'index': i,
                'timestamp': state.timestamp,
                'operation_type': state.operation.get('type', 'unknown'),
                'description': state.operation.get('description', ''),
                'is_current': i == self.current_index,
                'has_correction': state.correction_state is not None
            })
        return history

    def undo_split_operation(self) -> bool:
        """專門處理拆分操作的撤銷"""
        try:
            # 檢查 GUI 引用是否可用
            if not self.gui:
                self.logger.error("無法執行拆分撤銷：缺少 GUI 引用")
                return False

            # 檢查是否有拆分操作記錄
            if not self.last_split_operation:
                self.logger.warning("沒有拆分操作記錄，無法撤銷")
                return False

            # 獲取拆分操作記錄
            split_op = self.last_split_operation
            srt_index = split_op.get('srt_index')
            split_result = split_op.get('split_result', [])
            original_correction_state = split_op.get('original_correction_state', {})
            original_word_text = split_op.get('original_word_text', "")

            self.logger.debug(f"執行拆分操作撤銷，索引: {srt_index}, 拆分數: {len(split_result)}")

            # 找出拆分生成的所有項目
            items_to_remove = []
            positions = []
            first_item_position = -1

            # 尋找所有相關項目
            for item in self.gui.tree.get_children():
                values = self.gui.tree.item(item, 'values')

                # 根據顯示模式獲取索引位置
                index_pos = 1 if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT] else 0

                if len(values) > index_pos:
                    try:
                        item_index = int(values[index_pos])
                        # 檢查是否是拆分生成的項目 (原始索引或原始索引+偏移)
                        is_split_item = (item_index == srt_index) or any(item_index == srt_index + i for i in range(1, len(split_result)))

                        if is_split_item:
                            position = self.gui.tree.index(item)
                            items_to_remove.append(item)
                            positions.append(position)

                            # 記錄第一個項目(最小位置)的位置
                            if first_item_position == -1 or position < first_item_position:
                                first_item_position = position

                    except (ValueError, TypeError):
                        continue

            # 如果沒有找到任何相關項目，退出
            if not items_to_remove:
                self.logger.warning(f"找不到與索引 {srt_index} 相關的拆分項目")
                return False

            # 恢復原始文本和時間
            original_text = ""
            for text, _, _ in split_result:
                original_text += text

            # 獲取時間範圍
            original_start = split_result[0][1] if split_result else ""
            original_end = split_result[-1][2] if split_result else ""

            # 在刪除前獲取第一個項目的校正狀態
            first_item = items_to_remove[0] if items_to_remove else None
            current_correction_state = None

            if first_item:
                values = self.gui.tree.item(first_item, 'values')
                vx_idx = -1  # 校正圖標通常在最後一列

                if len(values) > vx_idx:
                    current_correction_icon = values[vx_idx]
                    # 根據圖標確定當前校正狀態
                    if current_correction_icon == '✅':
                        current_correction_state = 'correct'
                    elif current_correction_icon == '❌':
                        current_correction_state = 'error'

            # 刪除所有拆分生成的項目
            for item in items_to_remove:
                self.gui.tree.delete(item)

            # 檢查文本是否需要校正
            needs_correction, corrected_text, original_plain_text, _ = self.gui.correction_service.check_text_for_correction(original_text)

            # 確定校正狀態和要顯示的文本
            correction_state = 'correct'  # 默認為已校正
            display_text = original_text
            correction_icon = ''

            if needs_correction:
                # 優先使用當前的校正狀態(拆分後可能更改過)
                if current_correction_state:
                    correction_state = current_correction_state
                    if correction_state == 'correct':
                        display_text = corrected_text
                        correction_icon = '✅'
                    else:  # 'error'
                        display_text = original_text
                        correction_icon = '❌'
                else:
                    # 否則使用拆分前的校正狀態
                    if str(srt_index) in original_correction_state:
                        orig_state = original_correction_state[str(srt_index)].get('state', 'correct')
                        correction_state = orig_state
                        if orig_state == 'correct':
                            display_text = corrected_text
                            correction_icon = '✅'
                        else:  # 'error'
                            display_text = original_text
                            correction_icon = '❌'
                    else:
                        # 如果沒有記錄，默認為已校正
                        correction_state = 'correct'
                        display_text = corrected_text
                        correction_icon = '✅'

            # 創建恢復的值列表，包含Word文本
            restored_values = self._create_restored_values_with_correction(
                display_text, original_text, corrected_text,
                original_start, original_end, srt_index,
                correction_icon, needs_correction,
                original_word_text
            )

            # 插入還原後的項目
            new_item = self.gui.insert_item('', first_item_position, values=tuple(restored_values))

            # 保存校正狀態
            if needs_correction:
                self.gui.correction_service.set_correction_state(
                    str(srt_index),
                    original_plain_text,
                    corrected_text,
                    correction_state
                )

            # 更新 SRT 數據
            self._update_srt_for_undo_split(srt_index, display_text, original_start, original_end)

            # 重新編號
            self.gui.renumber_items()

            # 如果有音頻，更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            # 清除拆分操作記錄
            self.last_split_operation = None

            # 選中恢復的項目
            self.gui.tree.selection_set(new_item)
            self.gui.tree.see(new_item)

            # 更新狀態
            self.gui.update_status("已撤銷拆分操作")
            return True

        except Exception as e:
            self.logger.error(f"撤銷拆分操作時出錯: {e}", exc_info=True)
            return False

    def _create_restored_values_with_correction(self, display_text, original_text, corrected_text,
                                      start, end, srt_index, correction_icon, needs_correction, word_text=""):
        """
        為拆分還原創建值列表，包含校正狀態和Word文本
        """
        # 檢查 GUI 引用是否可用
        if not self.gui:
            self.logger.error("無法創建恢復值：缺少 GUI 引用")
            return []

        # 初始化 values 變數，確保在所有情況下都有定義
        values = []

        # 根據顯示模式準備值
        if self.gui.display_mode == self.gui.DISPLAY_MODE_ALL:
            values = [
                self.gui.PLAY_ICON,
                str(srt_index),
                start,
                end,
                display_text,
                word_text,
                "",  # Match
                correction_icon
            ]
        elif self.gui.display_mode == self.gui.DISPLAY_MODE_SRT_WORD:
            values = [
                str(srt_index),
                start,
                end,
                display_text,
                word_text,
                "",  # Match
                correction_icon
            ]
        elif self.gui.display_mode == self.gui.DISPLAY_MODE_AUDIO_SRT:
            values = [
                self.gui.PLAY_ICON,
                str(srt_index),
                start,
                end,
                display_text,
                correction_icon
            ]
        else:  # SRT模式
            values = [
                str(srt_index),
                start,
                end,
                display_text,
                correction_icon
            ]

        return values

    def _update_srt_for_undo_split(self, srt_index, text, start, end):
        """為拆分撤銷更新SRT數據"""
        try:
            # 檢查 GUI 引用是否可用
            if not self.gui:
                self.logger.error("無法更新 SRT 數據：缺少 GUI 引用")
                return

            # 將所有大於等於srt_index+1的項目從SRT數據中刪除，但保留原始索引
            i = 0
            while i < len(self.gui.srt_data):
                if self.gui.srt_data[i].index > srt_index:
                    self.gui.srt_data.pop(i)
                else:
                    i += 1

            # 更新或新增拆分還原的項目
            if srt_index <= len(self.gui.srt_data):
                # 更新現有項目
                sub = self.gui.srt_data[srt_index - 1]
                sub.text = text
                sub.start = pysrt.SubRipTime.from_string(start) if isinstance(start, str) else start
                sub.end = pysrt.SubRipTime.from_string(end) if isinstance(end, str) else end
            else:
                # 新增項目
                sub = pysrt.SubRipItem(
                    index=srt_index,
                    start=pysrt.SubRipTime.from_string(start) if isinstance(start, str) else start,
                    end=pysrt.SubRipTime.from_string(end) if isinstance(end, str) else end,
                    text=text
                )
                self.gui.srt_data.append(sub)

        except Exception as e:
            self.logger.error(f"更新SRT數據時出錯: {e}", exc_info=True)
            raise

    def undo_combine_operation(self):
        """專門處理合併操作的撤銷"""
        try:
            # 檢查 GUI 引用是否可用
            if not self.gui:
                self.logger.error("無法執行合併撤銷：缺少 GUI 引用")
                return False

            # 檢查是否有合併操作記錄
            if not self.last_combine_operation:
                self.logger.warning("沒有合併操作記錄，無法撤銷")
                return False

            # 獲取合併操作記錄
            combine_op = self.last_combine_operation
            original_items_data = combine_op.get('original_items_data', [])

            if not original_items_data:
                self.logger.warning("合併操作記錄不完整，無法撤銷")
                return False

            self.logger.debug(f"執行合併操作撤銷，原始項目數: {len(original_items_data)}")

            # 找出合併後生成的項目
            merged_item = None
            merged_position = -1

            # 找出合併後的項目 - 通常是第一個位置
            if original_items_data:
                first_pos = original_items_data[0]['position']
                items = self.gui.tree.get_children()

                if len(items) > first_pos:
                    merged_item = items[first_pos]
                    merged_position = first_pos

            # 如果找不到合併項目，嘗試通過索引找
            if merged_item is None and original_items_data:
                first_item_data = original_items_data[0]
                index_pos = 1 if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT] else 0

                if 'values' in first_item_data and len(first_item_data['values']) > index_pos:
                    target_index = first_item_data['values'][index_pos]

                    for item in self.gui.tree.get_children():
                        values = self.gui.tree.item(item, 'values')
                        if len(values) > index_pos and str(values[index_pos]) == str(target_index):
                            merged_item = item
                            merged_position = self.gui.tree.index(item)
                            break

            # 如果找不到合併項目，無法撤銷
            if merged_item is None:
                self.logger.warning("找不到合併後的項目，無法撤銷")
                return False

            # 刪除合併項目
            self.gui.tree.delete(merged_item)

            # 插入原始項目
            for item_data in original_items_data:
                values = item_data.get('values', [])
                position = item_data.get('position', 0)
                tags = item_data.get('tags')
                use_word = item_data.get('use_word', False)

                # 插入原項目
                new_id = self.gui.insert_item('', position, values=tuple(values))

                # 恢復標籤
                if tags:
                    self.gui.tree.item(new_id, tags=tags)

                # 恢復使用 Word 文本標記
                if use_word:
                    self.gui.use_word_text[new_id] = True

                # 恢復校正狀態
                correction = item_data.get('correction')
                if correction:
                    index_pos = 1 if self.gui.display_mode in [self.gui.DISPLAY_MODE_ALL, self.gui.DISPLAY_MODE_AUDIO_SRT] else 0
                    index = str(values[index_pos]) if len(values) > index_pos else ""

                    if index and correction.get('state'):
                        self.gui.correction_service.set_correction_state(
                            index,
                            correction.get('original', ''),
                            correction.get('corrected', ''),
                            correction.get('state', 'correct')
                        )

            # 重建 SRT 數據
            self.gui.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            # 選中所有恢復的項目
            select_ids = []
            for i, item_data in enumerate(original_items_data):
                position = item_data.get('position', 0)
                items = self.gui.tree.get_children()
                if 0 <= position < len(items):
                    select_ids.append(items[position])

            if select_ids:
                self.gui.tree.selection_set(select_ids)
                self.gui.tree.see(select_ids[0])

            # 清除合併操作記錄
            self.last_combine_operation = None

            # 更新狀態
            self.gui.update_status("已撤銷合併操作")
            return True

        except Exception as e:
            self.logger.error(f"撤銷合併操作時出錯: {e}", exc_info=True)
            return False

    def undo_time_adjust_operation(self):
        """專門處理時間軸調整的撤銷"""
        try:
            # 檢查 GUI 引用是否可用
            if not self.gui:
                self.logger.error("無法執行時間調整撤銷：缺少 GUI 引用")
                return False

            # 檢查是否有時間調整操作記錄
            if not self.last_time_adjust_operation:
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
                items = self.gui.tree.get_children()
                if 0 <= item_index < len(items):
                    current_item = items[item_index]
                    values = list(self.gui.tree.item(current_item, 'values'))

                    # 恢復時間值
                    if len(values) > start_index:
                        values[start_index] = original_start
                    if len(values) > end_index:
                        values[end_index] = original_end

                    # 更新項目
                    self.gui.tree.item(current_item, values=tuple(values))

            # 更新 SRT 數據
            self.gui.update_srt_data_from_treeview()

            # 如果有音頻，更新音頻段落
            if self.gui.audio_imported and hasattr(self.gui, 'audio_player'):
                self.gui.audio_player.segment_audio(self.gui.srt_data)

            # 清除時間調整操作記錄
            self.last_time_adjust_operation = None

            # 更新狀態
            self.gui.update_status("已撤銷時間調整操作")
            return True

        except Exception as e:
            self.logger.error(f"撤銷時間調整操作時出錯: {e}", exc_info=True)
            return False

    def redo_combine_operation(self, state, operation):
        """處理合併操作的重做"""
        try:
            # 清除當前樹狀視圖
            self.gui.clear_current_treeview()

            # 從狀態恢復樹狀視圖
            if 'tree_items' in state.state:
                for item_data in state.state['tree_items']:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')
                    tags = item_data.get('tags')
                    use_word = item_data.get('use_word', False)

                    # 插入項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

                    # 恢復使用 Word 文本的標記
                    if use_word:
                        self.gui.use_word_text[new_id] = True

            # 恢復 SRT 數據
            if 'srt_data' in state.state:
                self.gui.restore_srt_data(state.state['srt_data'])

            # 恢復校正狀態
            if state.correction_state and hasattr(self.gui, 'correction_service'):
                self.gui.correction_service.deserialize_state(state.correction_state)

            # 選中合併後的項目
            if 'new_item' in operation and self.gui.tree.exists(operation['new_item']):
                self.gui.tree.selection_set(operation['new_item'])
                self.gui.tree.see(operation['new_item'])

            return True

        except Exception as e:
            self.logger.error(f"重做合併操作時出錯: {e}", exc_info=True)
            return False

    def redo_time_adjustment(self, state, operation):
        """處理時間調整操作的重做"""
        try:
            # 清除當前樹狀視圖
            self.gui.clear_current_treeview()

            # 從狀態恢復樹狀視圖
            if 'tree_items' in state.state:
                for item_data in state.state['tree_items']:
                    values = item_data.get('values', [])
                    position = item_data.get('position', 'end')
                    tags = item_data.get('tags')
                    use_word = item_data.get('use_word', False)

                    # 插入項目
                    new_id = self.gui.insert_item('', position, values=tuple(values))

                    # 恢復標籤
                    if tags:
                        self.gui.tree.item(new_id, tags=tags)

                    # 恢復使用 Word 文本的標記
                    if use_word:
                        self.gui.use_word_text[new_id] = True

            # 恢復 SRT 數據
            if 'srt_data' in state.state:
                self.gui.restore_srt_data(state.state['srt_data'])

            # 恢復校正狀態
            if state.correction_state and hasattr(self.gui, 'correction_service'):
                self.gui.correction_service.deserialize_state(state.correction_state)

            return True

        except Exception as e:
            self.logger.error(f"重做時間調整操作時出錯: {e}", exc_info=True)
            return False