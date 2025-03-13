"""登入視窗類別模組"""

import datetime
import tkinter as tk
from tkinter import ttk
import logging
from gui.base_dialog import BaseDialog
from gui.base_window import BaseWindow
from gui.custom_messagebox import show_info, show_warning, show_error
from database.db_manager import DatabaseManager
from database.models import User
from gui.project_manager import ProjectManager

class LoginWindow(BaseWindow):
    """登入視窗類別"""

    def __init__(self, master=None):
        """初始化登入視窗"""
        super().__init__(title="文本對齊工具 - 登入", width=400, height=300, master=master)

        # 初始化資料庫連接
        self.db_manager = DatabaseManager()
        self.db_session = self.db_manager.get_session()
        self.current_user = None

        # 創建登入介面
        self.create_login_interface()

    def create_login_interface(self):
        """創建登入介面"""
        # 主框架
        main_frame = ttk.Frame(self.main_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 標題
        title_label = ttk.Label(main_frame, text="登入系統", font=("Arial", 16))
        title_label.pack(pady=(0, 20))

        # 使用者名稱輸入框
        username_frame = ttk.Frame(main_frame)
        username_frame.pack(fill=tk.X, pady=5)
        ttk.Label(username_frame, text="使用者名稱:").pack(side=tk.LEFT)
        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 密碼輸入框
        password_frame = ttk.Frame(main_frame)
        password_frame.pack(fill=tk.X, pady=5)
        ttk.Label(password_frame, text="密碼:").pack(side=tk.LEFT)
        self.password_entry = ttk.Entry(password_frame, show="*")
        self.password_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 按鈕框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # 登入按鈕
        login_button = ttk.Button(button_frame, text="登入", command=self.login)
        login_button.pack(side=tk.RIGHT, padx=5)

        # 註冊按鈕
        register_button = ttk.Button(button_frame, text="註冊", command=self.show_register)
        register_button.pack(side=tk.RIGHT, padx=5)

        # 設置焦點和綁定 Enter 鍵
        self.username_entry.focus_set()
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus_set())
        self.password_entry.bind("<Return>", lambda e: self.login())

        # 在初始化時重置所有用戶的登入狀態
        self.reset_all_login_states()

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
                project_manager.run()

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
        register_dialog = RegisterDialog(self.master)
        if register_dialog.result:
            # 註冊成功後自動填入使用者名稱
            self.username_entry.delete(0, tk.END)
            self.username_entry.insert(0, register_dialog.result)
            self.password_entry.focus_set()

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
        super().__init__(parent, title="註冊新使用者", width=400, height=300)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()

        # 初始化資料庫連接
        self.db_manager = DatabaseManager()
        self.db_session = self.db_manager.get_session()

        # 建立註冊表單
        self.create_register_form()

    def create_register_form(self):
        """創建註冊表單"""
        # 主框架
        main_frame = ttk.Frame(self.main_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 使用者名稱輸入框
        username_frame = ttk.Frame(main_frame)
        username_frame.pack(fill=tk.X, pady=5)
        ttk.Label(username_frame, text="使用者名稱:").pack(side=tk.LEFT)
        self.username_entry = ttk.Entry(username_frame)
        self.username_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 電子郵件輸入框
        email_frame = ttk.Frame(main_frame)
        email_frame.pack(fill=tk.X, pady=5)
        ttk.Label(email_frame, text="電子郵件:").pack(side=tk.LEFT)
        self.email_entry = ttk.Entry(email_frame)
        self.email_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 密碼輸入框
        password_frame = ttk.Frame(main_frame)
        password_frame.pack(fill=tk.X, pady=5)
        ttk.Label(password_frame, text="密碼:").pack(side=tk.LEFT)
        self.password_entry = ttk.Entry(password_frame, show="*")
        self.password_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 確認密碼輸入框
        confirm_frame = ttk.Frame(main_frame)
        confirm_frame.pack(fill=tk.X, pady=5)
        ttk.Label(confirm_frame, text="確認密碼:").pack(side=tk.LEFT)
        self.confirm_entry = ttk.Entry(confirm_frame, show="*")
        self.confirm_entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 按鈕框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # 註冊按鈕
        register_button = ttk.Button(button_frame, text="註冊", command=self.register)
        register_button.pack(side=tk.RIGHT, padx=5)

        # 取消按鈕
        cancel_button = ttk.Button(button_frame, text="取消", command=self.cancel)
        cancel_button.pack(side=tk.RIGHT, padx=5)

        # 設置焦點
        self.username_entry.focus_set()

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