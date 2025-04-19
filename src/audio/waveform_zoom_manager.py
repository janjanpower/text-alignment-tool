# src/audio/waveform_zoom_manager.py
from typing import Tuple


class WaveformZoomManager:
    """
    波形縮放管理器，負責動態計算視圖範圍和縮放比例
    """
    def __init__(self, audio_duration: int):
        self.audio_duration = audio_duration
        self.min_view_width = 500  # 最小視窗寬度（毫秒）
        self.max_view_width = 10000  # 最大視窗寬度（毫秒）

    def calculate_optimal_zoom(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """
        計算最佳縮放級別，根據選中文本的持續時間動態調整
        """
        duration = end_time - start_time
        center_time = (start_time + end_time) / 2

        # 動態調整縮放係數
        if duration < 100:  # 極短文本（< 0.1秒）
            zoom_factor = 5.0
        elif duration < 500:  # 短文本（< 0.5秒）
            zoom_factor = 4.0
        elif duration < 1000:  # 中等長度（< 1秒）
            zoom_factor = 3.0
        elif duration < 3000:  # 較長文本（< 3秒）
            zoom_factor = 2.5
        else:  # 長文本（≥ 3秒）
            zoom_factor = 2.0

        view_width = duration * zoom_factor
        view_width = max(self.min_view_width, min(self.max_view_width, view_width))

        # 計算視圖起始和結束位置
        view_start = max(0, center_time - view_width / 2)
        view_end = min(self.audio_duration, view_start + view_width)

        # 調整確保包含完整選擇區域
        if view_start > start_time:
            view_start = max(0, start_time - view_width * 0.1)
        if view_end < end_time:
            view_end = min(self.audio_duration, end_time + view_width * 0.1)

        return view_start, view_end

    def calculate_drag_zoom(self, new_time: int, fixed_time: int,
                           is_start_adjustment: bool,
                           current_view_range: Tuple[int, int]) -> Tuple[int, int]:
        """
        計算拖動時的縮放效果
        """
        current_duration = abs(new_time - fixed_time)
        current_view_width = current_view_range[1] - current_view_range[0]

        # 根據選擇範圍變化調整視圖寬度
        if current_duration < 500:
            new_view_width = current_view_width * 0.9  # 放大視圖
        elif current_duration > 2000:
            new_view_width = current_view_width * 1.1  # 縮小視圖
        else:
            new_view_width = current_view_width

        new_view_width = max(self.min_view_width, min(self.max_view_width, new_view_width))

        # 計算新的視圖範圍
        if is_start_adjustment:
            view_end = min(self.audio_duration, fixed_time + new_view_width * 0.3)
            view_start = max(0, view_end - new_view_width)
        else:
            view_start = max(0, fixed_time - new_view_width * 0.3)
            view_end = min(self.audio_duration, view_start + new_view_width)

        return view_start, view_end