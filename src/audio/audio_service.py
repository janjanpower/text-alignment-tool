"""音頻服務模組，負責處理音頻相關操作的高層邏輯 - 優化版本"""

import logging
import os
from typing import Dict, List, Optional, Any

import pysrt
from pydub import AudioSegment

from audio.audio_player import AudioPlayer
from audio.audio_segment_manager import AudioSegmentManager
from audio.audio_resource_cleaner import AudioResourceCleaner
from utils.time_utils import parse_time, time_to_milliseconds


class AudioService:
    """音頻服務類，提供音頻處理的高層業務邏輯 - 優化版本"""

    def __init__(self, gui_reference=None):
        """初始化音頻服務"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.audio_player = None
        self.audio_imported = False
        self.audio_file_path = None
        self.gui_reference = gui_reference  # 對 GUI 的引用，用於回調
        self._audio_loading_in_progress = False  # 避免重複觸發加載事件

    def initialize_player(self, master):
        """初始化音頻播放器"""
        try:
            self.audio_player = AudioPlayer(master)
            # 可以添加音頻載入事件的回調
            if hasattr(master, 'bind'):
                master.bind("<<AudioLoaded>>", self.handle_audio_loaded)
            return self.audio_player
        except Exception as e:
            self.logger.error(f"初始化音頻播放器時出錯: {e}")
            return None

    def load_audio(self, file_path):
        """載入音頻檔案"""
        try:
            if self._audio_loading_in_progress:
                self.logger.debug("音頻正在加載中，忽略重複請求")
                return False

            self._audio_loading_in_progress = True
            self.logger.info(f"開始載入音頻文件: {file_path}")

            if not os.path.exists(file_path):
                self.logger.error(f"音頻檔案不存在: {file_path}")
                self._audio_loading_in_progress = False
                return False

            if not self.audio_player:
                self.logger.error("音頻播放器未初始化")
                self._audio_loading_in_progress = False
                return False

            # 載入音頻
            result = self.audio_player.load_audio(file_path)

            if result:
                self.audio_imported = True
                self.audio_file_path = file_path

                # 確保音頻已預加載到所有段落
                if hasattr(self, 'srt_data') and self.srt_data and len(self.srt_data) > 0:
                    self.audio_player.segment_audio(self.srt_data)
                    self.logger.info(f"已預加載音頻到 {len(self.srt_data)} 個段落")

                self.logger.info(f"音頻載入成功: {file_path}")
                self._audio_loading_in_progress = False
                return True
            else:
                self.logger.error("音頻載入失敗")
                self._audio_loading_in_progress = False
                return False

        except Exception as e:
            self.logger.error(f"載入音頻時出錯: {e}", exc_info=True)
            self._audio_loading_in_progress = False
            return False

    def segment_audio(self, srt_data):
        """根據 SRT 數據分割音頻"""
        if not self.audio_player or not self.audio_imported:
            return False

        try:
            # 保存 SRT 數據以備後用
            self.srt_data = srt_data
            return self.audio_player.segment_audio(srt_data)
        except Exception as e:
            self.logger.error(f"分割音頻時出錯: {e}", exc_info=True)
            return False

    def play_segment(self, index):
        """播放指定的音頻段落"""
        if not self.audio_player or not self.audio_imported:
            return False

        try:
            return self.audio_player.play_segment(index)
        except Exception as e:
            self.logger.error(f"播放音頻段落時出錯: {e}", exc_info=True)
            return False

    def update_audio_segments(self, srt_data):
        """完全重建音頻段落映射，確保與當前 SRT 數據一致"""
        if not self.audio_player or not self.audio_imported:
            return False

        try:
            # 更新保存的 SRT 數據
            self.srt_data = srt_data
            return self.audio_player.segment_audio(srt_data)
        except Exception as e:
            self.logger.error(f"更新音頻段落時出錯: {e}", exc_info=True)
            return False

    def stop_playback(self):
        """停止音頻播放"""
        if not self.audio_player:
            return

        try:
            self.audio_player.stop()
        except Exception as e:
            self.logger.error(f"停止音頻播放時出錯: {e}", exc_info=True)

    def cleanup(self):
        """清理音頻資源"""
        if not self.audio_player:
            return

        try:
            self.audio_player.cleanup()
            self.audio_player = None
            self.audio_imported = False
            self.audio_file_path = None
        except Exception as e:
            self.logger.error(f"清理音頻資源時出錯: {e}", exc_info=True)

    def handle_audio_loaded(self, event=None):
        """處理音頻載入事件 - 優化版本"""
        try:
            if self.gui_reference and hasattr(self.gui_reference, 'on_audio_loaded_callback'):
                # 檢查是否重複處理相同文件
                if hasattr(self.gui_reference, 'audio_file_path') and \
                   self.gui_reference.audio_file_path == self.audio_file_path and \
                   self.gui_reference.audio_imported:
                    self.logger.debug(f"跳過重複處理相同音頻文件: {self.audio_file_path}")
                    return

                # 僅傳遞文件路徑，不做其他處理
                self.gui_reference.on_audio_loaded_callback(self.audio_file_path)

        except Exception as e:
            self.logger.error(f"處理音頻載入事件時出錯: {e}", exc_info=True)

    @property
    def audio_segments(self):
        """獲取音頻段落 - 方便的屬性訪問"""
        if not self.audio_player or not hasattr(self.audio_player, 'segment_manager'):
            return {}
        return self.audio_player.segment_manager.audio_segments

    def merge_audio_segments(self, indices_to_merge, new_index):
        """合併多個音頻段落 - 優化版本"""
        if not self.audio_player or not self.audio_imported:
            return False

        try:
            # 檢查音頻段落管理器
            if not hasattr(self.audio_player, 'segment_manager'):
                self.logger.error("音頻段落管理器不可用")
                return False

            segment_manager = self.audio_player.segment_manager

            # 獲取要合併的有效段落
            valid_segments = []
            for idx in indices_to_merge:
                segment = segment_manager.get_segment(idx)
                if segment:
                    valid_segments.append((idx, segment))

            if not valid_segments:
                self.logger.warning("沒有找到有效的音頻段落可合併")
                return False

            # 按照索引排序
            valid_segments.sort(key=lambda x: x[0])

            # 合併段落
            combined_segment = valid_segments[0][1]
            for _, segment in valid_segments[1:]:
                combined_segment = combined_segment + segment

            # 保存合併後的段落
            segment_manager.audio_segments[new_index] = combined_segment

            # 刪除被合併的段落 (除了新索引本身)
            for idx, _ in valid_segments:
                if idx != new_index and segment_manager.has_segment(idx):
                    segment_manager.audio_segments.pop(idx, None)

            self.logger.info(f"成功合併 {len(valid_segments)} 個音頻段落為索引 {new_index}")
            return True
        except Exception as e:
            self.logger.error(f"合併音頻段落時出錯: {e}", exc_info=True)
            return False