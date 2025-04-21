"""文件下載器模組，負責下載更新文件和處理下載進度"""

import logging
import os
import threading
import time
from typing import Optional, Callable
from urllib.parse import urlparse

import requests


class FileDownloader:
    """文件下載器類，提供下載功能和進度報告"""

    def __init__(self):
        """初始化文件下載器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.active_downloads = {}  # 記錄活動的下載 {download_id: download_info}
        self.cancel_flags = {}  # 記錄取消標記 {download_id: is_cancelled}

    def download_file(self, url: str, destination_path: str,
                    progress_callback: Optional[Callable] = None,
                    complete_callback: Optional[Callable] = None) -> str:
        """
        開始下載文件（異步）
        :param url: 下載URL
        :param destination_path: 目標文件路徑
        :param progress_callback: 進度回調，接收(download_id, progress_percent, downloaded_size, total_size)
        :param complete_callback: 完成回調，接收(download_id, success, error_message, file_path)
        :return: 下載ID，可用於取消下載
        """
        # 生成唯一下載ID
        download_id = f"download_{int(time.time() * 1000)}"

        # 確保目標目錄存在
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        # 記錄下載信息
        self.active_downloads[download_id] = {
            'url': url,
            'path': destination_path,
            'start_time': time.time(),
            'progress': 0,
            'downloaded': 0,
            'total_size': 0,
            'status': 'starting'
        }

        # 設置取消標誌
        self.cancel_flags[download_id] = False

        # 啟動下載線程
        thread = threading.Thread(
            target=self._download_thread,
            args=(download_id, url, destination_path, progress_callback, complete_callback)
        )
        thread.daemon = True
        thread.start()

        return download_id

    def _download_thread(self, download_id: str, url: str, destination_path: str,
                       progress_callback: Optional[Callable],
                       complete_callback: Optional[Callable]) -> None:
        """
        下載線程
        :param download_id: 下載ID
        :param url: 下載URL
        :param destination_path: 目標文件路徑
        :param progress_callback: 進度回調
        :param complete_callback: 完成回調
        """
        temp_file = f"{destination_path}.download"
        success = False
        error_message = ""

        try:
            self.logger.info(f"開始下載 {url} 到 {destination_path}")
            self.active_downloads[download_id]['status'] = 'downloading'

            # 使用流式下載以報告進度
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()

            # 獲取文件大小
            total_size = int(response.headers.get('content-length', 0))
            self.active_downloads[download_id]['total_size'] = total_size

            # 設置下載塊大小
            block_size = 8192  # 8KB
            downloaded = 0

            # 初始進度回調
            if progress_callback:
                progress_callback(download_id, 0, downloaded, total_size)

            # 下載文件
            with open(temp_file, 'wb') as f:
                start_time = time.time()
                last_progress_update = start_time

                for chunk in response.iter_content(chunk_size=block_size):
                    # 檢查取消標誌
                    if self.cancel_flags.get(download_id, False):
                        raise Exception("下載被取消")

                    if chunk:  # 過濾空塊
                        f.write(chunk)
                        downloaded += len(chunk)

                        # 更新下載信息
                        self.active_downloads[download_id]['downloaded'] = downloaded

                        # 計算進度
                        progress = 0
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            self.active_downloads[download_id]['progress'] = progress

                        # 調用進度回調（限制更新頻率以避免 UI 過載）
                        current_time = time.time()
                        if progress_callback and (current_time - last_progress_update) >= 0.1:  # 100ms間隔
                            progress_callback(download_id, progress, downloaded, total_size)
                            last_progress_update = current_time

            # 重命名臨時文件為目標文件
            if os.path.exists(destination_path):
                os.remove(destination_path)
            os.rename(temp_file, destination_path)

            # 更新下載狀態
            self.active_downloads[download_id]['status'] = 'completed'
            self.active_downloads[download_id]['progress'] = 100

            # 記錄下載完成
            elapsed_time = time.time() - start_time
            download_speed = downloaded / elapsed_time if elapsed_time > 0 else 0
            self.logger.info(f"下載完成 {url} -> {destination_path}, "
                           f"大小: {self._format_size(downloaded)}, "
                           f"時間: {elapsed_time:.1f}秒, "
                           f"速度: {self._format_size(download_speed)}/s")

            success = True

        except Exception as e:
            self.logger.error(f"下載 {url} 時出錯: {e}")

            # 更新下載狀態
            self.active_downloads[download_id]['status'] = 'failed'

            # 刪除臨時文件
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

            error_message = str(e)
            success = False

        finally:
            # 最後的進度回調
            if progress_callback and success:
                progress_callback(download_id, 100, downloaded, total_size)

            # 完成回調
            if complete_callback:
                complete_callback(download_id, success, error_message, destination_path if success else "")

            # 清理
            if download_id in self.cancel_flags:
                del self.cancel_flags[download_id]

    def cancel_download(self, download_id: str) -> bool:
        """
        取消下載
        :param download_id: 下載ID
        :return: 是否成功取消
        """
        if download_id not in self.active_downloads:
            return False

        # 設置取消標誌
        self.cancel_flags[download_id] = True
        self.active_downloads[download_id]['status'] = 'cancelling'

        self.logger.info(f"已取消下載 {download_id}")
        return True

    def get_download_status(self, download_id: str) -> dict:
        """
        獲取下載狀態
        :param download_id: 下載ID
        :return: 下載狀態字典，如果下載ID不存在則返回空字典
        """
        return self.active_downloads.get(download_id, {})

    def get_all_downloads(self) -> dict:
        """
        獲取所有下載的狀態
        :return: 所有下載狀態的字典，格式為 {download_id: download_info}
        """
        return self.active_downloads

    def cleanup_completed_downloads(self) -> int:
        """
        清理已完成的下載記錄
        :return: 清理的記錄數量
        """
        to_remove = []

        for download_id, download_info in self.active_downloads.items():
            if download_info['status'] in ['completed', 'failed']:
                to_remove.append(download_id)

        for download_id in to_remove:
            del self.active_downloads[download_id]

        return len(to_remove)

    def _format_size(self, size_bytes: int) -> str:
        """
        格式化文件大小
        :param size_bytes: 位元組數
        :return: 格式化的大小字符串
        """
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f}MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f}GB"

    def calculate_eta(self, download_id: str) -> str:
        """
        計算預計剩餘時間
        :param download_id: 下載ID
        :return: 預計剩餘時間字符串
        """
        if download_id not in self.active_downloads:
            return "未知"

        download_info = self.active_downloads[download_id]
        downloaded = download_info['downloaded']
        total_size = download_info['total_size']

        if downloaded == 0 or total_size == 0:
            return "計算中..."

        elapsed_time = time.time() - download_info['start_time']
        if elapsed_time <= 0:
            return "計算中..."

        # 計算下載速度 (bytes/second)
        speed = downloaded / elapsed_time

        if speed <= 0:
            return "未知"

        # 計算剩餘時間 (seconds)
        remaining_bytes = total_size - downloaded
        eta_seconds = remaining_bytes / speed

        # 格式化剩餘時間
        if eta_seconds < 60:
            return f"{eta_seconds:.0f}秒"
        elif eta_seconds < 3600:
            return f"{eta_seconds/60:.1f}分鐘"
        else:
            return f"{eta_seconds/3600:.1f}小時"