import os
import sys
import logging

def get_current_directory() -> str:
    """
    獲取當前執行目錄
    :return: 目錄路徑
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)

    # 獲取當前檔案的絕對路徑
    current_file = os.path.abspath(__file__)
    # 獲取 utils 目錄的路徑
    utils_dir = os.path.dirname(current_file)
    # 獲取 src 目錄的路徑
    src_dir = os.path.dirname(utils_dir)
    # 獲取專案根目錄的路徑
    root_dir = os.path.dirname(src_dir)

    return root_dir

def ensure_directories(base_dir=None) -> None:
    """
    確保必要的目錄結構存在
    :param base_dir: 基礎目錄，如果未指定則使用當前目錄
    """
    logger = logging.getLogger(__name__)

    if base_dir is None:
        base_dir = get_current_directory()

    directories = ['projects', 'logs', 'temp', 'assets']

    for directory in directories:
        dir_path = os.path.join(base_dir, directory)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            logger.info(f"創建目錄：{dir_path}")