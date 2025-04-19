"""音頻可視化類的改進實現"""

import logging
import tkinter as tk
from typing import Optional, Tuple, List
import numpy as np
from PIL import Image, ImageTk, ImageDraw
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

        # 初始狀態設置為空白波形
        self._create_empty_waveform("等待音頻...")

    def _preprocess_audio(self, audio_segment):
        """預處理音頻數據，只處理一次"""
        try:
            samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

            # 處理立體聲
            if audio_segment.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)

            # 正規化
            max_abs = np.max(np.abs(samples))
            if max_abs > 0:
                samples = samples / max_abs
            else:
                samples = np.zeros_like(samples)

            self.logger.debug(f"音頻預處理完成: 樣本數={len(samples)}, 最大振幅={max_abs}")
            return samples
        except Exception as e:
            self.logger.error(f"音頻預處理失敗: {e}")
            return np.zeros(1000)  # 返回空數組作為後備

    def set_audio_segment(self, audio_segment: AudioSegment) -> None:
        """設置音頻段落並預處理"""
        try:
            if audio_segment is None or len(audio_segment) == 0:
                self._create_empty_waveform("無效的音頻段落")
                return

            self.original_audio = audio_segment
            self.audio_duration = len(audio_segment)
            # 預處理並緩存音頻數據
            self.samples_cache = self._preprocess_audio(audio_segment)
            self.logger.debug(f"音頻段落設置完成，總時長: {self.audio_duration}ms, 樣本數: {len(self.samples_cache)}")

            # 初始化視圖為整個音頻段落
            self.current_view_range = (0, self.audio_duration)

            # 重要：設置音頻後立即創建完整波形視圖
            self.create_waveform_with_selection((0, self.audio_duration), (0, self.audio_duration))
        except Exception as e:
            self.logger.error(f"設置音頻段落時出錯: {e}")
            self._create_empty_waveform(f"錯誤: {str(e)}")

    def update_waveform_and_selection(self, view_range: Tuple[int, int], selection_range: Tuple[int, int]) -> None:
        """即時更新波形和選擇區域"""
        try:
            if self.samples_cache is None or self.original_audio is None:
                self._create_empty_waveform("未設置音頻數據")
                return

            # 使用時間範圍處理器驗證並修正範圍
            from .time_range_handler import TimeRangeHandler  # 確保導入時間處理器
            handler = TimeRangeHandler()

            # 獲取音頻總長度
            audio_duration = self.audio_duration

            # 驗證並修正視圖範圍和選擇範圍
            safe_view_range = handler.validate_range(view_range, audio_duration, min_range=500)
            safe_selection_range = handler.validate_range(selection_range, audio_duration, min_range=100)

            # 記錄當前的視圖和選擇範圍
            view_start, view_end = safe_view_range
            sel_start, sel_end = safe_selection_range

            self.current_view_range = (view_start, view_end)
            self.current_selection_range = (sel_start, sel_end)

            # 計算樣本範圍
            if len(self.samples_cache) == 0:
                self._create_empty_waveform("沒有音頻樣本數據")
                return

            # 計算顯示的樣本起始和結束索引
            sample_rate = len(self.samples_cache) / audio_duration if audio_duration > 0 else 44100
            start_sample = int(view_start * sample_rate)
            end_sample = int(view_end * sample_rate)

            # 確保樣本範圍有效
            start_sample = max(0, start_sample)
            end_sample = min(len(self.samples_cache), end_sample)

            # 再次檢查樣本範圍有效性
            if start_sample >= end_sample - 10:  # 確保至少有10個樣本
                # 強制設置一個有效範圍
                start_sample = 0
                end_sample = min(1000, len(self.samples_cache))

            # 獲取顯示區域的樣本
            display_samples = self.samples_cache[start_sample:end_sample]

            # 降採樣
            samples_per_pixel = max(1, len(display_samples) // self.width)
            downsampled = []

            for i in range(self.width):
                start_idx = i * samples_per_pixel
                end_idx = min(start_idx + samples_per_pixel, len(display_samples))

                if start_idx < len(display_samples) and end_idx > start_idx:
                    segment = display_samples[start_idx:end_idx]
                    downsampled.append(np.max(np.abs(segment)))
                else:
                    downsampled.append(0)

            downsampled = np.array(downsampled)

            # 創建圖像
            img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
            draw = ImageDraw.Draw(img)

            # 繪製中心線
            center_y = self.height // 2
            draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

            # 繪製波形
            for x in range(self.width):
                if x < len(downsampled):
                    amplitude = downsampled[x]
                    wave_height = int(amplitude * (self.height // 2 - 4))
                    y1 = center_y - wave_height
                    y2 = center_y + wave_height
                    draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

            # 計算選擇區域在視圖中的位置
            view_duration = view_end - view_start
            if view_duration > 0:
                # 確保選擇區與視圖範圍有交集
                if sel_end >= view_start and sel_start <= view_end:
                    # 計算相對位置 - 確保選擇區域正確映射到視圖範圍
                    # 如果選擇區域超出視圖範圍，則將其裁剪到視圖範圍內
                    display_sel_start = max(sel_start, view_start)
                    display_sel_end = min(sel_end, view_end)

                    # 計算相對於當前視圖的比例位置
                    relative_start = (display_sel_start - view_start) / view_duration
                    relative_end = (display_sel_end - view_start) / view_duration

                    # 轉換為像素位置
                    start_x = int(relative_start * self.width)
                    end_x = int(relative_end * self.width)

                    # 確保有最小寬度且不超出畫布範圍
                    if end_x - start_x < 2:
                        end_x = min(start_x + 2, self.width)

                    start_x = max(0, start_x)
                    end_x = min(self.width, end_x)

                    if start_x < end_x:  # 確保有效的選擇區域
                        # 繪製高亮區域
                        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
                        overlay_draw = ImageDraw.Draw(overlay)

                        # 半透明藍色高亮
                        overlay_draw.rectangle(
                            [(start_x, 0), (end_x, self.height)],
                            fill=(79, 195, 247, 128)  # 更明顯的高亮
                        )

                        # 合併圖層
                        img = Image.alpha_composite(img, overlay)
                        draw = ImageDraw.Draw(img)

                        # 繪製邊界線 - 更明顯的邊界
                        draw.line([(start_x, 0), (start_x, self.height)], fill=(79, 195, 247, 255), width=2)
                        draw.line([(end_x, 0), (end_x, self.height)], fill=(79, 195, 247, 255), width=2)

            # 更新顯示
            self.waveform_image = img
            self.waveform_photo = ImageTk.PhotoImage(img)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

            # 強制立即更新顯示
            self.canvas.update()

        except Exception as e:
            self.logger.error(f"更新波形時出錯: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._create_empty_waveform(f"錯誤: {str(e)}")
    def _validate_prerequisites(self) -> bool:
        """驗證必要的音頻數據是否可用"""
        if self.samples_cache is None or self.original_audio is None:
            self._create_empty_waveform("未設置音頻數據")
            return False
        return True

    def _validate_and_fix_ranges(self, view_range: Tuple[int, int],
                            selection_range: Tuple[int, int]) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:

        # 驗證並修正視圖和選擇範圍
        ranges = self._validate_and_fix_ranges(view_range, selection_range)
        if ranges is None:
            # 如果範圍無效且無法修正，直接返回
            return

        # 解包有效的範圍
        view_range, selection_range = ranges

        """驗證並修正視圖和選擇範圍"""
        # 確保範圍有效
        view_start, view_end = view_range
        sel_start, sel_end = selection_range

        # 關鍵修正：檢查並交換顛倒的開始/結束時間
        if view_start > view_end:
            self.logger.warning(f"視圖範圍顛倒: {view_start} - {view_end}，自動交換")
            view_start, view_end = view_end, view_start

        # 修正：確保時間範圍有效，開始時間必須小於結束時間
        view_start = max(0, view_start)
        view_end = min(self.audio_duration, view_end)

        # 關鍵修正：如果視圖結束時間小於等於開始時間，調整為有效範圍
        if view_end <= view_start:
            self.logger.warning(f"無效的視圖範圍: {view_start} - {view_end}")
            # 使用開始時間和一個合理的持續時間
            view_end = min(view_start + 2000, self.audio_duration)  # 至少顯示2秒
            if view_end <= view_start:  # 如果仍然無效
                self._create_empty_waveform("無效的視圖範圍")
                return None

        # 同樣處理選擇範圍
        if sel_start > sel_end:
            self.logger.warning(f"選擇範圍顛倒: {sel_start} - {sel_end}，自動交換")
            sel_start, sel_end = sel_end, sel_start

        # 確保選擇範圍有效
        sel_start = max(0, sel_start)
        sel_end = min(self.audio_duration, sel_end)

        # 選擇範圍也需檢查有效性
        if sel_end <= sel_start:
            sel_end = min(sel_start + 1000, self.audio_duration)  # 確保至少1秒

        # 記錄當前的視圖和選擇範圍
        self.current_view_range = (view_start, view_end)
        self.current_selection_range = (sel_start, sel_end)

        return (view_start, view_end), (sel_start, sel_end)

    def _get_and_process_samples(self, view_range: Tuple[int, int]) -> Optional[List[float]]:
        """獲取並處理音頻樣本"""
        view_start, view_end = view_range

        # 計算樣本範圍
        if len(self.samples_cache) == 0:
            self._create_empty_waveform("沒有音頻樣本數據")
            return None

        # 計算顯示的樣本起始和結束索引
        sample_rate = len(self.samples_cache) / self.audio_duration if self.audio_duration > 0 else 44100
        start_sample = int(view_start * sample_rate)
        end_sample = int(view_end * sample_rate)

        # 確保樣本範圍有效
        start_sample = max(0, start_sample)
        end_sample = min(len(self.samples_cache), end_sample)

        # 確保至少有一個樣本可顯示
        if start_sample >= end_sample:
            self.logger.warning("無有效的顯示樣本")
            end_sample = min(start_sample + 100, len(self.samples_cache))
            if end_sample <= start_sample:
                self._create_empty_waveform("樣本範圍無效")
                return None

        # 獲取顯示區域的樣本
        display_samples = self.samples_cache[start_sample:end_sample]

        # 降採樣
        return self._downsample_audio(display_samples)

    def _downsample_audio(self, samples: np.ndarray) -> List[float]:
        """降低音頻樣本採樣率以適應螢幕寬度"""
        samples_per_pixel = max(1, len(samples) // self.width)
        downsampled = []

        for i in range(self.width):
            start_idx = i * samples_per_pixel
            end_idx = min(start_idx + samples_per_pixel, len(samples))

            if start_idx < len(samples) and end_idx > start_idx:
                segment = samples[start_idx:end_idx]
                downsampled.append(np.max(np.abs(segment)))
            else:
                downsampled.append(0)

        return np.array(downsampled)

    def _draw_waveform(self, downsampled: np.ndarray) -> Image.Image:
        """繪製波形圖"""
        # 創建圖像
        img = Image.new('RGBA', (self.width, self.height), (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)

        # 繪製中心線
        center_y = self.height // 2
        draw.line([(0, center_y), (self.width, center_y)], fill=(70, 70, 70, 255), width=1)

        # 繪製波形
        for x in range(self.width):
            if x < len(downsampled):
                amplitude = downsampled[x]
                wave_height = int(amplitude * (self.height // 2 - 4))
                y1 = center_y - wave_height
                y2 = center_y + wave_height
                draw.line([(x, y1), (x, y2)], fill=(100, 210, 255, 255), width=2)

        return img

    def _draw_selection_highlight(self, img: Image.Image, view_range: Tuple[int, int],
                                selection_range: Tuple[int, int]) -> Image.Image:
        """在波形圖上繪製選擇區域高亮"""
        view_start, view_end = view_range
        sel_start, sel_end = selection_range

        # 計算選擇區域在視圖中的位置
        view_duration = view_end - view_start
        if view_duration <= 0:
            return img

        # 確保選擇區與視圖範圍有交集
        if sel_end < view_start or sel_start > view_end:
            return img

        # 計算相對位置 - 確保選擇區域正確映射到視圖範圍
        # 如果選擇區域超出視圖範圍，則將其裁剪到視圖範圍內
        display_sel_start = max(sel_start, view_start)
        display_sel_end = min(sel_end, view_end)

        # 計算相對於當前視圖的比例位置
        relative_start = (display_sel_start - view_start) / view_duration
        relative_end = (display_sel_end - view_start) / view_duration

        # 轉換為像素位置
        start_x = int(relative_start * self.width)
        end_x = int(relative_end * self.width)

        # 確保有最小寬度且不超出畫布範圍
        if end_x - start_x < 2:
            end_x = min(start_x + 2, self.width)

        start_x = max(0, start_x)
        end_x = min(self.width, end_x)

        if start_x >= end_x:  # 確保有效的選擇區域
            return img

        # 繪製高亮區域
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)

        # 半透明藍色高亮
        overlay_draw.rectangle(
            [(start_x, 0), (end_x, self.height)],
            fill=(79, 195, 247, 128)  # 更明顯的高亮
        )

        # 合併圖層
        img = Image.alpha_composite(img, overlay)
        draw = ImageDraw.Draw(img)

        # 繪製邊界線 - 更明顯的邊界
        draw.line([(start_x, 0), (start_x, self.height)], fill=(79, 195, 247, 255), width=2)
        draw.line([(end_x, 0), (end_x, self.height)], fill=(79, 195, 247, 255), width=2)

        return img

    def _update_display(self, img: Image.Image) -> None:
        """更新顯示"""
        self.waveform_image = img
        self.waveform_photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.waveform_photo)

        # 強制立即更新顯示
        self.canvas.update()

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