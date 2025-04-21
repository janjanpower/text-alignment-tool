"""配置管理器模組，負責加載和保存配置"""

import json
import logging
import os
from typing import Dict, Any, Optional


class ConfigManager:
    """配置管理器類，處理配置加載和保存"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        :param config_path: 配置文件路徑，如果為None則使用默認路徑
        """
        self.logger = logging.getLogger(self.__class__.__name__)

        # 設置配置文件路徑
        if config_path:
            self.config_path = config_path
        else:
            # 默認路徑為應用程序目錄下的config.json
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.config_path = os.path.join(current_dir, "config.json")

        # 加載配置
        self.config = self._load_config()

        # 確保每個配置部分都存在
        self._ensure_config_sections()

    def _load_config(self) -> Dict[str, Any]:
        """
        加載配置文件
        :return: 配置字典
        """
        try:
            # 檢查配置文件是否存在
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info(f"已加載配置文件: {self.config_path}")
                return config
            else:
                self.logger.warning(f"配置文件不存在: {self.config_path}，將使用默認配置")
                return self._get_default_config()
        except Exception as e:
            self.logger.error(f"加載配置文件時出錯: {e}")
            return self._get_default_config()

    def _save_config(self) -> bool:
        """
        保存配置到文件
        :return: 是否成功保存
        """
        try:
            # 確保目錄存在
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            # 寫入配置文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)

            self.logger.info(f"已保存配置到: {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存配置文件時出錯: {e}")
            return False

    def _get_default_config(self) -> Dict[str, Any]:
        """
        獲取默認配置
        :return: 默認配置字典
        """
        return {
            "window": {
                "width": 1000,
                "height": 600,
                "title": "文本對齊工具"
            },
            "audio": {
                "sample_rate": 44100,
                "channels": 2,
                "buffer_size": 4096
            },
            "display": {
                "font_family": "Arial",
                "font_size": 12,
                "theme": "default"
            },
            "database": {
                "host": "localhost",
                "port": 5432,
                "username": "postgres",
                "password": "",
                "database": "Text_Alignment_Tool"
            },
            "recent_projects": [],
            "recent_files": [],
            "language": "zh_TW",
            "auto_save": True,
            "auto_save_interval": 300,
            "max_undo_steps": 50,
            "login": {
                "remember_username": False,
                "saved_username": ""
            },
            "update": {
                "auto_check": True,
                "check_interval": 24,  # 小時
                "last_check_time": 0,
                "repo_owner": "",
                "repo_name": "",
                "branch": "main",
                "current_version": "1.0.0"
            }
        }

    def _ensure_config_sections(self) -> None:
        """確保所有必要的配置段都存在"""
        default_config = self._get_default_config()

        # 檢查並添加缺失的部分
        for section, values in default_config.items():
            if section not in self.config:
                self.config[section] = values
                self.logger.debug(f"添加缺失的配置部分: {section}")
            elif isinstance(values, dict):
                # 檢查子項
                for key, value in values.items():
                    if key not in self.config[section]:
                        self.config[section][key] = value
                        self.logger.debug(f"添加缺失的配置項: {section}.{key}")

    def get_config(self) -> Dict[str, Any]:
        """
        獲取完整配置
        :return: 配置字典
        """
        return self.config

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        獲取特定配置區段
        :param section: 區段名稱
        :return: 區段配置字典
        """
        if section in self.config:
            return self.config[section]
        else:
            # 如果區段不存在，從默認配置中獲取
            default_config = self._get_default_config()
            if section in default_config:
                self.config[section] = default_config[section]
                return default_config[section]
            else:
                self.logger.warning(f"嘗試獲取不存在的配置區段: {section}")
                return {}

    def get_window_config(self) -> Dict[str, Any]:
        """
        獲取視窗配置
        :return: 視窗配置字典
        """
        return self.get_section("window")

    def get_audio_config(self) -> Dict[str, Any]:
        """
        獲取音頻配置
        :return: 音頻配置字典
        """
        return self.get_section("audio")

    def get_display_config(self) -> Dict[str, Any]:
        """
        獲取顯示配置
        :return: 顯示配置字典
        """
        return self.get_section("display")

    def get_database_config(self) -> Dict[str, Any]:
        """
        獲取數據庫配置
        :return: 數據庫配置字典
        """
        return self.get_section("database")

    def get_login_config(self) -> Dict[str, Any]:
        """
        獲取登入配置
        :return: 登入配置字典
        """
        return self.get_section("login")

    def get_update_config(self) -> Dict[str, Any]:
        """
        獲取更新配置
        :return: 更新配置字典
        """
        return self.get_section("update")

    def set_section(self, section: str, config: Dict[str, Any]) -> bool:
        """
        設置特定配置區段
        :param section: 區段名稱
        :param config: 區段配置字典
        :return: 是否成功設置
        """
        try:
            self.config[section] = config
            return self._save_config()
        except Exception as e:
            self.logger.error(f"設置配置區段時出錯: {section}, {e}")
            return False

    def set_option(self, section: str, option: str, value: Any) -> bool:
        """
        設置特定配置選項
        :param section: 區段名稱
        :param option: 選項名稱
        :param value: 選項值
        :return: 是否成功設置
        """
        try:
            # 如果區段不存在，創建它
            if section not in self.config:
                self.config[section] = {}

            self.config[section][option] = value
            return self._save_config()
        except Exception as e:
            self.logger.error(f"設置配置選項時出錯: {section}.{option}, {e}")
            return False

    def get_option(self, section: str, option: str, default: Any = None) -> Any:
        """
        獲取特定配置選項
        :param section: 區段名稱
        :param option: 選項名稱
        :param default: 默認值
        :return: 選項值
        """
        section_config = self.get_section(section)
        return section_config.get(option, default)

    def add_recent_project(self, project_path: str, max_size: int = 10) -> bool:
        """
        添加最近項目
        :param project_path: 項目路徑
        :param max_size: 最大保存數量
        :return: 是否成功添加
        """
        try:
            # 獲取最近項目列表
            recent_projects = self.config.get("recent_projects", [])

            # 如果項目已存在，先移除它
            if project_path in recent_projects:
                recent_projects.remove(project_path)

            # 將新項目添加到列表頭部
            recent_projects.insert(0, project_path)

            # 限制列表大小
            if len(recent_projects) > max_size:
                recent_projects = recent_projects[:max_size]

            # 更新配置
            self.config["recent_projects"] = recent_projects

            # 保存配置
            return self._save_config()
        except Exception as e:
            self.logger.error(f"添加最近項目時出錯: {e}")
            return False

    def add_recent_file(self, file_path: str, max_size: int = 10) -> bool:
        """
        添加最近文件
        :param file_path: 文件路徑
        :param max_size: 最大保存數量
        :return: 是否成功添加
        """
        try:
            # 獲取最近文件列表
            recent_files = self.config.get("recent_files", [])

            # 如果文件已存在，先移除它
            if file_path in recent_files:
                recent_files.remove(file_path)

            # 將新文件添加到列表頭部
            recent_files.insert(0, file_path)

            # 限制列表大小
            if len(recent_files) > max_size:
                recent_files = recent_files[:max_size]

            # 更新配置
            self.config["recent_files"] = recent_files

            # 保存配置
            return self._save_config()
        except Exception as e:
            self.logger.error(f"添加最近文件時出錯: {e}")
            return False

    def set_window_config(self, config: Dict[str, Any]) -> bool:
        """
        設置視窗配置
        :param config: 視窗配置字典
        :return: 是否成功設置
        """
        return self.set_section("window", config)

    def set_audio_config(self, config: Dict[str, Any]) -> bool:
        """
        設置音頻配置
        :param config: 音頻配置字典
        :return: 是否成功設置
        """
        return self.set_section("audio", config)

    def set_display_config(self, config: Dict[str, Any]) -> bool:
        """
        設置顯示配置
        :param config: 顯示配置字典
        :return: 是否成功設置
        """
        return self.set_section("display", config)

    def set_database_config(self, config: Dict[str, Any]) -> bool:
        """
        設置數據庫配置
        :param config: 數據庫配置字典
        :return: 是否成功設置
        """
        return self.set_section("database", config)

    def set_login_config(self, config: Dict[str, Any]) -> bool:
        """
        設置登入配置
        :param config: 登入配置字典
        :return: 是否成功設置
        """
        return self.set_section("login", config)

    def set_update_config(self, config: Dict[str, Any]) -> bool:
        """
        設置更新配置
        :param config: 更新配置字典
        :return: 是否成功設置
        """
        return self.set_section("update", config)

    def update_last_check_time(self, timestamp: int) -> bool:
        """
        更新最後檢查更新時間
        :param timestamp: 時間戳
        :return: 是否成功更新
        """
        return self.set_option("update", "last_check_time", timestamp)

    def get_auto_check_update(self) -> bool:
        """
        獲取是否自動檢查更新設置
        :return: 是否自動檢查更新
        """
        return self.get_option("update", "auto_check", True)

    def set_auto_check_update(self, auto_check: bool) -> bool:
        """
        設置是否自動檢查更新
        :param auto_check: 是否自動檢查更新
        :return: 是否成功設置
        """
        return self.set_option("update", "auto_check", auto_check)

    def get_check_update_interval(self) -> int:
        """
        獲取檢查更新間隔時間（小時）
        :return: 間隔小時數
        """
        return self.get_option("update", "check_interval", 24)

    def set_check_update_interval(self, interval: int) -> bool:
        """
        設置檢查更新間隔時間
        :param interval: 間隔小時數
        :return: 是否成功設置
        """
        return self.set_option("update", "check_interval", interval)

    def get_github_repo_info(self) -> tuple:
        """
        獲取GitHub存儲庫信息
        :return: (所有者, 存儲庫名, 分支名)
        """
        update_config = self.get_update_config()
        return (
            update_config.get("repo_owner", ""),
            update_config.get("repo_name", ""),
            update_config.get("branch", "main")
        )

    def set_github_repo_info(self, owner: str, repo: str, branch: str = "main") -> bool:
        """
        設置GitHub存儲庫信息
        :param owner: 存儲庫所有者
        :param repo: 存儲庫名稱
        :param branch: 分支名稱
        :return: 是否成功設置
        """
        update_config = self.get_update_config()
        update_config["repo_owner"] = owner
        update_config["repo_name"] = repo
        update_config["branch"] = branch
        return self.set_update_config(update_config)

    def get_current_version(self) -> str:
        """
        獲取當前版本
        :return: 版本字符串
        """
        return self.get_option("update", "current_version", "1.0.0")

    def set_current_version(self, version: str) -> bool:
        """
        設置當前版本
        :param version: 版本字符串
        :return: 是否成功設置
        """
        return self.set_option("update", "current_version", version)