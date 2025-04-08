"""專案服務模組，處理專案相關操作"""

import os
import logging
from typing import List, Optional

class ProjectService:
    """專案服務，提供統一的專案數據訪問接口"""

    def __init__(self):
        """初始化專案服務"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.projects_dir = self.get_projects_directory()

    def get_projects_directory(self) -> str:
        """獲取專案目錄路徑"""
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(current_dir, "projects")

    def ensure_projects_directory(self):
        """確保專案目錄存在"""
        os.makedirs(self.projects_dir, exist_ok=True)

    def get_user_projects(self, user_id: Optional[int] = None) -> List[str]:
        """
        獲取用戶的專案列表 (從檔案系統)
        :param user_id: 用戶ID (可選，本地版本不使用)
        :return: 專案名稱列表
        """
        return self.get_directory_projects()

    def get_directory_projects(self) -> List[str]:
        """
        從目錄獲取專案列表
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

    def add_project(self, project_name: str, user_id: Optional[int] = None) -> bool:
        """
        添加新專案
        :param project_name: 專案名稱
        :param user_id: 用戶ID (本地版本不使用)
        :return: 是否成功
        """
        try:
            # 檢查專案是否已存在
            project_path = os.path.join(self.projects_dir, project_name)
            if os.path.exists(project_path):
                self.logger.warning(f"專案 {project_name} 已存在")
                return False

            # 建立專案目錄
            os.makedirs(project_path, exist_ok=True)
            self.logger.info(f"已成功添加專案 {project_name}")
            return True

        except Exception as e:
            self.logger.error(f"添加專案時出錯: {e}")
            return False

    def delete_project(self, project_name: str, user_id: Optional[int] = None) -> bool:
        """
        刪除專案
        :param project_name: 專案名稱
        :param user_id: 用戶ID (本地版本不使用)
        :return: 是否成功
        """
        try:
            # 刪除專案目錄
            project_path = os.path.join(self.projects_dir, project_name)
            if os.path.exists(project_path):
                import shutil
                shutil.rmtree(project_path)
                self.logger.info(f"已成功刪除專案 {project_name}")
                return True
            else:
                self.logger.warning(f"專案 {project_name} 不存在，無法刪除")
                return False
        except Exception as e:
            self.logger.error(f"刪除專案時出錯: {e}")
            return False

    def close(self):
        """關閉資源 (為向後兼容而保留的方法)"""
        # 本地檔案系統版本不需要特殊的關閉操作
        pass