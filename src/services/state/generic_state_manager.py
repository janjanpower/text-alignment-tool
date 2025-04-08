"""通用狀態管理模組"""

import time
import copy
import logging
from typing import List, Dict, Any, Optional

from .base_state_manager import BaseStateManager, StateRecord

class GenericStateManager(BaseStateManager):
    """基本的狀態管理器實現，提供基礎的撤銷和重做功能"""

    def __init__(self, max_states: int = 50) -> None:
        super().__init__(max_states)
        self.states: List[StateRecord] = []
        self.current_state_index: int = -1
        self.last_undo_time: float = 0
        self.undo_counter: int = 0

    def save_state(self, current_state: Any, operation_info: Optional[Dict] = None) -> None:
        """
        保存新的狀態
        :param current_state: 當前狀態
        :param operation_info: 操作信息（可選）
        """
        # 如果當前狀態與最後一個狀態相同，不保存
        if (self.current_state_index >= 0 and
            self.current_state_index < len(self.states) and
            current_state == self.states[self.current_state_index].state):
            return

        # 如果不是在最後一個狀態，刪除之後的狀態
        if self.current_state_index < len(self.states) - 1:
            self.states = self.states[:self.current_state_index + 1]

        # 創建深拷貝以防止後續修改
        state_copy = copy.deepcopy(current_state)
        operation_copy = copy.deepcopy(operation_info or {'type': 'unknown', 'description': 'Unknown operation'})

        # 創建狀態記錄
        state_record = StateRecord(
            state=state_copy,
            operation=operation_copy,
            timestamp=time.time()
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

    def undo(self) -> Optional[Any]:
        """
        執行撤銷操作
        :return: 上一個狀態，如果無法撤銷則返回 None
        """
        # 檢查是否可以撤銷
        if not self.can_undo():
            self.logger.debug("無法撤銷：已經是最初狀態")
            return None

        # 更新撤銷指標和計數器
        self.current_state_index -= 1
        self.last_undo_time = time.time()
        self.undo_counter += 1

        # 獲取前一個狀態
        previous_state = self.states[self.current_state_index].state

        # 觸發撤銷回調
        self.trigger_callback('on_undo', previous_state, self.states[self.current_state_index].operation)

        # 觸發狀態變更回調
        self.trigger_callback('on_state_change')

        return previous_state

    def redo(self) -> Optional[Any]:
        """
        執行重做操作
        :return: 下一個狀態，如果無法重做則返回 None
        """
        if not self.can_redo():
            self.logger.debug("無法重做：已經是最新狀態")
            return None

        self.current_state_index += 1
        next_state = self.states[self.current_state_index].state

        # 觸發重做回調
        self.trigger_callback('on_redo', next_state, self.states[self.current_state_index].operation)

        # 觸發狀態變更回調
        self.trigger_callback('on_state_change')

        return next_state

    def clear_states(self) -> None:
        """清除所有狀態"""
        self.states.clear()
        self.current_state_index = -1
        self.last_undo_time = 0
        self.undo_counter = 0
        self.logger.debug("清除所有狀態")

    def get_current_state(self) -> Optional[Any]:
        """
        獲取當前狀態
        :return: 當前狀態，如果沒有狀態則返回 None
        """
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].state
        return None

    def get_state_history(self) -> List[StateRecord]:
        """
        獲取狀態歷史
        :return: 狀態記錄列表
        """
        return self.states

    def get_operation_history(self) -> List[Dict[str, Any]]:
        """
        獲取操作歷史
        :return: 操作記錄列表
        """
        return [state.operation for state in self.states]

    def get_undo_count(self) -> int:
        """
        獲取撤銷操作次數
        :return: 撤銷次數
        """
        return self.undo_counter

    def reset_undo_count(self) -> None:
        """重置撤銷計數器"""
        self.undo_counter = 0