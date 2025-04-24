"""登入視窗類別模組"""


import datetime
import json
import os
import tkinter as tk
from tkinter import ttk
import logging
from gui.base_dialog import BaseDialog
from gui.base_window import BaseWindow
from gui.custom_messagebox import show_info, show_warning, show_error
from database.db_manager import DatabaseManager
from database.models import User
from gui.project_manager import ProjectManager
from utils.font_manager import FontManager
from services.config_manager import ConfigManager
from gui.alignment_gui import AlignmentGUI
from gui.components.button_manager import ButtonManager  # 導入按鈕管理器

class LoginWindow(BaseWindow):
    """登入視窗類別"""

    def __init__(self, master=None):
        """初始化登入視窗"""
        super().__init__(title="文本對齊工具 - 登入", width=400, height=300, master=master)

        # 確保字型管理器存在
        if not hasattr(self, 'font_manager'):
            self.font_manager = FontManager(self.config if hasattr(self, 'config') else None)

        # 初始化按鈕管理器
        self.button_manager = ButtonManager(self.main_frame)

        # 初始化資料庫連接
        self.db_manager = DatabaseManager()
        self.db_session = self.db_manager.get_session()
        self.current_user = None

        # 設置記住帳號變數（記得先初始化這個變數）
        self.remember_var = tk.BooleanVar(value=False)
        self.config = ConfigManager()

        # 創建登入介面
        self.create_login_interface()

        # 應用字型設定
        self.apply_font_settings()

        # 載入已保存的帳號
        self.load_saved_username()

    def apply_font_settings(self):
        """應用字型設定到所有控制項"""
        try:
            for widget in self.main_frame.winfo_children():
                if isinstance(widget, (tk.Label, ttk.Label, tk.Button, ttk.Button,
                                      tk.Entry, ttk.Entry)):
                    self.font_manager.apply_to_widget(widget)
        except Exception as e:
            self.logger.error(f"應用字型設定時出錯: {e}")

    def create_login_interface(self):
        """創建登入介面"""
        # 主框架
        main_frame = ttk.Frame(self.main_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 標題
        title_label = ttk.Label(main_frame, text="SRT文本處理系統", font=("Noto Sans TC", 13))
        title_label.pack(pady=(0, 20))

        # 載入圖標 - 更新為新的圖標路徑
        try:
            # 獲取專案根目錄
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)

            # 指向assets/icons
            icons_dir = os.path.join(project_root, "assets", "icons")

            # 定義圖標檔案名稱
            icon_files = {
                "account": "account.png",
                "password": "password.png"
            }

            # 記錄成功載入的圖標
            self.icons = {}

            # 載入所有圖標
            from PIL import Image, ImageTk

            for icon_name, file_name in icon_files.items():
                icon_path = os.path.join(icons_dir, file_name)
                if os.path.exists(icon_path):
                    try:
                        img = Image.open(icon_path)
                        img = img.resize((20, 20), Image.Resampling.LANCZOS)
                        self.icons[icon_name] = ImageTk.PhotoImage(img)
                        self.logger.debug(f"成功載入圖標: {icon_name}")
                    except Exception as e:
                        self.logger.warning(f"載入圖標 {icon_name} 時出錯: {e}")
                else:
                    self.logger.warning(f"找不到圖標文件: {icon_path}")
        except Exception as e:
            self.logger.error(f"載入圖標時出錯: {e}")
            self.icons = {}

        # 使用者名稱輸入框
        username_frame = ttk.Frame(main_frame)
        username_frame.pack(pady=5)

        # 帳號圖標
        if "account" in self.icons:
            account_icon_label = ttk.Label(username_frame, image=self.icons["account"])
            account_icon_label.pack(side=tk.LEFT, padx=(0, 5))

        username_label = ttk.Label(username_frame, text="帳 號", width=6, font=("Noto Sans TC", 10))
        username_label.pack(side=tk.LEFT)
        username_container = ttk.Frame(username_frame)
        username_container.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.username_entry = tk.Entry(
            username_container,
            bg="#334D6D",
            fg="white",
            width=25,
            insertbackground="white"
        )
        self.username_entry.pack(fill=tk.X)

        # 密碼輸入框
        password_frame = ttk.Frame(main_frame)
        password_frame.pack(pady=5)

        # 密碼圖標
        if "password" in self.icons:
            password_icon_label = ttk.Label(password_frame, image=self.icons["password"])
            password_icon_label.pack(side=tk.LEFT, padx=(0, 5))

        password_label = ttk.Label(password_frame, text="密 碼", width=6, font=("Noto Sans TC", 10))
        password_label.pack(side=tk.LEFT)
        password_container = ttk.Frame(password_frame)
        password_container.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.password_entry = tk.Entry(
            password_container,
            bg="#334D6D",
            fg="white",
            width=25,
            insertbackground="white",
            show="*"  # 確保密碼顯示為 * 號
        )
        self.password_entry.pack(fill=tk.X)

        # 記住帳號勾選框
        self.remember_var = tk.BooleanVar(value=False)
        remember_frame = ttk.Frame(main_frame)
        remember_frame.pack(fill=tk.X, pady=(10,5))
        remember_checkbox = ttk.Checkbutton(
            remember_frame,
            text="記住帳號",
            variable=self.remember_var,
            onvalue=True,
            offvalue=False
        )
        remember_checkbox.pack(side=tk.RIGHT, padx=(0, 45))  # 與左側標籤對齊

        # 按鈕框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # 內部按鈕容器，用於置中按鈕
        inner_button_frame = ttk.Frame(button_frame)
        inner_button_frame.pack(anchor=tk.CENTER)

        # 使用按鈕管理器創建按鈕
        button_configs = [
            {
                'id': 'login',
                'normal_icon': 'login_icon.png',
                'hover_icon': 'login_hover.png',
                'command': self.login,
                'tooltip': '登入系統',
                'side': tk.LEFT,
                'padx': 10
            },
            {
                'id': 'register',
                'normal_icon': 'register_icon.png',
                'hover_icon': 'register_hover.png',
                'command': self.show_register,
                'tooltip': '註冊帳號',
                'side': tk.LEFT,
                'padx': 10
            }
        ]

        # 創建按鈕
        self.login_buttons = self.button_manager.create_button_set(inner_button_frame, button_configs)

        # 設置焦點和綁定 Enter 鍵
        self.username_entry.focus_set()
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus_set())
        self.password_entry.bind("<Return>", lambda e: self.login())

        # 在初始化時重置所有用戶的登入狀態
        self.reset_all_login_states()

    def load_saved_username(self):
        """載入保存的帳號"""
        try:
            # 獲取專案根目錄
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            saved_file = os.path.join(root_dir, "saved_account.json")

            # 如果文件存在，讀取內容
            if os.path.exists(saved_file):
                with open(saved_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    saved_username = data.get('username', '')
                    remember = data.get('remember', False)

                    if remember and saved_username:
                        self.username_entry.delete(0, tk.END)
                        self.username_entry.insert(0, saved_username)
                        self.remember_var.set(True)
                        self.logger.info(f"已載入保存的帳號: {saved_username}")
                    else:
                        self.remember_var.set(False)
            else:
                self.logger.debug("沒有找到保存的帳號文件")
                self.remember_var.set(False)

        except Exception as e:
            self.logger.error(f"載入保存的帳號時出錯: {e}", exc_info=True)
            # 發生錯誤時不要影響登入流程
            self.remember_var.set(False)

    def save_username(self, username):
        """保存帳號"""
        try:
            # 獲取專案根目錄
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            saved_file = os.path.join(root_dir, "saved_account.json")

            # 獲取勾選框的值
            remember = self.remember_var.get()

            # 創建要保存的數據
            data = {
                'username': username if remember else '',
                'remember': remember
            }

            # 保存到文件
            with open(saved_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            self.logger.info(f"已保存帳號設置: 用戶名={username if remember else '(已清除)'}, 記住={remember}")

        except Exception as e:
            self.logger.error(f"保存帳號時出錯: {e}", exc_info=True)

    def reset_all_login_states(self):
        """重置所有用戶的登入狀態"""
        try:
            # 查詢所有已登入的用戶
            logged_in_users = self.db_session.query(User).filter_by(is_logged_in=True).all()

            if logged_in_users:
                # 更新所有用戶的登入狀態為 False
                for user in logged_in_users:
                    user.is_logged_in = False
                    self.logger.info(f"重置用戶 {user.username} 的登入狀態")

                # 提交更改
                self.db_session.commit()
                self.logger.info(f"已重置 {len(logged_in_users)} 個用戶的登入狀態")

        except Exception as e:
            self.logger.error(f"重置登入狀態時出錯: {e}")
            # 不需要向用戶顯示錯誤，因為這是一個後台操作

    def login(self):
        """登入處理"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            show_warning("警告", "請輸入使用者名稱和密碼", self.master)
            return

        try:
            # 查詢使用者
            user = self.db_session.query(User).filter_by(username=username).first()

            if user and user.check_password(password):
                # 檢查用戶是否已經登入
                if user.is_logged_in:
                    # 檢查最後登入時間，如果超過 8 小時，認為是過時的狀態
                    now = datetime.datetime.now()
                    if not user.last_login or (now - user.last_login).total_seconds() > 28800:  # 8小時
                        # 過時的狀態，允許登入
                        self.logger.info(f"用戶 {username} 的上次登入狀態可能未正確清除，允許重新登入")
                    else:
                        # 真實的重複登入
                        show_warning("警告", "此帳號已在其他裝置登入中", self.master)
                        return

                # 檢查付費狀態
                if not hasattr(user, 'is_premium') or not user.is_premium:
                    show_warning("付費提示", "您的帳號尚未付費，請先完成付費後再登入。\n請將款項匯入指定帳戶，並在付款備註填寫您的用戶名稱。", self.master)
                    return

                # 檢查付費狀態是否過期
                if hasattr(user, 'is_premium') and user.is_premium:
                    now = datetime.datetime.now()
                    if user.premium_end_date and now > user.premium_end_date:
                        user.is_premium = False
                        self.db_session.commit()
                        show_warning("付費提示", "您的付費已過期，請重新付費後再登入。", self.master)
                        self.logger.info(f"用戶 {username} 的付費已過期")
                        return

                # 保存帳號（在登入成功前先保存）
                self.save_username(username)

                self.logger.info(f"用戶 {username} 登入成功，記住帳號狀態: {self.remember_var.get()}")

                # 登入成功
                self.current_user = user
                # 更新登入狀態和最後登入時間
                user.is_logged_in = True
                user.last_login = datetime.datetime.now()
                self.db_session.commit()

                # 關閉登入視窗
                self.master.destroy()

                # 開啟專案管理器
                root = tk.Tk()
                project_manager = ProjectManager(root, user_id=user.id)
                # 綁定關閉事件來確保登出狀態更新
                root.protocol("WM_DELETE_WINDOW", lambda: self.logout_user(user.id, root))
                # 使用 mainloop 替代 run
                project_manager.master.mainloop()

            else:
                # 登入失敗
                show_error("錯誤", "使用者名稱或密碼錯誤", self.master)

        except Exception as e:
            self.logger.error(f"登入時出錯: {e}")
            show_error("錯誤", f"登入失敗：{str(e)}", self.master)

    def logout_user(self, user_id, root):
        """處理用戶登出"""
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
            self.logger.error(f"登出更新失敗: {e}")
        finally:
            # 關閉視窗
            root.destroy()

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

    def cleanup(self):
        """清理資源"""
        # 關閉資料庫連接
        if hasattr(self, 'db_session'):
            self.db_manager.close_session(self.db_session)

        # 調用父類清理
        super().cleanup()
class RegisterDialog(BaseDialog):
    """註冊對話框"""

    def __init__(self, parent=None):
        """初始化註冊對話框"""
        self.result = None

        # 先調用父類初始化
        super().__init__(parent, title="註冊新使用者", width=400, height=300)

        # 在 window 創建後再初始化按鈕管理器
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self.window)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()

        # 確保按鈕管理器已初始化
        if not hasattr(self, 'button_manager'):
            from gui.components.button_manager import ButtonManager
            self.button_manager = ButtonManager(self.window)

        # 初始化資料庫連接
        self.db_manager = DatabaseManager()
        self.db_session = self.db_manager.get_session()

        # 建立註冊表單
        self.create_register_form()

    def create_register_form(self):
        """創建註冊表單"""
        # 主框架
        main_frame = ttk.Frame(self.main_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 標題
        title_label = ttk.Label(main_frame, text="SRT文本處理系統 - 註冊", font=("Noto Sans TC", 13))
        title_label.pack(pady=(0, 20))


        # 載入圖標 - 基於新的資料夾結構
        try:
            # 獲取專案根目錄
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)

            # 指向assets/icons
            icons_dir = os.path.join(project_root, "assets", "icons")

            # 定義圖標檔案名稱
            icon_files = {
                "account": "account.png",
                "password": "password.png",
                "email": "email_icon.png",
                "check": "check_icon.png",
                "checked": "checked_icon.png"
            }

            # 記錄成功載入的圖標
            self.icons = {}

            # 載入所有圖標
            from PIL import Image, ImageTk

            for icon_name, file_name in icon_files.items():
                icon_path = os.path.join(icons_dir, file_name)
                if os.path.exists(icon_path):
                    try:
                        img = Image.open(icon_path)
                        img = img.resize((20, 20), Image.Resampling.LANCZOS)
                        self.icons[icon_name] = ImageTk.PhotoImage(img)
                        self.logger.debug(f"成功載入圖標: {icon_name}")
                    except Exception as e:
                        self.logger.warning(f"載入圖標 {icon_name} 時出錯: {e}")
                else:
                    self.logger.warning(f"找不到圖標文件: {icon_path}")

            # 確保有基本圖標，如果缺失則使用替代方案
            if "account" not in self.icons and "password" in self.icons:
                self.icons["account"] = self.icons["password"]
            if "email" not in self.icons and "account" in self.icons:
                self.icons["email"] = self.icons["account"]
            if "check" not in self.icons and "password" in self.icons:
                self.icons["check"] = self.icons["password"]
            if "checked" not in self.icons and "check" in self.icons:
                self.icons["checked"] = self.icons["check"]

        except Exception as e:
            self.logger.error(f"載入圖標時出錯: {e}")
            self.icons = {}

        # 使用者名稱輸入框
        username_frame = ttk.Frame(main_frame)
        username_frame.pack(pady=5)

        # 帳號圖標
        if "account" in self.icons:
            account_icon_label = ttk.Label(username_frame, image=self.icons["account"])
            account_icon_label.pack(side=tk.LEFT, padx=(0, 5))

        username_label = ttk.Label(username_frame, text="帳　號", width=6, font=("Noto Sans TC", 10))
        username_label.pack(side=tk.LEFT)
        username_container = ttk.Frame(username_frame)
        username_container.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.username_entry = tk.Entry(
            username_container,
            bg="#334D6D",
            fg="white",
            width=25,
            insertbackground="white"
        )
        self.username_entry.pack(fill=tk.X)

        # 電子郵件輸入框
        email_frame = ttk.Frame(main_frame)
        email_frame.pack(pady=5)

        # 郵箱圖標
        if "email" in self.icons:
            email_icon_label = ttk.Label(email_frame, image=self.icons["email"])
            email_icon_label.pack(side=tk.LEFT, padx=(0, 5))

        email_label = ttk.Label(email_frame, text="郵　箱", width=6, font=("Noto Sans TC", 10))
        email_label.pack(side=tk.LEFT)
        email_container = ttk.Frame(email_frame)
        email_container.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.email_entry = tk.Entry(
            email_container,
            bg="#334D6D",
            fg="white",
            width=25,
            insertbackground="white"
        )
        self.email_entry.pack(fill=tk.X)

        # 密碼輸入框
        password_frame = ttk.Frame(main_frame)
        password_frame.pack(pady=5)

        # 密碼圖標
        if "password" in self.icons:
            password_icon_label = ttk.Label(password_frame, image=self.icons["password"])
            password_icon_label.pack(side=tk.LEFT, padx=(0, 5))

        password_label = ttk.Label(password_frame, text="密　碼", width=6, font=("Noto Sans TC", 10))
        password_label.pack(side=tk.LEFT)
        password_container = ttk.Frame(password_frame)
        password_container.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.password_entry = tk.Entry(
            password_container,
            bg="#334D6D",
            fg="white",
            width=25,
            insertbackground="white",
            show="*"
        )
        self.password_entry.pack(fill=tk.X)

        # 確認密碼輸入框
        confirm_frame = ttk.Frame(main_frame)
        confirm_frame.pack(pady=5)

        # 確認圖標（初始使用check_icon）
        self.confirm_icon_label = ttk.Label(
            confirm_frame,
            image=self.icons.get("check")
        )
        self.confirm_icon_label.pack(side=tk.LEFT, padx=(0, 5))

        confirm_label = ttk.Label(confirm_frame, text="確　認", width=6, font=("Noto Sans TC", 10))
        confirm_label.pack(side=tk.LEFT)
        confirm_container = ttk.Frame(confirm_frame)
        confirm_container.pack(side=tk.LEFT, fill=tk.X, padx=5)
        self.confirm_entry = tk.Entry(
            confirm_container,
            bg="#334D6D",
            fg="white",
            width=25,
            insertbackground="white",
            show="*"
        )
        self.confirm_entry.pack(fill=tk.X)

        # 檢查密碼一致性並更改圖標
        def check_password_match(*args):
            if self.password_entry.get() == self.confirm_entry.get() and self.password_entry.get():
                # 密碼一致且不為空，使用已確認圖標
                if "checked" in self.icons:
                    self.confirm_icon_label.configure(image=self.icons["checked"])
            else:
                # 密碼不一致或為空，使用確認前圖標
                if "check" in self.icons:
                    self.confirm_icon_label.configure(image=self.icons["check"])

        # 綁定密碼變更事件
        self.password_var = tk.StringVar()
        self.password_entry.configure(textvariable=self.password_var)
        self.password_var.trace_add("write", check_password_match)

        self.confirm_var = tk.StringVar()
        self.confirm_entry.configure(textvariable=self.confirm_var)
        self.confirm_var.trace_add("write", check_password_match)

        # 按鈕框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # 內部按鈕容器，用於置中按鈕
        inner_button_frame = ttk.Frame(button_frame)
        inner_button_frame.pack(anchor=tk.CENTER)

        # 使用按鈕管理器創建圖片按鈕
        button_configs = [
            {
                'id': 'register',
                'normal_icon': 'register_icon.png',
                'hover_icon': 'register_hover.png',
                'command': self.register,
                'tooltip': '註冊新帳號',
                'side': tk.LEFT,
                'padx': 10
            },
            {
                'id': 'cancel',
                'normal_icon': 'cancel_icon.png',
                'hover_icon': 'cancel_hover.png',
                'command': self.cancel,
                'tooltip': '取消註冊',
                'side': tk.LEFT,
                'padx': 10
            }
        ]

        # 創建按鈕
        self.register_buttons = self.button_manager.create_button_set(inner_button_frame, button_configs)

        # 設置焦點
        self.username_entry.focus_set()

        # 設置鍵盤事件
        self.username_entry.bind("<Return>", lambda e: self.email_entry.focus_set())
        self.email_entry.bind("<Return>", lambda e: self.password_entry.focus_set())
        self.password_entry.bind("<Return>", lambda e: self.confirm_entry.focus_set())
        self.confirm_entry.bind("<Return>", lambda e: self.register())
        self.window.bind("<Escape>", lambda e: self.cancel())

    def register(self):
        """註冊處理"""
        username = self.username_entry.get().strip()
        email = self.email_entry.get().strip()
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()

        # 基本驗證
        if not username or not email or not password:
            show_warning("警告", "請填寫所有欄位", self.window)
            return

        if password != confirm:
            show_warning("警告", "兩次輸入的密碼不一致", self.window)
            return

        try:
            # 檢查使用者名稱是否已存在
            existing_user = self.db_session.query(User).filter_by(username=username).first()
            if existing_user:
                show_warning("警告", "使用者名稱已被使用", self.window)
                return

            # 檢查電子郵件是否已存在
            existing_email = self.db_session.query(User).filter_by(email=email).first()
            if existing_email:
                show_warning("警告", "電子郵件已被使用", self.window)
                return

            # 創建新使用者
            new_user = User(username=username, email=email)
            new_user.set_password(password)

            # 添加到資料庫
            self.db_session.add(new_user)
            self.db_session.commit()

            # 註冊成功
            show_info("成功", "註冊成功，請使用新帳號登入", self.window)
            self.result = username
            self.close()

        except Exception as e:
            self.logger.error(f"註冊時出錯: {e}")
            show_error("錯誤", f"註冊失敗：{str(e)}", self.window)

    def cleanup(self):
        """清理資源"""
        # 關閉資料庫連接
        if hasattr(self, 'db_session'):
            self.db_manager.close_session(self.db_session)

    def ok(self, event=None):
        """確定按鈕事件"""
        try:
            if self.validate():
                self.apply()
                # 釋放窗口控制權，但不立即銷毀
                self.window.grab_release()
                self.window.destroy()
        except tk.TclError:
            # 窗口可能已關閉
            pass

    def cancel(self, event=None):
        """取消按鈕事件"""
        try:
            self.result = None
            # 釋放窗口控制權，但不立即銷毀
            self.window.grab_release()
            self.window.destroy()
        except tk.TclError:
            # 窗口可能已關閉
            pass