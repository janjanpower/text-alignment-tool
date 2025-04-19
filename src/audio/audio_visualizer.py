"""音頻可視化類的改進實現"""

import logging
import tkinter as tk
from typing import Optional, Tuple
import numpy as np
from PIL import Image, ImageTk, ImageDraw,ImageFont
from pydub import AudioSegment


class AudioVisualizer:
    """音頻可視化類別，負責顯示音頻波形和選擇區域"""

    def __init__(self, parent: tk.Widget, width: int = 100, height: int = 50):
        """初始化音頻可視化器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        self.parent = parent
        self.width = width
        self.height = height

        # 創建畫布
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg="#1E1E1E",
            highlightthickness=0
        )

        # 波形相關變數
        self.waveform_image = None
        self.waveform_photo = None
        self.audio_duration = 0

        # 保存原始音頻數據用於動態縮放
        self.original_audio = None
        self.current_view_range = (0, 0)
        self.current_selection_range = (0, 0)
        self.samples_cache = None  # 緩存音頻樣本數據

        # 新增縮放控制變數
        self.zoom_level = 1.0
        self.last_selection_duration = 0

        # 初始狀態設置為空白波形
        self._create_empty_waveform("等待音頻...")

    def _preprocess_audio(self, audio_segment):
        """
        預處理音頻數據，確保音頻的一致性和可用性

        Args:
            audio_segment (AudioSegment): 待處理的音頻段落

        Returns:
            numpy.ndarray: 處理後的音頻樣本數據
        """
        try:
            # 詳細的前置檢查
            if audio_segment is None:
                self.logger.error("音頻段落為 None")
                return np.zeros(1000, dtype=np.float32)

            if len(audio_segment) == 0:
                self.logger.error("音頻段落長度為 0")
                return np.zeros(1000, dtype=np.float32)

            # 強制標準化音頻格式
            try:
                # 確保音頻為 16-bit PCM
                audio_segment = audio_segment.set_sample_width(2)
                # 設置為 44.1kHz 單聲道
                audio_segment = audio_segment.set_frame_rate(44100)
                audio_segment = audio_segment.set_channels(1)
            except Exception as format_e:
                self.logger.error(f"音頻格式標準化失敗: {format_e}")
                return np.zeros(1000, dtype=np.float32)

            # 安全獲取樣本數據
            try:
                samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
            except Exception as sample_e:
                self.logger.error(f"獲取音頻樣本失敗: {sample_e}")
                return np.zeros(1000, dtype=np.float32)

            # 檢查樣本數據
            if len(samples) == 0:
                self.logger.error("音頻樣本數組為空")
                return np.zeros(1000, dtype=np.float32)

            # 正規化
            max_abs = np.max(np.abs(samples))
            if max_abs > 0:
                samples = samples / max_abs
            else:
                samples = np.zeros_like(samples)

            # 日誌記錄
            self.logger.debug(f"音頻預處理成功: 樣本數 = {len(samples)}, 最大振幅 = {max_abs}")

            return samples

        except Exception as e:
            self.logger.error(f"音頻預處理的整體異常: {e}")
            return np.zeros(1000, dtype=np.float32)

    def _calculate_dynamic_view_range(self, start_time: int, end_time: int) -> Tuple[int, int]:
        """
        根據選擇範圍計算動態視圖範圍，確保隨著時間範圍變化自動縮放

        Args:
            start_time: 選擇區域開始時間（毫秒）
            end_time: 選擇區域結束時間（毫秒）

        Returns:
            (視圖開始時間, 視圖結束時間)
        """
        try:
            # 計算選擇範圍的持續時間
            selection_duration = end_time - start_time

            # 基礎視圖範圍：根據選擇範圍動態調整
            # 時間越短，視圖範圍越小（放大）；時間越長，視圖範圍越大（縮小）
            base_zoom = 3.0
            if selection_duration < 500:  # 小於 0.5 秒
                zoom_factor = 1.5
            elif selection_duration < 1000:  # 小於 1 秒
                zoom_factor = 2.0
            elif selection_duration < 2000:  # 小於 2 秒
                zoom_factor = 2.5
            else:  # 大於 2 秒
                zoom_factor = 3.0

            # 計算總視圖寬度
            view_width = selection_duration * zoom_factor
            view_width = max(1000, view_width)  # 最小保持 1 秒的視圖寬度

            # 計算視圖中心
            center_time = (start_time + end_time) / 2

            # 計算視圖起止點
            view_start = max(0, center_time - view_width / 2)
            view_end = min(self.audio_duration, center_time + view_width / 2)

            # 確保視圖範圍不超出音頻邊界
            if view_end - view_start < view_width:
                if view_start == 0:
                    view_end = min(self.audio_duration, view_width)
                else:
                    view_start = max(0, self.audio_duration - view_width)

            return view_start, view_end

        except Exception as e:
            self.logger.error(f"計算動態視圖範圍時出錯: {e}")
            return (0, 2000)  # 返回默認範圍

    def set_audio_segment(self, audio_segment: AudioSegment) -> None:
        """設置音頻段落並預處理"""
        try:
            # 詳細的前置檢查
            if audio_segment is None:
                self.logger.warning("嘗試設置空的音頻段落")
                self._create_empty_waveform("無音頻數據")
                return

            if len(audio_segment) == 0:
                self.logger.warning("音頻段落長度為0")
                self._create_empty_waveform("音頻長度為0")
                return

            # 保存原始音頻段落
            self.original_audio = audio_segment
            self.audio_duration = len(audio_segment)

            # 預處理並緩存音頻數據 - 添加更多檢查
            self.samples_cache = self._preprocess_audio(audio_segment)

            # 額外檢查緩存的樣本
            if len(self.samples_cache) == 0:
                self.logger.error("預處理後的音頻樣本為空")
                self._create_empty_waveform("音頻樣本處理失敗")
                return

            self.logger.debug(f"音頻段落設置完成，總時長: {self.audio_duration}ms, 樣本數: {len(self.samples_cache)}")

            # 初始化視圖範圍
            self.view_quantum_step = max(100, int(self.audio_duration * 0.01))

            # 設置初始視圖範圍
            initial_view_start = 0
            initial_view_end = min(self.audio_duration, self.view_quantum_step * 10)

            # 設置當前視圖範圍
            self.current_view_range = (initial_view_start, initial_view_end)

            # 創建初始波形視圖
            self.create_waveform_with_selection(
                (initial_view_start, initial_view_end),
                (initial_view_start, initial_view_end)
            )

        except Exception as e:
            self.logger.error(f"設置音頻段落時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def update_waveform_and_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int]) -> None:
        try:
            if self.samples_cache is None or self.original_audio is None:
                self._create_empty_waveform("未設置音頻數據")
                return

            view_start, view_end = view_range
            sel_start, sel_end = selection_range

            # 確保範圍有效
            view_start = max(0, view_start)
            view_end = min(self.audio_duration, view_end)
            sel_start = max(view_start, sel_start)
            sel_end = min(view_end, sel_end)

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

            # 計算樣本範圍
            sample_rate = len(self.samples_cache) / self.audio_duration
            start_sample = int(view_start * sample_rate)
            end_sample = int(view_end * sample_rate)

            # 確保樣本範圍有效
            start_sample = max(0, start_sample)
            end_sample = min(len(self.samples_cache), end_sample)

            # 獲取顯示區域的樣本
            display_samples = self.samples_cache[start_sample:end_sample]

            # 智能降採樣
            if len(display_samples) > self.width * 2:
                # 使用RMS降採樣以保留更多細節
                samples_per_pixel = len(display_samples) // self.width
                downsampled = []

                for i in range(self.width):
                    start_idx = i * samples_per_pixel
                    end_idx = min(start_idx + samples_per_pixel, len(display_samples))

                    if start_idx < len(display_samples) and end_idx > start_idx:
                        segment = display_samples[start_idx:end_idx]
                        # 使用RMS值以更好地表示振幅
                        rms = np.sqrt(np.mean(segment**2))
                        downsampled.append(rms)
                    else:
                        downsampled.append(0)
            else:
                # 簡單映射
                x_scale = self.width / len(display_samples)
                downsampled = []
                for i in range(self.width):
                    sample_idx = int(i / x_scale)
                    if sample_idx < len(display_samples):
                        downsampled.append(abs(display_samples[sample_idx]))
                    else:
                        downsampled.append(0)

            # 正規化
            downsampled = np.array(downsampled)
            if np.max(downsampled) > 0:
                downsampled = downsampled / np.max(downsampled)

            # 繪製波形
            for x in range(self.width):
                if x < len(downsampled):
                    amplitude = downsampled[x]
                    wave_height = int(amplitude * (self.height // 2 - 4))
                    y1 = center_y - wave_height
                    y2 = center_y + wave_height
                    draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

            # 計算選擇區域在視圖中的精確像素位置
            view_duration = view_end - view_start
            if view_duration > 0:
                # 改進的像素位置計算
                pixel_start = int(((sel_start - view_start) / view_duration) * self.width)
                pixel_end = int(((sel_end - view_start) / view_duration) * self.width)

                # 確保高亮區域至少可見
                if pixel_end - pixel_start < 1:
                    pixel_end = pixel_start + 1

                pixel_start = max(0, pixel_start)
                pixel_end = min(self.width, pixel_end)

                # 繪製高亮區域
                if pixel_start < pixel_end:
                    # 創建半透明高亮層
                    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                    overlay_draw = ImageDraw.Draw(overlay)

                    # 半透明藍色高亮
                    overlay_draw.rectangle(
                        [(pixel_start, 0), (pixel_end, self.height)],
                        fill=(79, 195, 247, 100)  # 降低透明度以便更好地看到波形
                    )

                    # 邊界線
                    overlay_draw.line([(pixel_start, 0), (pixel_start, self.height)],
                                    fill=(79, 195, 247, 200), width=2)
                    overlay_draw.line([(pixel_end, 0), (pixel_end, self.height)],
                                    fill=(79, 195, 247, 200), width=2)

                    # 合併圖層
                    img = Image.alpha_composite(img, overlay)
                    draw = ImageDraw.Draw(img)

                    # 添加時間文本
                    try:
                        sel_duration = (sel_end - sel_start) / 1000.0
                        time_text = f"{sel_duration:.2f}s"
                        font = ImageFont.load_default()
                        text_width = font.getlength(time_text)
                        text_x = pixel_start + (pixel_end - pixel_start - text_width) // 2
                        text_x = max(2, min(self.width - text_width - 2, text_x))
                        draw.text((text_x, 5), time_text, fill=(255, 255, 255, 200))
                    except:
                        pass

            # 更新顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
            self.canvas.update()

        except Exception as e:
            self.logger.error(f"更新波形時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def _create_empty_waveform(self, message="等待音頻..."):
        """創建空白波形圖"""
        try:
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)
            draw.text((10, center_y - 7), message, fill=(180, 180, 180, 255))

            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)

            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)
            self.canvas.update()

        except Exception as e:
            self.logger.error(f"創建空白波形出錯: {e}")

    def create_waveform(self, audio_segment: AudioSegment, initial_selection: Optional[Tuple[int, int]] = None) -> None:
        """
        創建音頻波形圖（初始化時使用）
        :param audio_segment: 音頻段落
        :param initial_selection: 初始選擇範圍 (start_ms, end_ms)
        """
        try:
            self.set_audio_segment(audio_segment)

            if self.original_audio is None:
                return

            if initial_selection is None:
                initial_selection = (0, len(self.original_audio))

            # 創建默認視圖（完整音頻）
            self.create_waveform_with_selection((0, len(self.original_audio)), initial_selection)
        except Exception as e:
            self.logger.error(f"創建波形圖時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def update_selection(self, start_ms: int, end_ms: int) -> None:
        """更新選擇區域（保持現有視圖範圍）"""
        try:
            if self.original_audio is None:
                self.logger.warning("音頻未設置，無法更新選擇區域")
                return

            # 確保範圍有效
            start_ms = max(0, start_ms)
            end_ms = min(end_ms, self.audio_duration)

            # 如果選擇區域改變，重新繪製
            if (start_ms, end_ms) != self.current_selection_range:
                # 檢查當前視圖範圍
                view_start, view_end = self.current_view_range

                # 如果當前視圖範圍有效
                if view_start < view_end:
                    # 檢查選擇區域是否在當前視圖範圍內
                    if end_ms < view_start or start_ms > view_end:
                        # 選擇區域完全在視圖範圍外，調整視圖範圍
                        duration = end_ms - start_ms
                        center_time = (start_ms + end_ms) / 2

                        # 動態調整視圖寬度
                        view_width = max(duration * 3, 2000)  # 至少2秒或時間範圍的3倍
                        new_view_start = max(0, center_time - view_width / 2)
                        new_view_end = min(self.audio_duration, new_view_start + view_width)

                        # 確保視圖範圍不超出音頻長度
                        if new_view_end > self.audio_duration:
                            new_view_start = max(0, self.audio_duration - view_width)
                            new_view_end = self.audio_duration

                        # 更新視圖範圍和選擇區域
                        self.update_waveform_and_selection((new_view_start, new_view_end), (start_ms, end_ms))
                    else:
                        # 選擇區域與視圖範圍有交集，只需更新選擇區域
                        self.update_waveform_and_selection(self.current_view_range, (start_ms, end_ms))
                else:
                    # 如果當前視圖範圍無效，創建新的視圖範圍
                    duration = end_ms - start_ms
                    center_time = (start_ms + end_ms) / 2
                    view_width = max(duration * 3, 2000)
                    new_view_start = max(0, center_time - view_width / 2)
                    new_view_end = min(self.audio_duration, new_view_start + view_width)

                    # 更新視圖範圍和選擇區域
                    self.update_waveform_and_selection((new_view_start, new_view_end), (start_ms, end_ms))
        except Exception as e:
            self.logger.error(f"更新選擇區域時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    def create_waveform_with_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int]) -> None:
        """
        創建帶有選擇區域的波形圖 - 使用更高效的實現
        :param view_range: 視圖範圍 (start_ms, end_ms)
        :param selection_range: 選擇範圍 (start_ms, end_ms)
        """
        try:
            # 直接使用更高效的update_waveform_and_selection方法
            self.update_waveform_and_selection(view_range, selection_range)
        except Exception as e:
            self.logger.error(f"創建波形圖時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def show(self) -> None:
        """顯示波形容器"""
        self.canvas.pack(side=tk.TOP, pady=(2, 0))

    def hide(self) -> None:
        """隱藏波形容器"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.pack_forget()
        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"隱藏波形容器時出錯: {e}")

    def clear_waveform(self) -> None:
        """清除波形圖"""
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")

            self.waveform_image = None
            self.waveform_photo = None

            # 創建空白波形，避免顯示空白
            self._create_empty_waveform("等待音頻...")

        except tk.TclError:
            pass
        except Exception as e:
            self.logger.error(f"清除波形圖時出錯: {e}")