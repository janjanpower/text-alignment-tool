import tkinter as tk
from tkinter import ttk
import logging
import os
import csv
from gui.base_dialog import BaseDialog
from gui.custom_messagebox import show_warning, show_info, show_error

class QuickCorrectionDialog(BaseDialog):
    """快速添加校正對話框"""

    def __init__(self, parent=None, selected_text="", project_path=""):
        """初始化快速添加校正對話框"""
        self.result = None
        self.selected_text = selected_text
        self.project_path = project_path
        super().__init__(parent, title="添加錯誤校正", width=350, height=200)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()
        self.create_content()

    def create_content(self):
        """創建對話框內容"""
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 錯誤字輸入框
        error_frame = ttk.Frame(content_frame)
        error_frame.pack(fill=tk.X, pady=(5,5))
        ttk.Label(error_frame, text="錯誤字：").pack(side=tk.LEFT)
        self.error_entry = ttk.Entry(error_frame)
        self.error_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        # 預先填入選中的文本
        self.error_entry.insert(0, self.selected_text)

        # 校正字輸入框
        correction_frame = ttk.Frame(content_frame)
        correction_frame.pack(fill=tk.X, pady=5)
        ttk.Label(correction_frame, text="校正字：").pack(side=tk.LEFT)
        self.correction_entry = ttk.Entry(correction_frame)
        self.correction_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 按鈕區域
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(side=tk.BOTTOM, pady=10)

        ttk.Button(button_frame, text="確定", command=self.ok,
                  width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=self.cancel,
                  width=10).pack(side=tk.LEFT, padx=5)

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

        # 保存到校正數據庫
        if self.project_path:
            success = self.add_correction_to_database(error, correction)
            if success:
                self.result = (error, correction)
                self.window.destroy()
        else:
            show_warning("警告", "未設置專案路徑，無法保存校正", self.window)

    def cancel(self, event=None):
        """取消按鈕事件"""
        self.result = None
        self.window.destroy()

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result

    def add_correction_to_database(self, error, correction):
        """添加校正到資料庫"""
        try:
            # 確保當前專案路徑有效
            if not self.project_path:
                show_warning("警告", "未設置當前專案路徑，無法保存校正", self.window)
                return False

            # 設置資料庫檔案路徑
            database_file = os.path.join(self.project_path, "corrections.csv")

            # 載入現有校正資料
            corrections = {}
            if os.path.exists(database_file):
                try:
                    with open(database_file, 'r', encoding='utf-8-sig') as file:
                        reader = csv.reader(file)
                        next(reader)  # 跳過標題行
                        for row in reader:
                            if len(row) >= 2:
                                corrections[row[0]] = row[1]
                except Exception as e:
                    logging.error(f"載入校正資料庫失敗: {e}")

            # 添加新的校正項目
            corrections[error] = correction

            # 保存回資料庫
            try:
                with open(database_file, 'w', encoding='utf-8-sig', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow(["錯誤字", "校正字"])
                    for error_text, correction_text in corrections.items():
                        writer.writerow([error_text, correction_text])

                # 顯示成功訊息
                show_info("成功", f"已添加校正規則：\n{error} → {correction}", self.window)
                return True
            except Exception as e:
                logging.error(f"保存校正資料庫失敗: {e}")
                show_error("錯誤", f"保存校正資料庫失敗: {str(e)}", self.window)
                return False
        except Exception as e:
            logging.error(f"添加校正到資料庫時出錯: {e}")
            return False