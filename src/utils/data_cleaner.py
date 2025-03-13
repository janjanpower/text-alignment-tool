"""數據清理相關模組"""

import logging

class DataResourceCleaner:
    """數據資源清理類別"""

    @staticmethod
    def clear_treeview_data(tree) -> None:
        """清理 Treeview 數據"""
        logger = logging.getLogger("DataResourceCleaner")
        try:
            for item in tree.get_children():
                tree.delete(item)
        except Exception as e:
            logger.error(f"清理 Treeview 數據時出錯: {e}")

    @staticmethod
    def clear_correction_states(manager) -> None:
        """清理校正狀態"""
        logger = logging.getLogger("DataResourceCleaner")
        try:
            if hasattr(manager, 'correction_states'):
                manager.correction_states.clear()
            if hasattr(manager, 'original_texts'):
                manager.original_texts.clear()
            if hasattr(manager, 'corrected_texts'):
                manager.corrected_texts.clear()
        except Exception as e:
            logger.error(f"清理校正狀態時出錯: {e}")