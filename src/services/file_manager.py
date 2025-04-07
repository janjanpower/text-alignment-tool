"""檔案管理模組，負責處理所有檔案相關操作"""

import csv
import logging
import os
import pysrt
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Dict, Optional, Tuple, List, Any, Callable, Union
from gui.custom_messagebox import show_info, show_warning, show_error, ask_question
class FileManager:
    """檔案管理類別，負責處理所有檔案相關操作"""

    def __init__(self, parent: tk.Tk):
        """
        初始化檔案管理器
        :param parent: 父視窗
        """
        self.parent = parent
        self.logger = logging.getLogger(self.__class__.__name__)

        # 檔案路徑
        self.srt_file_path = None
        self.audio_file_path = None
        self.word_file_path = None
        self.current_project_path = None
        self.database_file = None

        # 檔案狀態
        self.srt_imported = False
        self.audio_imported = False
        self.word_imported = False

        # 回調函數 - 定義需要的回調
        self.callbacks = {
            'on_srt_loaded': None,           # 當SRT檔案載入後，參數: srt_data
            'on_audio_loaded': None,         # 當音頻載入後，參數: audio_file_path
            'on_word_loaded': None,          # 當Word文檔載入後，參數: word_file_path
            'on_file_info_updated': None,    # 當檔案信息更新時，無參數
            'on_status_updated': None,       # 當狀態更新時，參數: status_message
            'get_corrections': None,         # 獲取校正數據，無參數，返回校正字典
            'get_srt_data': None,            # 獲取當前SRT數據，無參數，返回SRT數據
            'get_tree_data': None,           # 獲取樹視圖數據，無參數，返回樹視圖數據
            'update_tree_data': None,        # 更新樹視圖數據，參數: srt_data, corrections
            'segment_audio': None,           # 分割音頻，參數: srt_data
            'show_info': None,
            'show_warning': None,
            'show_error': None,
            'ask_question': None
        }

    def set_callback(self, name: str, callback: Callable) -> None:
        """設置單個回調函數"""
        if name not in self.callbacks:
            self.callbacks[name] = None
            self.logger.debug(f"創建新的回調: {name}")

        self.callbacks[name] = callback
        self.logger.debug(f"設置回調: {name}, 函數: {callback.__name__ if hasattr(callback, '__name__') else str(callback)}")

    def set_callbacks(self, **callbacks) -> None:
        """
        設置多個回調函數
        :param callbacks: 回調函數字典，如 on_srt_loaded=func1, on_audio_loaded=func2
        """
        for name, callback in callbacks.items():
            self.set_callback(name, callback)

    # === SRT 檔案相關功能 ===

    def load_srt(self, event: Optional[tk.Event] = None, file_path: Optional[str] = None) -> Optional[pysrt.SubRipFile]:
        """載入 SRT 文件"""
        try:
            self.logger.debug("開始載入 SRT 檔案")

            if file_path is None:
                self.logger.debug("未提供檔案路徑，開啟檔案選擇對話框")
                file_path = filedialog.askopenfilename(
                    filetypes=[("SRT files", "*.srt")],
                    parent=self.parent
                )

            if not file_path:
                self.logger.debug("未選擇檔案或對話框被取消")
                return None

            # 載入 SRT 數據
            try:
                self.logger.debug(f"嘗試載入檔案: {file_path}")
                srt_data = pysrt.open(file_path, encoding='utf-8')
                if not srt_data:
                    raise ValueError("SRT文件為空或格式無效")
                self.logger.debug(f"成功載入 SRT 檔案，項目數: {len(srt_data)}")
            except Exception as e:
                self.logger.error(f"讀取 SRT 檔案失敗: {e}")
                if 'show_error' in self.callbacks and self.callbacks['show_error']:
                    self.callbacks['show_error']("錯誤", f"讀取 SRT 檔案失敗: {str(e)}")
                else:
                    show_error("錯誤", f"讀取 SRT 檔案失敗: {str(e)}", self.parent)
                return None

            # 更新狀態
            self.srt_file_path = file_path
            self.srt_imported = True

            # 獲取校正數據
            corrections = None
            if 'get_corrections' in self.callbacks and self.callbacks['get_corrections']:
                self.logger.debug("嘗試獲取校正數據")
                corrections = self.callbacks['get_corrections']()
                self.logger.debug(f"獲取到 {len(corrections) if corrections else 0} 條校正記錄")

            # 關鍵點：直接返回 SRT 數據，而不是在這裡處理
            # 讓 alignment_gui.py 處理數據顯示
            if 'on_srt_loaded' in self.callbacks and self.callbacks['on_srt_loaded']:
                self.logger.debug("調用 on_srt_loaded 回調")
                self.callbacks['on_srt_loaded'](srt_data, file_path, corrections)

            # 更新界面信息
            if 'on_file_info_updated' in self.callbacks and self.callbacks['on_file_info_updated']:
                self.callbacks['on_file_info_updated']()

            if 'on_status_updated' in self.callbacks and self.callbacks['on_status_updated']:
                self.callbacks['on_status_updated'](f"已載入SRT檔案：{os.path.basename(file_path)}")

            # 顯示成功消息
            if 'show_info' in self.callbacks and self.callbacks['show_info']:
                self.callbacks['show_info']("成功", f"已成功載入SRT檔案：\n{os.path.basename(file_path)}")
            else:
                messagebox.showinfo("成功", f"已成功載入SRT檔案：\n{os.path.basename(file_path)}", parent=self.parent)


            # 更新所有相關狀態和界面
            self._update_all_related_states(srt_data, file_path)

            return srt_data

        except Exception as e:
            self.logger.error(f"載入 SRT 檔案時出錯: {e}", exc_info=True)
            if 'show_error' in self.callbacks and self.callbacks['show_error']:
                self.callbacks['show_error']("錯誤", f"無法載入 SRT 檔案: {str(e)}")
            else:
                messagebox.showerror("錯誤", f"無法載入 SRT 檔案: {str(e)}", parent=self.parent)
            return None

    def _update_all_related_states(self, srt_data, file_path):
        """更新所有狀態，集中處理各種狀態更新"""
        # 更新內部狀態
        self.srt_file_path = file_path
        self.srt_imported = True

        # 調用回調更新界面
        if self.callbacks['on_srt_loaded']:
            self.callbacks['on_srt_loaded'](srt_data, file_path)

        if self.callbacks['on_file_info_updated']:
            self.callbacks['on_file_info_updated']()

        if self.callbacks['on_status_updated']:
            self.callbacks['on_status_updated'](f"已載入SRT檔案：{os.path.basename(file_path)}")

    def save_srt(self, event: Optional[tk.Event] = None) -> bool:
        """
        儲存 SRT 文件
        :param event: 事件對象（可選）
        :return: 是否成功儲存
        """
        # 直接調用 export_srt 方法，參數為 False 表示不是從工具列呼叫
        return self.export_srt(from_toolbar=False)

    def save_srt_as(self) -> bool:
        """
        另存新檔
        :return: 是否成功儲存
        """
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".srt",
                filetypes=[("SRT files", "*.srt")],
                parent=self.parent
            )

            if not file_path:
                return False

            # 獲取當前SRT數據
            srt_data = None
            if self.callbacks['get_srt_data']:
                srt_data = self.callbacks['get_srt_data']()

            if not srt_data:
                if 'show_error' in self.callbacks and self.callbacks['show_error']:
                    self.callbacks['show_error']("錯誤", "無法獲取SRT數據")
                else:
                    show_error("錯誤", "無法獲取SRT數據", self.parent)
                return False

            # 保存文件
            srt_data.save(file_path, encoding='utf-8')

            # 更新文件路徑
            self.srt_file_path = file_path

            if self.callbacks['on_file_info_updated']:
                self.callbacks['on_file_info_updated']()

            if self.callbacks['on_status_updated']:
                self.callbacks['on_status_updated'](f"已另存新檔：{os.path.basename(file_path)}")

            return True
        except Exception as e:
            self.logger.error(f"另存新檔時出錯: {e}", exc_info=True)
            if 'show_error' in self.callbacks and self.callbacks['show_error']:
                self.callbacks['show_error']("錯誤", f"另存新檔失敗: {str(e)}")
            else:
                show_error("錯誤", f"另存新檔失敗: {str(e)}", self.parent)
            return False

    def export_srt(self, from_toolbar: bool = False) -> bool:
        """
        匯出 SRT 檔案 - 直接覆蓋原始檔案
        :param from_toolbar: 不再使用此參數，保留僅為兼容性
        :return: 是否成功匯出
        """
        try:
            self.logger.info("開始匯出 SRT 檔案")

            # 檢查是否有數據可匯出
            if self.callbacks['get_tree_data'] and not self.callbacks['get_tree_data']():
                if 'show_warning' in self.callbacks and self.callbacks['show_warning']:
                    self.callbacks['show_warning']("警告", "沒有可匯出的資料！")
                else:
                    show_warning("警告", "沒有可匯出的資料！", self.parent)
                return False

            # 檢查原始文件路徑
            if not self.srt_file_path:
                if 'show_warning' in self.callbacks and self.callbacks['show_warning']:
                    self.callbacks['show_warning']("警告", "找不到原始檔案路徑！")
                else:
                    show_warning("警告", "找不到原始檔案路徑！", self.parent)
                return False

            file_path = self.srt_file_path
            self.logger.info(f"將覆蓋原始檔案: {file_path}")

            # 獲取當前SRT數據
            srt_data = None
            if self.callbacks['get_srt_data']:
                srt_data = self.callbacks['get_srt_data']()

            if not srt_data:
                if 'show_error' in self.callbacks and self.callbacks['show_error']:
                    self.callbacks['show_error']("錯誤", "無法獲取SRT數據")
                else:
                    show_error("錯誤", "無法獲取SRT數據", self.parent)
                return False

            # 保存文件
            srt_data.save(file_path, encoding='utf-8')
            self.logger.info(f"已成功覆蓋 SRT 檔案，項目數: {len(srt_data)}")

            # 顯示成功訊息
            if 'show_info' in self.callbacks and self.callbacks['show_info']:
                self.callbacks['show_info']("成功", f"SRT 檔案已更新：\n{file_path}")
            else:
                show_info("成功", f"SRT 檔案已更新：\n{file_path}", self.parent)

            return True
        except Exception as e:
            self.logger.error(f"匯出 SRT 檔案時出錯: {e}", exc_info=True)
            if 'show_error' in self.callbacks and self.callbacks['show_error']:
                self.callbacks['show_error']("錯誤", f"匯出 SRT 檔案失敗：{str(e)}")
            else:
                show_error("錯誤", f"匯出 SRT 檔案失敗：{str(e)}", self.parent)
            return False

    # === 音頻檔案相關功能 ===

    def import_audio(self) -> None:
        """匯入音頻檔案"""
        try:
            self.logger.info("===== 開始匯入音頻檔案 =====")
            self.logger.info(f"當前 SRT 匯入狀態: {self.srt_imported}")

            # 檢查是否已匯入 SRT
            if not self.srt_imported:
                if 'show_warning' in self.callbacks and self.callbacks['show_warning']:
                    self.callbacks['show_warning']("警告", "請先匯入 SRT 文件")
                else:
                    show_warning("警告", "請先匯入 SRT 文件", self.parent)
                return

            file_path = filedialog.askopenfilename(
                filetypes=[("Audio files", "*.mp3 *.wav")],
                parent=self.parent
            )

            if not file_path:
                self.logger.info("用戶取消了文件選擇")
                return

            # 確認文件存在
            import os
            if not os.path.exists(file_path):
                self.logger.error(f"選擇的文件不存在: {file_path}")
                if 'show_error' in self.callbacks and self.callbacks['show_error']:
                    self.callbacks['show_error']("錯誤", "選擇的文件不存在")
                else:
                    show_error("錯誤", "選擇的文件不存在", self.parent)
                return

            # 更新狀態
            self.audio_file_path = file_path
            self.audio_imported = True
            self.logger.info(f"音頻路徑已更新: {file_path}")
            self.logger.info(f"音頻匯入狀態已更新: {self.audio_imported}")

            # 調用回調函數
            if self.callbacks['on_audio_loaded']:
                self.logger.info("調用 on_audio_loaded 回調")
                self.callbacks['on_audio_loaded'](file_path)
            else:
                self.logger.warning("on_audio_loaded 回調未設置")

            if self.callbacks['on_file_info_updated']:
                self.logger.info("調用 on_file_info_updated 回調")
                self.callbacks['on_file_info_updated']()
            else:
                self.logger.warning("on_file_info_updated 回調未設置")

            # 通知完成音頻載入
            if 'show_info' in self.callbacks and self.callbacks['show_info']:
                self.callbacks['show_info']("成功", f"已成功載入音頻檔案：\n{os.path.basename(file_path)}")
            else:
                show_info("成功", f"已成功載入音頻檔案：\n{os.path.basename(file_path)}", self.parent)

        except Exception as e:
            self.logger.error(f"匯入音頻文件時出錯: {e}", exc_info=True)
            if 'show_error' in self.callbacks and self.callbacks['show_error']:
                self.callbacks['show_error']("錯誤", f"無法匯入音頻文件: {str(e)}")
            else:
                show_error("錯誤", f"無法匯入音頻文件: {str(e)}", self.parent)

    # === Word 文檔相關功能 ===

    def import_word_document(self) -> None:
        """匯入 Word 文檔"""
        try:
            # 檢查是否已匯入 SRT
            if not self.srt_imported:
                if 'show_warning' in self.callbacks and self.callbacks['show_warning']:
                    self.callbacks['show_warning']("警告", "請先匯入 SRT 文件")
                else:
                    show_warning("警告", "請先匯入 SRT 文件", self.parent)
                return

            file_path = filedialog.askopenfilename(
                filetypes=[("Word files", "*.docx")],
                parent=self.parent
            )

            if not file_path:
                return

            # 更新狀態
            self.word_file_path = file_path
            self.word_imported = True

            # 調用回調函數
            if self.callbacks['on_word_loaded']:
                self.callbacks['on_word_loaded'](file_path)

            if self.callbacks['on_file_info_updated']:
                self.callbacks['on_file_info_updated']()

            if self.callbacks['on_status_updated']:
                self.callbacks['on_status_updated'](f"已載入 Word 文檔: {os.path.basename(file_path)}")

        except Exception as e:
            self.logger.error(f"匯入 Word 文檔時出錯: {e}", exc_info=True)
            if 'show_error' in self.callbacks and self.callbacks['show_error']:
                self.callbacks['show_error']("錯誤", f"匯入 Word 文檔失敗: {str(e)}")
            else:
                show_error("錯誤", f"匯入 Word 文檔失敗: {str(e)}", self.parent)

    # === 專案管理相關功能 ===

    def switch_project(self, confirm_callback: Optional[Callable] = None, switch_callback: Optional[Callable] = None) -> None:
        """
        切換專案
        :param confirm_callback: 確認是否可以切換專案的回調
        :param switch_callback: 切換專案的實際執行回調
        """
        try:
            # 如果有確認回調，先檢查是否可以切換
            if confirm_callback and not confirm_callback():
                return

            # 如果有切換回調，執行切換
            if switch_callback:
                switch_callback()
            else:
                if 'show_info' in self.callbacks and self.callbacks['show_info']:
                    self.callbacks['show_info']("資訊", "未提供切換專案的執行方法")
                else:
                    show_info("資訊", "未提供切換專案的執行方法", self.parent)

        except Exception as e:
            self.logger.error(f"切換專案時出錯: {e}")
            if 'show_error' in self.callbacks and self.callbacks['show_error']:
                self.callbacks['show_error']("錯誤", f"切換專案失敗: {str(e)}")
            else:
                show_error("錯誤", f"切換專案失敗: {str(e)}", self.parent)
    # === 實用工具方法 ===

    def load_corrections(self) -> Dict[str, str]:
        """載入校正數據庫"""
        corrections = {}
        try:
            if self.current_project_path:
                corrections_file = os.path.join(self.current_project_path, "corrections.csv")
                if os.path.exists(corrections_file):
                    with open(corrections_file, 'r', encoding='utf-8-sig') as file:
                        reader = csv.reader(file)
                        next(reader)  # 跳過標題行
                        for row in reader:
                            if len(row) >= 2:
                                error, correction = row
                                corrections[error] = correction
            return corrections
        except Exception as e:
            self.logger.error(f"載入校正數據庫失敗: {e}")
            return {}

    def clear_file_status(self) -> None:
        """清除檔案狀態"""
        self.srt_file_path = None
        self.audio_file_path = None
        self.word_file_path = None
        self.srt_imported = False
        self.audio_imported = False
        self.word_imported = False

        if self.callbacks['on_file_info_updated']:
            self.callbacks['on_file_info_updated']()