"""文本對齊工具套件"""

import os
import sys

# 獲取當前目錄
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from utils import *
from .base_window import BaseWindow
from .base_dialog import BaseDialog
from .text_edit_dialog import TextEditDialog
from .project_manager import ProjectManager
from .config_manager import ConfigManager
from .state_manager import StateManager
from .audio_player import AudioPlayer
from .alignment_gui import AlignmentGUI


__all__ = [
    'BaseWindow',
    'BaseDialog',
    'TextEditDialog',
    'ProjectManager',
    'ConfigManager',
    'StateManager',
    'AudioPlayer',
    'AlignmentGUI'
]