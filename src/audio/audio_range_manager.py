"""音頻範圍管理器：整合視圖範圍計算、時間範圍處理和波形縮放功能"""

import logging
from typing import Tuple
import tkinter as tk


class AudioRangeManager:
    """
    統一的音頻範圍管理器，提供：
    - 視圖範圍計算 (原 WaveformZoomManager)
    - 時間範圍驗證 (原 TimeRangeHandler)
    - 視覺化範圍管理 (原 VisualizationRangeManager)
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
        self.min_selection_width = 50 # 最小選擇寬度（毫秒）  # 確保這行正確

        # 緩存最後一次計算的範圍
        self.last_selection = (0, min(5000, self.audio_duration))
        self.last_view_range = (0, min(10000, self.audio_duration))

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

            # 緩存結果
            self.last_view_range = (view_start, view_end)

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
            # 這裡使用正確的屬性
            start_time = min(new_time, fixed_time - self.min_selection_width)
            end_time = fixed_time
        else:
            start_time = fixed_time
            # 這裡也使用正確的屬性
            end_time = max(new_time, fixed_time + self.min_selection_width)

        # 更新選擇區域
        self.last_selection = (start_time, end_time)

        # 使用選擇區域計算新的視圖範圍
        return self.get_optimal_view_range((start_time, end_time))

    def _validate_time_range(self, time_range: Tuple[float, float]) -> Tuple[float, float]:
        """
        驗證並修正時間範圍
        """
        start, end = time_range

        # 確保開始時間不大於結束時間
        if start > end:
            self.logger.warning(f"時間範圍顛倒: {start} - {end}，自動交換")
            start, end = end, start

        # 確保時間在有效範圍內
        start = max(0, min(start, self.audio_duration))

        # 使用 self.min_selection_width 而不是局部變數
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

    # 兼容舊版接口
    def calculate_optimal_zoom(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """
        計算最佳縮放級別 (兼容舊版接口)

        Args:
            start_time: 開始時間（毫秒）
            end_time: 結束時間（毫秒）

        Returns:
            (view_start, view_end): 視圖範圍（毫秒）
        """
        return self.get_optimal_view_range((start_time, end_time))



class WaveformVisualization:
    """整合音頻波形可視化類別，結合了視圖範圍管理和音頻可視化功能"""

    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 50):
        """初始化音頻可視化器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.width = width
        self.height = height

        # 創建畫布
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg="#233A68",
            highlightthickness=0
        )

        # 波形相關變數
        self.waveform_image = None
        self.waveform_photo = None
        self.audio_duration = 0

        # 保存原始音頻數據用於動態縮放
        self.original_audio = None
        self.current_view_range = (0, 0)
        self.current_selection_range = (0, 0)
        self.samples_cache = None  # 緩存音頻樣本數據

        # 視圖配置
        self.min_view_width = 500    # 最小視圖寬度（毫秒）
        self.max_view_width = 10000  # 最大視圖寬度（毫秒）
        self.min_selection_width = 100  # 最小選擇區域寬度（毫秒）

        # 初始狀態設置為空白波形
        self._create_empty_waveform("等待音頻...")

        # 添加用於動畫過渡的變數
        self.animation_active = False
        self.target_view_range = (0, 0)
        self.target_selection_range = (0, 0)
        self.animation_frames = 10
        self.animation_duration = 0.2  # 秒
        self.prev_waveform_image = None
        self.prev_view_range = (0, 0)

    def get_optimal_view_range(self, selection: Tuple[int, int]) -> Tuple[int, int]:
        """
        整合的方法：根據選擇區域計算最佳視圖範圍

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

    def _calculate_view_width(self, selection_duration: int) -> int:
        """
        根據選擇區域持續時間計算合適的視圖寬度

        Args:
            selection_duration: 選擇區域的持續時間（毫秒）

        Returns:
            合適的視圖寬度（毫秒）
        """
        # 根據選擇時間長度使用不同的縮放因子
        if selection_duration < 100:     # 極短時間（小於100毫秒）
            zoom_factor = 10.0
        elif selection_duration < 500:   # 非常短時間（100-500毫秒）
            zoom_factor = 6.0
        elif selection_duration < 2000:  # 短時間（0.5-2秒）
            zoom_factor = 4.0
        elif selection_duration < 5000:  # 中等時間（2-5秒）
            zoom_factor = 3.0
        else:                          # 長時間（>5秒）
            zoom_factor = 2.0

        # 計算並限制視圖寬度
        view_width = max(self.min_view_width, min(self.max_view_width, selection_duration * zoom_factor))

        return view_width
