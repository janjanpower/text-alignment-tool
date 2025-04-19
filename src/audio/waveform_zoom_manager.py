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
        if duration <= 0:
            duration = 100  # 最小持續時間

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

        # 確保包含完整選擇區域
        if view_start > start_time:
            view_start = max(0, start_time - view_width * 0.1)
        if view_end < end_time:
            view_end = min(self.audio_duration, end_time + view_width * 0.1)

        # 如果計算結果無效，使用默認值
        if view_end <= view_start:
            view_start = max(0, center_time - 1000)
            view_end = min(self.audio_duration, center_time + 1000)

        return view_start, view_end