"""文字校正工具組件"""

import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog
import os
import logging
from typing import Dict, Optional, Tuple, List, Callable
from gui.base_window import BaseWindow
from gui.base_dialog import BaseDialog
from gui.custom_messagebox import show_info, show_warning, show_error, ask_question
from gui.alignment_gui import AlignmentGUI
from services.correction.correction_service import CorrectionService
from gui.quick_correction_dialog import QuickCorrectionDialog
from gui.components.button_manager import ButtonManager  # 導入按鈕管理器

class CorrectionInputDialog(BaseDialog):
    """校正項輸入對話框"""

    def __init__(self, parent=None, correction_service=None):
        """
        初始化校正輸入對話框

        Args:
            parent: 父窗口
            correction_service: 校正服務實例
        """
        self.result = None  # 確保在 super().__init__ 之前初始化 result
        self.correction_service = correction_service

        # 先調用父類初始化
        super().__init__(parent, title="新增資料", width=300, height=200)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()

        # 在調用 super().create_dialog() 之後初始化按鈕管理器
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self.window)

        self.create_content()

    def create_content(self):
        """創建對話框內容"""
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(15,0))

        # 錯誤字輸入框
        error_frame = ttk.Frame(content_frame)
        error_frame.pack(fill=tk.X, pady=(5,10))
        ttk.Label(error_frame, text="錯 誤 字").pack(side=tk.LEFT,pady=(5,0))
        self.error_entry = tk.Entry(
            error_frame,
            bg="#334D6D",     # 背景色設為藍色
            fg="white",       # 文字顏色設為白色
            width=35,         # 設定較短的寬度
            insertbackground="white"  # 游標顏色也設為白色提高可見度
        )
        self.error_entry.pack(side=tk.LEFT, padx=5,pady=(10,3))

        # 校正字輸入框
        correction_frame = ttk.Frame(content_frame)
        correction_frame.pack(fill=tk.X, pady=5)
        ttk.Label(correction_frame, text="校 正 字").pack(side=tk.LEFT,pady=(5,0))
        self.correction_entry = ttk.Entry(correction_frame)
        self.correction_entry = tk.Entry(
            correction_frame,
            bg="#334D6D",     # 背景色設為藍色
            fg="white",       # 文字顏色設為白色
            width=35,         # 設定較短的寬度
            insertbackground="white"  # 游標顏色也設為白色提高可見度
        )
        self.correction_entry.pack(side=tk.LEFT, padx=5,pady=(6,0))

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
                'normal_icon': 'cancel_icon.png',
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

        # 如果有提供 correction_service，則添加校正
        if self.correction_service:
            self.correction_service.add_correction(error, correction)

        self.result = (error, correction)
        self.close()

    def cancel(self, event=None):
        """取消按鈕事件"""
        self.result = None
        self.close()

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result
class CorrectionTool(BaseWindow):
    def __init__(self, master: Optional[tk.Tk] = None, project_path: str = "") -> None:
        """初始化校正工具"""
        self.project_path = project_path
        self.database_file = os.path.join(project_path, "corrections.csv")

        # 定義 on_correction_change 方法的引用
        self.on_correction_change = self.on_correction_change_handler  # 添加這行

        # 初始化校正服務
        self.correction_service = CorrectionService(
            database_file=self.database_file,
            on_correction_change=self.on_correction_change
        )
        # 從校正服務獲取資料
        self.data_rows = [(error, correction) for error, correction in self.correction_service.get_all_corrections().items()]

        # 取得專案名稱
        project_name = os.path.basename(project_path)

        # 調用父類初始化，並設置包含專案名稱的標題
        super().__init__(title=f"校正資料庫 - {project_name}", width=600, height=300, master=master)

        # 初始化按鈕管理器
        self.button_manager = ButtonManager(self.main_frame)

        # 創建界面
        self.create_correction_interface()

    def create_correction_interface(self) -> None:
        """創建校正工具界面"""
        # 主框架
        main_frame = ttk.Frame(self.main_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 工具列
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))

        # 使用按鈕管理器創建按鈕
        button_configs = [
        {
            'id': 'logout',
            'normal_icon': 'loginout_icon.png',
            'hover_icon': 'loginout_hover.png',
            'command': self.logout,
            'tooltip': '登出系統',
            'side': tk.LEFT,
            'padx': 2
        },
        {
            'id': 'text_management',
            'normal_icon': 'text_icon.png',
            'hover_icon': 'text_hover.png',
            'command': self.enter_alignment_tool,
            'tooltip': '進入文本管理',
            'side': tk.RIGHT,
            'padx': 2
        },
        {
            'id': 'add_data',
            'normal_icon': 'adddata_icon.png',
            'hover_icon': 'adddata_hover.png',
            'command': self.add_correction,
            'tooltip': '新增校正資料',
            'side': tk.RIGHT,
            'padx': 2
        },
        {
            'id': 'delete_data',
            'normal_icon': 'deletedata_icon.png',
            'hover_icon': 'deletedata_hover.png',
            'command': self.delete_correction,
            'tooltip': '刪除校正資料',
            'side': tk.RIGHT,
            'padx': 2
        }
         ]

        # 創建按鈕
        self.toolbar_buttons = self.button_manager.create_button_set(toolbar, button_configs)

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

        # 初始化顯示
        self.update_display()

    def logout(self) -> None:
        """登出功能，回到登入介面"""
        try:
            # 關閉當前視窗
            self.master.destroy()

            # 創建新的 root 和登入視窗
            root = tk.Tk()
            from gui.login_window import LoginWindow
            login_window = LoginWindow(root)
            root.mainloop()
        except Exception as e:
            self.logger.error(f"登出時出錯: {e}")
            show_error("錯誤", f"登出失敗: {str(e)}", self.master)
            sys.exit(1)

    def add_correction(self) -> None:
        """新增校正項"""
        try:
            # 匯入視窗工具模組
            from utils.window_utils import ensure_child_window_topmost

            # 創建校正輸入對話框
            dialog = CorrectionInputDialog(self.master, self.correction_service)

            # 確保對話框置頂
            if hasattr(dialog, 'window'):
                ensure_child_window_topmost(self.master, dialog.window)

            # 運行對話框並獲取結果
            result = dialog.run()

            if result:
                error, correction = result

                # 檢查是否重複
                duplicate = False
                for i, (existing_error, _) in enumerate(self.data_rows):
                    if existing_error == error:
                        # 更新現有項而不是添加新項
                        self.data_rows[i] = (error, correction)
                        duplicate = True
                        break

                # 如果不是重複的，添加新項
                if not duplicate:
                    # 更新數據列表
                    self.data_rows.append((error, correction))

                # 更新顯示 - 確保先清空再重新加載
                self.tree.delete(*self.tree.get_children())
                self.update_display()

                # 顯示成功訊息
                show_info("成功", f"已{'更新' if duplicate else '添加'}校正規則：\n{error} → {correction}", self.master)

        except Exception as e:
            self.logger.error(f"添加校正項時出錯: {e}")
            show_error("錯誤", f"添加校正項失敗: {str(e)}", self.master)

    def delete_correction(self) -> None:
        """刪除選中項"""
        selected = self.tree.selection()
        if not selected:
            show_warning("警告", "請先選擇要刪除的項目", self.master)
            return

        try:
            # 獲取樹視圖中選中項目的值
            item_values = self.tree.item(selected[0], 'values')
            if len(item_values) >= 2:  # 確保有錯誤字欄位
                error_text = item_values[1]  # 錯誤字通常在第二列

                # 直接從校正服務中移除
                if hasattr(self, 'correction_service') and self.correction_service:
                    if error_text in self.correction_service.corrections:
                        # 確認刪除
                        if ask_question("確認刪除", f"確定要刪除校正規則「{error_text}」嗎？", self.master):
                            # 從校正服務中移除
                            self.correction_service.remove_correction(error_text)

                            # 在 data_rows 中查找對應的錯誤字並移除
                            for i, (error, _) in enumerate(self.data_rows):
                                if error == error_text:
                                    self.data_rows.pop(i)
                                    break

                            # 更新顯示
                            self.update_display()
                    else:
                        self.logger.warning(f"在校正服務中找不到錯誤字 '{error_text}'")
                        show_warning("警告", "無法刪除所選項目，請重新選擇", self.master)
                else:
                    self.logger.warning("校正服務不可用")
                    show_warning("警告", "校正服務不可用，無法刪除", self.master)
            else:
                self.logger.warning("選中項的數據不完整")
                show_warning("警告", "選中項數據不完整，請重新選擇", self.master)

        except Exception as e:
            self.logger.error(f"刪除校正項時出錯: {e}", exc_info=True)
            show_error("錯誤", f"刪除失敗: {str(e)}", self.master)

    def update_display(self) -> None:
        """更新顯示"""
        # 先清空現有顯示
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 確保數據沒有重複
        unique_data = {}
        for error, correction in self.data_rows:
            unique_data[error] = correction

        # 使用去重後的數據更新顯示
        self.data_rows = list(unique_data.items())

        print(f"更新顯示：共 {len(self.data_rows)} 筆資料")
        for i, (error, correction) in enumerate(self.data_rows, 1):
            self.tree.insert("", "end", values=(i, error, correction))

    def on_double_click(self, event: tk.Event) -> None:
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
            item_values = self.tree.item(item)["values"]
            col_idx = int(column[1]) - 1
            current_value = item_values[col_idx] if col_idx < len(item_values) else ""
            entry.insert(0, current_value)
            entry.select_range(0, tk.END)
            entry.focus_force()

            def save_edit(event=None):
                try:
                    new_value = entry.get().strip()
                    # 獲取項目在樹視圖中的索引
                    tree_index = self.tree.index(item)

                    # 確保 tree_index 在有效範圍內
                    if 0 <= tree_index < len(self.data_rows):
                        old_error, old_correction = self.data_rows[tree_index]

                        # 更新校正服務和本地數據
                        if col_idx == 1:  # 錯誤字列
                            # 在校正服務中先移除舊的
                            self.correction_service.remove_correction(old_error)
                            # 再添加新的
                            self.correction_service.add_correction(new_value, old_correction)
                            # 更新本地數據
                            self.data_rows[tree_index] = (new_value, old_correction)
                        else:  # 校正字列
                            # 直接更新現有的
                            self.correction_service.add_correction(old_error, new_value)
                            # 更新本地數據
                            self.data_rows[tree_index] = (old_error, new_value)

                        # 更新顯示
                        self.update_display()
                    else:
                        self.logger.warning(f"項目索引 {tree_index} 超出範圍 (0-{len(self.data_rows)-1})")
                except Exception as e:
                    self.logger.error(f"保存編輯時出錯: {e}")

                # 無論成功與否都關閉編輯視窗
                edit_window.destroy()

            def cancel_edit(event=None):
                edit_window.destroy()

            entry.bind('<Return>', save_edit)
            entry.bind('<Escape>', cancel_edit)

            # 修改 FocusOut 事件處理，避免即時保存導致的問題
            def handle_focus_out(event=None):
                # 檢查鼠標位置是否仍在編輯窗口內
                mouse_x = edit_window.winfo_pointerx()
                mouse_y = edit_window.winfo_pointery()
                window_x = edit_window.winfo_rootx()
                window_y = edit_window.winfo_rooty()
                window_width = edit_window.winfo_width()
                window_height = edit_window.winfo_height()

                if (window_x <= mouse_x <= window_x + window_width and
                    window_y <= mouse_y <= window_y + window_height):
                    # 鼠標仍在窗口內，不處理失去焦點
                    return

                # 如果鼠標移出窗口，保存編輯
                save_edit()

            entry.bind('<FocusOut>', handle_focus_out)

        except Exception as e:
            print(f"編輯時發生錯誤：{e}")
            show_error("錯誤", f"編輯失敗：{str(e)}", self.master)

    def enter_alignment_tool(self) -> None:
        """進入文本對齊工具"""
        try:
            # 確保所有變更已保存
            show_info("提示", "校正資料庫已更新", self.master)

            # 關閉當前視窗
            self.master.destroy()

            # 創建新的 root 和對齊工具，並傳遞專案路徑和校正服務
            root = tk.Tk()
            alignment_gui = AlignmentGUI(root)

            # 設置專案路徑
            alignment_gui.current_project_path = self.project_path

            # 如果 AlignmentGUI 支持設置校正服務，直接傳遞現有實例
            if hasattr(alignment_gui, 'set_correction_service'):
                alignment_gui.set_correction_service(self.correction_service)
            else:
                # 如果不支持，至少設置相同的資料庫路徑
                alignment_gui.database_file = self.database_file
                if hasattr(alignment_gui, 'correction_service'):
                    alignment_gui.correction_service.set_database_file(self.database_file)

            alignment_gui.set_title(f"文本管理 - {os.path.basename(self.project_path)}")
            root.mainloop()

        except Exception as e:
            show_error("錯誤", f"切換失敗：{str(e)}", self.master)
            sys.exit(1)

    def on_correction_change_handler(self):
        """校正數據變化的回調函數"""
        # 防止短時間內重複更新
        current_time = time.time()
        if hasattr(self, '_last_update_time') and current_time - self._last_update_time < 0.1:
            return
        self._last_update_time = current_time

        # 清空原有數據
        self.data_rows = []

        # 從校正服務獲取最新數據
        self.data_rows = [(error, correction) for error, correction in
                        self.correction_service.get_all_corrections().items()]

        # 確保沒有重複項
        unique_data = {}
        for error, correction in self.data_rows:
            unique_data[error] = correction

        # 更新為去重後的數據
        self.data_rows = list(unique_data.items())

        # 更新顯示
        self.update_display()

    def cleanup(self):
        """清理資源"""
        print("\n=== 開始清理資源 ===")

        # 保存所有校正數據
        if hasattr(self, 'correction_service'):
            self.correction_service.save_corrections()

        # 清空數據
        self.data_rows.clear()

        # 清空界面
        if hasattr(self, 'tree'):
            for item in self.tree.get_children():
                self.tree.delete(item)

        # 調用父類清理
        super().cleanup()

        print("資源清理完成")