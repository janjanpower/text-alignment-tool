import tkinter as tk
import logging
from typing import Optional
from gui.base_window import BaseWindow

def show_new_window(root: tk.Tk, window: BaseWindow) -> None:
    """
    顯示新視窗
    """
    logger = logging.getLogger(__name__)
    try:
        # 更新檔案資訊（如果有的話）
        if hasattr(window, 'update_file_info'):
            window.update_file_info()

        # 顯示視窗
        root.deiconify()
        root.focus_force()

    except Exception as e:
        logger.error(f"顯示新視窗時出錯: {e}")
        import sys
        sys.exit(1)