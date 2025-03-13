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

        # 確定按鈕
        ok_button = ttk.Button(
            button_frame,
            text="確定",
            command=self.ok,
            width=10
        )
        ok_button.pack(side=tk.RIGHT, padx=5, pady=(0,15))

        # 取消按鈕
        cancel_button = ttk.Button(
            button_frame,
            text="取消",
            command=self.cancel,
            width=10
        )
        cancel_button.pack(side=tk.RIGHT, padx=5, pady=(0,15))

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
        :param user_id: 使用者 ID
        :param icon_size: 圖示大小，格式為 (寬, 高)
        """
        super().__init__(title="專案管理", width=400, height=200, master=master)

        # 保存用戶ID用於登出處理
        self.user_id = user_id

        # 初始化變數
        self.current_directory = get_current_directory()
        self.projects_dir = os.path.join(self.current_directory, "projects")
        self.selected_project = tk.StringVar()
        self.result = None
        self.icon_size = icon_size

        # 初始化資料庫連接
        self.db_manager = DatabaseManager()
        self.db_session = self.db_manager.get_session()
        self.user_id = user_id

        # 獲取當前使用者
        self.current_user = None
        if user_id:
            self.current_user = self.db_session.query(User).filter_by(id=user_id).first()

        # 載入圖示
        self.load_icons()

        # 確保專案目錄存在
        if not os.path.exists(self.projects_dir):
            os.makedirs(self.projects_dir)

        # 創建界面元素
        self.create_widgets()

        # 綁定 Enter 鍵
        self.master.bind('<Return>', lambda e: self.confirm())

        # 添加登出按鈕
        self.add_logout_button()

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

        # 取得圖示檔案的目錄路徑
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons")

        try:
            # 檢查圖示目錄是否存在
            if not os.path.exists(icons_dir):
                print(f"圖示目錄不存在: {icons_dir}")
                os.makedirs(icons_dir)

            # 定義圖示檔案的完整路徑
            add_normal_path = os.path.join(icons_dir, "add_normal.png")
            add_hover_path = os.path.join(icons_dir, "add_hover.png")
            delete_path = os.path.join(icons_dir, "delete.png")

            # 檢查並載入圖示檔案
            if os.path.exists(add_normal_path):
                img = Image.open(add_normal_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.add_icon = ImageTk.PhotoImage(img)
            else:
                print(f"找不到新增按鈕圖示: {add_normal_path}")
                self.add_icon = tk.PhotoImage()

            if os.path.exists(add_hover_path):
                img = Image.open(add_hover_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.add_hover_icon = ImageTk.PhotoImage(img)
            else:
                print(f"找不到新增按鈕懸停圖示: {add_hover_path}")
                self.add_hover_icon = tk.PhotoImage()

            if os.path.exists(delete_path):
                img = Image.open(delete_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.delete_icon = ImageTk.PhotoImage(img)
            else:
                print(f"找不到刪除按鈕圖示: {delete_path}")
                self.delete_icon = tk.PhotoImage()

        except Exception as e:
            print(f"載入圖示時發生錯誤: {str(e)}")
            self.add_icon = tk.PhotoImage()
            self.add_hover_icon = tk.PhotoImage()
            self.delete_icon = tk.PhotoImage()

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
            image=self.delete_icon,
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

        # 確定按鈕
        confirm_button = ttk.Button(
            button_container,
            text="確定",
            command=self.confirm,
            style='Custom.TButton',
            width=15
        )
        confirm_button.pack(side=tk.RIGHT)

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

    def update_project_list(self):
        """更新專案列表"""
        try:
            self.project_combobox.configure(state='disabled')  # 暫時禁用

            # 從資料庫中獲取使用者的專案
            if self.current_user:
                projects = self.db_session.query(Project).filter_by(owner_id=self.current_user.id).all()
                project_names = [project.name for project in projects]
            else:
                # 如果沒有使用者，使用目錄方式尋找專案（向後兼容）
                projects = [d for d in os.listdir(self.projects_dir)
                        if os.path.isdir(os.path.join(self.projects_dir, d))]
                project_names = projects

            current = self.selected_project.get()
            self.project_combobox['values'] = project_names

            if current and current in project_names:
                self.project_combobox.set(current)
            elif project_names:
                self.project_combobox.set(project_names[0])
            else:
                self.project_combobox.set('')

        finally:
            self.project_combobox.configure(state='readonly')  # 重新啟用

    def add_project(self):
        """新增專案"""
        try:
            dialog = ProjectInputDialog(parent=self.master)
            project_name = dialog.run()

            if project_name and self.current_user:
                # 檢查專案名稱是否已存在
                existing_project = self.db_session.query(Project).filter_by(
                    name=project_name, owner_id=self.current_user.id).first()

                if existing_project:
                    show_warning("警告", "專案已存在！", self.master)
                    return

                # 建立專案目錄
                project_path = os.path.join(self.projects_dir, project_name)
                if not os.path.exists(project_path):
                    os.makedirs(project_path)

                # 在資料庫中建立專案記錄
                new_project = Project(
                    name=project_name,
                    owner_id=self.current_user.id
                )
                self.db_session.add(new_project)
                self.db_session.commit()

                # 更新下拉列表
                self.update_project_list()
                self.project_combobox.set(project_name)

        except Exception as e:
            show_error(
                "錯誤",
                f"新增專案時發生錯誤：{str(e)}",
                self.master
            )

    def delete_project(self):
        """刪除專案"""
        selected = self.selected_project.get()
        if not selected:
            show_warning("警告", "請先選擇要刪除的專案！", self.master)
            return

        if ask_question("確認刪除", f"確定要刪除專案 '{selected}' 嗎？", self.master):
            project_path = os.path.join(self.projects_dir, selected)
            try:
                import shutil
                shutil.rmtree(project_path)

                # 清空當前選擇
                self.selected_project.set('')

                # 重新載入專案列表
                projects = [d for d in os.listdir(self.projects_dir)
                         if os.path.isdir(os.path.join(self.projects_dir, d))]

                # 更新下拉選單的值
                self.project_combobox['values'] = projects

                # 如果還有其他專案，選擇第一個
                if projects:
                    self.project_combobox.set(projects[0])

            except Exception as e:
                show_error("錯誤", f"刪除專案時發生錯誤：{str(e)}", self.master)

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

            # 關閉當前視窗
            self.master.destroy()

            # 創建新的 root 和校正工具
            root = tk.Tk()
            correction_tool = CorrectionTool(root, project_path)
            root.mainloop()

        except Exception as e:
            self.logger.error(f"切換視窗時出錯: {e}")
            show_error("錯誤", f"切換失敗: {str(e)}", self.master)
            sys.exit(1)

    def cleanup(self):
        """清理資源"""
        # 在清理資源時也確保用戶登出
        if self.user_id:
            self.update_logout_status(self.user_id)

        # 調用父類清理
        super().cleanup()

    def close_window(self, event=None):
        """重寫關閉視窗方法"""
        # 確保用戶登出
        if self.user_id:
            self.update_logout_status(self.user_id)

        # 調用父類關閉視窗方法
        super().close_window(event)


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