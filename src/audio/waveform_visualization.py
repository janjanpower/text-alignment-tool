"""
音頻波形可視化模組的向後兼容層

此模組重導入 AudioVisualizer 類，保持向後兼容性。
新代碼應直接使用 AudioVisualizer 類。
"""

import logging
import warnings
from audio.audio_visualizer import AudioVisualizer

# 發出棄用警告
warnings.warn(
    "WaveformVisualization 已重構並合併到 AudioVisualizer 中。"
    "請在新代碼中直接使用 AudioVisualizer，以獲得更好的性能和功能。",
    DeprecationWarning,
    stacklevel=2
)

# 為向後兼容性設置別名
WaveformVisualization = AudioVisualizer

# 記錄日誌
logger = logging.getLogger("WaveformVisualization")
logger.warning(
    "WaveformVisualization 已合併到 AudioVisualizer 中。"
    "請在新代碼中直接使用 AudioVisualizer，以獲得更好的性能和功能。"
)