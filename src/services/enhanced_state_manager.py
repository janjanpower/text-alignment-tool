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

class EnhancedStateManager:
    """增強狀態管理類別，提供狀態保存、撤銷和重做功能"""

    def __init__(self, max_states: int = 50) -> None:
        """
        初始化狀態管理器
        :param max_states: 最大狀態數量
        """
        self.states: List[StateRecord] = []
        self.current_state_index: int = -1
        self.max_states = max_states
        self.logger = logging.getLogger(self.__class__.__name__)

        # 添加回調函數字典
        self.callbacks = {
            'on_state_change': None,
            'on_undo': None,
            'on_redo': None,
            'on_state_applied': None
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

            # 保存當前狀態作為可能的回滾點
            current_state = None
            current_correction_state = None
            if self.current_state_index < len(self.states):
                current_record = self.states[self.current_state_index]
                current_state = copy.deepcopy(current_record.state)
                current_correction_state = copy.deepcopy(current_record.correction_state)

                # 記錄當前操作的詳細信息
                current_op = current_record.operation.get('type', 'unknown')
                current_desc = current_record.operation.get('description', 'Unknown')
                self.logger.debug(f"當前操作: [{current_op}] {current_desc}")

                # 記錄當前狀態的特徵
                if 'tree_items' in current_state:
                    tree_items_count = len(current_state['tree_items'])
                    self.logger.debug(f"當前狀態特徵: 樹項目數={tree_items_count}")

            # 獲取目標狀態的詳細信息
            prev_index = self.current_state_index - 1
            if 0 <= prev_index < len(self.states):
                prev_record = self.states[prev_index]
                prev_op = prev_record.operation.get('type', 'unknown')
                prev_desc = prev_record.operation.get('description', 'Unknown')
                self.logger.debug(f"目標操作: [{prev_op}] {prev_desc}")

                # 記錄目標狀態的特徵
                prev_state = prev_record.state
                if 'tree_items' in prev_state:
                    tree_items_count = len(prev_state['tree_items'])
                    self.logger.debug(f"目標狀態特徵: 樹項目數={tree_items_count}")

            # 實際執行索引變更
            self.current_state_index -= 1
            prev_state = self.states[self.current_state_index]

            # 記錄回調觸發前的時間
            callback_start_time = time.time()

            # 使用 try-except 包裝回調調用
            try:
                # 觸發撤銷回調
                self.logger.debug(f"觸發撤銷回調")
                if self.callbacks['on_undo']:
                    self.callbacks['on_undo'](prev_state.state, prev_state.correction_state, prev_state.operation)
                    callback_duration = time.time() - callback_start_time
                    self.logger.debug(f"撤銷回調完成，耗時: {callback_duration:.3f}秒")
                else:
                    self.logger.warning("沒有設置撤銷回調函數")

                # 觸發狀態變更回調
                self.trigger_callback('on_state_change')

                return True
            except Exception as e:
                # 如果撤銷回調執行失敗
                self.logger.error(f"撤銷回調執行失敗: {e}", exc_info=True)

                # 嘗試回滾到之前的狀態
                if current_state:
                    try:
                        # 恢復索引
                        self.current_state_index += 1
                        self.logger.warning(f"撤銷失敗，嘗試回滾到索引 {self.current_state_index}")

                        # 如果有回滾回調，嘗試執行
                        if self.callbacks.get('on_rollback'):
                            self.callbacks['on_rollback'](current_state, current_correction_state,
                                                        {'type': 'rollback', 'description': '撤銷失敗回滾'})
                            self.logger.info("成功回滾到之前狀態")
                        else:
                            self.logger.warning("無法回滾：未設置回滾回調")
                    except Exception as rollback_error:
                        self.logger.error(f"回滾失敗: {rollback_error}", exc_info=True)
                else:
                    self.logger.error("撤銷失敗，無法回滾：沒有保存當前狀態")

                return False
        except Exception as e:
            # 處理方法本身的執行錯誤
            self.logger.error(f"undo 方法執行時發生錯誤: {e}", exc_info=True)

            # 確保索引不會越界
            if self.current_state_index < 0:
                self.current_state_index = 0
                self.logger.warning("索引修正: 設置為 0")
            elif self.current_state_index >= len(self.states):
                self.current_state_index = len(self.states) - 1
                self.logger.warning(f"索引修正: 設置為 {self.current_state_index}")

            return False

    def redo(self) -> bool:
        """
        執行重做操作
        :return: 是否成功重做
        """
        if not self.can_redo():
            self.logger.debug("無法重做：已經是最新狀態")
            return False

        # 更新索引
        self.current_state_index += 1
        next_state = self.states[self.current_state_index]

        # 觸發重做回調
        self.trigger_callback('on_redo', next_state.state, next_state.correction_state, next_state.operation)
        return True

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