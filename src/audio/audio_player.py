"""音頻播放器模組"""
import os
import sys
import logging
import time
import tempfile
from typing import Any
import pygame
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 添加項目根目錄到Python路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 使用絕對導入
from audio.audio_segment_manager import AudioSegmentManager
from audio.audio_resource_cleaner import AudioResourceCleaner
from utils.time_utils import parse_time

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
                self.audio_file = file_path
                self.audio = self.segment_manager.load_audio(file_path)
                self.total_duration = len(self.audio) / 1000.0

                # 初始化音頻段落字典，確保它不為空
                self.segment_manager.audio_segments = {}

                # 生成一個默認段落（整個音頻文件）
                self.segment_manager.audio_segments[0] = self.audio

                # 產生音頻載入事件
                self.master.event_generate("<<AudioLoaded>>")
                return file_path

        except Exception as e:
            self.logger.error(f"加載音頻文件時出錯: {e}")
            messagebox.showerror("錯誤", f"無法加載音頻文件: {str(e)}")

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
            self.logger.debug(f"嘗試播放索引 {index} 的音頻段落")
            self.logger.debug(f"現有音頻段落索引: {list(self.segment_manager.audio_segments.keys())}")

            # 將索引轉換為整數
            try:
                if isinstance(index, str):
                    index = int(index)
            except ValueError:
                self.logger.warning(f"無法將索引 '{index}' 轉換為整數")

            # 檢查音頻段落是否存在
            if not self.segment_manager.has_segments():
                self.logger.warning("音頻段落為空")
                return False

            # 如果指定索引不存在，嘗試找最接近的索引
            if index not in self.segment_manager.audio_segments:
                self.logger.warning(f"索引 {index} 不存在於音頻段落中")
                valid_indices = list(self.segment_manager.audio_segments.keys())
                if valid_indices:
                    closest_index = min(valid_indices, key=lambda x: abs(int(x) - index) if isinstance(x, (int, str)) and str(x).isdigit() else float('inf'))
                    self.logger.info(f"使用最接近的索引 {closest_index} 代替 {index}")
                    index = closest_index
                else:
                    self.logger.error("沒有可用的音頻段落")
                    return False

            segment = self.segment_manager.audio_segments[index]
            if segment is None:
                self.logger.error(f"索引 {index} 的段落為空")
                return False

            # 清理之前的臨時文件
            self.cleanup_temp_file()

            # 創建新的臨時文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                self.temp_file = temp_file.name
                segment.export(
                    temp_file.name,
                    format='wav',
                    parameters=[
                        "-ar", str(self.sample_rate),
                        "-ac", "2",
                        "-acodec", "pcm_s16le"
                    ]
                )

            # 播放音頻
            pygame.mixer.quit()
            pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=2, buffer=4096)
            pygame.mixer.music.load(self.temp_file)
            pygame.mixer.music.play()
            self.logger.debug(f"開始播放索引 {index} 的音頻段落")
            return True

        except Exception as e:
            self.logger.error(f"播放音頻段落時出錯: {e}")
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