"""更新管理器模組，負責檢查和安裝應用程式更新"""

import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple, Callable, Any

import requests

from services.config_manager import ConfigManager


class UpdateManager:
    """更新管理器類，處理從GitHub獲取和安裝更新"""

    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        初始化更新管理器
        :param config_manager: 配置管理器實例，如果為None則創建新實例
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config_manager = config_manager or ConfigManager()

        # 從配置中讀取更新相關設置
        self.update_settings = self.config_manager.get_update_config()

        # 設置GitHub存儲庫資訊
        self.repo_owner = self.update_settings.get('repo_owner', '')
        self.repo_name = self.update_settings.get('repo_name', '')
        self.branch = self.update_settings.get('branch', 'main')
        self.github_api_url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}"

        # 獲取當前版本
        self.current_version = self._get_current_version()

        # 更新相關屬性
        self.latest_version = None
        self.update_available = False
        self.release_notes = ""
        self.download_url = ""
        self.update_size = 0
        self.background_thread = None
        self.update_in_progress = False
        self.update_progress_callback = None
        self.update_complete_callback = None
        self.check_update_callback = None

        # 應用程式路徑
        self.app_path = self._get_app_path()
        self.backup_path = os.path.join(os.path.dirname(self.app_path), "backup")

        self.logger.debug(f"UpdateManager初始化完成，當前版本: {self.current_version}")
        self.logger.debug(f"GitHub倉庫: {self.repo_owner}/{self.repo_name}, 分支: {self.branch}")

    def _get_app_path(self) -> str:
        """
        獲取應用程式路徑
        :return: 應用程式主目錄路徑
        """
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包的應用
            return os.path.dirname(sys.executable)
        else:
            # 一般運行的 Python 腳本
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _get_current_version(self) -> str:
        """
        獲取當前應用程式版本
        :return: 版本字符串
        """
        # 首先嘗試從配置文件讀取
        version = self.update_settings.get('current_version', '')
        if version:
            return version

        # 如果配置中沒有，嘗試從VERSION文件讀取
        version_file = os.path.join(self._get_app_path(), "VERSION")
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()
            except Exception as e:
                self.logger.error(f"讀取VERSION文件時出錯: {e}")

        # 如果都沒有，返回默認版本
        return "1.0.0"

    def check_for_updates(self, callback: Optional[Callable] = None) -> bool:
        """
        檢查更新並通過回調返回結果
        :param callback: 完成後的回調函數，接收(has_update, version, release_notes)
        :return: 是否有更新可用
        """
        self.check_update_callback = callback

        try:
            # 發送請求獲取最新版本
            releases_url = f"{self.github_api_url}/releases/latest"
            self.logger.debug(f"檢查更新，API URL: {releases_url}")

            response = requests.get(releases_url, timeout=10)
            response.raise_for_status()

            release_data = response.json()
            self.latest_version = release_data.get('tag_name', '').lstrip('v')
            self.release_notes = release_data.get('body', '')

            # 找到適合當前系統的資產
            assets = release_data.get('assets', [])
            for asset in assets:
                if self._is_suitable_asset(asset['name']):
                    self.download_url = asset['browser_download_url']
                    self.update_size = asset['size']
                    break

            # 檢查版本比較
            has_update = self._compare_versions(self.latest_version, self.current_version) > 0
            self.update_available = has_update and self.download_url

            self.logger.info(f"更新檢查結果: 當前版本={self.current_version}, 最新版本={self.latest_version}, "
                           f"有更新={self.update_available}")

            # 調用回調函數
            if callback:
                callback(self.update_available, self.latest_version, self.release_notes)

            return self.update_available

        except Exception as e:
            self.logger.error(f"檢查更新時出錯: {e}")
            if callback:
                callback(False, "", f"檢查更新時出錯: {str(e)}")
            return False

    def _is_suitable_asset(self, asset_name: str) -> bool:
        """
        檢查資產是否適合當前系統
        :param asset_name: 資產名稱
        :return: 是否適合
        """
        system = platform.system().lower()
        if system == 'windows' and '.exe' in asset_name.lower():
            return True
        elif system == 'darwin' and ('.dmg' in asset_name.lower() or '.zip' in asset_name.lower()):
            return True
        elif system == 'linux' and ('.tar.gz' in asset_name.lower() or '.AppImage' in asset_name.lower()):
            return True

        # 通用版本（zip文件）
        if 'zip' in asset_name.lower() and 'universal' in asset_name.lower():
            return True

        return False

    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        比較兩個版本號
        :param version1: 第一個版本號
        :param version2: 第二個版本號
        :return: 如果version1 > version2返回1，如果version1 < version2返回-1，如果相等返回0
        """
        # 清理版本號（移除前綴'v'等）
        v1 = re.sub(r'^[vV]', '', version1)
        v2 = re.sub(r'^[vV]', '', version2)

        # 將版本號拆分為部分並轉換為整數
        v1_parts = [int(x) for x in v1.split('.') if x.isdigit()]
        v2_parts = [int(x) for x in v2.split('.') if x.isdigit()]

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

    def download_update(self, progress_callback: Optional[Callable] = None,
                      complete_callback: Optional[Callable] = None) -> None:
        """
        下載更新
        :param progress_callback: 下載進度回調，接收(progress_percent, downloaded_size, total_size)
        :param complete_callback: 下載完成回調，接收(success, error_message, download_path)
        """
        if not self.update_available or not self.download_url:
            if complete_callback:
                complete_callback(False, "沒有可用的更新或下載URL", "")
            return

        self.update_progress_callback = progress_callback
        self.update_complete_callback = complete_callback

        # 使用線程執行下載以避免UI阻塞
        self.background_thread = threading.Thread(
            target=self._download_update_thread,
            args=(self.download_url, progress_callback, complete_callback)
        )
        self.background_thread.daemon = True
        self.background_thread.start()

    def _download_update_thread(self, url: str, progress_callback: Optional[Callable],
                              complete_callback: Optional[Callable]) -> None:
        """
        下載更新的線程函數
        :param url: 下載URL
        :param progress_callback: 進度回調
        :param complete_callback: 完成回調
        """
        self.update_in_progress = True
        temp_dir = tempfile.mkdtemp()
        file_name = os.path.basename(urlparse(url).path)
        download_path = os.path.join(temp_dir, file_name)

        try:
            self.logger.info(f"開始下載更新: {url}")

            # 使用流式下載以便報告進度
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            block_size = 8192  # 8KB 塊大小
            downloaded = 0

            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # 更新下載進度
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress, downloaded, total_size)

            self.logger.info(f"更新下載完成: {download_path}")

            # 調用完成回調
            if complete_callback:
                complete_callback(True, "", download_path)

        except Exception as e:
            self.logger.error(f"下載更新時出錯: {e}")
            if complete_callback:
                complete_callback(False, str(e), "")
        finally:
            self.update_in_progress = False

    def install_update(self, download_path: str, progress_callback: Optional[Callable] = None,
                     complete_callback: Optional[Callable] = None) -> None:
        """
        安裝下載的更新
        :param download_path: 下載的文件路徑
        :param progress_callback: 安裝進度回調，接收(progress_percent, step_description)
        :param complete_callback: 安裝完成回調，接收(success, error_message)
        """
        if not os.path.exists(download_path):
            if complete_callback:
                complete_callback(False, f"更新文件不存在: {download_path}")
            return

        # 使用線程執行安裝
        self.background_thread = threading.Thread(
            target=self._install_update_thread,
            args=(download_path, progress_callback, complete_callback)
        )
        self.background_thread.daemon = True
        self.background_thread.start()

    def _install_update_thread(self, download_path: str, progress_callback: Optional[Callable],
                             complete_callback: Optional[Callable]) -> None:
        """
        安裝更新的線程函數
        :param download_path: 下載文件路徑
        :param progress_callback: 進度回調
        :param complete_callback: 完成回調
        """
        self.update_in_progress = True
        temp_dir = os.path.dirname(download_path)
        extract_dir = os.path.join(temp_dir, "extract")

        try:
            # 創建提取目錄
            if not os.path.exists(extract_dir):
                os.makedirs(extract_dir)

            # 更新進度：10%
            if progress_callback:
                progress_callback(10, "準備安裝更新...")

            # 檢查文件類型並安裝
            file_ext = os.path.splitext(download_path)[1].lower()

            if file_ext == '.zip':
                self._install_from_zip(download_path, extract_dir, progress_callback, complete_callback)
            elif file_ext == '.exe':
                self._install_from_exe(download_path, progress_callback, complete_callback)
            elif file_ext == '.dmg':
                self._install_from_dmg(download_path, progress_callback, complete_callback)
            elif file_ext in ['.gz', '.bz2']:
                self._install_from_tarball(download_path, extract_dir, progress_callback, complete_callback)
            else:
                if complete_callback:
                    complete_callback(False, f"不支持的更新文件類型: {file_ext}")

        except Exception as e:
            self.logger.error(f"安裝更新時出錯: {e}")
            if complete_callback:
                complete_callback(False, f"安裝更新時出錯: {str(e)}")
        finally:
            self.update_in_progress = False

    def _install_from_zip(self, zip_path: str, extract_dir: str,
                        progress_callback: Optional[Callable],
                        complete_callback: Optional[Callable]) -> None:
        """
        從ZIP文件安裝更新
        """
        try:
            # 更新進度：20%
            if progress_callback:
                progress_callback(20, "解壓縮更新文件...")

            # 解壓文件
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)

            # 更新進度：40%
            if progress_callback:
                progress_callback(40, "備份當前版本...")

            # 備份當前版本
            self._backup_current_version()

            # 更新進度：60%
            if progress_callback:
                progress_callback(60, "安裝新版本...")

            # 安裝新版本
            self._replace_with_new_version(extract_dir)

            # 更新進度：80%
            if progress_callback:
                progress_callback(80, "更新版本信息...")

            # 更新版本號
            self._update_version_info()

            # 更新進度：100%
            if progress_callback:
                progress_callback(100, "更新完成")

            # 完成回調
            if complete_callback:
                complete_callback(True, "")

        except Exception as e:
            self.logger.error(f"從ZIP安裝更新時出錯: {e}")

            # 如果有錯誤，嘗試恢復備份
            try:
                self._restore_from_backup()
                error_msg = f"更新失敗並已恢復原版本: {str(e)}"
            except Exception as restore_error:
                error_msg = f"更新失敗且無法恢復原版本: {str(e)}, 恢復錯誤: {str(restore_error)}"

            if complete_callback:
                complete_callback(False, error_msg)

    def _install_from_exe(self, exe_path: str, progress_callback: Optional[Callable],
                        complete_callback: Optional[Callable]) -> None:
        """
        從EXE安裝程序安裝更新
        """
        try:
            # 更新進度：50%
            if progress_callback:
                progress_callback(50, "啟動安裝程序...")

            # 在Windows上運行安裝程序
            if platform.system().lower() == 'windows':
                result = subprocess.run([exe_path, '/SILENT'], capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"安裝程序返回錯誤代碼: {result.returncode}, 錯誤: {result.stderr}")

                # 更新進度：100%
                if progress_callback:
                    progress_callback(100, "更新完成")

                # 完成回調
                if complete_callback:
                    complete_callback(True, "")
            else:
                if complete_callback:
                    complete_callback(False, "EXE安裝程序僅支持Windows系統")
        except Exception as e:
            self.logger.error(f"從EXE安裝更新時出錯: {e}")
            if complete_callback:
                complete_callback(False, f"從EXE安裝更新時出錯: {str(e)}")

    def _install_from_dmg(self, dmg_path: str, progress_callback: Optional[Callable],
                        complete_callback: Optional[Callable]) -> None:
        """
        從DMG文件安裝更新 (macOS)
        """
        try:
            # 僅適用於macOS
            if platform.system().lower() != 'darwin':
                if complete_callback:
                    complete_callback(False, "DMG安裝僅支持macOS系統")
                return

            # 更新進度：30%
            if progress_callback:
                progress_callback(30, "掛載DMG映像...")

            # 掛載DMG
            mount_process = subprocess.run(['hdiutil', 'attach', dmg_path], capture_output=True, text=True)
            if mount_process.returncode != 0:
                raise Exception(f"無法掛載DMG: {mount_process.stderr}")

            # 解析掛載點
            mount_point = None
            for line in mount_process.stdout.split('\n'):
                if '/Volumes/' in line:
                    mount_point = line.split('/Volumes/')[1].strip()
                    break

            if not mount_point:
                raise Exception("無法確定DMG掛載點")

            full_mount_path = f"/Volumes/{mount_point}"

            # 更新進度：60%
            if progress_callback:
                progress_callback(60, "安裝應用程式...")

            # 拷貝應用程式
            app_name = None
            for item in os.listdir(full_mount_path):
                if item.endswith('.app'):
                    app_name = item
                    break

            if not app_name:
                raise Exception("DMG中未找到應用程式")

            source_app = os.path.join(full_mount_path, app_name)
            dest_app = f"/Applications/{app_name}"

            # 複製應用程式
            shutil.rmtree(dest_app, ignore_errors=True)
            shutil.copytree(source_app, dest_app)

            # 更新進度：90%
            if progress_callback:
                progress_callback(90, "清理...")

            # 卸載DMG
            subprocess.run(['hdiutil', 'detach', full_mount_path], capture_output=True)

            # 更新進度：100%
            if progress_callback:
                progress_callback(100, "更新完成")

            # 完成回調
            if complete_callback:
                complete_callback(True, "")

        except Exception as e:
            self.logger.error(f"從DMG安裝更新時出錯: {e}")
            if complete_callback:
                complete_callback(False, f"從DMG安裝更新時出錯: {str(e)}")

    def _install_from_tarball(self, tarball_path: str, extract_dir: str,
                            progress_callback: Optional[Callable],
                            complete_callback: Optional[Callable]) -> None:
        """
        從tarball文件安裝更新 (Linux)
        """
        try:
            import tarfile

            # 更新進度：20%
            if progress_callback:
                progress_callback(20, "解壓縮更新文件...")

            # 解壓文件
            with tarfile.open(tarball_path) as tar:
                tar.extractall(path=extract_dir)

            # 與_install_from_zip類似的其餘步驟
            # 更新進度：40%
            if progress_callback:
                progress_callback(40, "備份當前版本...")

            # 備份當前版本
            self._backup_current_version()

            # 更新進度：60%
            if progress_callback:
                progress_callback(60, "安裝新版本...")

            # 安裝新版本
            self._replace_with_new_version(extract_dir)

            # 更新進度：80%
            if progress_callback:
                progress_callback(80, "更新版本信息...")

            # 更新版本號
            self._update_version_info()

            # 更新進度：100%
            if progress_callback:
                progress_callback(100, "更新完成")

            # 完成回調
            if complete_callback:
                complete_callback(True, "")

        except Exception as e:
            self.logger.error(f"從tarball安裝更新時出錯: {e}")

            # 如果有錯誤，嘗試恢復備份
            try:
                self._restore_from_backup()
                error_msg = f"更新失敗並已恢復原版本: {str(e)}"
            except Exception as restore_error:
                error_msg = f"更新失敗且無法恢復原版本: {str(e)}, 恢復錯誤: {str(restore_error)}"

            if complete_callback:
                complete_callback(False, error_msg)

    def _backup_current_version(self) -> None:
        """
        備份當前版本
        """
        # 確保備份目錄存在
        if not os.path.exists(self.backup_path):
            os.makedirs(self.backup_path)

        # 清理舊備份
        for item in os.listdir(self.backup_path):
            item_path = os.path.join(self.backup_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

        # 創建帶時間戳的新備份目錄
        timestamp = time.strftime("%Y%m%d%H%M%S")
        backup_dir = os.path.join(self.backup_path, f"backup_{timestamp}")
        os.makedirs(backup_dir)

        # 複製當前文件到備份目錄（排除某些不需要備份的目錄和文件）
        exclude_dirs = ['__pycache__', 'backup', 'temp', 'logs', '.git']

        for item in os.listdir(self.app_path):
            # 跳過排除的目錄
            if item in exclude_dirs:
                continue

            src_path = os.path.join(self.app_path, item)
            dst_path = os.path.join(backup_dir, item)

            try:
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
            except Exception as e:
                self.logger.warning(f"備份時跳過 {src_path}: {e}")

        # 保存版本信息以便恢復
        version_info = {
            'version': self.current_version,
            'backup_time': timestamp,
            'backup_path': backup_dir
        }

        with open(os.path.join(backup_dir, 'backup_info.json'), 'w', encoding='utf-8') as f:
            json.dump(version_info, f, ensure_ascii=False, indent=2)

        self.logger.info(f"已備份當前版本到 {backup_dir}")

    def _replace_with_new_version(self, extract_dir: str) -> None:
        """
        用新版本替換當前版本
        :param extract_dir: 解壓縮的新版本路徑
        """
        # 查找目錄中的主要內容
        # 有時解壓後會有一個嵌套目錄
        content_dir = extract_dir
        dir_contents = os.listdir(extract_dir)

        # 如果只有一個目錄，可能是包含實際內容的根目錄
        if len(dir_contents) == 1 and os.path.isdir(os.path.join(extract_dir, dir_contents[0])):
            content_dir = os.path.join(extract_dir, dir_contents[0])

        # 複製新文件到目標路徑（排除某些目錄）
        exclude_dirs = ['__pycache__', 'backup', 'temp', 'logs', '.git', 'projects']

        for item in os.listdir(content_dir):
            # 跳過排除的目錄
            if item in exclude_dirs:
                continue

            src_path = os.path.join(content_dir, item)
            dst_path = os.path.join(self.app_path, item)

            try:
                # 如果目標存在，先移除
                if os.path.exists(dst_path):
                    if os.path.isdir(dst_path):
                        shutil.rmtree(dst_path)
                    else:
                        os.remove(dst_path)

                # 複製新文件
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)

            except Exception as e:
                self.logger.error(f"替換文件時出錯 {src_path} -> {dst_path}: {e}")
                raise

        self.logger.info("已用新版本替換當前文件")

    def _restore_from_backup(self) -> None:
        """
        從備份恢復
        """
        if not os.path.exists(self.backup_path):
            raise Exception("備份目錄不存在")

        # 查找最新的備份
        backup_dirs = [d for d in os.listdir(self.backup_path)
                     if os.path.isdir(os.path.join(self.backup_path, d)) and d.startswith("backup_")]

        if not backup_dirs:
            raise Exception("沒有找到可用的備份")

        # 按名稱排序（由於使用時間戳，最新的會排在最後）
        backup_dirs.sort()
        latest_backup = os.path.join(self.backup_path, backup_dirs[-1])

        # 執行恢復
        self._replace_with_new_version(latest_backup)

        # 恢復版本信息
        backup_info_path = os.path.join(latest_backup, 'backup_info.json')
        if os.path.exists(backup_info_path):
            try:
                with open(backup_info_path, 'r', encoding='utf-8') as f:
                    backup_info = json.load(f)

                # 更新版本設置
                self.current_version = backup_info.get('version', self.current_version)
                self.update_settings['current_version'] = self.current_version
                self.config_manager.set_update_config(self.update_settings)

                # 更新VERSION文件
                with open(os.path.join(self.app_path, "VERSION"), 'w', encoding='utf-8') as f:
                    f.write(self.current_version)

            except Exception as e:
                self.logger.warning(f"恢復版本信息時出錯: {e}")

        self.logger.info(f"已從備份 {latest_backup} 恢復應用程序")

    def _update_version_info(self) -> None:
        """
        更新版本信息
        """
        if not self.latest_version:
            return

        # 更新記憶的當前版本
        self.current_version = self.latest_version

        # 更新配置中的版本
        self.update_settings['current_version'] = self.current_version
        self.config_manager.set_update_config(self.update_settings)

        # 更新VERSION文件
        version_file = os.path.join(self.app_path, "VERSION")
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(self.current_version)

        self.logger.info(f"已更新版本信息到 {self.current_version}")

    def cancel_update(self) -> bool:
        """
        取消正在進行的更新
        :return: 是否成功取消
        """
        if not self.update_in_progress:
            return True

        # 目前無法真正取消正在進行的下載/安裝，但可以設置標誌
        self.update_in_progress = False

        # 如果線程還在運行，等待它結束
        if self.background_thread and self.background_thread.is_alive():
            self.background_thread.join(timeout=1.0)

        return True

    def schedule_update_check(self, interval_hours: int = 24,
                           callback: Optional[Callable] = None) -> None:
        """
        排程定期檢查更新
        :param interval_hours: 檢查間隔（小時）
        :param callback: 當有更新時的回調函數
        """
        def check_update_job():
            while True:
                # 檢查更新
                has_update = self.check_for_updates()

                # 如果有更新且回調函數存在，調用回調
                if has_update and callback:
                    callback(self.update_available, self.latest_version, self.release_notes)

                # 等待指定時間
                time.sleep(interval_hours * 3600)

        # 啟動後台線程進行定期檢查
        thread = threading.Thread(target=check_update_job)
        thread.daemon = True
        thread.start()

    def restart_application(self) -> None:
        """
        重啟應用程序以應用更新
        """
        try:
            python = sys.executable
            script_path = sys.argv[0]

            # 使用subprocess啟動新進程
            subprocess.Popen([python, script_path], close_fds=True, start_new_session=True)

            # 終止當前程序
            sys.exit(0)
        except Exception as e:
            self.logger.error(f"重啟應用程序時出錯: {e}")
            raise