"""專案服務模組，處理專案相關操作"""

import os
import logging
from typing import List, Optional, Tuple
from database.db_manager import DatabaseManager
from database.models import User, Project

class ProjectService:
    """專案服務，提供統一的專案數據訪問接口"""

    def __init__(self):
        """初始化專案服務"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_manager = DatabaseManager()
        self.db_session = self.db_manager.get_session()
        self.projects_dir = self.get_projects_directory()

    def __del__(self):
        """析構函數，確保資源釋放"""
        self.close()

    def close(self):
        """關閉資源"""
        if hasattr(self, 'db_session'):
            self.db_manager.close_session(self.db_session)

    def get_projects_directory(self) -> str:
        """獲取專案目錄路徑"""
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(current_dir, "projects")

    def ensure_projects_directory(self):
        """確保專案目錄存在"""
        os.makedirs(self.projects_dir, exist_ok=True)

    def get_user_projects(self, user_id: int) -> List[str]:
        """
        獲取用戶的專案列表
        :param user_id: 用戶ID
        :return: 專案名稱列表
        """
        try:
            # 確保連接有效
            if not self.db_manager.is_session_active(self.db_session):
                self.db_session = self.db_manager.get_session()

            # 獲取用戶
            user = self.db_session.query(User).filter_by(id=user_id).first()
            if not user:
                self.logger.warning(f"找不到ID為 {user_id} 的用戶")
                return self.get_directory_projects()  # 回退到目錄方式

            # 獲取用戶的專案
            projects = self.db_session.query(Project).filter_by(owner_id=user.id).all()
            project_names = [project.name for project in projects]
            self.logger.debug(f"已從資料庫載入用戶 {user.username} 的專案，共 {len(project_names)} 個")

            return project_names
        except Exception as e:
            self.logger.error(f"獲取用戶專案列表時出錯: {e}")
            return self.get_directory_projects()  # 出錯時回退到目錄方式

    def get_directory_projects(self) -> List[str]:
        """
        從目錄獲取專案列表（向後兼容）
        :return: 專案名稱列表
        """
        try:
            self.ensure_projects_directory()
            projects = [d for d in os.listdir(self.projects_dir)
                     if os.path.isdir(os.path.join(self.projects_dir, d))]
            return projects
        except Exception as e:
            self.logger.error(f"從目錄獲取專案列表時出錯: {e}")
            return []

    def add_project(self, project_name: str, user_id: int) -> bool:
        """
        添加新專案
        :param project_name: 專案名稱
        :param user_id: 用戶ID
        :return: 是否成功
        """
        try:
            # 確保連接有效
            if not self.db_manager.is_session_active(self.db_session):
                self.db_session = self.db_manager.get_session()

            # 檢查用戶是否存在
            user = self.db_session.query(User).filter_by(id=user_id).first()
            if not user:
                self.logger.warning(f"找不到ID為 {user_id} 的用戶")
                return False

            # 檢查專案是否已存在
            existing_project = self.db_session.query(Project).filter_by(
                name=project_name, owner_id=user.id).first()
            if existing_project:
                self.logger.warning(f"專案 {project_name} 已存在")
                return False

            # 建立專案目錄
            project_path = os.path.join(self.projects_dir, project_name)
            os.makedirs(project_path, exist_ok=True)

            # 在資料庫中建立專案記錄
            new_project = Project(
                name=project_name,
                owner_id=user.id
            )
            self.db_session.add(new_project)
            self.db_session.commit()

            self.logger.info(f"已成功添加專案 {project_name} 給用戶 {user.username}")
            return True
        except Exception as e:
            self.logger.error(f"添加專案時出錯: {e}")
            if hasattr(self, 'db_session'):
                self.db_session.rollback()
            return False

    def delete_project(self, project_name: str, user_id: Optional[int] = None) -> bool:
        """
        刪除專案
        :param project_name: 專案名稱
        :param user_id: 用戶ID（可選）
        :return: 是否成功
        """
        try:
            # 刪除專案目錄
            project_path = os.path.join(self.projects_dir, project_name)
            if os.path.exists(project_path):
                import shutil
                shutil.rmtree(project_path)

            # 如果有用戶ID，也從資料庫刪除專案記錄
            if user_id:
                # 確保連接有效
                if not self.db_manager.is_session_active(self.db_session):
                    self.db_session = self.db_manager.get_session()

                # 刪除資料庫記錄
                project = self.db_session.query(Project).filter_by(
                    name=project_name, owner_id=user_id).first()
                if project:
                    self.db_session.delete(project)
                    self.db_session.commit()

            self.logger.info(f"已成功刪除專案 {project_name}")
            return True
        except Exception as e:
            self.logger.error(f"刪除專案時出錯: {e}")
            if hasattr(self, 'db_session'):
                self.db_session.rollback()
            return False