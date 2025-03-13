"""支付服務模組"""

import datetime
import logging
import os
import csv
from typing import List, Dict, Any, Optional, Tuple

from ..database.db_manager import DatabaseManager
from ..database.models import User, PaymentRecord

class PaymentService:
    """處理付款和銀行轉帳的服務"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db_manager = DatabaseManager()
        self.session = self.db_manager.get_session()

    def __del__(self):
        """關閉資料庫連接"""
        self.db_manager.close_session(self.session)

    def check_bank_transfers(self) -> str:
        """
        檢查銀行轉帳記錄
        此方法應當與實際銀行API整合，或者從某處導入轉帳數據
        :return: 處理結果訊息
        """
        try:
            # 獲取銀行轉帳數據
            bank_transfers = self._get_bank_transfers()
            self.logger.info(f"獲取到 {len(bank_transfers)} 筆銀行轉帳數據")

            # 追蹤處理的轉帳數量
            processed_count = 0

            for transfer in bank_transfers:
                # 嘗試通過帳號或參考號匹配用戶
                user = self._find_matching_user(transfer)

                if user:
                    # 檢查是否已經處理過這筆轉帳
                    existing_payment = self.session.query(PaymentRecord).filter_by(
                        transaction_id=transfer['transaction_id']
                    ).first()

                    if not existing_payment:
                        # 創建付款記錄
                        payment = PaymentRecord(
                            user_id=user.id,
                            amount=transfer['amount'],
                            transaction_id=transfer['transaction_id'],
                            bank_reference=transfer['reference'],
                            status="pending"
                        )

                        self.session.add(payment)
                        self.session.commit()

                        # 計算訂閱時長（以月為單位，基於付款金額）
                        months = self._calculate_subscription_duration(transfer['amount'])

                        # 確認付款並更新用戶狀態
                        payment.status = "confirmed"
                        payment.verified_at = datetime.datetime.now()

                        # 更新用戶的付費狀態
                        now = datetime.datetime.now()
                        user.is_premium = True
                        user.premium_start_date = now

                        # 如果用戶已有付費期限且未過期，則延長期限
                        if user.premium_end_date and user.premium_end_date > now:
                            user.premium_end_date = user.premium_end_date + datetime.timedelta(days=30 * months)
                        else:
                            # 否則從當前日期開始計算
                            user.premium_end_date = now + datetime.timedelta(days=30 * months)

                        self.session.commit()
                        processed_count += 1

                        self.logger.info(f"用戶 {user.username} 的付款已確認，付費狀態已更新至 {user.premium_end_date}")

            return f"已處理 {processed_count} 筆轉帳"

        except Exception as e:
            self.logger.error(f"處理銀行轉帳時出錯: {e}")
            return f"處理銀行轉帳時出錯: {e}"

    def _calculate_subscription_duration(self, amount: float) -> int:
        """
        根據付款金額計算訂閱時長（月）
        :param amount: 支付金額
        :return: 訂閱月數
        """
        # 假設每月 299 元
        monthly_fee = 299.0

        # 計算月份，無條件進位至整數
        months = max(1, int(amount / monthly_fee + 0.5))

        return months

    def _get_bank_transfers(self) -> List[Dict[str, Any]]:
        """
        獲取銀行轉帳數據
        實際實作應與銀行API整合或讀取特定格式的文件
        :return: 轉帳數據列表
        """
        # 示例數據路徑 - 您需要更改為實際的文件路徑
        transfers_file = os.path.join(os.path.dirname(__file__), 'bank_transfers.csv')

        # 如果文件存在，讀取文件內容
        if os.path.exists(transfers_file):
            try:
                transfers = []
                with open(transfers_file, 'r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        # 假設CSV有這些列: account, amount, transaction_id, reference, date
                        transfers.append({
                            'account': row.get('account', ''),
                            'amount': float(row.get('amount', 0)),
                            'transaction_id': row.get('transaction_id', ''),
                            'reference': row.get('reference', ''),
                            'date': datetime.datetime.strptime(row.get('date', ''), '%Y-%m-%d')
                        })
                return transfers
            except Exception as e:
                self.logger.error(f"讀取轉帳數據時出錯: {e}")

        # 示例數據，實際應由真實銀行數據替換
        return [
            {
                'account': '123456789',
                'amount': 299.0,
                'transaction_id': 'T123456',
                'reference': 'USER001',  # 可能是用戶名或專用參考碼
                'date': datetime.datetime.now()
            },
            # 更多轉帳記錄...
        ]

    def _find_matching_user(self, transfer: Dict[str, Any]) -> Optional[User]:
        """
        根據轉帳數據尋找匹配的用戶
        :param transfer: 轉帳數據
        :return: 匹配的用戶對象，如果未找到則返回 None
        """
        # 嘗試通過銀行帳號匹配
        user = self.session.query(User).filter_by(bank_account=transfer['account']).first()

        # 如果找不到，嘗試通過參考號（可能是用戶名）匹配
        if not user and 'reference' in transfer:
            user = self.session.query(User).filter_by(username=transfer['reference']).first()

        return user

    def check_premium_expiry_for_all_users(self) -> int:
        """
        檢查所有用戶的付費狀態是否過期
        :return: 過期的用戶數量
        """
        users = self.session.query(User).filter_by(is_premium=True).all()

        now = datetime.datetime.now()
        expired_count = 0

        for user in users:
            if user.premium_end_date and now > user.premium_end_date:
                user.is_premium = False
                expired_count += 1
                self.logger.info(f"用戶 {user.username} 的付費已過期")

        self.session.commit()
        return expired_count