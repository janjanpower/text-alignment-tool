"""更新對話框模組，提供檢查和下載更新的圖形界面"""

import logging
import threading
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

from gui.base_dialog import BaseDialog
from services.update.update_manager import UpdateManager
from gui.custom_messagebox import show_info, show_warning, show_error


class UpdateCheckDialog(BaseDialog):
    """檢查更新對話框，顯示檢查更新進度和結果"""

    def __init__(self, parent=None, update_manager: Optional[UpdateManager] = None):
        """
        初始化檢查更新對話框
        :param parent: 父視窗
        :param update_manager: 更新管理器實例
        """
        self.result = None
        self.update_manager = update_manager or UpdateManager()

        # 更新狀態
        self.checking = False
        self.has_update = False
        self.latest_version = ""
        self.current_version = self.update_manager.current_version
        self.release_notes = ""

        # 先調用父類初始化
        super().__init__(parent, title="檢查更新", width=400, height=150)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()

        # 在調用 super().create_dialog() 之後初始化按鈕管理器
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self.window)

        self.create_content()

        # 立即開始檢查更新
        self.start_update_check()

    def create_content(self):
        """創建對話框內容"""
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 版本信息
        version_frame = ttk.Frame(content_frame)
        version_frame.pack(fill=tk.X, pady=(0, 10))

        # 當前版本標籤
        ttk.Label(
            version_frame,
            text=f"當前版本：{self.current_version}",
            anchor=tk.W
        ).pack(fill=tk.X, pady=2)

        # 最新版本標籤
        self.latest_version_label = ttk.Label(
            version_frame,
            text="最新版本：檢查中...",
            anchor=tk.W
        )
        self.latest_version_label.pack(fill=tk.X, pady=2)

        # 狀態框架
        status_frame = ttk.Frame(content_frame)
        status_frame.pack(fill=tk.X, pady=5)

        # 狀態標籤
        self.status_label = ttk.Label(
            status_frame,
            text="正在檢查更新，請稍候...",
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 進度條
        self.progress = ttk.Progressbar(
            status_frame,
            orient=tk.HORIZONTAL,
            length=100,
            mode='indeterminate'
        )
        self.progress.pack(fill=tk.X, pady=10)
        self.progress.start(10)  # 開始進度條動畫

        # 更新說明框架
        notes_frame = ttk.LabelFrame(content_frame, text="更新說明")
        notes_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 更新說明文本
        self.notes_text = tk.Text(
            notes_frame,
            wrap=tk.WORD,
            height=4,
            width=40,
            state=tk.DISABLED,
            bg="#f0f0f0",
            font=("Arial", 9)
        )
        self.notes_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加滾動條
        notes_scroll = ttk.Scrollbar(self.notes_text, orient=tk.VERTICAL, command=self.notes_text.yview)
        notes_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.notes_text.configure(yscrollcommand=notes_scroll.set)

        # 按鈕區域
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        # 使用按鈕管理器創建按鈕
        button_configs = [
            {
                'id': 'update',
                'normal_icon': 'update_icon.png',
                'hover_icon': 'update_hover.png',
                'command': self.start_update,
                'tooltip': '下載並安裝更新',
                'side': tk.RIGHT,
                'padx': 5
            },
            {
                'id': 'cancel',
                'normal_icon': 'cancel_icon.png',
                'hover_icon': 'cancel_hover.png',
                'command': self.cancel,
                'tooltip': '關閉',
                'side': tk.RIGHT,
                'padx': 5
            }
        ]

        # 創建按鈕
        self.dialog_buttons = self.button_manager.create_button_set(button_frame, button_configs)

        # 初始時禁用更新按鈕
        if 'update' in self.dialog_buttons:
            self.dialog_buttons['update'].configure(state=tk.DISABLED)

        # 綁定事件
        self.window.bind('<Escape>', lambda e: self.cancel())

    def start_update_check(self):
        """開始檢查更新"""
        if self.checking:
            return

        self.checking = True

        # 啟動檢查線程
        thread = threading.Thread(target=self._check_update_thread)
        thread.daemon = True
        thread.start()

    def _check_update_thread(self):
        """檢查更新線程"""
        try:
            # 調用更新管理器檢查更新
            self.update_manager.check_for_updates(callback=self._update_check_callback)
        except Exception as e:
            # 在主線程中處理錯誤
            self.window.after(0, lambda: self._show_check_error(str(e)))

    def _update_check_callback(self, has_update, latest_version, release_notes):
        """
        檢查更新回調
        :param has_update: 是否有更新
        :param latest_version: 最新版本
        :param release_notes: 發行說明
        """
        # 在主線程中更新UI
        self.window.after(0, lambda: self._update_ui_after_check(has_update, latest_version, release_notes))

    def _update_ui_after_check(self, has_update, latest_version, release_notes):
        """更新UI顯示檢查結果"""
        # 停止進度條動畫
        self.progress.stop()
        self.progress.pack_forget()

        # 更新檢查狀態
        self.checking = False
        self.has_update = has_update
        self.latest_version = latest_version
        self.release_notes = release_notes

        # 更新版本標籤
        if latest_version:
            self.latest_version_label.config(text=f"最新版本：{latest_version}")
        else:
            self.latest_version_label.config(text="最新版本：未知")

        # 更新狀態標籤
        if has_update:
            self.status_label.config(text=f"發現新版本！建議更新到 v{latest_version}")
        else:
            self.status_label.config(text="已是最新版本")

        # 更新發行說明
        if release_notes:
            self.notes_text.configure(state=tk.NORMAL)
            self.notes_text.delete(1.0, tk.END)
            self.notes_text.insert(tk.END, release_notes)
            self.notes_text.configure(state=tk.DISABLED)

        # 更新按鈕狀態
        if has_update and 'update' in self.dialog_buttons:
            self.dialog_buttons['update'].configure(state=tk.NORMAL)
        else:
            # 如果沒有更新，則只顯示關閉按鈕
            if 'update' in self.dialog_buttons:
                self.dialog_buttons['update'].pack_forget()

    def _show_check_error(self, error_message):
        """顯示檢查更新錯誤"""
        # 停止進度條動畫
        self.progress.stop()

        # 更新狀態
        self.checking = False
        self.status_label.config(text=f"檢查更新失敗: {error_message}")

        # 禁用更新按鈕
        if 'update' in self.dialog_buttons:
            self.dialog_buttons['update'].configure(state=tk.DISABLED)

    def start_update(self):
        """開始下載更新"""
        self.result = True
        self.close()

        # 顯示下載更新對話框
        download_dialog = UpdateDownloadDialog(
            self.window.master,  # 使用最上層視窗作為父視窗
            self.update_manager
        )
        download_dialog.run()

    def cancel(self, event=None):
        """取消操作"""
        # 如果還在檢查，取消檢查
        if self.checking:
            # 目前無法取消正在進行的檢查，只能關閉對話框
            pass

        self.result = False
        self.close()

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result, self.has_update, self.latest_version


class UpdateDownloadDialog(BaseDialog):
    """下載更新對話框，顯示下載進度和安裝更新"""

    def __init__(self, parent=None, update_manager: Optional[UpdateManager] = None):
        """
        初始化下載更新對話框
        :param parent: 父視窗
        :param update_manager: 更新管理器實例
        """
        self.result = None
        self.update_manager = update_manager or UpdateManager()

        # 下載狀態
        self.downloading = False
        self.installing = False
        self.download_complete = False
        self.download_path = ""

        # 先調用父類初始化
        super().__init__(parent, title="下載更新", width=400, height=200)

    def create_dialog(self) -> None:
        """創建對話框視窗"""
        super().create_dialog()

        # 在調用 super().create_dialog() 之後初始化按鈕管理器
        from gui.components.button_manager import ButtonManager
        self.button_manager = ButtonManager(self.window)

        self.create_content()

        # 立即開始下載更新
        self.start_download()

    def create_content(self):
        """創建對話框內容"""
        content_frame = ttk.Frame(self.main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 頂部信息
        info_frame = ttk.Frame(content_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        # 版本信息標籤
        self.version_label = ttk.Label(
            info_frame,
            text=f"正在下載 {self.update_manager.current_version} → {self.update_manager.latest_version}",
            font=("Arial", 10, "bold"),
            anchor=tk.W
        )
        self.version_label.pack(fill=tk.X, pady=2)

        # 狀態標籤
        self.status_label = ttk.Label(
            info_frame,
            text="準備下載更新...",
            anchor=tk.W
        )
        self.status_label.pack(fill=tk.X, pady=2)

        # 進度框架
        progress_frame = ttk.Frame(content_frame)
        progress_frame.pack(fill=tk.X, pady=10)

        # 進度標籤
        self.progress_label = ttk.Label(
            progress_frame,
            text="0%",
            width=6,
            anchor=tk.E
        )
        self.progress_label.pack(side=tk.LEFT, padx=(0, 5))

        # 進度條
        self.progress = ttk.Progressbar(
            progress_frame,
            orient=tk.HORIZONTAL,
            length=100,
            mode='determinate'
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 大小標籤
        self.size_label = ttk.Label(
            progress_frame,
            text="0 KB / 0 KB",
            width=15,
            anchor=tk.W
        )
        self.size_label.pack(side=tk.LEFT, padx=(5, 0))

        # 詳細信息框架
        details_frame = ttk.LabelFrame(content_frame, text="詳細信息")
        details_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # 詳細信息文本
        self.details_text = tk.Text(
            details_frame,
            wrap=tk.WORD,
            height=4,
            width=40,
            state=tk.NORMAL,
            bg="#f0f0f0",
            font=("Arial", 9)
        )
        self.details_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 添加滾動條
        details_scroll = ttk.Scrollbar(self.details_text, orient=tk.VERTICAL, command=self.details_text.yview)
        details_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.details_text.configure(yscrollcommand=details_scroll.set)

        # 在詳細信息文本框中顯示初始信息
        self.add_log("準備下載更新...")

        # 按鈕區域
        button_frame = ttk.Frame(content_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        # 使用按鈕管理器創建按鈕
        button_configs = [
            {
                'id': 'install',
                'normal_icon': 'ok_icon.png',
                'hover_icon': 'ok_hover.png',
                'command': self.install_update,
                'tooltip': '安裝更新',
                'side': tk.RIGHT,
                'padx': 5
            },
            {
                'id': 'cancel',
                'normal_icon': 'cancel_icon.png',
                'hover_icon': 'cancel_hover.png',
                'command': self.cancel,
                'tooltip': '取消',
                'side': tk.RIGHT,
                'padx': 5
            }
        ]

        # 創建按鈕
        self.dialog_buttons = self.button_manager.create_button_set(button_frame, button_configs)

        # 初始時禁用安裝按鈕
        if 'install' in self.dialog_buttons:
            self.dialog_buttons['install'].configure(state=tk.DISABLED)

        # 綁定事件
        self.window.bind('<Escape>', lambda e: self.cancel())

    def start_download(self):
        """開始下載更新"""
        if self.downloading or not self.update_manager.update_available:
            return

        self.downloading = True

        # 添加日誌
        self.add_log(f"開始從 {self.update_manager.download_url} 下載更新")

        # 開始下載
        self.update_manager.download_update(
            progress_callback=self._download_progress_callback,
            complete_callback=self._download_complete_callback
        )

    def _download_progress_callback(self, progress, downloaded, total):
        """
        下載進度回調
        :param progress: 進度百分比
        :param downloaded: 已下載大小
        :param total: 總大小
        """
        # 在主線程中更新UI
        self.window.after(0, lambda: self._update_progress_ui(progress, downloaded, total))

    def _update_progress_ui(self, progress, downloaded, total):
        """更新UI顯示下載進度"""
        # 更新進度條
        self.progress['value'] = progress

        # 更新進度標籤
        self.progress_label.config(text=f"{progress:.1f}%")

        # 更新大小標籤
        downloaded_str = self._format_size(downloaded)
        total_str = self._format_size(total)
        self.size_label.config(text=f"{downloaded_str} / {total_str}")

        # 更新狀態標籤
        self.status_label.config(text=f"正在下載更新... ({progress:.1f}%)")

        # 每10%更新一次日誌
        if int(progress) % 10 == 0 and int(progress) > 0:
            progress_int = int(progress)
            if not hasattr(self, '_last_logged_progress') or self._last_logged_progress != progress_int:
                self.add_log(f"下載進度: {progress_int}% ({downloaded_str} / {total_str})")
                self._last_logged_progress = progress_int

    def _download_complete_callback(self, success, error_message, download_path):
        """
        下載完成回調
        :param success: 是否成功
        :param error_message: 錯誤信息
        :param download_path: 下載文件路徑
        """
        # 在主線程中更新UI
        self.window.after(0, lambda: self._update_ui_after_download(success, error_message, download_path))

    def _update_ui_after_download(self, success, error_message, download_path):
        """更新UI顯示下載結果"""
        # 更新下載狀態
        self.downloading = False
        self.download_complete = success
        self.download_path = download_path

        if success:
            # 更新UI
            self.progress['value'] = 100
            self.progress_label.config(text="100%")
            self.status_label.config(text="下載完成，準備安裝")

            # 添加日誌
            self.add_log(f"下載完成: {download_path}")
            self.add_log("請點擊「安裝更新」按鈕開始安裝")

            # 啟用安裝按鈕
            if 'install' in self.dialog_buttons:
                self.dialog_buttons['install'].configure(state=tk.NORMAL)

        else:
            # 更新UI
            self.status_label.config(text=f"下載失敗: {error_message}")

            # 添加日誌
            self.add_log(f"下載失敗: {error_message}")

            # 顯示錯誤提示
            show_error("下載失敗", f"無法下載更新：{error_message}", self.window)

    def install_update(self):
        """安裝更新"""
        if self.installing or not self.download_complete or not self.download_path:
            return

        self.installing = True

        # 更新UI
        self.status_label.config(text="正在安裝更新...")
        self.progress['value'] = 0

        # 禁用按鈕
        for button in self.dialog_buttons.values():
            button.configure(state=tk.DISABLED)

        # 添加日誌
        self.add_log("開始安裝更新...")

        # 啟動安裝線程
        thread = threading.Thread(target=self._install_update_thread)
        thread.daemon = True
        thread.start()

    def _install_update_thread(self):
        """安裝更新線程"""
        try:
            # 調用更新管理器安裝更新
            self.update_manager.install_update(
                self.download_path,
                progress_callback=self._install_progress_callback,
                complete_callback=self._install_complete_callback
            )
        except Exception as e:
            # 在主線程中處理錯誤
            self.window.after(0, lambda: self._show_install_error(str(e)))

    def _install_progress_callback(self, progress, step_description):
        """
        安裝進度回調
        :param progress: 進度百分比
        :param step_description: 當前步驟描述
        """
        # 在主線程中更新UI
        self.window.after(0, lambda: self._update_install_progress_ui(progress, step_description))

    def _update_install_progress_ui(self, progress, step_description):
        """更新UI顯示安裝進度"""
        # 更新進度條
        self.progress['value'] = progress

        # 更新進度標籤
        self.progress_label.config(text=f"{progress:.1f}%")

        # 更新狀態標籤
        self.status_label.config(text=f"正在安裝更新: {step_description}")

        # 添加日誌
        self.add_log(f"安裝進度: {progress:.1f}% - {step_description}")

    def _install_complete_callback(self, success, error_message):
        """
        安裝完成回調
        :param success: 是否成功
        :param error_message: 錯誤信息
        """
        # 在主線程中更新UI
        self.window.after(0, lambda: self._update_ui_after_install(success, error_message))

    def _update_ui_after_install(self, success, error_message):
        """更新UI顯示安裝結果"""
        # 更新安裝狀態
        self.installing = False

        if success:
            # 更新UI
            self.progress['value'] = 100
            self.progress_label.config(text="100%")
            self.status_label.config(text="安裝完成，即將重啟應用程式")

            # 添加日誌
            self.add_log("安裝完成！")
            self.add_log("應用程式將在5秒後重啟...")

            # 顯示成功訊息
            show_info("安裝成功", "更新已成功安裝，應用程式即將重啟", self.window)

            # 設置結果
            self.result = True

            # 5秒後重啟應用程式
            self.window.after(5000, self._restart_application)

        else:
            # 更新UI
            self.status_label.config(text=f"安裝失敗: {error_message}")

            # 添加日誌
            self.add_log(f"安裝失敗: {error_message}")

            # 顯示錯誤提示
            show_error("安裝失敗", f"安裝更新時出錯：{error_message}", self.window)

            # 啟用取消按鈕
            if 'cancel' in self.dialog_buttons:
                self.dialog_buttons['cancel'].configure(state=tk.NORMAL)

    def _restart_application(self):
        """重啟應用程式"""
        try:
            # 關閉對話框
            self.close()

            # 重啟應用程式
            self.update_manager.restart_application()
        except Exception as e:
            logging.error(f"重啟應用程式時出錯: {e}")
            show_error("重啟失敗", f"重啟應用程式時出錯：{str(e)}", self.window)

    def _show_install_error(self, error_message):
        """顯示安裝錯誤"""
        # 更新狀態
        self.installing = False
        self.status_label.config(text=f"安裝失敗: {error_message}")

        # 添加日誌
        self.add_log(f"安裝失敗: {error_message}")

        # 啟用取消按鈕
        if 'cancel' in self.dialog_buttons:
            self.dialog_buttons['cancel'].configure(state=tk.NORMAL)

        # 顯示錯誤訊息
        show_error("安裝失敗", f"安裝更新時出錯：{error_message}", self.window)

    def cancel(self, event=None):
        """取消操作"""
        # 如果正在下載，取消下載
        if self.downloading:
            if self.update_manager.cancel_update():
                self.add_log("已取消下載")

        self.result = False
        self.close()

    def add_log(self, message):
        """添加日誌到詳細信息文本框"""
        if not hasattr(self, 'details_text') or not self.details_text:
            return

        self.details_text.configure(state=tk.NORMAL)
        if self.details_text.index('end-1c') != '1.0':
            self.details_text.insert(tk.END, '\n')
        self.details_text.insert(tk.END, message)
        self.details_text.see(tk.END)
        self.details_text.configure(state=tk.NORMAL)

    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f}MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f}GB"

    def run(self):
        """運行對話框並返回結果"""
        self.window.wait_window()
        return self.result