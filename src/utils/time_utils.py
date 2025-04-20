# time_utils.py
import logging
import pysrt
from typing import Any, Union


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


def time_to_milliseconds(time_obj: Union[pysrt.SubRipTime, Any]) -> int:
    """
    將 SRT 時間轉換為毫秒
    :param time_obj: SRT 時間對象或其他時間對象
    :return: 毫秒數
    """
    if isinstance(time_obj, pysrt.SubRipTime):
        return (time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds) * 1000 + time_obj.milliseconds

    # 如果不是 SubRipTime，嘗試獲取 hours、minutes、seconds、milliseconds 屬性
    try:
        return (getattr(time_obj, 'hours', 0) * 3600 +
                getattr(time_obj, 'minutes', 0) * 60 +
                getattr(time_obj, 'seconds', 0)) * 1000 + getattr(time_obj, 'milliseconds', 0)
    except Exception:
        logging.error(f"時間轉換錯誤，無法處理類型: {type(time_obj)}")
        return 0


def milliseconds_to_time(time_obj) -> pysrt.SubRipTime:
    """
    將毫秒轉換為 SubRipTime 對象
    :param time_obj: 毫秒數
    :return: SubRipTime 對象
    """
    try:
        # 確保輸入是有效的數值
        if not isinstance(time_obj, (int, float)):
            logging.warning(f"毫秒轉換接收到非數值類型: {type(time_obj)}")
            time_obj = 0

        time_obj = float(time_obj)  # 確保能夠轉換為浮點數

        total_seconds = time_obj / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((time_obj % 1000))

        # 增加防護措施
        hours = max(0, min(99, hours))  # 限制小時在0-99之間
        minutes = max(0, min(59, minutes))  # 限制分鐘在0-59之間
        seconds = max(0, min(59, seconds))  # 限制秒在0-59之間
        milliseconds = max(0, min(999, milliseconds))  # 限制毫秒在0-999之間

        return pysrt.SubRipTime(hours, minutes, seconds, milliseconds)
    except Exception as e:
        logging.error(f"轉換毫秒 {time_obj} 為時間對象時出錯: {e}")
        return pysrt.SubRipTime(0, 0, 0, 0)


def time_to_seconds(time_obj: pysrt.SubRipTime) -> float:
    """
    將時間對象轉換為秒數
    :param time_obj: 時間對象
    :return: 秒數(浮點數)
    """
    try:
        return time_obj.hours * 3600 + time_obj.minutes * 60 + time_obj.seconds + time_obj.milliseconds / 1000
    except Exception as e:
        logging.error(f"時間轉換為秒數時出錯: {e}")
        return 0.0