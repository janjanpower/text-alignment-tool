import datetime

from database.base import Base
from sqlalchemy import Column, Float, Integer, String, Boolean, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash
class User(Base):
    """使用者資料表"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)  # 帳號
    password_hash = Column(String(255), nullable=False)  # 密碼
    email = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)  # 帳戶是否啟用
    is_logged_in = Column(Boolean, default=False)  # 追蹤用戶是否登入中
    is_premium = Column(Boolean, default=False)  # 是否付費
    premium_start_date = Column(DateTime)  # 付費時間(付費起算日)
    premium_end_date = Column(DateTime)  # 到期時間
    created_at = Column(DateTime, default=datetime.datetime.now)  # 創建時間
    last_login = Column(DateTime)  # 最後登入時間
    bank_account = Column(String(100))  # 銀行帳戶資訊 (選擇性)

    # 添加與 Project 的關係
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

    def set_password(self, password):
        """設置密碼，使用安全的雜湊函數儲存"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """驗證密碼是否正確"""
        return check_password_hash(self.password_hash, password)

    def update_premium_status(self, is_premium=True, duration_months=1):
        """更新用戶的付費狀態"""
        now = datetime.datetime.now()

        if is_premium:
            self.is_premium = True
            self.premium_start_date = now
            # 計算到期時間 (當前時間 + duration_months 個月)
            self.premium_end_date = now + datetime.timedelta(days=30 * duration_months)
        else:
            self.is_premium = False
            self.premium_start_date = None
            self.premium_end_date = None

        return self.premium_end_date

    def check_premium_expiry(self):
        """檢查用戶付費狀態是否過期"""
        if not self.is_premium or not self.premium_end_date:
            return False

        now = datetime.datetime.now()
        if now > self.premium_end_date:
            self.is_premium = False
            return True  # 已過期

        return False  # 未過期

class Project(Base):
    """專案表"""
    __tablename__ = 'projects'
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # 新增使用者關聯
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    owner = relationship("User", back_populates="projects")

    # 子表關聯
    corrections = relationship("Correction", back_populates="project", cascade="all, delete-orphan")
    subtitles = relationship("Subtitle", back_populates="project", cascade="all, delete-orphan")

class Correction(Base):
    """校正資料表"""
    __tablename__ = 'corrections'

    id = Column(Integer, primary_key=True)
    error_text = Column(String(255), nullable=False)
    correction_text = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # 關聯到專案
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship("Project", back_populates="corrections")

class Subtitle(Base):
    """字幕資料表"""
    __tablename__ = 'subtitles'

    id = Column(Integer, primary_key=True)
    index = Column(Integer, nullable=False)
    start_time = Column(String(50), nullable=False)
    end_time = Column(String(50), nullable=False)
    text = Column(String(1000), nullable=False)
    word_text = Column(String(1000))
    is_corrected = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)

    # 關聯到專案
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    project = relationship("Project", back_populates="subtitles")

    class PaymentRecord(Base):
        """付款記錄資料表"""
        __tablename__ = 'payment_records'

        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
        user = relationship("User", backref="payment_records")
        amount = Column(Float, nullable=False)  # 付款金額
        payment_date = Column(DateTime, default=datetime.datetime.now)  # 付款日期
        transaction_id = Column(String(100))  # 交易編號
        bank_reference = Column(String(100))  # 銀行參考號
        status = Column(String(20), default="pending")  # 狀態: pending, confirmed, rejected
        verified_at = Column(DateTime)  # 驗證時間

        def confirm_payment(self):
            """確認付款並更新用戶狀態"""
            self.status = "confirmed"
            self.verified_at = datetime.datetime.now()

            # 更新用戶付費狀態 (預設1個月)
            self.user.update_premium_status(True, 1)

            return True