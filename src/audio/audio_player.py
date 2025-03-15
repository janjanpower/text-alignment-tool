"""音頻播放器模組"""
import os
import sys
import logging
import time
import tempfile
from typing import Any
import pygame
import tkinter as tk
from tkinter import ttk, filedialog

# 添加項目根目錄到Python路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 使用絕對導入
from audio.audio_segment_manager import AudioSegmentManager
from audio.audio_resource_cleaner import AudioResourceCleaner
from utils.time_utils import parse_time
from gui.custom_messagebox import (
    show_info,
    show_warning,
    show_error,
    ask_question
)
class AudioPlayer(ttk.Frame):
    """音頻播放器類別"""

    def __init__(self, master: tk.Widget) -> None:
        """
        初始化音頻播放器
        :param master: 父視窗元件
        """
        super().__init__(master)
        self.master = master

        # 初始化變數
        self.initialize_variables()

        # 設置日誌
        self.logger = logging.getLogger(self.__class__.__name__)

        # 初始化播放器
        self.initialize_player()

        # 創建控制界面
        self.create_controls()

        # 初始化音頻段落管理器
        self.segment_manager = AudioSegmentManager(self.sample_rate)

    def initialize_variables(self) -> None:
        """初始化變數"""
        self.audio_file = None
        self.audio = None
        self.playing = False
        self.current_position = 0
        self.total_duration = 0
        self.sample_rate = 44100
        self.temp_file = None

    def initialize_player(self) -> None:
        """初始化播放器"""
        pygame.mixer.init(
            frequency=self.sample_rate,
            size=-16,
            channels=2,
            buffer=4096
        )

    def create_controls(self) -> None:
        """創建控制界面"""
        # 控制框架
        control_frame = ttk.Frame(self)
        control_frame.pack(pady=5)

        # 載入按鈕
        self.load_button = ttk.Button(
            control_frame,
            text="載入音頻",
            command=self.load_audio,
            width=20,
            style='Custom.TButton'
        )
        self.load_button.pack(side=tk.LEFT, padx=(5, 10))

        # 播放/暫停按鈕
        self.play_button = ttk.Button(
            control_frame,
            text="播放",
            command=self.play_pause,
            width=10,
            style='Custom.TButton'
        )
        self.play_button.pack(side=tk.LEFT, padx=5)

        # 停止按鈕
        self.stop_button = ttk.Button(
            control_frame,
            text="停止",
            command=self.stop,
            width=10,
            style='Custom.TButton'
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # 進度條框架
        progress_frame = ttk.Frame(self)
        progress_frame.pack(fill=tk.X, pady=5)

        # 進度條
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(
            progress_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.progress_var,
            command=self.seek
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 時間標籤
        self.time_label = ttk.Label(
            progress_frame,
            text="00:00 / 00:00",
            style='Custom.TLabel'
        )
        self.time_label.pack(side=tk.RIGHT, padx=5)

    def load_audio(self, file_path=None):
        """
        載入音頻文件
        :param file_path: 音頻文件路徑（可選）
        :return: 成功載入的文件路徑，如果未載入則返回 None
        """
        try:
            if file_path is None:
                file_path = filedialog.askopenfilename(
                    filetypes=[("Audio files", "*.mp3 *.wav")]
                )

            if file_path:
                try:
                    self.logger.info(f"開始載入音頻文件: {file_path}")
                    self.audio_file = file_path

                    # 使用 pydub 加載音頻
                    import os
                    if not os.path.exists(file_path):
                        self.logger.error(f"音頻文件不存在: {file_path}")
                        return None

                    # 確保 segment_manager 已初始化
                    if not hasattr(self, 'segment_manager'):
                        self.segment_manager = AudioSegmentManager(self.sample_rate)

                    # 加載音頻
                    self.audio = self.segment_manager.load_audio(file_path)

                    if self.audio is None:
                        self.logger.error(f"音頻加載返回空值: {file_path}")
                        return None

                    self.total_duration = len(self.audio) / 1000.0
                    self.logger.info(f"音頻載入成功，總時長: {self.total_duration} 秒")

                    # 初始化或清空音頻段落字典
                    self.segment_manager.audio_segments = {}

                    # 生成一個默認段落（整個音頻文件）
                    self.segment_manager.audio_segments[0] = self.audio
                    self.logger.info("創建了默認音頻段落")

                    # 產生音頻載入事件
                    if hasattr(self, 'master') and self.master:
                        self.master.event_generate("<<AudioLoaded>>")

                    return file_path
                except Exception as e:
                    self.logger.error(f"載入音頻文件失敗: {e}", exc_info=True)
                    import traceback
                    self.logger.error(traceback.format_exc())
                    show_error("錯誤", f"無法載入音頻文件: {str(e)}", self.master)
                    return None

            return None

        except Exception as e:
            self.logger.error(f"加載音頻文件時出錯: {e}", exc_info=True)
            import traceback
            self.logger.error(traceback.format_exc())
            show_error("錯誤", f"無法加載音頻文件: {str(e)}", self.master)
            return None

    def sync_audio_with_srt(self, srt_data):
        """
        重新同步音頻段落與 SRT 數據
        :param srt_data: 最新的 SRT 數據
        :return: 是否成功
        """
        try:
            if not self.audio:
                self.logger.warning("沒有音頻數據可供同步")
                return False

            # 使用已加載的音頻和最新的 SRT 數據重新分割
            self.segment_audio(srt_data)
            self.logger.info("音頻段落已與 SRT 數據重新同步")
            return True

        except Exception as e:
            self.logger.error(f"同步音頻段落時出錯: {e}")
            return False

    def segment_audio(self, srt_data):
        """
        分割音頻為段落，完全依照 SRT 時間軸而非索引
        :param srt_data: SRT 數據
        """
        if not self.audio:
            self.logger.warning("沒有預加載的音頻數據可供分割")
            return False

        # 直接傳遞當前加載的音頻和 SRT 數據
        self.segment_manager.segment_audio(self.audio, srt_data)
        return True

    def segment_single_audio(self, original_start_time, original_end_time, new_start_times, new_end_times, original_index):
        """
        根據新的時間軸切分音頻段落
        """
        if not self.audio:
            self.logger.warning("未加載音頻文件")
            return

        self.segment_manager.segment_single_audio(
            self.audio, original_start_time, original_end_time,
            new_start_times, new_end_times, original_index
        )

    @property
    def audio_segments(self):
        """提供對音頻段落的訪問"""
        return self.segment_manager.audio_segments if hasattr(self.segment_manager, 'audio_segments') else {}

    def play_segment(self, index):
        """播放指定的音頻段落"""
        try:
            self.logger.info(f"===== 開始播放索引 {index} 的音頻段落 =====")
            self.logger.info(f"self.audio 存在: {hasattr(self, 'audio') and self.audio is not None}")
            self.logger.info(f"self.segment_manager 存在: {hasattr(self, 'segment_manager')}")
            self.logger.info(f"audio_segments 存在: {hasattr(self.segment_manager, 'audio_segments') if hasattr(self, 'segment_manager') else False}")
            self.logger.info(f"音頻段落數量: {len(self.segment_manager.audio_segments) if hasattr(self.segment_manager, 'audio_segments') else 0}")
            self.logger.info(f"音頻段落索引: {list(self.segment_manager.audio_segments.keys()) if hasattr(self.segment_manager, 'audio_segments') else []}")

            # 基本檢查
            if not hasattr(self, 'audio') or self.audio is None:
                self.logger.error("音頻未載入")
                show_warning("警告", "無法播放音訊：音訊未載入或為空", self.master)
                return False

            if not hasattr(self, 'segment_manager'):
                self.logger.error("segment_manager 不存在")
                return False

            if not hasattr(self.segment_manager, 'audio_segments'):
                self.logger.error("audio_segments 不存在")
                # 創建音頻段落字典
                self.segment_manager.audio_segments = {}

            # 統一索引格式
            if isinstance(index, str):
                try:
                    index = int(index)
                except ValueError:
                    self.logger.error(f"無法將索引 '{index}' 轉換為整數")

            # 檢查該索引的段落是否存在
            if index not in self.segment_manager.audio_segments:
                self.logger.warning(f"索引 {index} 不存在，嘗試創建段落")
                # 直接使用完整音頻作為該索引的段落
                self.segment_manager.audio_segments[index] = self.audio

            # 獲取對應的段落
            segment = self.segment_manager.audio_segments[index]
            if segment is None:
                self.logger.error("段落為空")
                # 使用完整音頻作為段落
                self.segment_manager.audio_segments[index] = self.audio
                segment = self.audio

            # 停止當前播放
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()

            # 清理臨時文件
            self.cleanup_temp_file()

            # 創建臨時文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                self.logger.info(f"創建臨時文件: {temp_file.name}")
                self.temp_file = temp_file.name

                # 導出音頻段落到臨時文件
                try:
                    segment.export(
                        temp_file.name,
                        format='wav',
                        parameters=[
                            "-ar", str(self.sample_rate),
                            "-ac", "2",
                            "-acodec", "pcm_s16le"
                        ]
                    )
                    self.logger.info("音頻段落導出成功")
                except Exception as e:
                    self.logger.error(f"導出音頻段落失敗: {e}")
                    # 如果有問題，嘗試重新使用完整音頻
                    self.audio.export(
                        temp_file.name,
                        format='wav',
                        parameters=[
                            "-ar", str(self.sample_rate),
                            "-ac", "2",
                            "-acodec", "pcm_s16le"
                        ]
                    )

            # 初始化播放器並播放
            try:
                pygame.mixer.quit()
                pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=2, buffer=4096)

                # 檢查臨時文件是否存在
                import os
                if not os.path.exists(self.temp_file):
                    self.logger.error("臨時文件不存在")
                    return False

                # 載入並播放
                pygame.mixer.music.load(self.temp_file)
                pygame.mixer.music.play()
                self.logger.info(f"成功播放索引 {index} 的音頻段落")
                return True
            except Exception as e:
                self.logger.error(f"播放音頻失敗: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                return False

        except Exception as e:
            self.logger.error(f"播放音頻段落時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.cleanup_temp_file()
            return False

    def time_to_milliseconds(self, time: Any) -> int:
        """
        將 SRT 時間轉換為毫秒
        :param time: SRT 時間對象
        :return: 毫秒數
        """
        # 如果 segment_manager 已有此方法，直接使用
        if hasattr(self.segment_manager, 'time_to_milliseconds'):
            return self.segment_manager.time_to_milliseconds(time)

        # 否則，自己實現
        return (time.hours * 3600 + time.minutes * 60 + time.seconds) * 1000 + time.milliseconds

    def play_pause(self):
        """播放/暫停切換"""
        if not self.audio_file:
            self.logger.warning("未加載音頻")
            return

        if self.playing:
            pygame.mixer.music.pause()
            self.play_button.config(text="播放")
            self.playing = False
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.load(self.audio_file)
                pygame.mixer.music.play(start=self.current_position)
            self.play_button.config(text="暫停")
            self.playing = True

        self.update_ui()

    def stop(self):
        """停止播放"""
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.cleanup_temp_file()
        self.playing = False
        self.current_position = 0
        self.play_button.config(text="播放")
        self.update_ui()

    def seek(self, value):
        """
        跳轉到指定位置
        :param value: 進度值（0-100）
        """
        if self.audio_file:
            position = float(value) / 100 * self.total_duration
            if self.playing:
                pygame.mixer.music.play(start=position)
            self.current_position = position
            self.update_time_label()

    def update_ui(self):
        """更新界面"""
        if self.playing:
            self.current_position = pygame.mixer.music.get_pos() / 1000
            progress = (self.current_position / self.total_duration) * 100
            self.progress_var.set(progress)
            self.update_time_label()
        self.after(100, self.update_ui)

    def update_time_label(self):
        """更新時間標籤"""
        current_time = self.format_time(self.current_position)
        total_time = self.format_time(self.total_duration)
        self.time_label.config(text=f"{current_time} / {total_time}")

    @staticmethod
    def format_time(seconds):
        """
        格式化時間
        :param seconds: 秒數
        :return: 格式化的時間字符串
        """
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def cleanup_temp_file(self):
        """清理臨時文件"""
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                time.sleep(0.1)
                os.remove(self.temp_file)
                self.temp_file = None
            except Exception as e:
                self.logger.error(f"清理臨時文件時出錯: {e}")

    def cleanup(self):
        """清理音頻資源"""
        AudioResourceCleaner.cleanup_audio(self.temp_file)

    def reset_player(self):
        """重置播放器狀態"""
        self.stop()
        self.audio_file = None
        self.audio = None
        self.playing = False
        self.current_position = 0
        self.total_duration = 0
        self.segment_manager.clear_segments()
        self.progress_var.set(0)
        self.update_time_label()

    def __del__(self):
        """析構函數"""
        self.cleanup()