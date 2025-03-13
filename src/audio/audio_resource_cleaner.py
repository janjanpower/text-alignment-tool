"""音頻資源清理模組"""

import os
import logging
import time
import pygame
from typing import Optional

class AudioResourceCleaner:
    """音頻資源清理類別"""

    @staticmethod
    def cleanup_audio(temp_file: Optional[str] = None) -> None:
        """清理音頻相關資源"""
        logger = logging.getLogger("AudioResourceCleaner")
        try:
            if temp_file:
                if os.path.exists(temp_file):
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    time.sleep(0.1)  # 短暫延遲確保檔案解除鎖定
                    os.remove(temp_file)

            pygame.mixer.quit()

        except Exception as e:
            logger.error(f"清理音頻資源時出錯: {e}")