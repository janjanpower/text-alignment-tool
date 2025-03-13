import opencc
import csv
import os
import logging
from typing import Dict

def simplify_to_traditional(simplified_text: str) -> str:
    """
    將簡體中文轉換為繁體中文
    :param simplified_text: 簡體中文文本
    :return: 繁體中文文本
    """
    converter = opencc.OpenCC('s2twp')
    return converter.convert(simplified_text)

def load_correction_database(database_file: str) -> Dict[str, str]:
    """
    加載校正數據庫
    :param database_file: 數據庫文件路徑
    :return: 校正對照表
    """
    logger = logging.getLogger(__name__)
    corrections = {}
    if os.path.exists(database_file):
        try:
            with open(database_file, 'r', encoding='utf-8') as file:
                reader = csv.reader(file)
                next(reader)  # 跳過標題行
                for row in reader:
                    if len(row) >= 2:
                        error, correction = row
                        corrections[error] = correction
        except Exception as e:
            logger.error(f"載入校正數據庫失敗: {e}")
    return corrections

def save_correction_database(corrections: Dict[str, str], database_file: str) -> None:
    """
    保存校正數據庫
    :param corrections: 校正對照表
    :param database_file: 數據庫文件路徑
    """
    logger = logging.getLogger(__name__)
    try:
        with open(database_file, 'w', encoding='utf-8-sig', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["錯誤字", "校正字"])
            for error, correction in corrections.items():
                writer.writerow([error, correction])
    except Exception as e:
        logger.error(f"保存校正數據庫失敗: {e}")

def correct_text(text: str, corrections: Dict[str, str]) -> str:
    """
    根據校正數據庫修正文本
    :param text: 原始文本
    :param corrections: 校正對照表
    :return: 校正後的文本
    """
    corrected_text = text
    for error, correction in corrections.items():
        corrected_text = corrected_text.replace(error, correction)
    return corrected_text