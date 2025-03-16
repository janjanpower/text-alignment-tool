import copy
import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable

@dataclass
class AppState:
    """應用程式狀態記錄"""
    tree_data: List[Dict[str, Any]]  # 樹狀視圖數據
    correction_states: Dict[str, Dict[str, Any]]  # 校正狀態
    display_mode: str  # 顯示模式
    use_word_flags: Dict[str, bool]  # 使用 Word 文本的標記
    timestamp: float  # 時間戳
    operation_info: Dict[str, Any]  # 操作信息

class AppStateManager:
    """應用程式狀態管理類別，與 UI 解耦"""

    def __init__(self, max_states: int = 50):
        """初始化應用程式狀態管理器"""
        self.states: List[AppState] = []
        self.current_index: int = -1
        self.max_states = max_states
        self.logger = logging.getLogger(self.__class__.__name__)
        self.callbacks = {}  # 回調函數字典

    def register_callback(self, event_name: str, callback: Callable) -> None:
        """註冊事件回調函數"""
        self.callbacks[event_name] = callback

    def _trigger_callback(self, event_name: str, *args, **kwargs) -> None:
        """觸發回調函數"""
        if event_name in self.callbacks and callable(self.callbacks[event_name]):
            self.callbacks[event_name](*args, **kwargs)

    def save_state(self, state_data: Dict[str, Any]) -> None:
        """保存新的應用程式狀態"""
        # 深拷貝狀態數據
        copied_state = copy.deepcopy(state_data)

        # 如果當前索引小於狀態列表長度-1，刪除後面的狀態
        if self.current_index < len(self.states) - 1:
            self.states = self.states[:self.current_index + 1]

        # 建立狀態記錄
        app_state = AppState(
            tree_data=copied_state.get('tree_data', []),
            correction_states=copied_state.get('correction_states', {}),
            display_mode=copied_state.get('display_mode', ''),
            use_word_flags=copied_state.get('use_word_flags', {}),
            timestamp=time.time(),
            operation_info=copied_state.get('operation_info', {})
        )

        # 添加新狀態
        self.states.append(app_state)

        # 如果超過最大狀態數，刪除最舊的狀態
        if len(self.states) > self.max_states:
            self.states.pop(0)
            self.current_index -= 1

        self.current_index = len(self.states) - 1
        self.logger.debug(f"保存狀態：索引 {self.current_index}")

        # 觸發狀態變更回調
        self._trigger_callback('on_state_change')

    def can_undo(self) -> bool:
        """檢查是否可以撤銷"""
        return self.current_index > 0

    def can_redo(self) -> bool:
        """檢查是否可以重做"""
        return self.current_index < len(self.states) - 1

    def undo(self) -> Optional[AppState]:
        """執行撤銷操作"""
        if not self.can_undo():
            self.logger.debug("無法撤銷：已經是最初狀態")
            return None

        self.current_index -= 1
        state = self.states[self.current_index]

        # 觸發撤銷回調
        self._trigger_callback('on_undo', state)

        return state

    def redo(self) -> Optional[AppState]:
        """執行重做操作"""
        if not self.can_redo():
            self.logger.debug("無法重做：已經是最新狀態")
            return None

        self.current_index += 1
        state = self.states[self.current_index]

        # 觸發重做回調
        self._trigger_callback('on_redo', state)

        return state

    def get_current_state(self) -> Optional[AppState]:
        """獲取當前狀態"""
        if 0 <= self.current_index < len(self.states):
            return self.states[self.current_index]
        return None

    def clear_states(self) -> None:
        """清空所有狀態"""
        self.states.clear()
        self.current_index = -1
        self.logger.debug("已清空所有狀態")

    def get_state_history(self) -> List[Dict[str, Any]]:
        """獲取狀態歷史摘要"""
        return [
            {
                'index': i,
                'timestamp': state.timestamp,
                'operation_type': state.operation_info.get('type', 'unknown'),
                'description': state.operation_info.get('description', ''),
                'is_current': i == self.current_index,
            }
            for i, state in enumerate(self.states)
        ]