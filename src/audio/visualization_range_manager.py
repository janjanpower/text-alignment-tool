"""音頻可視化範圍管理器"""

import logging
from typing import Tuple


class VisualizationRangeManager:
    """管理音頻可視化的視圖範圍和選擇範圍"""

    def __init__(self, audio_duration: int):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audio_duration = audio_duration
        self.last_selection_duration = 0
        self.last_view_range = (0, audio_duration)

    def calculate_initial_view_range(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """
        計算初始視圖範圍，確保完整顯示文本時間段

        Args:
            start_time: 文本開始時間
            end_time: 文本結束時間

        Returns:
            (視圖開始時間, 視圖結束時間)
        """
        duration = end_time - start_time
        center_time = (start_time + end_time) / 2

        # 計算視圖寬度，基於文本持續時間
        view_width = self._calculate_view_width(duration)

        # 計算視圖範圍
        view_start = max(0, center_time - view_width / 2)
        view_end = min(self.audio_duration, center_time + view_width / 2)

        # 確保視圖範圍包含完整的文本時間段
        if start_time < view_start:
            view_start = max(0, start_time - view_width * 0.1)
        if end_time > view_end:
            view_end = min(self.audio_duration, end_time + view_width * 0.1)

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
            (新視圖開始時間, 新視圖結束時間)
        """
        if is_start_adjustment:
            start_time = new_time
            end_time = fixed_time
        else:
            start_time = fixed_time
            end_time = new_time

        # 計算時間變化率
        current_duration = end_time - start_time
        duration_change_ratio = current_duration / max(self.last_selection_duration, 1)

        # 根據時間變化調整視圖範圍
        current_view_width = current_view_range[1] - current_view_range[0]

        if duration_change_ratio < 1.0:  # 時間縮短，放大視圖
            new_view_width = max(1000, current_view_width * 0.8)
        elif duration_change_ratio > 1.0:  # 時間延長，縮小視圖
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
            view_end = view_start + new_view_width
        if end_time > view_end:
            view_end = min(self.audio_duration, end_time + new_view_width * 0.1)
            view_start = max(0, view_end - new_view_width)

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
        # 基本規則：視圖寬度為時間範圍的3倍，但不小於2秒
        if duration < 1000:  # 小於1秒
            return max(2000, duration * 4)
        elif duration < 5000:  # 1-5秒
            return duration * 3
        else:  # 大於5秒
            return duration * 2