# gui/components/columns.py

import tkinter as tk
from typing import Dict, Any

class ColumnConfig:
    """欄位配置管理器"""

    # 更新 COLUMNS 字典，添加比例權重
    COLUMNS = {
        'V.O': {'width': 50, 'stretch': False, 'anchor': 'center', 'weight': 0},
        'Index': {'width': 50, 'stretch': False, 'anchor': 'center', 'weight': 0},
        'Start': {'width': 100, 'stretch': False, 'anchor': 'center', 'weight': 0},
        'End': {'width': 100, 'stretch': False, 'anchor': 'center', 'weight': 0},
        'SRT Text': {'width': 180, 'stretch': True, 'anchor': 'w', 'weight': 3},
        'Word Text': {'width': 180, 'stretch': True, 'anchor': 'w', 'weight': 3},
        'Match': {'width': 200, 'stretch': True, 'anchor': 'center', 'weight': 2},
        'V/X': {'width': 50, 'stretch': False, 'anchor': 'center', 'weight': 0}
    }

    @classmethod
    def configure_column(cls, tree, column_name: str) -> None:
        """設定指定列的配置"""
        if column_name in cls.COLUMNS:
            config = cls.COLUMNS[column_name]
            tree.column(
                column_name,
                width=config['width'],
                stretch=config['stretch'],  # 使用配置中的 stretch 值
                anchor=config['anchor'],
                minwidth=50  # 設置一個合理的最小寬度
            )
            # 設定列標題
            tree.heading(column_name, text=column_name, anchor='center')

    @classmethod
    def calculate_column_widths(cls, tree, total_width: int, columns: list) -> Dict[str, int]:
        """
        計算各列應該分配的寬度

        :param tree: Treeview 控件
        :param total_width: 總可用寬度
        :param columns: 要顯示的列名列表
        :return: 列名到寬度的映射
        """
        # 計算不可伸縮列的總寬度
        fixed_width = sum(cls.COLUMNS[col]['width'] for col in columns if not cls.COLUMNS[col]['stretch'])

        # 可伸縮列的總權重
        total_weight = sum(cls.COLUMNS[col]['weight'] for col in columns if cls.COLUMNS[col]['stretch'])

        # 可伸縮列可分配的寬度
        stretchable_width = max(0, total_width - fixed_width)

        result = {}
        for col in columns:
            config = cls.COLUMNS[col]
            if config['stretch']:
                # 按權重分配寬度
                if total_weight > 0:
                    width = max(config['width'], int(stretchable_width * config['weight'] / total_weight))
                else:
                    width = config['width']
            else:
                width = config['width']
            result[col] = width

        return result