"""付費狀態檢查腳本"""

import logging
import datetime
import sys
import os

# 添加項目根目錄到路徑中，以便導入項目模組
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ..services.payment_service import PaymentService
from ..database.db_manager import DatabaseManager
from ..database.models import User

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='logs/premium_check.log'
)
logger = logging.getLogger('premium_check')

def main():
    """執行付費狀態檢查"""
    logger.info("開始檢查付費狀態和銀行轉帳")

    try:
        payment_service = PaymentService()

        # 檢查銀行轉帳
        result = payment_service.check_bank_transfers()
        logger.info(f"銀行轉帳檢查結果: {result}")

        # 檢查付費狀態過期
        expired_count = payment_service.check_premium_expiry_for_all_users()
        logger.info(f"檢查完成: {expired_count} 個用戶付費已過期")

    except Exception as e:
        logger.error(f"檢查過程中出錯: {e}", exc_info=True)

if __name__ == "__main__":
    main()