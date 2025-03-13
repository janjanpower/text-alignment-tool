# db_migration.py

import sys
import os

# 添加 src 目錄到 Python 路徑
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from sqlalchemy import Column, Boolean, DateTime, String, inspect, text
from db_manager import DatabaseManager

def add_columns_to_users_table():
    """向 users 表添加新欄位"""
    try:
        # 初始化數據庫連接
        db_manager = DatabaseManager()
        engine = db_manager.engine
        session = db_manager.get_session()

        print("連接數據庫成功")

        # 檢查並添加新欄位
        columns_to_add = [
            {'name': 'is_logged_in', 'type': 'BOOLEAN', 'default': 'FALSE'},
            {'name': 'is_premium', 'type': 'BOOLEAN', 'default': 'FALSE'},
            {'name': 'premium_start_date', 'type': 'TIMESTAMP'},
            {'name': 'premium_end_date', 'type': 'TIMESTAMP'},
            {'name': 'bank_account', 'type': 'VARCHAR(100)'}
        ]

        # 獲取用戶表中現有的列
        inspector = inspect(engine)
        existing_columns = [col['name'] for col in inspector.get_columns('users')]

        # 創建一個連接
        with engine.connect() as conn:
            # 開始一個事務
            with conn.begin():
                # 添加缺少的列
                for col_info in columns_to_add:
                    col_name = col_info['name']
                    if col_name not in existing_columns:
                        print(f"正在添加欄位: {col_name}")

                        # 使用 SQL 直接添加列
                        sql = None
                        if 'default' in col_info:
                            # 適應不同的數據庫類型
                            if 'sqlite' in str(engine.url).lower():
                                # SQLite 不支持 ALTER TABLE ADD COLUMN WITH DEFAULT 語法
                                # 先添加列
                                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_info['type']}"))
                                # 然後設置默認值
                                conn.execute(text(f"UPDATE users SET {col_name} = {col_info['default']}"))
                            else:
                                # PostgreSQL 和其他數據庫
                                sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_info['type']} DEFAULT {col_info['default']}"
                                conn.execute(text(sql))
                        else:
                            sql = f"ALTER TABLE users ADD COLUMN {col_name} {col_info['type']}"
                            conn.execute(text(sql))

                        print(f"已成功添加欄位: {col_name}")

        print("數據庫更新成功")

    except Exception as e:
        print(f"更新數據庫時出錯: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if session:
            session.close()

if __name__ == "__main__":
    add_columns_to_users_table()