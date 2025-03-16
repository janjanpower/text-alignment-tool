"""狀態管理類別模組"""

import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class StateRecord:
    """狀態記錄數據類別"""
    state: Any
    operation: Dict[str, Any]
    timestamp: float

class StateManager:
    """狀態管理類別，用於處理撤銷/重做功能"""

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

        # 創建狀態記錄
        state_record = StateRecord(
            state=current_state,
            operation=operation_info or {'type': 'unknown', 'description': 'Unknown operation'},
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

    def get_current_operation(self):
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

    def get_previous_operation(self):
        """獲取前一個操作的信息"""
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            return self.states[self.current_state_index].operation
        return None

    def undo(self) -> Optional[Any]:
        """
        執行撤銷操作
        :return: 上一個狀態，如果無法撤銷則返回 None
        """
        # 檢查是否可以撤銷
        if not self.can_undo():
            self.logger.debug("無法撤銷：已經是最初狀態")
            return None

        # 輸出更多調試信息
        self.logger.debug(f"撤銷前: 當前索引={self.current_state_index}, 狀態數={len(self.states)}")

        # 如果是第一個操作，需要特別處理
        if self.current_state_index == 1:
            self.logger.debug("嘗試撤銷第一個操作")
            current_operation = self.states[self.current_state_index].operation
            if current_operation and current_operation.get('type') == 'combine_sentences':
                self.logger.debug("第一個操作是合併字幕，使用特殊處理")
                # 獲取原始狀態
                original_state = current_operation.get('original_state')
                if original_state:
                    self.logger.debug(f"使用合併操作的原始狀態，包含 {len(original_state)} 項目")
                    # 將當前狀態索引設為0，回到初始狀態
                    self.current_state_index = 0
                    self.last_undo_time = time.time()
                    self.undo_counter += 1
                    return original_state

        # 獲取當前操作的信息
        current_operation = None
        if self.current_state_index >= 0 and self.current_state_index < len(self.states):
            current_record = self.states[self.current_state_index]
            current_operation = current_record.operation

            # 輸出操作類型
            op_type = current_operation.get('type', 'unknown') if current_operation else 'none'
            self.logger.debug(f"當前操作類型: {op_type}")

            # 特別處理合併操作
            if current_operation and current_operation.get('type') == 'combine_sentences':
                # 對於合併操作，直接返回原始狀態
                original_state = current_operation.get('original_state')
                if original_state:
                    self.logger.debug(f"使用合併操作的原始狀態，包含 {len(original_state)} 項目")
                    # 將當前狀態索引減一
                    self.current_state_index -= 1
                    self.last_undo_time = time.time()
                    self.undo_counter += 1
                    return original_state

            # 處理斷句操作
            elif current_operation and current_operation.get('type') in ['split_srt', 'split_word_text']:
                # 對於斷句操作，也直接使用保存的原始狀態
                original_state = current_operation.get('original_state')
                if original_state:
                    # 將當前狀態索引減一
                    self.current_state_index -= 1
                    self.last_undo_time = time.time()
                    self.undo_counter += 1

                    # 返回斷句前的原始狀態
                    self.logger.debug(f"撤銷斷句操作，恢復原始狀態")
                    return original_state

            # 處理時間調整操作
            elif current_operation and current_operation.get('type') == 'align_end_times':
                # 檢查是否存在原始狀態
                original_state = current_operation.get('original_state')
                if original_state:
                    # 更新索引
                    self.current_state_index -= 1
                    self.last_undo_time = time.time()
                    self.undo_counter += 1

                    # 返回原始狀態
                    self.logger.debug(f"撤銷時間調整操作，恢復原始狀態")
                    return original_state

            # 處理文本編輯操作
            elif current_operation and current_operation.get('type') == 'edit_text':
                # 檢查是否存在原始狀態
                original_state = current_operation.get('original_state')
                if original_state:
                    # 更新索引
                    self.current_state_index -= 1
                    self.last_undo_time = time.time()
                    self.undo_counter += 1

                    # 返回原始狀態
                    self.logger.debug(f"撤銷文本編輯操作，恢復原始狀態")
                    return original_state

        # 標準撤銷邏輯 - 如果上述特殊情況都不適用
        # 先記錄前一個狀態的索引
        prev_index = self.current_state_index - 1

        # 再次檢查索引有效性
        if prev_index < 0 or prev_index >= len(self.states):
            self.logger.debug(f"無效的前一個狀態索引: {prev_index}")
            return None

        # 獲取前一個狀態
        previous_state = self.states[prev_index].state

        # 然後更新索引
        self.current_state_index = prev_index
        self.last_undo_time = time.time()
        self.undo_counter += 1

        # 記錄撤銷操作
        self.logger.debug(f"撤銷到狀態索引: {self.current_state_index}")

        # 返回前一個狀態
        return previous_state

        # 執行標準撤銷，獲取上一個狀態
    def redo(self) -> Optional[Any]:
        """
        執行重做操作
        :return: 下一個狀態，如果無法重做則返回 None
        """
        if not self.can_redo():
            self.logger.debug("無法重做：已經是最新狀態")
            return None

        self.current_state_index += 1
        next_state = self.states[self.current_state_index]
        self.logger.debug(f"重做到狀態索引：{self.current_state_index}")
        return next_state.state

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

    def merge_consecutive_states(self, time_threshold: float = 1.0) -> None:
        """
        合併連續的相似狀態
        :param time_threshold: 時間閾值（秒）
        """
        if len(self.states) < 2:
            return

        i = len(self.states) - 1
        while i > 0:
            current_state = self.states[i]
            previous_state = self.states[i - 1]

            # 如果兩個狀態的時間間隔小於閾值且操作類型相同
            if (current_state.timestamp - previous_state.timestamp < time_threshold and
                current_state.operation['type'] == previous_state.operation['type']):
                # 合併這兩個狀態
                self.states.pop(i - 1)
                if self.current_state_index >= i - 1:
                    self.current_state_index -= 1
            i -= 1

    def get_undo_count(self) -> int:
        """
        獲取撤銷操作次數
        :return: 撤銷次數
        """
        return self.undo_counter

    def reset_undo_count(self) -> None:
        """重置撤銷計數器"""
        self.undo_counter = 0

    def trim_old_states(self, max_age: float = 3600.0) -> None:
        """
        清理過舊的狀態
        :param max_age: 最大保留時間（秒）
        """
        current_time = time.time()
        cutoff_time = current_time - max_age

        # 刪除超過最大年齡的狀態
        while (len(self.states) > 0 and
               self.states[0].timestamp < cutoff_time):
            self.states.pop(0)
            if self.current_state_index > 0:
                self.current_state_index -= 1