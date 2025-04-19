"""時間範圍處理工具類別，用於音頻可視化的時間範圍管理和驗證"""

import logging
from typing import Tuple, Optional


class TimeRangeHandler:
    """時間範圍處理工具，提供各種時間範圍的驗證、修復和調整功能"""

    def __init__(self):
        """初始化時間範圍處理器"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_range(self, time_range: Tuple[float, float],
                       max_duration: float,
                       min_range: float = 100.0) -> Tuple[float, float]:
        """
        驗證並修正時間範圍

        Args:
            time_range: 輸入的時間範圍 (start, end)
            max_duration: 最大合法時間值
            min_range: 最小範圍持續時間

        Returns:
            修正後的有效時間範圍 (start, end)
        """
        if not isinstance(time_range, tuple) or len(time_range) != 2:
            self.logger.warning(f"無效的時間範圍格式: {time_range}，使用默認範圍(0, {min_range})")
            return (0.0, min_range)

        start, end = time_range

        # 轉換為浮點數以確保一致性
        try:
            start = float(start)
            end = float(end)
        except (ValueError, TypeError):
            self.logger.warning(f"無法轉換時間範圍為數值: {time_range}，使用默認範圍(0, {min_range})")
            return (0.0, min_range)

        # 檢查並交換順序顛倒的時間
        if start > end:
            self.logger.warning(f"時間範圍順序顛倒: ({start}, {end})，自動交換")
            start, end = end, start

        # 確保時間在合法範圍內
        start = max(0.0, min(start, max_duration))
        end = max(start, min(end, max_duration))

        # 確保範圍至少有最小持續時間
        if end - start < min_range:
            # 嘗試擴展結束時間
            if end + min_range <= max_duration:
                end = start + min_range
            # 若無法擴展結束時間，則嘗試縮小開始時間
            elif start - min_range >= 0:
                start = end - min_range
            # 若兩者都不可行，則重置到有效範圍
            else:
                start = 0.0
                end = min(min_range, max_duration)

        return (start, end)

    def create_view_range(self, selection_range: Tuple[float, float],
                          max_duration: float,
                          context_factor: float = 3.0,
                          min_view_width: float = 2000.0) -> Tuple[float, float]:
        """
        根據選擇範圍創建合適的視圖範圍

        Args:
            selection_range: 選擇範圍 (start, end)
            max_duration: 最大合法時間值
            context_factor: 視圖範圍相對於選擇範圍的倍數
            min_view_width: 最小視圖寬度

        Returns:
            合適的視圖範圍 (view_start, view_end)
        """
        # 先確保選擇範圍有效
        sel_start, sel_end = self.validate_range(selection_range, max_duration)

        # 計算選擇中心點和持續時間
        duration = sel_end - sel_start
        center = (sel_start + sel_end) / 2

        # 計算適當的視圖寬度
        view_width = max(duration * context_factor, min_view_width)

        # 根據中心點和視圖寬度計算視圖範圍
        view_start = max(0.0, center - view_width / 2)
        view_end = min(max_duration, view_start + view_width)

        # 確保視圖寬度得到保持，若超出上限則調整起點
        if view_end == max_duration and view_end - view_start < view_width:
            view_start = max(0.0, max_duration - view_width)

        # 確保選擇範圍在視圖範圍內
        if sel_start < view_start:
            # 如果選擇開始點在視圖開始點之前，擴展視圖
            delta = view_start - sel_start
            view_start = sel_start
            # 嘗試同等擴展結束點，除非超出最大時間
            view_end = min(max_duration, view_end + delta)

        if sel_end > view_end:
            # 如果選擇結束點在視圖結束點之後，擴展視圖
            delta = sel_end - view_end
            view_end = sel_end
            # 嘗試同等擴展開始點，除非低於0
            view_start = max(0.0, view_start - delta)

        # 最終驗證確保範圍有效
        return self.validate_range((view_start, view_end), max_duration, min_view_width / 10)