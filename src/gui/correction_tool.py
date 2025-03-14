"""文字校正工具組件"""

import sys
import time
import tkinter as tk
from tkinter import ttk
import csv
import os
import logging
from typing import Dict, Optional, Tuple, List
from gui.base_window import BaseWindow
from gui.base_dialog import BaseDialog
from gui.custom_messagebox import show_info, show_warning, show_error
from gui.alignment.main_gui import AlignmentGUI

class CorrectionInputDialog(BaseDialog):
    """校正項輸入對話框"""
    def __init__(self, parent=None):
        """初始化校正輸入對話框"""
        self.result = None  # 確保在 super().__init__ 之前初始化 result
        super().__init__(parent, title="新增資料", width=300, height=200)

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

        self.result = (error, correction)
        self.window.destroy()

    def cancel(self, event=None):
        """取消按鈕事件"""
        self.result = None
        self.window.destroy()

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result

class CorrectionTool(BaseWindow):
    def __init__(self, master: Optional[tk.Tk] = None, project_path: str = "") -> None:
        """初始化校正工具"""
        self.project_path = project_path
        self.database_file = os.path.join(project_path, "corrections.csv")
        self.data_rows = []

        # 取得專案名稱
        project_name = os.path.basename(project_path)

        # 調用父類初始化，並設置包含專案名稱的標題
        super().__init__(title=f"校正資料庫 - {project_name}", width=600, height=300, master=master)

        # 創建界面
        self.create_correction_interface()

        # 載入資料庫
        self.load_database()

    def create_correction_interface(self) -> None:
        """創建校正工具界面"""
        # 主框架
        main_frame = ttk.Frame(self.main_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 工具列
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 按鈕配置
        buttons = [
            ("新增資料", self.add_correction),
            ("刪除資料", self.delete_correction),
            ("進入文本工具", self.enter_alignment_tool)
        ]

        for text, command in buttons:
            ttk.Button(toolbar, text=text, command=command,
                    width=15, style='Custom.TButton').pack(side=tk.LEFT, padx=2)

        # Treeview 和卷軸
        tree_container = ttk.Frame(main_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(
            tree_container,
            columns=("index", "error", "correction"),
            show="headings",
            selectmode="browse"
        )

        # 設置列標題
        self.tree.heading("index", text="序號")
        self.tree.heading("error", text="錯誤字")
        self.tree.heading("correction", text="校正字")

        # 設置列寬度
        self.tree.column("index", width=50, minwidth=50, anchor=tk.CENTER)
        self.tree.column("error", width=200, minwidth=150, anchor=tk.CENTER)
        self.tree.column("correction", width=200, minwidth=150, anchor=tk.CENTER)

        # 添加卷軸
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Grid 布局
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree_container.grid_columnconfigure(0, weight=1)
        tree_container.grid_rowconfigure(0, weight=1)

        # 確保 Treeview 完全清空
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 綁定雙擊事件
        self.tree.bind('<Double-1>', self.on_double_click)

    def load_database(self) -> None:
        """載入資料庫"""
        print("\n=== 開始載入資料庫 ===")
        print(f"資料庫路徑: {self.database_file}")

        try:
            # 先清空現有數據
            self.data_rows.clear()
            print("已清空現有數據")

            # 檢查檔案是否存在
            if not os.path.exists(self.database_file):
                print("資料庫檔案不存在，保持空白")
                self.update_display()
                return

            # 載入資料
            with open(self.database_file, 'r', encoding='utf-8-sig') as file:
                reader = csv.reader(file)
                next(reader)  # 跳過標題行
                for row in reader:
                    if len(row) >= 2:
                        self.data_rows.append((row[0], row[1]))

            print(f"成功載入 {len(self.data_rows)} 筆資料")
            self.update_display()

        except Exception as e:
            print(f"載入資料庫時發生錯誤: {str(e)}")
            show_error("錯誤", f"載入資料庫失敗：{str(e)}", self.master)

    def save_database(self) -> None:
        """保存資料庫"""
        try:
            # 檢查 project_path 是否有效
            if not self.project_path:
                show_error("錯誤", "專案路徑無效", self.master)
                return

            # 確保專案目錄存在
            os.makedirs(self.project_path, exist_ok=True)

            # 直接使用完整的檔案路徑
            with open(self.database_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["錯誤字", "校正字"])
                writer.writerows(self.data_rows)

            print(f"成功保存資料到：{self.database_file}")

        except Exception as e:
            print(f"保存失敗，路徑：{self.database_file}，錯誤：{str(e)}")
            show_error("錯誤", f"保存資料庫失敗：{str(e)}", self.master)

    def update_display(self) -> None:
        """更新顯示"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        print(f"更新顯示：共 {len(self.data_rows)} 筆資料")
        for i, (error, correction) in enumerate(self.data_rows, 1):
            self.tree.insert("", "end", values=(i, error, correction))

    def add_correction(self) -> None:
        """新增校正項"""
        dialog = CorrectionInputDialog(self.master)
        result = dialog.run()
        if result:
            error, correction = result
            self.data_rows.append((error, correction))
            self.save_database()  # 當加入第一筆資料時會自動建立檔案
            self.update_display()

    def delete_correction(self) -> None:
        """刪除選中項"""
        selected = self.tree.selection()
        if not selected:
            show_warning("警告", "請先選擇要刪除的項目", self.master)
            return

        index = self.tree.index(selected[0])
        self.data_rows.pop(index)
        self.save_database()
        self.update_display()

    def on_double_click(self, event) -> None:
        """處理雙擊編輯，確保編輯視窗精確定位"""
        try:
            region = self.tree.identify("region", event.x, event.y)
            if region != "cell":
                return

            # 確保有選中的項目
            selected = self.tree.selection()
            if not selected:
                return

            item = selected[0]
            column = self.tree.identify_column(event.x)

            # 只允許編輯錯誤字和校正字列
            if column not in ("#2", "#3"):  # #1 是序號列
                return

            # 取得單元格的精確位置和大小
            bbox = self.tree.bbox(item, column)
            if not bbox:
                return

            x, y, w, h = bbox

            # 計算全局座標
            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()

            # 創建彈出式編輯視窗
            edit_window = tk.Toplevel(self.master)
            edit_window.overrideredirect(True)  # 移除視窗裝飾
            edit_window.geometry(f'{w}x{h}+{tree_x + x}+{tree_y + y}')

            entry = ttk.Entry(edit_window, width=int(w/10))  # 寬度調整
            entry.pack(fill=tk.BOTH, expand=True)

            # 獲取當前值
            index = self.tree.index(item)
            col_idx = int(column[1]) - 1
            current_value = self.tree.item(item)["values"][col_idx]
            entry.insert(0, current_value)
            entry.select_range(0, tk.END)
            entry.focus_force()

            def save_edit(event=None):
                new_value = entry.get().strip()
                if col_idx == 1:  # 錯誤字列
                    self.data_rows[index] = (new_value, self.data_rows[index][1])
                else:  # 校正字列
                    self.data_rows[index] = (self.data_rows[index][0], new_value)

                self.save_database()
                self.update_display()
                edit_window.destroy()

            def cancel_edit(event=None):
                edit_window.destroy()

            entry.bind('<Return>', save_edit)
            entry.bind('<FocusOut>', save_edit)
            entry.bind('<Escape>', cancel_edit)

        except Exception as e:
            print(f"編輯時發生錯誤：{e}")
            show_error("錯誤", f"編輯失敗：{str(e)}", self.master)

    def enter_alignment_tool(self) -> None:
        """進入文本對齊工具"""
        try:
            show_info("提示", "資料庫已更新", self.master)

            # 關閉當前視窗
            self.master.destroy()

            # 創建新的 root 和對齊工具，並傳遞專案路徑
            root = tk.Tk()
            alignment_gui = AlignmentGUI(root)
            alignment_gui.current_project_path = self.project_path
            alignment_gui.set_title(f"文本管理 - {os.path.basename(self.project_path)}")
            root.mainloop()

        except Exception as e:
            show_error("錯誤", f"切換失敗：{str(e)}", self.master)
            sys.exit(1)

    def cleanup(self):
        """清理資源"""
        print("\n=== 開始清理資源 ===")

        # 清空數據
        self.data_rows.clear()

        # 清空界面
        if hasattr(self, 'tree'):
            for item in self.tree.get_children():
                self.tree.delete(item)

        # 調用父類清理
        super().cleanup()

        print("資源清理完成")