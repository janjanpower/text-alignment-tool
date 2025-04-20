"""簡化的波形縮放管理器模組，只專注於時間範圍的視圖計算"""

import logging
from typing import Tuple


class WaveformZoomManager:
    """
    簡化的波形縮放管理器，專注於提供基本的視圖範圍計算
    - 只負責根據選擇範圍計算合適的視圖範圍
    - 移除了所有交互功能（按鍵、縮放等）
    - 保留與滑桿和時間標籤相關的核心功能
    """

    def __init__(self, audio_duration: int):
        """
        初始化波形縮放管理器

        Args:
            audio_duration: 音頻總長度（毫秒）
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audio_duration = audio_duration

        # 視圖範圍配置
        self.min_view_width = 500   # 最小視圖寬度（毫秒）
        self.max_view_width = 10000  # 最大視圖寬度（毫秒）
        self.min_selection_width = 100  # 最小選擇區域寬度（毫秒）

    def get_optimal_view_range(self, selection: Tuple[int, int]) -> Tuple[int, int]:
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

            # 計算選擇區域中心點和持續時間
            duration = max(end_ms - start_ms, self.min_selection_width)
            center_time = (start_ms + end_ms) / 2

            # 動態計算視圖寬度
            view_width = self._calculate_view_width(duration)

            # 計算視圖範圍
            view_start = max(0, center_time - view_width / 2)
            view_end = min(self.audio_duration, view_start + view_width)

            # 確保視圖包含完整的選擇區域
            if start_ms < view_start:
                view_start = max(0, start_ms - view_width * 0.1)
                view_end = min(self.audio_duration, view_start + view_width)

            if end_ms > view_end:
                view_end = min(self.audio_duration, end_ms + view_width * 0.1)
                view_start = max(0, view_end - view_width)

            return view_start, view_end

        except Exception as e:
            self.logger.error(f"計算視圖範圍時出錯: {e}")
            # 返回默認範圍
            return 0, min(self.audio_duration, 5000)

    def calculate_optimal_zoom(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """
        計算最佳縮放級別，根據選中文本的持續時間動態調整
        (兼容舊版接口)

        Args:
            start_time: 開始時間（毫秒）
            end_time: 結束時間（毫秒）

        Returns:
            (view_start, view_end): 視圖範圍（毫秒）
        """
        # 簡單調用 get_optimal_view_range 以保持兼容性
        return self.get_optimal_view_range((start_time, end_time))

    def _calculate_view_width(self, selection_duration: int) -> int:
        """
        根據選擇區域持續時間計算合適的視圖寬度

        Args:
            selection_duration: 選擇區域的持續時間（毫秒）

        Returns:
            合適的視圖寬度（毫秒）
        """
        # 根據選擇時間長度使用不同的縮放因子
        if selection_duration < 500:  # 短於0.5秒
            zoom_factor = 4.0
        elif selection_duration < 2000:  # 短於2秒
            zoom_factor = 3.0
        elif selection_duration < 5000:  # 短於5秒
            zoom_factor = 2.5
        else:  # 長於5秒
            zoom_factor = 2.0

        # 計算並限制視圖寬度
        view_width = max(self.min_view_width, min(self.max_view_width, selection_duration * zoom_factor))

        return view_width

    def _validate_time_range(self, time_range: Tuple[int, int]) -> Tuple[int, int]:
        """
        驗證並修正時間範圍

        Args:
            time_range: 時間範圍 (start_ms, end_ms)

        Returns:
            修正後的時間範圍 (start_ms, end_ms)
        """
        start_ms, end_ms = time_range

        # 確保開始時間不小於0
        start_ms = max(0, start_ms)

        # 確保結束時間不超過音頻總長度
        end_ms = min(self.audio_duration, end_ms)

        # 確保開始時間小於結束時間
        if start_ms >= end_ms:
            # 如果開始時間大於等於結束時間，重置為合理值
            if start_ms == 0:
                end_ms = min(self.min_selection_width, self.audio_duration)
            else:
                start_ms = max(0, end_ms - self.min_selection_width)

        return start_ms, end_ms