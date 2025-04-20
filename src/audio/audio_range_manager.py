"""音頻範圍管理器：統一視圖範圍計算、時間範圍處理和波形縮放功能"""

import logging
from typing import Tuple, Optional, Dict, Any
import numpy as np


class AudioRangeManager:
    """
    統一的音頻範圍管理器，提供：
    - 視圖範圍計算
    - 時間範圍驗證
    - 視覺化範圍管理
    - 適應性縮放計算
    """

    def __init__(self, audio_duration: int):
        """
        初始化音頻範圍管理器

        Args:
            audio_duration: 音頻總長度（毫秒）
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audio_duration = max(1, audio_duration)  # 確保至少為1毫秒

        # 視圖範圍配置
        self.min_view_width = 500     # 最小視圖寬度（毫秒）
        self.max_view_width = 30000   # 最大視圖寬度（毫秒）
        self.min_selection_width = 50 # 最小選擇寬度（毫秒）

        # 緩存最後一次計算的範圍
        self.last_selection = (0, min(5000, self.audio_duration))
        self.last_view_range = (0, min(10000, self.audio_duration))

        # 歷史記錄
        self.history = []
        self.max_history = 10

        # 當前段落的音頻特性
        self.audio_features = {
            'mean_amplitude': 0.0,
            'peak_amplitude': 0.0,
            'has_speech': False,
            'speech_segments': []
        }

    def get_optimal_view_range(self, selection: Tuple[float, float]) -> Tuple[float, float]:
        """
        根據選擇區域計算最佳視圖範圍

        Args:
            selection: 當前選擇的時間範圍 (start_ms, end_ms)

        Returns:
            最佳視圖範圍 (view_start_ms, view_end_ms)
        """
        try:
            # 驗證並修正選擇範圍
            start_ms, end_ms = self._validate_time_range(selection)

            # 緩存選擇範圍
            self.last_selection = (start_ms, end_ms)

            # 計算選擇區域中心點和持續時間
            duration = end_ms - start_ms
            center_time = (start_ms + end_ms) / 2

            # 動態計算視圖寬度
            view_width = self._calculate_view_width(duration)

            # 計算視圖範圍
            view_start = max(0, center_time - view_width / 2)
            view_end = min(self.audio_duration, view_start + view_width)

            # 確保視圖寬度得到維持，如果超出上限則調整起點
            if view_end == self.audio_duration and view_end - view_start < view_width:
                view_start = max(0, self.audio_duration - view_width)

            # 確保選擇區域在視圖範圍內
            if start_ms < view_start:
                # 如果選擇開始點在視圖開始點之前，擴展視圖
                delta = view_start - start_ms
                view_start = start_ms
                # 嘗試同等擴展結束點，除非超出最大時間
                view_end = min(self.audio_duration, view_end + delta)

            if end_ms > view_end:
                # 如果選擇結束點在視圖結束點之後，擴展視圖
                delta = end_ms - view_end
                view_end = end_ms
                # 嘗試同等擴展開始點，除非低於0
                view_start = max(0, view_start - delta)

            # 添加額外的邊距，確保顯示更多上下文
            margin = min(500, view_width * 0.1)  # 最大500ms或10%的視圖寬度
            view_start = max(0, view_start - margin)
            view_end = min(self.audio_duration, view_end + margin)

            # 緩存結果
            self.last_view_range = (view_start, view_end)

            # 記錄到歷史
            self._add_to_history({
                'selection': (start_ms, end_ms),
                'view': (view_start, view_end)
            })

            return view_start, view_end

        except Exception as e:
            self.logger.error(f"計算最佳視圖範圍時出錯: {e}")
            # 返回安全的默認值 - 從0開始的5秒視圖
            return 0, min(5000, self.audio_duration)

    def calculate_view_range_on_slide(self,
                                 new_time: float,
                                 fixed_time: float,
                                 is_start_adjustment: bool) -> Tuple[float, float]:
        """
        根據滑桿移動計算新的視圖範圍

        Args:
            new_time: 滑桿新位置對應的時間
            fixed_time: 固定點時間
            is_start_adjustment: 是否正在調整開始時間

        Returns:
            (新視圖開始時間, 新視圖結束點時間)
        """
        # 確保時間值有效
        new_time = max(0, min(new_time, self.audio_duration))
        fixed_time = max(0, min(fixed_time, self.audio_duration))

        # 根據調整類型設置選擇範圍
        if is_start_adjustment:
            start_time = min(new_time, fixed_time - self.min_selection_width)
            end_time = fixed_time
        else:
            start_time = fixed_time
            end_time = max(new_time, fixed_time + self.min_selection_width)

        # 更新選擇區域
        self.last_selection = (start_time, end_time)

        # 使用選擇區域計算新的視圖範圍
        return self.get_optimal_view_range((start_time, end_time))

    def _validate_time_range(self, time_range: Tuple[float, float]) -> Tuple[float, float]:
        """
        驗證並修正時間範圍，確保時間有效且範圍合理
        """
        start, end = time_range

        # 確保開始時間不大於結束時間
        if start > end:
            self.logger.warning(f"時間範圍顛倒: {start} - {end}，自動交換")
            start, end = end, start

        # 確保時間在有效範圍內
        start = max(0, min(start, self.audio_duration))
        end = max(start + self.min_selection_width, min(end, self.audio_duration))

        return start, end

    def _calculate_view_width(self, duration: float) -> float:
        """
        根據選擇區域持續時間動態計算合適的視圖寬度

        Args:
            duration: 選擇區域的持續時間（毫秒）

        Returns:
            合適的視圖寬度（毫秒）
        """
        # 確保持續時間有效
        duration = max(1, duration)

        # 基於選擇持續時間的動態縮放計算
        if duration < 100:      # 極短時間（<100ms）
            return max(self.min_view_width, duration * 20)
        elif duration < 500:    # 短時間（100-500ms）
            return max(self.min_view_width, duration * 12)
        elif duration < 1000:   # 中短時間（0.5-1秒）
            return max(self.min_view_width, duration * 8)
        elif duration < 3000:   # 中等時間（1-3秒）
            return max(self.min_view_width, duration * 5)
        elif duration < 10000:  # 中長時間（3-10秒）
            return max(self.min_view_width, duration * 3)
        else:                   # 長時間（>10秒）
            return max(self.min_view_width, duration * 2)

    def calculate_zoom_level(self, selection: Tuple[float, float]) -> float:
        """
        根據選擇區域計算適當的縮放級別

        Args:
            selection: 選擇區域範圍 (start_ms, end_ms)

        Returns:
            縮放級別（1.0為標準縮放）
        """
        start_ms, end_ms = self._validate_time_range(selection)
        duration = end_ms - start_ms

        # 根據持續時間計算縮放級別
        if duration < 50:          # 極短範圍 (<50ms)
            return 5.0             # 極度放大
        elif duration < 100:       # 非常短時間 (<100ms)
            return 4.0             # 非常高縮放
        elif duration < 250:       # 較短範圍 (<250ms)
            return 3.0             # 高縮放
        elif duration < 500:       # 短範圍 (<500ms)
            return 2.5             # 中高縮放
        elif duration < 1000:      # 中短範圍 (<1s)
            return 2.0             # 中等縮放
        elif duration < 2000:      # 中等範圍 (<2s)
            return 1.5             # 低縮放
        else:                      # 長範圍 (>=2s)
            return 1.0             # 標準縮放

    def zoom_to_fit(self, selection: Tuple[float, float]) -> Tuple[float, float]:
        """
        計算最佳視圖範圍，使選擇區域居中並有適當的邊距

        Args:
            selection: 選擇區域 (start_ms, end_ms)

        Returns:
            適合的視圖範圍 (view_start_ms, view_end_ms)
        """
        # 驗證選擇範圍
        start_ms, end_ms = self._validate_time_range(selection)

        # 計算選擇持續時間
        duration = end_ms - start_ms

        # 初始視圖寬度 - 選擇區域的3-5倍，取決於持續時間
        if duration < 200:
            view_width = duration * 5  # 對於非常短的選擇，視圖寬度為5倍
        elif duration < 1000:
            view_width = duration * 4  # 較短的選擇
        elif duration < 5000:
            view_width = duration * 3  # 中等長度
        else:
            view_width = duration * 2  # 長選擇

        # 限制視圖寬度在最小和最大範圍內
        view_width = max(self.min_view_width, min(self.max_view_width, view_width))

        # 計算選擇區域的中心點
        center = (start_ms + end_ms) / 2

        # 計算視圖範圍，使選擇區域居中
        view_start = max(0, center - view_width / 2)
        view_end = min(self.audio_duration, view_start + view_width)

        # 如果視圖已到達音頻結尾，調整起始點
        if view_end == self.audio_duration and view_end - view_start < view_width:
            view_start = max(0, view_end - view_width)

        return view_start, view_end

    def set_audio_features(self, features: Dict[str, Any]) -> None:
        """
        設置當前音頻段落的特性，用於更智能的範圍計算

        Args:
            features: 音頻特性詞典
        """
        self.audio_features = features

    def _add_to_history(self, entry: Dict[str, Any]) -> None:
        """
        添加範圍到歷史記錄

        Args:
            entry: 範圍記錄
        """
        # 添加新記錄
        self.history.append(entry)

        # 限制歷史長度
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def get_last_view_range(self) -> Tuple[float, float]:
        """
        獲取最後計算的視圖範圍

        Returns:
            (view_start, view_end)
        """
        return self.last_view_range

    def get_last_selection(self) -> Tuple[float, float]:
        """
        獲取最後的選擇範圍

        Returns:
            (selection_start, selection_end)
        """
        return self.last_selection