"""資源清理相關模組"""

import logging
import tkinter as tk
from typing import Optional



class ResourceCleaner:
    """資源清理基礎類別"""

    @staticmethod
    def clear_window_resources(window: tk.Tk) -> None:
        """清理視窗相關資源"""
        logger = logging.getLogger("ResourceCleaner")
        try:
            # 停止所有計時器
            for after_id in window.tk.eval('after info').split():
                try:
                    window.after_cancel(after_id)
                except Exception:
                    pass

            # 解除所有事件綁定
            for widget in window.winfo_children():
                try:
                    for binding in widget.bind():
                        widget.unbind(binding)
                except Exception:
                    pass

            # 確保處理完所有待處理的事件
            window.update_idletasks()

        except Exception as e:
            logger.error(f"清理視窗資源時出錯: {e}")