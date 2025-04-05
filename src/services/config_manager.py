"""配置管理類別模組"""

import json
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

class ConfigManager:
    """配置管理類別"""

    def __init__(self, config_file: str = "config.json") -> None:
        """
        初始化配置管理器
        :param config_file: 配置文件路徑
        """
        # 獲取專案根目錄
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 建構完整的配置文件路徑
        self.config_file = os.path.join(root_dir, config_file)
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(self.__class__.__name__)

        # 輸出配置文件路徑，便於調試
        self.logger.debug(f"配置文件路徑: {self.config_file}")
        self.load_config()

    def load_config(self) -> None:
        """載入配置文件"""
        try:
            if os.path.exists(self.config_file):
                self.logger.debug(f"配置文件存在: {self.config_file}")
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                    self.logger.debug(f"成功載入配置: {self.config}")
            else:
                self.logger.warning(f"配置文件不存在，創建默認配置: {self.config_file}")
                self.config = self.get_default_config()
                self.save_config()
        except Exception as e:
            self.logger.error(f"載入配置文件時出錯: {e}", exc_info=True)
            self.config = self.get_default_config()

    def save_config(self) -> None:
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.error(f"保存配置文件時出錯: {e}")

    def get_default_config(self) -> Dict[str, Any]:
        """
        取得預設配置
        :return: 預設配置字典
        """
        return {
            "window": {
                "width": 600,
                "height": 400,
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
            "recent_projects": [],
            "recent_files": [],
            "language": "zh_TW",
            "auto_save": True,
            "auto_save_interval": 300,
            "max_undo_steps": 50
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        取得配置值
        :param key: 配置鍵值
        :param default: 預設值
        :return: 配置值
        """
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                if k not in value:
                    self.logger.debug(f"配置項不存在: {key}，返回默認值: {default}")
                    return default
                value = value[k]
            return value
        except (KeyError, TypeError):
            self.logger.debug(f"取得配置值出錯: {key}，返回默認值: {default}")
            return default

    def set(self, key: str, value: Any) -> None:
        """
        設置配置值
        :param key: 配置鍵值
        :param value: 配置值
        """
        try:
            keys = key.split('.')
            config = self.config
            for k in keys[:-1]:
                config = config.setdefault(k, {})
            config[keys[-1]] = value
            self.save_config()
        except Exception as e:
            self.logger.error(f"設置配置值時出錯: {e}")

    def add_recent_project(self, project_path: str) -> None:
        """
        添加最近使用的專案
        :param project_path: 專案路徑
        """
        recent_projects = self.get('recent_projects', [])
        if project_path in recent_projects:
            recent_projects.remove(project_path)
        recent_projects.insert(0, project_path)
        recent_projects = recent_projects[:10]  # 保留最近的10個
        self.set('recent_projects', recent_projects)

    def add_recent_file(self, file_path: str) -> None:
        """
        添加最近使用的文件
        :param file_path: 文件路徑
        """
        recent_files = self.get('recent_files', [])
        if file_path in recent_files:
            recent_files.remove(file_path)
        recent_files.insert(0, file_path)
        recent_files = recent_files[:10]  # 保留最近的10個
        self.set('recent_files', recent_files)

    def clear_recent_projects(self) -> None:
        """清除最近使用的專案列表"""
        self.set('recent_projects', [])

    def clear_recent_files(self) -> None:
        """清除最近使用的文件列表"""
        self.set('recent_files', [])

    def get_window_config(self) -> Dict[str, Any]:
        """取得視窗配置"""
        return self.get('window', self.get_default_config()['window'])

    def get_audio_config(self) -> Dict[str, Any]:
        """取得音頻配置"""
        return self.get('audio', self.get_default_config()['audio'])

    def get_display_config(self) -> Dict[str, Any]:
        """取得顯示配置"""
        return self.get('display', self.get_default_config()['display'])

    def reset_to_default(self) -> None:
        """重置為預設配置"""
        self.config = self.get_default_config()
        self.save_config()

    def import_config(self, file_path: str) -> bool:
        """
        從文件導入配置
        :param file_path: 配置文件路徑
        :return: 是否成功導入
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                new_config = json.load(f)
            self.config = new_config
            self.save_config()
            return True
        except Exception as e:
            self.logger.error(f"導入配置文件時出錯: {e}")
            return False

    def export_config(self, file_path: str) -> bool:
        """
        導出配置到文件
        :param file_path: 導出文件路徑
        :return: 是否成功導出
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            self.logger.error(f"導出配置文件時出錯: {e}")
            return False

    def validate_config(self) -> bool:
        """
        驗證配置
        :return: 配置是否有效
        """
        required_keys = ['window', 'audio', 'display']
        try:
            for key in required_keys:
                if key not in self.config:
                    self.logger.error(f"缺少必要的配置項: {key}")
                    return False
            return True
        except Exception as e:
            self.logger.error(f"驗證配置時出錯: {e}")
            return False