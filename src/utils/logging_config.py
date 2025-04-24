# src/utils/logging_config.py

import logging
import logging.handlers
import os
from datetime import datetime

def setup_production_logging(log_dir="/var/log/text-alignment"):
    """設置生產環境日誌"""
    # 確保日誌目錄存在
    os.makedirs(log_dir, exist_ok=True)

    # 創建根日誌器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 移除現有處理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 添加控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # 添加文件處理器
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"app-{today}.log")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5, encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # 錯誤日誌
    error_log = os.path.join(log_dir, f"error-{today}.log")
    error_handler = logging.handlers.RotatingFileHandler(
        error_log, maxBytes=10485760, backupCount=5, encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    root_logger.addHandler(error_handler)

    return root_logger