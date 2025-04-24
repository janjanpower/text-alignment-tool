import logging
import os
import sys
import tkinter as tk
from tkinter import ttk

from gui.base_dialog import BaseDialog
from gui.base_window import BaseWindow
from gui.correction_tool import CorrectionTool
from gui.custom_messagebox import show_warning, show_error, ask_question
from database.db_manager import DatabaseManager
from database.models import Project, User
from utils.file_utils import get_current_directory
from services.file.project_service import ProjectService
class ProjectInputDialog(BaseDialog):
    def __init__(self, parent=None):
        """初始化專案管理器"""
        self.result = None
        super().__init__(parent, title="新增專案", width=250, height=150)

    def create_dialog(self) -> None:
        """重寫以改進對話框創建方法"""
        super().create_dialog()

        # 內容框架
        content_frame = ttk.Frame(self.main_frame, padding="20")
        content_frame.pack(fill=tk.BOTH, expand=True)

        # 專案名稱輸入區域
        name_frame = ttk.Frame(content_frame)
        name_frame.pack(fill=tk.X, pady=(5, 10))

        ttk.Label(name_frame, text="專案名稱：").pack(side=tk.LEFT)
        self.name_entry = ttk.Entry(name_frame)
        self.name_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 按鈕容器
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=0)

        # 取消按鈕
        cancel_button = ttk.Button(
            button_frame,
            text="取消",
            command=self.cancel,
            width=10
        )
        cancel_button.pack(side=tk.RIGHT, padx=5, pady=(0,15))

        # 確定按鈕
        ok_button = ttk.Button(
            button_frame,
            text="確定",
            command=self.ok,
            width=10
        )
        ok_button.pack(side=tk.RIGHT, padx=5, pady=(0,15))

        # 確保輸入框獲得焦點
        self.window.after(100, lambda: self.name_entry.focus_force())

    def validate(self) -> bool:
        """驗證輸入"""
        project_name = self.name_entry.get().strip()

        if not project_name:
            show_warning("警告", "請輸入專案名稱", self.window)
            return False

        # 檢查名稱是否含有非法字符
        invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        if any(char in project_name for char in invalid_chars):
            show_warning("警告", "專案名稱不能包含以下字符：\\ / : * ? \" < > |", self.window)
            return False

        self.result = project_name
        return True

    def ok(self, event=None):
        """確定按鈕事件"""
        if self.validate():
            self.apply()
            self.window.grab_release()
            self.window.destroy()

    def apply(self) -> None:
        """應用更改"""
        pass

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result

class ProjectManager(BaseWindow):
    """專案管理視窗"""

    def __init__(self, master=None, user_id=None, icon_size=(24, 24)):
        """
        初始化專案管理器
        :param master: 父視窗
        :param user_id: 使用者 ID (本地版本不使用，但保留參數相容性)
        :param icon_size: 圖示大小，格式為 (寬, 高)
        """
        super().__init__(title="專案管理", width=400, height=200, master=master)

        # 保存用戶ID用於相容性
        self.user_id = user_id

        # 初始化變數
        self.current_directory = get_current_directory()
        self.projects_dir = os.path.join(self.current_directory, "projects")
        self.selected_project = tk.StringVar()
        self.result = None
        self.icon_size = icon_size

        # 初始化專案服務
        self.project_service = ProjectService()

        # 載入圖示
        self.load_icons()

        # 確保專案目錄存在
        self.project_service.ensure_projects_directory()

        # 創建界面元素
        self.create_widgets()

        # 綁定 Enter 鍵
        self.master.bind('<Return>', lambda e: self.confirm())

    def show_register(self):
        """顯示註冊視窗"""
        try:
            # 匯入視窗工具模組
            from utils.window_utils import ensure_child_window_topmost

            # 建立並顯示註冊對話框
            register_dialog = RegisterDialog(self.master)

            # 確保對話框置頂於登入視窗之上
            ensure_child_window_topmost(self.master, register_dialog.window)

            # 等待註冊對話框關閉
            self.master.wait_window(register_dialog.window)

            # 如果註冊成功，填入使用者名稱並設置焦點
            if register_dialog.result:
                self.username_entry.delete(0, tk.END)
                self.username_entry.insert(0, register_dialog.result)
                self.password_entry.focus_set()
            else:
                # 如果註冊取消或關閉，則焦點回到使用者名稱輸入框
                self.username_entry.focus_set()

            # 強制讓登入視窗獲取焦點
            self.master.focus_force()

        except Exception as e:
            self.logger.error(f"顯示註冊視窗時出錯: {e}")
            # 確保登入視窗重新獲得焦點
            self.master.focus_force()

    def add_logout_button(self):
        """添加登出按鈕"""
        # 假設已有按鈕容器 button_container
        if hasattr(self, 'button_container'):
            # 登出按鈕
            logout_button = ttk.Button(
                self.button_container,
                text="登出",
                command=self.logout,
                style='Custom.TButton',
                width=15
            )
            logout_button.pack(side=tk.LEFT, padx=5)

    def logout(self):
        """用戶主動登出"""
        try:
            if self.user_id:
                # 更新用戶登入狀態
                self.update_logout_status(self.user_id)

                # 關閉當前視窗
                self.master.destroy()

                def show_login_window():
                    from login_window import LoginWindow
                    root = tk.Tk()
                    login_window = LoginWindow(root)
                    root.mainloop()
        except Exception as e:
            self.logger.error(f"登出時出錯: {e}")
            self.master.destroy()

    def update_logout_status(self, user_id):
        """更新用戶登出狀態"""
        try:
            # 創建新的數據庫連接
            db_manager = DatabaseManager()
            session = db_manager.get_session()

            # 更新用戶登入狀態
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                user.is_logged_in = False
                session.commit()
                self.logger.info(f"用戶 {user.username} 已登出")

            # 關閉資料庫連接
            db_manager.close_session(session)

        except Exception as e:
            self.logger.error(f"更新登出狀態失敗: {e}")

    def load_icons(self):
        """載入所需的圖示"""
        from PIL import Image, ImageTk

        # 取得圖示檔案的目錄路徑 - 更新為assets/icons
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        icons_dir = os.path.join(project_root, "assets", "icons")

        try:
            # 檢查圖示目錄是否存在
            if not os.path.exists(icons_dir):
                self.logger.warning(f"圖示目錄不存在: {icons_dir}")
                os.makedirs(icons_dir)
                self.logger.info(f"已創建圖示目錄: {icons_dir}")

            # 定義圖示檔案的完整路徑
            add_normal_path = os.path.join(icons_dir, "add_normal.png")
            add_hover_path = os.path.join(icons_dir, "add_hover.png")
            delete_normal_path = os.path.join(icons_dir, "delete_normal.png")
            delete_hover_path = os.path.join(icons_dir, "delete_hover.png")

            # 檢查並載入圖示檔案
            if os.path.exists(add_normal_path):
                img = Image.open(add_normal_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.add_icon = ImageTk.PhotoImage(img)
                self.logger.debug(f"成功載入圖標: add_normal")
            else:
                self.logger.warning(f"找不到新增按鈕圖示: {add_normal_path}")
                self.add_icon = tk.PhotoImage()

            if os.path.exists(add_hover_path):
                img = Image.open(add_hover_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.add_hover_icon = ImageTk.PhotoImage(img)
                self.logger.debug(f"成功載入圖標: add_hover")
            else:
                self.logger.warning(f"找不到新增按鈕懸停圖示: {add_hover_path}")
                self.add_hover_icon = tk.PhotoImage()

            if os.path.exists(delete_normal_path):
                img = Image.open(delete_normal_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.delete_normal_icon = ImageTk.PhotoImage(img)
                self.logger.debug(f"成功載入圖標: delete_normal")
            else:
                self.logger.warning(f"找不到刪除按鈕圖示: {delete_normal_path}")
                self.delete_normal_icon = tk.PhotoImage()

            if os.path.exists(delete_hover_path):
                img = Image.open(delete_hover_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.delete_hover_icon = ImageTk.PhotoImage(img)
                self.logger.debug(f"成功載入圖標: delete_hover")
            else:
                self.logger.warning(f"找不到刪除按鈕圖示: {delete_hover_path}")
                self.delete_hover_icon = tk.PhotoImage()

        except Exception as e:
            self.logger.error(f"載入圖示時出錯: {e}")
            # 確保所有圖標變數都被初始化，即使出錯
            self.add_icon = tk.PhotoImage()
            self.add_hover_icon = tk.PhotoImage()
            self.delete_normal_icon = tk.PhotoImage()
            self.delete_hover_icon = tk.PhotoImage()

    def create_widgets(self):
        """創建專案管理界面元素"""
        # 創建主要容器
        container = ttk.Frame(self.main_frame)
        container.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # 標籤和圖示區域
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        # 專案列表標籤，靠左對齊
        list_label = ttk.Label(header_frame, text="專案列表",font=("Arial", 12))
        list_label.pack(side=tk.LEFT)

        # 圖示按鈕容器，靠右對齊
        icon_frame = ttk.Frame(header_frame)
        icon_frame.pack(side=tk.RIGHT)

        # 新增專案圖示按鈕
        self.add_button = tk.Label(
            icon_frame,
            image=self.add_icon,
            cursor="hand2"
        )
        self.add_button.pack(side=tk.LEFT, padx=2)

        # 刪除專案圖示按鈕
        self.delete_button = tk.Label(
            icon_frame,
            image=self.delete_normal_icon,
            cursor="hand2"
        )
        self.delete_button.pack(side=tk.LEFT, padx=2)

        # 下拉式選單容器
        combo_container = ttk.Frame(container)
        combo_container.pack(fill=tk.X)

        # 專案下拉式選單
        self.project_combobox = ttk.Combobox(
            combo_container,
            textvariable=self.selected_project,
            state="readonly",
            width=30
        )
        self.project_combobox.pack(fill=tk.X)
        self.update_project_list()

        # 綁定按鈕事件
        self.setup_button_events()

        # 確定按鈕容器
        button_container = ttk.Frame(container)
        button_container.pack(fill=tk.X, pady=(20, 0))
        # 保存引用以便在其他方法中使用
        self.button_container = button_container

        # 使用按鈕管理器創建確定按鈕
        button_configs = [
            {
                'id': 'confirm',
                'normal_icon': 'ok_icon.png',
                'hover_icon': 'ok_hover.png',
                'command': self.confirm,
                'tooltip': '確認選擇專案',
                'side': tk.BOTTOM,
                'padx': 0
            }
        ]

        # 創建按鈕
        self.project_buttons = self.button_manager.create_button_set(button_container, button_configs)

        # 綁定按鈕事件
        self.setup_button_events()

    def setup_button_events(self):
        """設置按鈕事件和懸停效果"""
        # 新增按鈕事件
        self.add_button.bind('<Button-1>', lambda e: self.add_project())
        self.add_button.bind('<Enter>', lambda e: self.add_button.configure(image=self.add_hover_icon))
        self.add_button.bind('<Leave>', lambda e: self.add_button.configure(image=self.add_icon))

        # 刪除按鈕事件
        self.delete_button.bind('<Button-1>', lambda e: self.delete_project())
        self.delete_button.bind('<Enter>', lambda e: self.delete_button.configure(image=self.delete_hover_icon))
        self.delete_button.bind('<Leave>', lambda e: self.delete_button.configure(image=self.delete_normal_icon))

    def update_project_list(self):
        """更新專案列表"""
        try:
            self.project_combobox.configure(state='disabled')  # 暫時禁用

            # 從專案服務獲取專案列表
            project_names = self.project_service.get_user_projects(self.user_id)

            # 保存當前選擇
            current = self.selected_project.get()
            self.project_combobox['values'] = project_names

            # 嘗試保持當前選擇，或設置第一個可用項目
            if current and current in project_names:
                self.project_combobox.set(current)
            elif project_names:
                self.project_combobox.set(project_names[0])
            else:
                self.project_combobox.set('')

        except Exception as e:
            self.logger.error(f"更新專案列表時出錯: {e}")
        finally:
            self.project_combobox.configure(state='readonly')  # 重新啟用

    def add_project(self):
        """新增專案"""
        try:
            dialog = ProjectInputDialog(parent=self.master)
            project_name = dialog.run()

            if project_name:
                # 使用專案服務添加專案
                success = self.project_service.add_project(project_name, self.user_id)
                if not success:
                    show_warning("警告", "專案已存在！", self.master)
                    return

                # 更新下拉列表 - 確保這行一定會執行
                self.update_project_list()
                # 設定選擇項為新增的專案
                self.project_combobox.set(project_name)

        except Exception as e:
            show_error(
                "錯誤",
                f"新增專案時發生錯誤：{str(e)}",
                self.master
            )
            # 發生錯誤時也嘗試更新列表
            self.update_project_list()

    def delete_project(self):
        """刪除專案"""
        selected = self.selected_project.get()
        if not selected:
            show_warning("警告", "請先選擇要刪除的專案！", self.master)
            return

        if ask_question("確認刪除", f"確定要刪除專案 '{selected}' 嗎？", self.master):
            try:
                # 使用專案服務刪除專案
                success = self.project_service.delete_project(selected, self.user_id)
                if success:
                    # 清空當前選擇
                    self.selected_project.set('')

                # 無論成功或失敗，都更新專案列表
                self.update_project_list()

            except Exception as e:
                show_error("錯誤", f"刪除專案時發生錯誤：{str(e)}", self.master)
                # 發生錯誤時也嘗試更新列表
                self.update_project_list()

    def cleanup(self):
        """清理資源"""
        # 關閉專案服務
        if hasattr(self, 'project_service'):
            self.project_service.close()

        # 在清理資源時也確保用戶登出
        if self.user_id:
            self.update_logout_status(self.user_id)

        # 調用父類清理
        super().cleanup()

    def confirm(self) -> None:
        """確認選擇並按順序開啟工具"""
        try:
            selected = self.selected_project.get()
            if not selected:
                show_warning("警告", "請選擇一個專案！", self.master)
                return

            project_path = os.path.join(self.projects_dir, selected)
            print(f"切換到專案路徑: {project_path}")

            if not os.path.exists(project_path):
                os.makedirs(project_path)

            # 保存用戶選擇的專案信息
            self.result = {"project_name": selected, "project_path": project_path}

            # 清理資源
            self.cleanup()

            # 安全地關閉當前視窗
            from utils.window_utils import close_window_safely
            close_window_safely(self.master)

            # 創建新的 root 和校正工具
            root = tk.Tk()
            correction_tool = CorrectionTool(root, project_path)
            root.mainloop()

        except Exception as e:
            self.logger.error(f"切換視窗時出錯: {e}")
            show_error("錯誤", f"切換失敗: {str(e)}", self.master)
            sys.exit(1)

    def close_window(self, event=None):
        """重寫關閉視窗方法，使用安全的視窗關閉函數"""
        # 確保用戶登出
        if self.user_id:
            self.update_logout_status(self.user_id)

        # 清理資源
        self.cleanup()

        # 使用安全的視窗關閉函數
        from utils.window_utils import close_window_safely
        close_window_safely(self.master)


    def run(self):
        """運行視窗並返回結果"""
        # 設置視窗在螢幕中央
        self.center_window()

        # 創建所有界面元素
        self.create_widgets()

        # 顯示視窗並等待結果
        self.master.focus_force()  # 強制獲取焦點
        self.master.grab_set()     # 設置為模態視窗
        self.master.wait_window()  # 等待視窗關閉

        return self.result