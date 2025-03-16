import copy
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable

from typing import List, Dict, Any, Optional, Set

from gui.custom_messagebox import show_error
@dataclass
class StateRecord:
    """狀態記錄數據類別"""
    state: Any  # 樹狀視圖狀態
    operation: Dict[str, Any]  # 操作信息
    timestamp: float  # 時間戳
    correction_state: Optional[Dict[str, Any]] = None  # 校正狀態


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

    def trigger_callback(self, event_name: str, *args, **kwargs) -> None:
        """
        觸發回調函數
        :param event_name: 事件名稱
        :param args: 位置參數
        :param kwargs: 關鍵字參數
        """
        if event_name in self.callbacks and callable(self.callbacks[event_name]):
            self.callbacks[event_name](*args, **kwargs)
        else:
            self.logger.debug(f"未找到事件 '{event_name}' 的回調或回調不可調用")

    def save_state(self, current_state: Any, operation_info: Optional[Dict] = None,
               correction_state: Optional[Dict] = None) -> None:
        # 深拷貝當前狀態和校正狀態，確保不會被後續操作修改
        copied_state = copy.deepcopy(current_state)
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

        # 觸發狀態變更回調
        self.trigger_callback('on_state_change')

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

    def undo(self) -> bool:
        """
        執行撤銷操作
        :return: 是否成功撤銷
        """
        if not self.can_undo():
            self.logger.debug("無法撤銷：已經是最初狀態")
            return False

        # 獲取前一個狀態
        self.current_state_index -= 1
        prev_state = self.states[self.current_state_index]

        # 觸發撤銷回調
        self.trigger_callback('on_undo', prev_state.state, prev_state.correction_state, prev_state.operation)

        return True

    def redo(self) -> bool:
        """
        執行重做操作
        :return: 是否成功重做
        """
        if not self.can_redo():
            self.logger.debug("無法重做：已經是最新狀態")
            return False

        # 獲取下一個狀態
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