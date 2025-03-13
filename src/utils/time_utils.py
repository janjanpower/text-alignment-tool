# time_utils.py
import logging
import pysrt
from typing import Any

def parse_time(time_str: str) -> Any:
    """
    解析時間字符串
    :param time_str: 時間字符串
    :return: 解析後的時間對象
    """
    try:
        # 如果已經是 SubRipTime 對象則直接返回
        if isinstance(time_str, pysrt.SubRipTime):
            return time_str

        # 清理時間字符串
        time_str = str(time_str).strip()

        # 處理空字符串
        if not time_str:
            return pysrt.SubRipTime(0, 0, 0, 0)

        # 標準 SRT 時間格式處理
        try:
            if ',' in time_str:  # 標準 SRT 格式 (00:00:00,000)
                return pysrt.SubRipTime.from_string(time_str)
            elif '.' in time_str:  # 替代格式 (00:00:00.000)
                time_str = time_str.replace('.', ',')
                return pysrt.SubRipTime.from_string(time_str)
            else:  # 嘗試解析其他格式
                parts = time_str.split(':')
                if len(parts) == 3:  # 00:00:00
                    hours, minutes, seconds = map(float, parts)
                    return pysrt.SubRipTime(
                        hours=int(hours),
                        minutes=int(minutes),
                        seconds=int(seconds),
                        milliseconds=int((seconds % 1) * 1000)
                    )
                elif len(parts) == 2:  # 00:00
                    minutes, seconds = map(float, parts)
                    return pysrt.SubRipTime(
                        hours=0,
                        minutes=int(minutes),
                        seconds=int(seconds),
                        milliseconds=int((seconds % 1) * 1000)
                    )
                else:
                    raise ValueError("無效的時間格式")
        except Exception as e:
            raise ValueError(f"無法解析時間格式: {time_str}, 錯誤: {str(e)}")

    except Exception as e:
        raise ValueError(f"時間解析錯誤: {str(e)}")

def format_time(time_obj: Any) -> str:
    """
    格式化時間值為字符串
    :param time_obj: 時間對象
    :return: 格式化的時間字符串
    """
    try:
        # 如果是 SubRipTime 對象，直接轉換為字符串
        if isinstance(time_obj, pysrt.SubRipTime):
            time_str = str(time_obj)
            if not time_str:
                return "00:00:00,000"
            return time_str

        # 如果是數字，轉換為 SubRipTime
        elif isinstance(time_obj, (int, float)):
            total_seconds = float(time_obj)
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            milliseconds = int((total_seconds * 1000) % 1000)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

        # 其他情況，嘗試轉換為字符串格式
        return str(pysrt.SubRipTime.from_string(str(time_obj)))

    except Exception as e:
        logging.error(f"時間格式化錯誤: {e}")
        return "00:00:00,000"