"""彈出視窗處理工具模組"""

import tkinter as tk
import logging
from typing import Optional, Any, Callable, Type, Dict, Union

# 配置日誌
logger = logging.getLogger(__name__)

def show_dialog_with_topmost(dialog_class, parent, *args, **kwargs):
    """
    顯示置頂對話框並返回結果

    :param dialog_class: 對話框類別
    :param parent: 父視窗
    :param args: 傳遞給對話框的位置參數
    :param kwargs: 傳遞給對話框的關鍵字參數
    :return: 對話框結果
    """
    try:
        # 保存父視窗的置頂狀態
        original_topmost = False
        if hasattr(parent, 'attributes'):
            try:
                original_topmost = parent.attributes('-topmost')
            except:
                pass

            # 暫時取消父視窗的置頂狀態
            try:
                parent.attributes('-topmost', False)
                parent.update()
            except:
                pass

        # 創建對話框實例
        dialog = dialog_class(parent, *args, **kwargs)

        # 確保對話框置頂
        dialog_window = None
        if hasattr(dialog, 'window'):
            dialog_window = dialog.window
        elif isinstance(dialog, tk.Toplevel):
            dialog_window = dialog

        if dialog_window:
            try:
                # 設置為 parent 的子視窗
                dialog_window.transient(parent)

                # 設置為模態視窗
                dialog_window.grab_set()

                # 設置置頂
                dialog_window.attributes('-topmost', True)
                dialog_window.update()

                # 強制獲取焦點
                dialog_window.focus_force()
            except Exception as e:
                logger.warning(f"設置對話框視窗屬性時出錯: {e}")

        # 運行對話框
        result = None
        if hasattr(dialog, 'run'):
            result = dialog.run()
        else:
            # 對於沒有 run 方法的對話框，等待視窗關閉
            if dialog_window:
                parent.wait_window(dialog_window)
                if hasattr(dialog, 'result'):
                    result = dialog.result

        # 恢復父視窗的原始置頂狀態
        if hasattr(parent, 'attributes') and original_topmost:
            try:
                parent.attributes('-topmost', original_topmost)
                parent.update()
                parent.focus_force()
            except:
                pass

        return result

    except Exception as e:
        logger.error(f"顯示置頂對話框時出錯: {e}")
        # 嘗試恢復父視窗狀態
        try:
            if hasattr(parent, 'attributes'):
                parent.attributes('-topmost', original_topmost)
                parent.focus_force()
        except:
            pass
        return None

def create_toplevel_window(parent: tk.Tk, title: str, width: int = 400, height: int = 300, topmost: bool = True) -> tk.Toplevel:
    """
    創建一個置頂的 Toplevel 視窗

    :param parent: 父視窗
    :param title: 視窗標題
    :param width: 視窗寬度
    :param height: 視窗高度
    :param topmost: 是否置頂
    :return: 創建的 Toplevel 視窗
    """
    try:
        # 創建 Toplevel 視窗
        window = tk.Toplevel(parent)
        window.title(title)
        window.geometry(f"{width}x{height}")

        # 設置視窗屬性
        if topmost:
            window.attributes('-topmost', True)

        # 設置為父視窗的子視窗
        window.transient(parent)

        # 置中顯示
        center_window(window, width, height)

        # 設置為模態視窗
        window.grab_set()
        window.focus_force()

        return window

    except Exception as e:
        logger.error(f"創建 Toplevel 視窗時出錯: {e}")
        return None

def center_window(window: Union[tk.Tk, tk.Toplevel], width: int = None, height: int = None) -> None:
    """
    將視窗置中顯示

    :param window: 要置中的視窗
    :param width: 視窗寬度，如果為 None 則使用視窗當前寬度
    :param height: 視窗高度，如果為 None 則使用視窗當前高度
    """
    try:
        window.update_idletasks()

        # 如果未指定尺寸，使用視窗當前尺寸
        if width is None:
            width = window.winfo_width()
        if height is None:
            height = window.winfo_height()

        # 計算視窗位置
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        # 設置視窗位置
        window.geometry(f"{width}x{height}+{x}+{y}")

    except Exception as e:
        logger.error(f"置中視窗時出錯: {e}")

def ensure_window_topmost(window: Union[tk.Tk, tk.Toplevel], topmost: bool = True) -> None:
    """
    確保視窗處於最上層

    :param window: 要設置的視窗
    :param topmost: 是否置頂
    """
    try:
        if hasattr(window, 'attributes'):
            window.attributes('-topmost', topmost)
            window.update()

        if topmost:
            window.focus_force()

    except Exception as e:
        logger.error(f"設置視窗置頂狀態時出錯: {e}")

def setup_child_window_for_parent(child: tk.Toplevel, parent: tk.Tk) -> None:
    """
    設置子視窗與父視窗的關係

    :param child: 子視窗
    :param parent: 父視窗
    """
    try:
        # 設置為父視窗的子視窗
        child.transient(parent)

        # 設置為模態視窗
        child.grab_set()

        # 設置置頂
        child.attributes('-topmost', True)

        # 強制獲取焦點
        child.update()
        child.focus_force()

    except Exception as e:
        logger.error(f"設置子視窗關係時出錯: {e}")

    def setup_child_window_for_parent(child: tk.Toplevel, parent: tk.Tk) -> None:
        """
        設置子視窗與父視窗的關係

        :param child: 子視窗
        :param parent: 父視窗
        """
        try:
            # 設置為父視窗的子視窗
            child.transient(parent)

            # 設置為模態視窗
            child.grab_set()

            # 設置置頂
            child.attributes('-topmost', True)

            # 強制獲取焦點
            child.update()
            child.focus_force()

        except Exception as e:
            logger.error(f"設置子視窗關係時出錯: {e}")

    def fix_existing_dialog(dialog_class):
        """
        修復現有對話框類別以支持置頂

        此函數會修改指定對話框類的 create_dialog 和 run 方法，
        確保它們能正確處理置頂和焦點問題。

        :param dialog_class: 要修復的對話框類別
        :return: 修改後的對話框類別
        """
        original_create_dialog = getattr(dialog_class, 'create_dialog', None)
        original_run = getattr(dialog_class, 'run', None)

        # 如果沒有這些方法，則不需要修改
        if not original_create_dialog or not original_run:
            return dialog_class

        def enhanced_create_dialog(self, *args, **kwargs):
            """增強的 create_dialog 方法，添加置頂支持"""
            # 調用原始方法
            result = original_create_dialog(self, *args, **kwargs)

            # 添加置頂設置
            if hasattr(self, 'window'):
                try:
                    self.window.attributes('-topmost', True)
                    self.window.update()
                except Exception as e:
                    logger.warning(f"設置對話框置頂時出錯: {e}")

            return result

        def enhanced_run(self, *args, **kwargs):
            """增強的 run 方法，確保對話框置頂且正確獲取焦點"""
            try:
                # 確保視窗置頂
                if hasattr(self, 'window'):
                    try:
                        self.window.attributes('-topmost', True)
                        self.window.update()
                        self.window.focus_force()
                    except Exception as e:
                        logger.warning(f"確保對話框置頂時出錯: {e}")

                # 調用原始方法
                return original_run(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"增強的對話框運行時出錯: {e}")
                return None

        # 替換方法
        setattr(dialog_class, 'create_dialog', enhanced_create_dialog)
        setattr(dialog_class, 'run', enhanced_run)

        return dialog_class