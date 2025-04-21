"""資源清理相關模組"""

import logging
import tkinter as tk
from typing import Optional, Callable, List


class ResourceCleaner:
    """資源清理基礎類別，提供更強大的資源清理功能"""

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
                    bindings = ResourceCleaner._get_all_bindings(widget)
                    for binding in bindings:
                        try:
                            widget.unbind(binding)
                        except Exception:
                            pass
                except Exception:
                    pass

            # 確保處理完所有待處理的事件
            try:
                window.update_idletasks()
            except tk.TclError:
                pass  # 忽略可能的錯誤

        except Exception as e:
            logger.error(f"清理視窗資源時出錯: {e}")

    @staticmethod
    def _get_all_bindings(widget) -> List[str]:
        """獲取控件的所有綁定"""
        try:
            bindings = []
            # 嘗試獲取虛擬事件綁定
            try:
                bindings.extend(widget.bind())
            except:
                pass

            # 嘗試獲取其他常見事件類型
            common_events = [
                '<Button-1>', '<Button-3>', '<Double-1>', '<Enter>', '<Leave>',
                '<FocusIn>', '<FocusOut>', '<Key>', '<Return>', '<Escape>',
                '<Configure>', '<Motion>', '<B1-Motion>', '<MouseWheel>'
            ]

            for event in common_events:
                try:
                    if widget.bind(event):
                        bindings.append(event)
                except:
                    pass

            return bindings
        except Exception as e:
            logging.getLogger("ResourceCleaner").warning(f"獲取控件綁定時出錯: {e}")
            return []

    @staticmethod
    def safe_destroy(widget) -> None:
        """安全地銷毀控件"""
        try:
            widget.destroy()
        except tk.TclError:
            pass  # 忽略控件已被銷毀的錯誤
        except Exception as e:
            logging.getLogger("ResourceCleaner").warning(f"銷毀控件時出錯: {e}")

    @staticmethod
    def safe_close_window(window: tk.Tk, cleanup_callback: Optional[Callable] = None) -> None:
        """
        安全地關閉視窗

        :param window: 要關閉的視窗
        :param cleanup_callback: 關閉前執行的清理函數
        """
        logger = logging.getLogger("ResourceCleaner")
        try:
            # 釋放抓取
            try:
                window.grab_release()
            except:
                pass

            # 執行清理回調
            if cleanup_callback and callable(cleanup_callback):
                try:
                    cleanup_callback()
                except Exception as e:
                    logger.error(f"執行清理回調時出錯: {e}")

            # 清理視窗資源
            ResourceCleaner.clear_window_resources(window)

            # 確保處理完所有待處理的事件
            try:
                window.update_idletasks()
            except:
                pass

            # 銷毀視窗
            ResourceCleaner.safe_destroy(window)

        except Exception as e:
            logger.error(f"安全關閉視窗時出錯: {e}")
            try:
                # 最後嘗試直接銷毀視窗
                window.destroy()
            except:
                pass