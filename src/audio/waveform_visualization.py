"""
為了向後兼容性而保留的文件。
這個模組實際上重導入了 AudioVisualizer。
import tkinter as tk
from typing import Tuple

import numpy as np
from PIL import Image, ImageTk, ImageDraw
from pydub import AudioSegment
"""

import logging
from audio.audio_visualizer import AudioVisualizer

# 為向後兼容性設置別名
WaveformVisualization = AudioVisualizer

# 發出棄用警告
logger = logging.getLogger("WaveformVisualization")
logger.warning(
    "WaveformVisualization 已合併到 AudioVisualizer 中。"
    "請在新代碼中直接使用 AudioVisualizer，以獲得更好的性能和功能。"
)