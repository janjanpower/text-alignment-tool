"""版本檢查模組，負責檢查版本信息和比較版本號"""

import logging
import re
from typing import Dict, Any, Optional, Tuple

import requests


class VersionChecker:
    """版本檢查類，提供版本檢查和比較功能"""

    def __init__(self, github_api_url: str):
        """
        初始化版本檢查器
        :param github_api_url: GitHub API URL
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.github_api_url = github_api_url

    def check_latest_version(self) -> Tuple[bool, Dict[str, Any]]:
        """
        檢查最新版本
        :return: 元組 (成功, 版本信息)
        """
        try:
            # 發送請求獲取最新版本信息
            releases_url = f"{self.github_api_url}/releases/latest"
            self.logger.debug(f"檢查最新版本，API URL: {releases_url}")

            response = requests.get(releases_url, timeout=10)
            response.raise_for_status()

            release_data = response.json()

            # 解析版本信息
            version_info = {
                'version': release_data.get('tag_name', '').lstrip('v'),
                'name': release_data.get('name', ''),
                'body': release_data.get('body', ''),
                'published_at': release_data.get('published_at', ''),
                'assets': self._parse_assets(release_data.get('assets', []))
            }

            return True, version_info

        except Exception as e:
            self.logger.error(f"檢查最新版本時出錯: {e}")
            return False, {'error': str(e)}

    def _parse_assets(self, assets: list) -> Dict[str, Dict[str, Any]]:
        """
        解析資產列表
        :param assets: GitHub API返回的資產列表
        :return: 解析後的資產字典，以資產名為鍵
        """
        result = {}

        for asset in assets:
            name = asset.get('name', '')
            if name:
                result[name] = {
                    'url': asset.get('browser_download_url', ''),
                    'size': asset.get('size', 0),
                    'created_at': asset.get('created_at', ''),
                    'download_count': asset.get('download_count', 0),
                    'content_type': asset.get('content_type', ''),
                    'os_info': self._detect_os_from_filename(name)
                }

        return result

    def _detect_os_from_filename(self, filename: str) -> Dict[str, bool]:
        """
        從文件名檢測操作系統信息
        :param filename: 文件名
        :return: 操作系統信息字典
        """
        result = {
            'windows': False,
            'macos': False,
            'linux': False,
            'universal': False
        }

        filename = filename.lower()

        # 檢測Windows
        if '.exe' in filename or 'win' in filename or 'windows' in filename:
            result['windows'] = True

        # 檢測macOS
        if '.dmg' in filename or 'mac' in filename or 'macos' in filename or 'darwin' in filename:
            result['macos'] = True

        # 檢測Linux
        if '.tar.gz' in filename or '.appimage' in filename or 'linux' in filename:
            result['linux'] = True

        # 檢測通用版本
        if 'universal' in filename or 'all' in filename:
            result['universal'] = True

        return result

    def compare_versions(self, version1: str, version2: str) -> int:
        """
        比較兩個版本號
        :param version1: 第一個版本號
        :param version2: 第二個版本號
        :return: 如果version1 > version2返回1，如果version1 < version2返回-1，如果相等返回0
        """
        # 清理版本號（移除前綴'v'等）
        v1 = re.sub(r'^[vV]', '', version1)
        v2 = re.sub(r'^[vV]', '', version2)

        # 將版本號拆分為部分
        v1_parts = self._parse_version_parts(v1)
        v2_parts = self._parse_version_parts(v2)

        # 確保有相同數量的部分進行比較
        while len(v1_parts) < len(v2_parts):
            v1_parts.append(0)
        while len(v2_parts) < len(v1_parts):
            v2_parts.append(0)

        # 逐部分比較
        for i in range(len(v1_parts)):
            if v1_parts[i] > v2_parts[i]:
                return 1
            elif v1_parts[i] < v2_parts[i]:
                return -1

        return 0  # 版本號相等

    def _parse_version_parts(self, version: str) -> list:
        """
        將版本號字符串解析為部分列表
        :param version: 版本號字符串
        :return: 版本部分列表，例如 "1.2.3-beta" -> [1, 2, 3, 0]
        """
        # 首先分離預發布標識符
        if '-' in version:
            version, prerelease = version.split('-', 1)
        else:
            prerelease = ""

        # 拆分主版本號
        parts = []
        for part in version.split('.'):
            try:
                parts.append(int(part))
            except ValueError:
                # 如果部分不是純數字，嘗試提取數字部分
                digits = ''.join(filter(str.isdigit, part))
                parts.append(int(digits) if digits else 0)

        # 處理預發布版本
        if prerelease:
            # 預發布版本應該排在相同主版本號的正式版本之前
            # 例如 1.0.0-beta < 1.0.0
            parts.append(0)  # 添加一個額外的0表示這是預發布版本

        return parts

    def is_update_available(self, current_version: str, latest_version: str) -> bool:
        """
        檢查是否有更新可用
        :param current_version: 當前版本
        :param latest_version: 最新版本
        :return: 是否有更新可用
        """
        return self.compare_versions(latest_version, current_version) > 0