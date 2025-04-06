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

        # 獲取當前使用者
        self.current_user = None
        if user_id:
            self.current_user = self.db_session.query(User).filter_by(id=user_id).first()

        # 確保專案目錄存在
        if not os.path.exists(self.projects_dir):
            os.makedirs(self.projects_dir)

        # 載入圖示
        self.load_icons()

        # 創建界面元素
        self.create_widgets()

        # 綁定 Enter 鍵
        self.master.bind('<Return>', lambda e: self.confirm())

    def switch_project(self):
        """切換專案"""
        try:
            if ask_question("確認切換",
                        "切換專案前，請確認是否已經儲存當前的文本？\n"
                        "未儲存的內容將會遺失。",
                        self.master):
                # 更新用戶登入狀態
                if self.user_id:
                    self.update_logout_status(self.user_id)

                # 關閉當前視窗
                self.master.destroy()

                # 創建新的 root 和專案管理器實例
                root = tk.Tk()
                project_manager = ProjectManager(root, self.user_id)
                root.mainloop()
        except Exception as e:
            self.logger.error(f"切換專案時出錯: {e}")
            show_error("錯誤", f"切換專案失敗: {str(e)}", self.master)

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
                self.logger.warning(f"圖示目錄不存在: {icons_dir}")
                os.makedirs(icons_dir, exist_ok=True)

            # 定義圖示檔案的完整路徑
            add_normal_path = os.path.join(icons_dir, "add_normal.png")
            add_hover_path = os.path.join(icons_dir, "add_hover.png")
            delete_normal_path = os.path.join(icons_dir, "delete.png")
            delete_hover_path = os.path.join(icons_dir, "delete_hover.png")

            # 檢查並載入圖示檔案
            if os.path.exists(add_normal_path):
                img = Image.open(add_normal_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.add_normal_icon = ImageTk.PhotoImage(img)
            else:
                self.logger.warning(f"找不到新增按鈕圖示: {add_normal_path}")
                self.add_normal_icon = tk.PhotoImage()

            if os.path.exists(add_hover_path):
                img = Image.open(add_hover_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.add_hover_icon = ImageTk.PhotoImage(img)
            else:
                self.logger.warning(f"找不到新增按鈕懸停圖示: {add_hover_path}")
                self.add_hover_icon = self.add_normal_icon  # 如果沒有hover圖標，使用normal圖標代替

            if os.path.exists(delete_normal_path):
                img = Image.open(delete_normal_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.delete_normal_icon = ImageTk.PhotoImage(img)
            else:
                self.logger.warning(f"找不到刪除按鈕圖示: {delete_normal_path}")
                self.delete_normal_icon = tk.PhotoImage()

            if os.path.exists(delete_hover_path):
                img = Image.open(delete_hover_path)
                img = img.resize(self.icon_size, Image.Resampling.LANCZOS)
                self.delete_hover_icon = ImageTk.PhotoImage(img)
            else:
                self.logger.warning(f"找不到刪除按鈕懸停圖示: {delete_hover_path}")
                self.delete_hover_icon = self.delete_normal_icon  # 如果沒有hover圖標，使用normal圖標代替

        except Exception as e:
            self.logger.error(f"載入圖示時出錯: {str(e)}")
            self.add_normal_icon = tk.PhotoImage()
            self.add_hover_icon = tk.PhotoImage()
            self.delete_normal_icon = tk.PhotoImage()
            self.delete_hover_icon = tk.PhotoImage()

    def create_image_button(self, btn_info, width=None, height=None):
        """
        創建圖片按鈕
        :param btn_info: 按鈕信息
        :param width: 按鈕寬度
        :param height: 按鈕高度
        """
        button_id = btn_info["id"]
        command = btn_info["command"]
        tooltip = btn_info.get("tooltip", "")

        # 獲取按鈕圖片
        if button_id == "add":
            normal_img = self.add_normal_icon
            hover_img = self.add_hover_icon
        elif button_id == "delete":
            normal_img = self.delete_normal_icon
            hover_img = self.delete_hover_icon
        else:
            self.logger.error(f"未知按鈕ID: {button_id}")
            return

        # 創建按鈕框架
        btn_frame = ttk.Frame(self.toolbar_frame)
        btn_frame.pack(side=tk.LEFT, padx=2)

        # 創建標籤按鈕
        btn = tk.Label(
            btn_frame,
            image=normal_img,
            cursor="hand2"
        )
        btn.normal_image = normal_img  # 保存引用以避免垃圾回收
        btn.hover_image = hover_img  # 保存引用以避免垃圾回收
        btn.pack()

        # 儲存原始命令
        btn.command = command

        # 綁定按下、釋放和進入、離開事件
        btn.bind("<ButtonPress-1>", lambda e, b=btn: self._on_button_press(e, b))
        btn.bind("<ButtonRelease-1>", lambda e, b=btn: self._on_button_release(e, b))
        btn.bind("<Enter>", lambda e, b=btn: b.configure(image=b.hover_image))
        btn.bind("<Leave>", lambda e, b=btn: b.configure(image=b.normal_image))

        # 儲存按鈕引用
        self.toolbar_buttons[button_id] = btn

        # 添加提示文字
        if tooltip:
            self._create_tooltip(btn, tooltip)

    def _on_button_press(self, event, button):
        """滑鼠按下按鈕事件處理"""
        if hasattr(button, 'hover_image'):
            button.configure(image=button.hover_image)
        # 保存按下的位置
        button.press_x = event.x
        button.press_y = event.y

    def _on_button_release(self, event, button):
        """滑鼠釋放按鈕事件處理"""
        if hasattr(button, 'normal_image'):
            button.configure(image=button.normal_image)

            # 判斷釋放是否在按鈕範圍內
            if hasattr(button, 'press_x') and hasattr(button, 'press_y'):
                # 檢查滑鼠是否仍在按鈕上
                if (0 <= event.x <= button.winfo_width() and
                    0 <= event.y <= button.winfo_height()):
                    # 在按鈕上釋放，執行命令
                    if hasattr(button, 'command') and callable(button.command):
                        button.command()

    def create_widgets(self):
        """創建專案管理界面元素"""
        # 創建主要容器
        container = ttk.Frame(self.main_frame)
        container.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # 標籤和圖示區域
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 5))

        # 專案列表標籤，靠左對齊
        list_label = ttk.Label(header_frame, text="專案列表", font=("Arial", 12))
        list_label.pack(side=tk.LEFT)

        # 圖示按鈕容器，靠右對齊
        icon_frame = ttk.Frame(header_frame)
        icon_frame.pack(side=tk.RIGHT)

        # 定義按鈕配置
        buttons = [
            {"id": "add", "command": self.add_project, "tooltip": "新增專案"},
            {"id": "delete", "command": self.delete_project, "tooltip": "刪除專案"}
        ]

        # 創建圖標按鈕
        self.toolbar_buttons = {}
        for btn_info in buttons:
            self.create_image_button(btn_info)

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

        # 確定按鈕容器
        self.button_container = ttk.Frame(container)  # 保存為實例變數
        self.button_container.pack(fill=tk.X, pady=(20, 0))

        # 確定按鈕
        confirm_button = ttk.Button(
            self.button_container,
            text="確定",
            command=self.confirm,
            style='Custom.TButton',
            width=15
        )
        confirm_button.pack(side=tk.RIGHT)

        # 添加登出按鈕
        self.add_logout_button()

    def setup_button_events(self):
        """設置按鈕事件和懸停效果"""
        # 確保按鈕存在
        if not hasattr(self, 'add_button') or not hasattr(self, 'delete_button'):
            self.logger.warning("按鈕未創建，無法綁定事件")
            return

        # 確保圖標已載入
        if not hasattr(self, 'add_icon') or not hasattr(self, 'add_hover_icon') or \
        not hasattr(self, 'delete_icon') or not hasattr(self, 'delete_hover_icon'):
            self.load_icons()

        # 移除之前可能的綁定以避免重複
        try:
            self.add_button.unbind('<Button-1>')
            self.add_button.unbind('<ButtonRelease-1>')
            self.add_button.unbind('<Enter>')
            self.add_button.unbind('<Leave>')

            self.delete_button.unbind('<Button-1>')
            self.delete_button.unbind('<ButtonRelease-1>')
            self.delete_button.unbind('<Enter>')
            self.delete_button.unbind('<Leave>')
        except Exception:
            pass

        # 新增專案按鈕
        self.add_button.bind('<Button-1>', lambda e: None)  # 點擊時不做任何操作
        self.add_button.bind('<ButtonRelease-1>', lambda e: self.add_project())  # 釋放時才執行新增專案操作

        # 懸停效果
        self.add_button.bind('<Enter>', lambda e: self.add_button.configure(image=self.add_hover_icon))  # 懸停時顯示懸停圖示
        self.add_button.bind('<Leave>', lambda e: self.add_button.configure(image=self.add_icon))  # 鼠標離開時恢復為原始圖示

        # 刪除專案按鈕
        self.delete_button.bind('<Button-1>', lambda e: None)  # 點擊時不做任何操作
        self.delete_button.bind('<ButtonRelease-1>', lambda e: self.delete_project())  # 釋放時才執行刪除專案操作

        # 刪除按鈕的懸停效果
        self.delete_button.bind('<Enter>', lambda e: self.delete_button.configure(image=self.delete_hover_icon))  # 懸停時顯示懸停圖示
        self.delete_button.bind('<Leave>', lambda e: self.delete_button.configure(image=self.delete_icon))  # 鼠標離開時恢復為原始圖示

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

            # 創建新的 root 和校正工具，並傳遞用戶ID
            root = tk.Tk()
            correction_tool = CorrectionTool(root, project_path)

            # 傳遞用戶ID
            correction_tool.user_id = self.user_id if hasattr(self, 'user_id') else None

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