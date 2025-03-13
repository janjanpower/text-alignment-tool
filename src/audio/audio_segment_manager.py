"""音頻段落管理模組"""

import logging
from typing import Dict, Any, Optional
from pydub import AudioSegment
import os
import sys

# 添加項目根目錄到 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 然後使用絕對導入
from utils.time_utils import parse_time

class AudioSegmentManager:
    """音頻段落管理類"""

    def __init__(self, sample_rate=44100):
        """初始化音頻段落管理器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audio_segments = {}
        self.sample_rate = sample_rate
        self.full_audio = None

    def load_audio(self, file_path):
        """載入音頻文件"""
        audio = AudioSegment.from_file(file_path)
        self.full_audio = audio  # 保存完整音頻
        return audio

    def segment_audio(self, audio, srt_data):
        """
        分割音頻為段落，完全依照 SRT 時間軸而非索引
        :param audio: 音頻數據
        :param srt_data: SRT 數據
        """
        try:
            # 保存完整音頻供後續使用
            self.full_audio = audio

            # 清空現有段落
            self.audio_segments = {}
            total_duration = len(audio)

            # 記錄分段處理
            processed_count = 0
            error_count = 0

            # 如果 srt_data 為空，創建一個包含整個音頻的預設段落
            if not srt_data:
                segment = audio.set_frame_rate(self.sample_rate)
                segment = segment.set_channels(2)
                segment = segment.set_sample_width(2)
                self.audio_segments[0] = segment
                self.logger.debug("SRT 數據為空，創建了包含整個音頻的預設段落")
                return

            for sub in srt_data:
                try:
                    # 獲取時間範圍
                    start_ms = self.time_to_milliseconds(sub.start)
                    end_ms = self.time_to_milliseconds(sub.end)

                    # 確保時間範圍有效
                    if start_ms >= end_ms:
                        self.logger.warning(f"字幕 {sub.index} 的時間範圍無效: {start_ms}-{end_ms}")
                        continue

                    # 修正時間範圍
                    start_ms = max(0, start_ms)
                    end_ms = min(end_ms, total_duration)

                    # 切割音頻，確保即使同一個索引也能根據不同時間範圍重新切分
                    segment = audio[start_ms:end_ms]

                    # 標準化音頻參數
                    segment = segment.set_frame_rate(self.sample_rate)
                    segment = segment.set_channels(2)
                    segment = segment.set_sample_width(2)

                    # 關鍵修改：確保使用數字索引，而不是字符串
                    index = int(sub.index)
                    self.audio_segments[index] = segment
                    processed_count += 1

                    self.logger.debug(f"音頻段落 {index}: {start_ms}ms - {end_ms}ms (時長: {end_ms-start_ms}ms)")

                except Exception as e:
                    self.logger.error(f"切割索引 {sub.index} 的音頻段落時出錯: {e}")
                    error_count += 1

                    # 發生錯誤時，也創建一個包含整個音頻的段落作為備用
                    try:
                        index = int(sub.index)
                        if index not in self.audio_segments:
                            segment = audio.set_frame_rate(self.sample_rate)
                            segment = segment.set_channels(2)
                            segment = segment.set_sample_width(2)
                            self.audio_segments[index] = segment
                            self.logger.debug(f"為索引 {index} 創建了包含整個音頻的備用段落")
                    except:
                        pass

            # 如果所有分割都失敗，創建一個預設段落
            if not self.audio_segments:
                segment = audio.set_frame_rate(self.sample_rate)
                segment = segment.set_channels(2)
                segment = segment.set_sample_width(2)
                self.audio_segments[0] = segment
                self.logger.warning("所有分割都失敗，創建了包含整個音頻的預設段落")

            self.logger.info(f"音頻分段完成: 成功 {processed_count}, 失敗 {error_count}, 段落數 {len(self.audio_segments)}")
            self.logger.info(f"音頻段落索引: {list(self.audio_segments.keys())}")

        except Exception as e:
            self.logger.error(f"分割音頻時出錯: {e}")

            # 發生嚴重錯誤時，仍然確保有一個預設段落
            segment = audio.set_frame_rate(self.sample_rate)
            segment = segment.set_channels(2)
            segment = segment.set_sample_width(2)
            self.audio_segments[0] = segment
            self.logger.warning("分割過程發生嚴重錯誤，創建了包含整個音頻的預設段落")

    def rebuild_segments(self, srt_data):
        """
        完全重建音頻段落，確保與 SRT 數據完全同步
        :param srt_data: SRT 數據
        """
        try:
            # 檢查參數
            if not srt_data:
                self.logger.warning("嘗試重建段落，但 SRT 數據為空")
                return False

            # 檢查是否有完整的音頻數據
            if not hasattr(self, 'full_audio') or self.full_audio is None:
                self.logger.warning("無法重建段落：缺少完整音頻數據")
                return False

            # 清空現有的音頻段落
            old_segments = self.audio_segments.copy()  # 備份
            self.audio_segments = {}

            # 處理每個 SRT 項目
            for sub in srt_data:
                try:
                    # 獲取字幕的起止時間
                    start_ms = self.time_to_milliseconds(sub.start)
                    end_ms = self.time_to_milliseconds(sub.end)

                    # 從完整音頻中切割此段落
                    segment = self.full_audio[start_ms:end_ms]

                    # 標準化音頻參數
                    segment = segment.set_frame_rate(self.sample_rate)
                    segment = segment.set_channels(2)
                    segment = segment.set_sample_width(2)

                    # 保存到音頻段落字典
                    self.audio_segments[sub.index] = segment
                    self.logger.debug(f"重建段落 {sub.index}: {start_ms}ms-{end_ms}ms")

                except Exception as e:
                    self.logger.error(f"重建段落 {sub.index} 時出錯: {e}")
                    # 如果特定段落處理失敗，嘗試使用原始段落
                    if sub.index in old_segments:
                        self.audio_segments[sub.index] = old_segments[sub.index]

            return True

        except Exception as e:
            self.logger.error(f"重建音頻段落時出錯: {e}")
            return False

    def segment_single_audio(self, audio, original_start_time, original_end_time, new_start_times, new_end_times, original_index):
        """
        根據新的時間軸切分音頻段落

        Args:
            audio: 音頻數據
            original_start_time: 原始開始時間
            original_end_time: 原始結束時間
            new_start_times: 新的開始時間列表
            new_end_times: 新的結束時間列表
            original_index: 原始段落索引
        """
        try:
            # 移除原有索引的音頻段落
            if original_index in self.audio_segments:
                del self.audio_segments[original_index]

            # 獲取新的索引列表
            new_indices = range(original_index, original_index + len(new_start_times))

            # 處理每個新的時間段
            for new_index, (start_time, end_time) in zip(new_indices, zip(new_start_times, new_end_times)):
                try:
                    # 轉換時間為毫秒
                    start_ms = self.time_to_milliseconds(parse_time(str(start_time)))
                    end_ms = self.time_to_milliseconds(parse_time(str(end_time)))

                    # 確保時間範圍有效
                    if start_ms >= end_ms:
                        self.logger.warning(f"切分段落 {new_index} 的時間範圍無效: {start_ms}-{end_ms}")
                        continue

                    # 修正時間範圍
                    total_duration = len(audio)
                    start_ms = max(0, start_ms)
                    end_ms = min(end_ms, total_duration)

                    # 使用完整的音頻文件切割，而不依賴於之前的段落
                    segment = audio[start_ms:end_ms]

                    # 標準化音頻參數
                    segment = segment.set_frame_rate(self.sample_rate)
                    segment = segment.set_channels(2)
                    segment = segment.set_sample_width(2)

                    # 使用新的索引保存音頻段落
                    self.audio_segments[new_index] = segment
                    self.logger.debug(f"已創建索引 {new_index} 的音頻段落: {start_ms}ms - {end_ms}ms (時長: {end_ms-start_ms}ms)")

                except Exception as e:
                    self.logger.error(f"處理索引 {new_index} 的音頻段落時出錯: {e}")

        except Exception as e:
            self.logger.error(f"音頻分段處理時出錯: {e}")

    def resegment_audio(self, audio, current_segments):
        """根據當前的字幕段落重新分割音頻"""
        new_segments = {}
        for index, segment_info in enumerate(current_segments, 1):
            start_time = self.time_to_milliseconds(parse_time(segment_info['start']))
            end_time = self.time_to_milliseconds(parse_time(segment_info['end']))

            segment = audio[start_time:end_time]
            segment = segment.set_frame_rate(self.sample_rate)
            segment = segment.set_channels(2)
            segment = segment.set_sample_width(2)

            new_segments[index] = segment

        self.audio_segments = new_segments

    def has_segments(self):
        """檢查是否有音頻段落"""
        return len(self.audio_segments) > 0

    def has_segment(self, index):
        """檢查指定索引的音頻段落是否存在"""
        try:
            # 嘗試將索引轉換為整數
            if isinstance(index, str):
                index = int(index)
        except ValueError:
            pass
        return index in self.audio_segments

    def get_segment(self, index):
        """獲取指定索引的音頻段落"""
        try:
            # 嘗試將索引轉換為整數
            if isinstance(index, str):
                index = int(index)
        except ValueError:
            pass
        return self.audio_segments.get(index)

    def clear_segments(self):
        """清除所有音頻段落"""
        self.audio_segments.clear()

    @staticmethod
    def time_to_milliseconds(time: Any) -> int:
        """
        將 SRT 時間轉換為毫秒
        :param time: SRT 時間對象
        :return: 毫秒數
        """
        return (time.hours * 3600 + time.minutes * 60 + time.seconds) * 1000 + time.milliseconds