"""文本段落切分服務，負責處理文本斷句的核心邏輯"""

import logging
import time
from typing import List, Dict, Any, Tuple, Optional

import pysrt
from utils.time_utils import parse_time, format_time, time_to_milliseconds


class SegmentationService:
    """文本段落切分服務類，提供文本斷句的核心邏輯"""

    def __init__(self):
        """初始化段落切分服務"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate_time_segments(self, lines: List[str], start_time: str, end_time: str) -> List[Tuple[str, str, str]]:
        """
        根據文本行生成對應的時間戳

        Args:
            lines: 文本行列表
            start_time: 起始時間
            end_time: 結束時間

        Returns:
            包含文本、開始時間、結束時間的列表
        """
        # 忽略空行
        valid_lines = [line for line in lines if line.strip()]
        if not valid_lines:
            return []

        # 解析時間
        start_time_obj = parse_time(start_time)
        end_time_obj = parse_time(end_time)
        total_duration = (end_time_obj.ordinal - start_time_obj.ordinal)

        # 計算總字符數（只考慮非空行）
        total_chars = sum(len(line.strip()) for line in valid_lines)

        # 至少要有一個字符
        if total_chars == 0:
            total_chars = 1

        # 記錄結果
        results = []
        current_time = start_time_obj

        for i, line in enumerate(valid_lines):
            line_text = line.strip()
            if not line_text:
                continue

            # 計算該行的時間比例
            if i == len(valid_lines) - 1:
                # 最後一行直接用到結束時間
                next_time = end_time_obj
            else:
                # 根據字符比例計算時間
                line_proportion = len(line_text) / total_chars
                time_duration = int(total_duration * line_proportion)
                next_time = pysrt.SubRipTime.from_ordinal(current_time.ordinal + time_duration)

            # 保存結果
            results.append((
                line_text,                  # 文本
                format_time(current_time),  # 開始時間
                format_time(next_time)      # 結束時間
            ))

            # 更新當前時間為下一行的開始時間
            current_time = next_time

        return results

    def process_split_result(self,
                            split_result: List[Tuple[str, str, str]],
                            original_index: int) -> List[Dict[str, Any]]:
        """
        處理斷句結果，生成用於更新的數據結構

        Args:
            split_result: 斷句結果列表[(文本,開始時間,結束時間),...]
            original_index: 原始項目索引

        Returns:
            用於更新的數據結構
        """
        processed_results = []

        for i, (text, start_time, end_time) in enumerate(split_result):
            new_index = original_index + i if i > 0 else original_index

            processed_results.append({
                'index': new_index,
                'text': text,
                'start_time': start_time,
                'end_time': end_time
            })

        return processed_results

    def validate_time_range(self, start_time: str, end_time: str) -> Tuple[bool, str]:
        """
        驗證時間範圍是否有效

        Args:
            start_time: 開始時間
            end_time: 結束時間

        Returns:
            (是否有效, 錯誤訊息)
        """
        if not start_time or not end_time:
            return False, "開始時間或結束時間為空"

        try:
            start = parse_time(start_time)
            end = parse_time(end_time)

            if end.ordinal <= start.ordinal:
                return False, "結束時間必須大於開始時間"

            return True, ""
        except ValueError as e:
            return False, f"時間格式解析錯誤：{str(e)}"