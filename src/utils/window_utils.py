import tkinter as tk
import logging
from typing import Optional
from gui.base_window import BaseWindow

def show_new_window(root: tk.Tk, window: BaseWindow) -> None:
    """
    顯示新視窗並確保資源正確處理
    """
    logger = logging.getLogger(__name__)
    try:
        # 更新檔案資訊（如果有的話）
        if hasattr(window, 'update_file_info'):
            window.update_file_info()

        # 在顯示視窗前，確保處理完所有待處理的事件
        root.update_idletasks()

        # 顯示視窗
        root.deiconify()
        root.focus_force()

    except tk.TclError as e:
        # 特別處理 TclError，通常發生在視窗已被刪除的情況
        if "window was deleted" in str(e):
            logger.warning(f"視窗已被刪除，無法顯示: {e}")
        else:
            logger.error(f"顯示新視窗時出現 TclError: {e}")
    except Exception as e:
        logger.error(f"顯示新視窗時出錯: {e}")
        import sys
        sys.exit(1)


def close_window_safely(window: tk.Tk, cleanup_callback=None) -> None:
    """
    安全地關閉視窗，確保所有資源正確清理

    :param window: 要關閉的視窗
    :param cleanup_callback: 關閉前執行的清理函數
    """
    logger = logging.getLogger(__name__)
    try:
        # 先解除所有事件綁定
        for widget in window.winfo_children():
            for binding in widget.bind():
                try:
                    widget.unbind(binding)
                except tk.TclError:
                    pass

        # 取消所有計時器
        for after_id in window.tk.eval('after info').split():
            try:
                window.after_cancel(after_id)
            except tk.TclError:
                pass

        # 執行自定義清理回調
        if cleanup_callback and callable(cleanup_callback):
            cleanup_callback()

        # 確保處理完所有待處理的事件
        try:
            window.update_idletasks()
        except tk.TclError:
            pass  # 忽略已刪除視窗的錯誤

        # 釋放焦點和抓取
        try:
            window.grab_release()
        except tk.TclError:
            pass  # 可能沒有抓取視窗焦點

        # 銷毀視窗
        try:
            window.destroy()
        except tk.TclError as e:
            logger.warning(f"視窗已被刪除，無需再次銷毀: {e}")
    except Exception as e:
        logger.error(f"安全關閉視窗時出錯: {e}")
        try:
            # 嘗試直接銷毀視窗
            window.destroy()
        except:
            pass  # 忽略所有錯誤