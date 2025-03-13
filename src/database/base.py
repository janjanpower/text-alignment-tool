from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool import QueuePool

# 創建基類
Base = declarative_base()

def init_db(connection_string):
    """初始化資料庫"""
    # 檢查是否使用 SQLite
    is_sqlite = connection_string.startswith('sqlite://')

    # 創建引擎，對 SQLite 使用不同的參數
    if is_sqlite:
        engine = create_engine(
            connection_string,
            connect_args={"check_same_thread": False},  # 允許多線程訪問 SQLite
        )
    else:
        engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=5,          # 連接池大小
            max_overflow=10,      # 最大超出連接數
            pool_timeout=30,      # 連接超時（秒）
            pool_recycle=1800,    # 連接回收時間（秒）
            pool_pre_ping=True    # 預先測試連接是否有效
        )

        # 設置特定於 PostgreSQL 的參數
        @event.listens_for(engine, "connect")
        def set_pg_params(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("SET timezone='UTC'")  # 設置時區
            cursor.close()

    # 創建所有表
    Base.metadata.create_all(engine)
    return engine