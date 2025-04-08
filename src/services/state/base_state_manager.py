"""狀態管理基礎模組"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Generic, TypeVar

# 定義狀態記錄的類型變數
T = TypeVar('T')

@dataclass
class StateRecord(Generic[T]):
    """狀態記錄數據類別"""
    state: T
    operation: Dict[str, Any]
    timestamp: float

class BaseStateManager(ABC):
    """狀態管理的抽象基類"""

    def __init__(self, max_states: int = 50) -> None:
        """
        初始化狀態管理器
        :param max_states: 最大狀態數量
        """
        self.max_states = max_states
        self.logger = logging.getLogger(self.__class__.__name__)
        self.callbacks: Dict[str, Optional[Callable]] = {
            'on_state_change': None,
            'on_undo': None,
            'on_redo': None,
            'on_state_applied': None
        }

    def set_callback(self, event_name: str, callback_func: Optional[Callable]) -> None:
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

    @abstractmethod
    def save_state(self, current_state: Any, operation_info: Dict[str, Any]) -> None:
        """
        保存狀態的抽象方法
        :param current_state: 當前狀態
        :param operation_info: 操作信息
        """
        pass

    @abstractmethod
    def can_undo(self) -> bool:
        """
        檢查是否可以撤銷
        :return: 是否可以撤銷
        """
        pass

    @abstractmethod
    def can_redo(self) -> bool:
        """
        檢查是否可以重做
        :return: 是否可以重做
        """
        pass

    @abstractmethod
    def undo(self) -> Any:
        """
        執行撤銷操作
        :return: 撤銷後的狀態
        """
        pass

    @abstractmethod
    def redo(self) -> Any:
        """
        執行重做操作
        :return: 重做後的狀態
        """
        pass

    @abstractmethod
    def clear_states(self) -> None:
        """清除所有狀態"""
        pass

    @abstractmethod
    def get_current_state(self) -> Optional[Any]:
        """
        獲取當前狀態
        :return: 當前狀態
        """
        pass