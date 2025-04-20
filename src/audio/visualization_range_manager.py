"""音頻可視化範圍管理器"""

import logging
from typing import Tuple, Optional


class VisualizationRangeManager:
    """管理音頻可視化的視圖範圍和選擇範圍"""

    def __init__(self, audio_duration: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audio_duration = max(1, audio_duration)  # 確保最小為 1ms
        self.last_selection_duration = 0
        self.last_view_range = (0, self.audio_duration)

    def validate_range(self, time_range: Tuple[float, float],
                     min_duration: float = 100.0) -> Tuple[float, float]:
        """
        驗證並修正時間範圍，確保範圍有效

        Args:
            time_range: 輸入的時間範圍 (start, end)
            min_duration: 最小持續時間

        Returns:
            修正後的有效時間範圍 (start, end)
        """
        start, end = time_range

        # 確保開始時間不大於結束時間
        if start > end:
            self.logger.warning(f"時間範圍顛倒: {start} - {end}，自動交換")
            start, end = end, start

        # 確保時間在有效範圍內
        start = max(0, min(start, self.audio_duration))
        end = max(start + min_duration, min(end, self.audio_duration))

        return start, end

    def calculate_initial_view_range(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """
        計算初始視圖範圍，確保完整顯示文本時間段

        Args:
            start_time: 文本開始時間
            end_time: 文本結束時間

        Returns:
            (視圖開始時間, 視圖結束時間)
        """
        # 先確保範圍有效
        start_time, end_time = self.validate_range((start_time, end_time))

        duration = end_time - start_time
        center_time = (start_time + end_time) / 2

        # 計算視圖寬度，基於文本持續時間
        view_width = self._calculate_view_width(duration)

        # 計算視圖範圍
        view_start = max(0, center_time - view_width / 2)
        view_end = min(self.audio_duration, view_start + view_width)

        # 如果視圖未能完全包含選擇範圍，進行調整
        if start_time < view_start:
            view_start = max(0, start_time - view_width * 0.1)
            view_end = min(self.audio_duration, view_start + view_width)

        if end_time > view_end:
            view_end = min(self.audio_duration, end_time + view_width * 0.1)
            view_start = max(0, view_end - view_width)

        return view_start, view_end

    def calculate_view_range_on_slide(self,
                                    new_time: int,
                                    fixed_time: int,
                                    is_start_adjustment: bool,
                                    current_view_range: Tuple[int, int]) -> Tuple[int, int]:
        """
        根據滑桿移動計算新的視圖範圍

        Args:
            new_time: 滑桿新位置對應的時間
            fixed_time: 固定點時間
            is_start_adjustment: 是否正在調整開始時間
            current_view_range: 當前視圖範圍

        Returns:
            (新視圖開始時間, 新視圖結束點時間)
        """
        # 確保時間值有效
        new_time = max(0, min(new_time, self.audio_duration))
        fixed_time = max(0, min(fixed_time, self.audio_duration))

        if is_start_adjustment:
            start_time = min(new_time, fixed_time - 100)  # 確保開始時間小於結束時間
            end_time = fixed_time
        else:
            start_time = fixed_time
            end_time = max(new_time, fixed_time + 100)  # 確保結束時間大於開始時間

        # 計算持續時間變化比例
        current_duration = end_time - start_time
        prev_duration = max(self.last_selection_duration, 1)
        duration_change_ratio = current_duration / prev_duration

        # 根據時間變化調整視圖範圍
        view_start, view_end = current_view_range
        current_view_width = max(1, view_end - view_start)

        if duration_change_ratio < 0.8:  # 時間顯著縮短，放大視圖
            new_view_width = max(1000, current_view_width * 0.8)
        elif duration_change_ratio > 1.5:  # 時間顯著延長，縮小視圖
            new_view_width = min(self.audio_duration, current_view_width * 1.2)
        else:
            new_view_width = current_view_width

        # 計算新的視圖範圍
        if is_start_adjustment:
            # 保持固定點（結束時間）在視圖右側
            view_end = min(self.audio_duration, fixed_time + new_view_width * 0.2)
            view_start = max(0, view_end - new_view_width)
        else:
            # 保持固定點（開始時間）在視圖左側
            view_start = max(0, fixed_time - new_view_width * 0.2)
            view_end = min(self.audio_duration, view_start + new_view_width)

        # 確保滑動部分在視圖中可見
        if start_time < view_start:
            view_start = max(0, start_time - new_view_width * 0.1)
            view_end = min(self.audio_duration, view_start + new_view_width)

        if end_time > view_end:
            view_end = min(self.audio_duration, end_time + new_view_width * 0.1)
            view_start = max(0, view_end - new_view_width)

        # 更新狀態
        self.last_selection_duration = current_duration
        self.last_view_range = (view_start, view_end)

        return view_start, view_end

    def _calculate_view_width(self, duration: int) -> int:
        """
        根據文本持續時間計算合適的視圖寬度

        Args:
            duration: 文本持續時間

        Returns:
            視圖寬度
        """
        # 確保持續時間有效
        duration = max(1, duration)

        # 基本規則：視圖寬度為時間範圍的3倍，但不小於2秒
        if duration < 1000:  # 小於1秒
            return max(2000, duration * 4)
        elif duration < 5000:  # 1-5秒
            return duration * 3
        else:  # 大於5秒
            return duration * 2