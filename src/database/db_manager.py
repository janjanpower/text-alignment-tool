import logging
# 改為這樣的絕對導入
import sys
import os


# 獲取項目根目錄並加入 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from database.base import Base, init_db
# 獲取項目根目錄並加入 Python 路徑
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 使用絕對導入
from services.config_manager import ConfigManager

from sqlalchemy.orm import sessionmaker, scoped_session


# 獲取 logger
logger = logging.getLogger(__name__)

class DatabaseManager:
    """資料庫管理器"""

    def __init__(self, connection_string=None):
        """
        初始化資料庫管理器
        :param connection_string: 資料庫連接字符串
        """
        # 先設置 logger 屬性
        self.logger = logger

        if connection_string is None:
            # 從配置文件獲取連接信息
            config = ConfigManager()

            # 輸出配置文件路徑，幫助调试
            self.logger.info(f"嘗試讀取配置文件: {config.config_file}")

            db_config = config.get("database", {})

            # 輸出讀取到的資料庫配置，幫助调试
            self.logger.info(f"讀取到的資料庫配置: {db_config}")

            if db_config:
                host = db_config.get("host", "localhost")
                port = db_config.get("port", 5432)
                username = db_config.get("username", "postgres")  # 改為通用預設值
                password = db_config.get("password", "")  # 從 config.json 讀取密碼

                # 輸出配置信息，但隱藏密碼
                masked_password = "*****" if password else ""
                self.logger.info(f"使用配置文件中的資料庫設定: {username}@{host}:{port}/")

                connection_string = f"postgresql://{username}:{password}@{host}:{port}/"
            else:
                # 嘗試使用 SQLite 作為備用方案
                import os
                db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "text_alignment.db")
                connection_string = f"sqlite:///{db_path}"
                self.logger.info(f"無法讀取資料庫配置，改用 SQLite: {db_path}")

            # 輸出最終使用的連接字串（隱藏密碼）
            display_conn_string = connection_string.replace(password, "*****") if password else connection_string
            self.logger.info(f"使用的連接字串: {display_conn_string}")

        try:
            self.engine = init_db(connection_string)
            self.session_factory = sessionmaker(bind=self.engine)
            self.Session = scoped_session(self.session_factory)
        except Exception as e:
            self.logger.error(f"數據庫連接失敗: {e}")

            # 嘗試使用 SQLite 作為備用方案（如果失敗是由於 PostgreSQL）
            if "postgresql" in connection_string.lower():
                try:
                    self.logger.info("嘗試切換到 SQLite 資料庫...")
                    import os
                    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "text_alignment.db")
                    sqlite_connection_string = f"sqlite:///{db_path}"

                    self.engine = init_db(sqlite_connection_string)
                    self.session_factory = sessionmaker(bind=self.engine)
                    self.Session = scoped_session(self.session_factory)

                    self.logger.info(f"成功切換到 SQLite 資料庫: {db_path}")
                except Exception as sqlite_error:
                    self.logger.error(f"切換到 SQLite 也失敗: {sqlite_error}")
                    raise
            else:
                raise

    def create_tables(self):
        """創建所有表"""
        try:
            Base.metadata.create_all(self.engine)
            self.logger.info("資料庫表創建成功")
            return True
        except Exception as e:
            self.logger.error(f"創建資料庫表時出錯: {e}")
            return False

    def get_session(self):
        """獲取資料庫會話"""
        return self.Session()

    def close_session(self, session):
        """關閉資料庫會話"""
        if session:
            session.close()