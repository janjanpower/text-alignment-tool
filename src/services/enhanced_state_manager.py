"""增強狀態管理模組"""

import copy
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable

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
            if self.current_state_index < len(self.states) - 1:
                self.states = self.states[:self.current_state_index + 1]

            # 嘗試壓縮連續的相似操作
            skip_save = self.try_compress_similar_operations(copied_operation, copied_state)
            if skip_save:
                self.logger.debug("跳過保存，已合併至上一個狀態")
                return

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
                self.current_state_index -= 1

            self.current_state_index = len(self.states) - 1

            # 記錄更詳細的信息
            op_type = operation_info.get('type', 'unknown')
            op_desc = operation_info.get('description', 'Unknown operation')
            tree_items_count = current_state.get('tree_items_count', 0)
            if isinstance(current_state.get('tree_items', []), list):
                tree_items_count = len(current_state.get('tree_items', []))

            self.logger.debug(f"保存狀態：索引 {self.current_state_index}, 操作: {op_desc} ({op_type}), "
                        f"項目數: {tree_items_count}, "
                        f"有校正狀態: {correction_state is not None}")

            # 觸發狀態變更回調
            self.trigger_callback('on_state_change')
        except Exception as e:
            self.logger.error(f"保存狀態時出錯: {e}")

    def try_compress_similar_operations(self, operation: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """
        嘗試壓縮連續的相似操作
        :param operation: 當前操作
        :param state: 當前狀態
        :return: 是否跳過保存
        """
        # 如果沒有先前狀態或操作類型不是可合併的，則不壓縮
        if self.current_state_index < 0 or self.current_state_index >= len(self.states):
            return False

        # 獲取上一個操作
        prev_op = self.states[self.current_state_index].operation

        # 檢查操作類型是否相同且時間間隔較短
        current_time = time.time()
        prev_time = self.states[self.current_state_index].timestamp
        time_diff = current_time - prev_time

        # 可合併的操作類型和最大時間間隔
        mergeable_types = ['edit_text', 'edit_word_text', 'toggle_correction']
        max_merge_interval = 2.0  # 2秒內的相同操作可合併

        if (prev_op.get('type') == operation.get('type') and
            prev_op.get('type') in mergeable_types and
            time_diff < max_merge_interval):

            # 更新上一個狀態的時間戳和狀態數據
            self.states[self.current_state_index].timestamp = current_time
            self.states[self.current_state_index].state = state

            # 如果是編輯操作，更新操作描述
            if 'edit' in prev_op.get('type', ''):
                prev_op['description'] = f"{prev_op.get('description', '編輯')} (多次)"

            return True

        return False

    def get_current_operation(self) -> Optional[Dict[str, Any]]:
        """獲取當前操作的信息"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].operation
        return None

    def can_undo(self):
        """檢查是否可以撤銷"""
        return self.current_index > 0

    def can_redo(self):
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
            # 首先檢查是否可以撤銷
            if not self.can_undo():
                self.logger.debug("無法撤銷：已經是最初狀態")
                return False

            # 詳細的日誌記錄
            self.logger.debug(f"開始撤銷操作，當前索引: {self.current_state_index}, 目標索引: {self.current_state_index-1}")

            # 獲取目標狀態
            prev_index = self.current_state_index - 1
            prev_state = self.states[prev_index]

            # 更新索引
            self.current_state_index = prev_index

            # 記錄撤銷操作
            self.logger.debug(f"撤銷到狀態索引: {self.current_state_index}")

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

            return True
        except Exception as e:
            self.logger.error(f"undo 方法執行時發生錯誤: {e}", exc_info=True)
            return False

    def redo(self) -> bool:
        """
        執行重做操作
        :return: 是否成功重做
        """
        try:
            if not self.can_redo():
                self.logger.debug("無法重做：已經是最新狀態")
                return False

            # 詳細的日誌記錄
            self.logger.debug(f"開始重做操作，當前索引: {self.current_state_index}, 目標索引: {self.current_state_index+1}")

            # 更新索引
            self.current_state_index += 1
            next_state = self.states[self.current_state_index]

            # 記錄重做操作
            self.logger.debug(f"重做到狀態索引: {self.current_state_index}")

            # 觸發重做回調
            try:
                if self.callbacks['on_redo']:
                    self.callbacks['on_redo'](next_state.state, next_state.correction_state, next_state.operation)
                    self.logger.debug("重做回調執行完成")
                else:
                    self.logger.warning("重做回調未設置")
            except Exception as e:
                self.logger.error(f"重做回調執行失敗: {e}", exc_info=True)
                return False

            # 觸發狀態變更回調
            self.trigger_callback('on_state_change')

            return True
        except Exception as e:
            self.logger.error(f"redo 方法執行時發生錯誤: {e}", exc_info=True)
            return False

    def clear_states(self) -> None:
        """清除所有狀態"""
        self.states.clear()
        self.current_state_index = -1
        self.logger.debug("清除所有狀態")

    def get_current_state(self) -> Optional[Dict[str, Any]]:
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