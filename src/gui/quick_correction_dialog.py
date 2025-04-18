import tkinter as tk
from tkinter import ttk
import logging
import os
from gui.base_dialog import BaseDialog
from gui.custom_messagebox import show_warning, show_info, show_error
from gui.components.button_manager import ButtonManager  # 導入按鈕管理器

class QuickCorrectionDialog(BaseDialog):
    """快速添加校正對話框"""

    def __init__(self, parent=None, selected_text="", correction_service=None, project_path=""):
        """
        初始化快速添加校正對話框

        Args:
            parent: 父窗口
            selected_text: 預選的文本
            correction_service: CorrectionService 實例，如果為 None 會創建新實例
            project_path: 專案路徑，用於設置校正服務的資料庫路徑
        """
        self.result = None
        self.selected_text = selected_text
        self.project_path = project_path
        self.parent = parent  # 保存父窗口引用

        # 使用提供的校正服務或創建新的
        if correction_service is not None:
            self.correction_service = correction_service
        else:
            database_file = os.path.join(project_path, "corrections.csv") if project_path else None

            # 嘗試導入 CorrectionService
            try:
                from services.correction.correction_service import CorrectionService
                self.correction_service = CorrectionService(database_file)
            except ImportError:
                self.correction_service = None
                logging.error("無法導入 CorrectionService")

        super().__init__(parent, title="添加錯誤校正", width=350, height=200)

        # 初始化按鈕管理器
        self.button_manager = ButtonManager(self.window)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()
        self.create_content()

    def create_content(self):
        """創建對話框內容"""
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(15,0))

        # 錯誤字輸入框
        error_frame = ttk.Frame(content_frame)
        error_frame.pack(fill=tk.X, pady=(5,5))
        ttk.Label(error_frame, text="錯誤字：").pack(side=tk.LEFT)
        self.error_entry = tk.Entry(
            error_frame,
            bg="#334D6D",     # 背景色設為藍色
            fg="white",       # 文字顏色設為白色
            width=35,         # 設定較短的寬度
            insertbackground="white"  # 游標顏色也設為白色提高可見度
        )
        self.error_entry.pack(side=tk.LEFT, padx=5,pady=(10,5))
        # 預先填入選中的文本
        self.error_entry.insert(0, self.selected_text)

        # 校正字輸入框
        correction_frame = ttk.Frame(content_frame)
        correction_frame.pack(fill=tk.X, pady=5)
        ttk.Label(correction_frame, text="校正字：").pack(side=tk.LEFT)
        # 使用tk.Entry而非ttk.Entry以便更好地自訂樣式
        self.correction_entry = tk.Entry(
            correction_frame,
            bg="#334D6D",     # 背景色設為藍色
            fg="white",       # 文字顏色設為白色
            width=35,         # 設定較短的寬度
            insertbackground="white"  # 游標顏色也設為白色提高可見度
        )
        self.correction_entry.pack(side=tk.LEFT, padx=5)  # 移除fill和expand以控制寬度

        # 按鈕區域
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(side=tk.BOTTOM, pady=10)

        # 使用按鈕管理器創建按鈕
        button_configs = [
            {
                'id': 'ok',
                'normal_icon': 'ok_icon.png',
                'hover_icon': 'ok_hover.png',
                'command': self.ok,
                'tooltip': '確認添加',
                'side': tk.LEFT,
                'padx': 5
            },
            {
                'id': 'cancel',
                'normal_icon': 'cancel.png',
                'hover_icon': 'cancel_hover.png',
                'command': self.cancel,
                'tooltip': '取消操作',
                'side': tk.LEFT,
                'padx': 5
            }
        ]

        # 創建按鈕
        self.dialog_buttons = self.button_manager.create_button_set(button_frame, button_configs)

        # 綁定事件
        self.error_entry.bind('<Return>', lambda e: self.correction_entry.focus())
        self.correction_entry.bind('<Return>', lambda e: self.ok())
        self.window.bind('<Escape>', lambda e: self.cancel())

        # 設置初始焦點
        self.error_entry.focus_force()
        # 選中所有文本，方便修改
        self.error_entry.select_range(0, tk.END)

    def ok(self, event=None):
        """確定按鈕事件"""
        error = self.error_entry.get().strip()
        correction = self.correction_entry.get().strip()

        if not error:
            show_warning("警告", "請輸入錯誤字", self.window)
            self.error_entry.focus()
            return

        if not correction:
            show_warning("警告", "請輸入校正字", self.window)
            self.correction_entry.focus()
            return

        # 保存到校正服務
        try:
            # 檢查校正服務是否可用
            if not hasattr(self, 'correction_service') or self.correction_service is None:
                database_file = os.path.join(self.project_path, "corrections.csv") if self.project_path else None

                # 如果父窗口有校正服務，使用它
                if hasattr(self.parent, 'correction_service') and self.parent.correction_service:
                    self.correction_service = self.parent.correction_service
                    logging.info("使用父窗口的校正服務")
                else:
                    # 嘗試導入並創建新的校正服務
                    try:
                        from services.correction.correction_service import CorrectionService
                        self.correction_service = CorrectionService(database_file)
                        logging.info(f"創建新的校正服務，資料庫路徑: {database_file}")
                    except ImportError:
                        logging.error("無法導入 CorrectionService")
                        show_error("錯誤", "無法創建校正服務，請檢查配置", self.window)
                        return

            # 添加校正規則
            updated = False
            if hasattr(self.correction_service, 'add_correction'):
                self.correction_service.add_correction(error, correction)
                updated = True

            # 確保更新了顯示
            try:
                # 如果父窗口有 tree 屬性和更新方法，直接調用
                if hasattr(self.parent, 'tree') and hasattr(self.correction_service, 'safe_apply_correction'):
                    # 使用安全方法應用校正
                    if hasattr(self.parent, 'display_mode'):
                        self.correction_service.safe_apply_correction(
                            error, correction, self.parent.tree, self.parent.display_mode
                        )

                # 如果父窗口有專門的方法，也調用它
                if hasattr(self.parent, 'apply_correction_to_all_items'):
                    try:
                        self.parent.apply_correction_to_all_items(error, correction)
                    except Exception as apply_error:
                        logging.error(f"在父窗口應用校正時出錯: {apply_error}")
            except Exception as e:
                logging.error(f"嘗試更新父窗口顯示時出錯: {e}")

            # 設置結果
            self.result = (error, correction)

            # 觸發回調
            if updated and hasattr(self.correction_service, 'on_correction_change') and self.correction_service.on_correction_change:
                try:
                    self.correction_service.on_correction_change()
                except Exception as e:
                    logging.error(f"執行校正回調時出錯: {e}")

            # 顯示成功訊息
            show_info("成功", f"已添加校正規則：\n{error} → {correction}", self.window)

            # 關閉視窗
            self.close()
        except Exception as e:
            logging.error(f"添加校正到資料庫時出錯: {e}")
            show_error("錯誤", f"保存校正規則失敗: {str(e)}", self.window)

    def cancel(self, event=None):
        """取消按鈕事件"""
        self.result = None
        self.close()

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result