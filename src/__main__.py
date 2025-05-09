"""文本對齊工具程式入口點"""

import logging
import os
import sys
import tkinter as tk
import threading
import time

from database.db_manager import DatabaseManager
from gui.alignment_gui import AlignmentGUI
from gui.correction_tool import CorrectionTool
from gui.login_window import LoginWindow
from gui.update_dialog import UpdateCheckDialog
from services.config_manager import ConfigManager
from services.update.update_manager import UpdateManager
from utils.logging_utils import setup_logging


# 添加必要的路徑到 Python 模組搜尋路徑
def setup_import_paths():
    """設置導入路徑，確保所有模組都能被正確找到"""
    current_file = os.path.abspath(__file__)
    current_dir = os.path.dirname(current_file)  # src 目錄
    project_root = os.path.dirname(current_dir)  # 專案根目錄

    # 添加路徑
    paths_to_add = [
        project_root,        # 專案根目錄
        current_dir,         # src 目錄
    ]

    # 將路徑添加到 sys.path
    for path in paths_to_add:
        if path not in sys.path:
            sys.path.insert(0, path)

    # 輸出當前的 Python 路徑，用於調試
    logging.debug(f"Python 搜尋路徑: {sys.path}")
    print(f"Python 搜尋路徑: {sys.path}")

# 設置導入路徑
setup_import_paths()

# 獲取當前目錄 (src 目錄)

# 設置日誌記錄
logger = setup_logging()
logger.info("應用程式啟動")

class ApplicationManager:
    """應用程式管理器"""

    def init(self):
        """初始化應用程式管理器"""
        logger.info("初始化應用程式管理器")
        self.config = self.setup_environment()

        # 初始化更新管理器
        self.update_manager = UpdateManager(self.config)

        # 初始化資料庫
        self.init_database()

    @staticmethod
    def setup_environment():
        """設置環境"""
        logger.info("設置環境")
        return ConfigManager()

    def init_database(self):
        """初始化資料庫"""
        logger.info("初始化資料庫")
        try:
            db_manager = DatabaseManager()
            db_manager.create_tables()
            logger.info("資料庫初始化成功")
        except Exception as e:
            logger.error(f"資料庫初始化失敗: {e}", exc_info=True)
            raise

    def check_for_updates(self):
        """檢查更新"""
        logger.info("檢查應用程式更新")

        # 從配置中獲取更新設置
        update_config = self.config.get_update_config()
        auto_check = update_config.get('auto_check', True)

        if not auto_check:
            logger.info("自動檢查更新已禁用")
            return False

        try:
            # 檢查更新
            has_update = self.update_manager.check_for_updates()

            if has_update:
                logger.info(f"發現新版本: {self.update_manager.latest_version}")
                return True
            else:
                logger.info("已是最新版本")
                return False

        except Exception as e:
            logger.error(f"檢查更新時出錯: {e}")
            return False

    def show_update_dialog(self):
        """顯示更新對話框"""
        try:
            # 創建臨時根窗口以顯示更新對話框
            temp_root = tk.Tk()
            temp_root.withdraw()  # 隱藏臨時窗口

            # 創建並顯示更新檢查對話框
            dialog = UpdateCheckDialog(temp_root, self.update_manager)
            result, has_update, latest_version = dialog.run()

            # 銷毀臨時窗口
            temp_root.destroy()

            return result and has_update

        except Exception as e:
            logger.error(f"顯示更新對話框時出錯: {e}")
            return False

    def init_correction_tool(self, project_path: str) -> bool:
        """
        初始化並運行文字校正工具
        :param project_path: 專案路徑
        :return: 是否成功完成校正
        """
        root = tk.Tk()
        tool = CorrectionTool(master=root, project_path=project_path)
        root.mainloop()

        # 檢查是否存在校正文件
        csv_path = os.path.join(project_path, "corrections.csv")
        return os.path.exists(csv_path)

    def init_alignment_tool(self, project_path: str) -> None:
        """
        初始化並運行文本對齊工具
        :param project_path: 專案路徑
        """
        root = tk.Tk()
        app = AlignmentGUI(master=root)
        app.current_project_path = project_path
        app.database_file = os.path.join(project_path, "corrections.csv")

        # 檢查並載入 SRT 文件
        srt_files = [f for f in os.listdir(project_path) if f.endswith('.srt')]
        if srt_files:
            srt_path = os.path.join(project_path, srt_files[0])
            app.srt_file_path = srt_path
            app.load_srt(file_path=srt_path)

        app.run()

    def schedule_update_check(self):
        """排程定期檢查更新"""
        update_config = self.config.get_update_config()
        check_interval = update_config.get('check_interval', 24)  # 小時

        def check_updates_job():
            while True:
                time.sleep(check_interval * 3600)  # 轉換為秒
                logger.info(f"定時檢查更新，間隔: {check_interval}小時")

                # 檢查更新
                try:
                    if self.update_manager.check_for_updates():
                        logger.info("發現更新，將在下次啟動時提示")
                        # 記錄有更新可用，下次啟動時提示
                        update_config = self.config.get_update_config()
                        update_config['has_pending_update'] = True
                        self.config.set_section('update', update_config)
                except Exception as e:
                    logger.error(f"定時檢查更新時出錯: {e}")

        # 啟動後台線程
        thread = threading.Thread(target=check_updates_job)
        thread.daemon = True
        thread.start()
        logger.info("已啟動定時檢查更新線程")

    def run(self):
        """運行應用程式"""
        try:
            logger.info("啟動應用程式")

            # 檢查是否有待處理的更新
            update_config = self.config.get_update_config()
            has_pending_update = update_config.get('has_pending_update', False)

            # 如果有待處理的更新，顯示更新對話框
            if has_pending_update:
                logger.info("檢測到待處理的更新")
                if self.show_update_dialog():
                    # 用戶選擇更新，退出程序（更新對話框將處理更新安裝和重啟）
                    logger.info("用戶選擇安裝更新，程式將退出")
                    return
                else:
                    # 用戶選擇稍後更新，清除標記
                    update_config['has_pending_update'] = False
                    self.config.set_section('update', update_config)
            else:
                # 檢查更新
                if self.check_for_updates():
                    if self.show_update_dialog():
                        # 用戶選擇更新，退出程序
                        logger.info("用戶選擇安裝更新，程式將退出")
                        return

            # 啟動定時檢查更新
            self.schedule_update_check()

            # 運行登入視窗
            login_root = tk.Tk()
            login_window = LoginWindow(master=login_root)
            login_window.master.mainloop()

            # 如果登入失敗，程式將結束
            if not login_window.current_user:
                logger.info("使用者取消登入，程式結束")
                sys.exit(0)

        except Exception as e:
            logger.error(f"運行程式時出錯：{e}", exc_info=True)
            sys.exit(1)

def main():
    """主程序入口"""
    try:
        logger.info("啟動主程序")
        app = ApplicationManager()
        app.init()
        app.run()
    except Exception as e:
        logger.error(f"主程序執行錯誤: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()