"""
事件類型定義模組
定義追蹤器使用的事件類型和數據結構
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal
from datetime import datetime


class EventType(Enum):
    """
    交易事件類型枚舉
    
    OPEN: 開倉 - 新建立一個倉位
    CLOSE: 平倉 - 完全關閉倉位
    INCREASE: 加倉 - 增加現有倉位
    DECREASE: 減倉 - 減少現有倉位（部分平倉）
    FLIP: 翻轉 - 從多轉空或從空轉多
    UNKNOWN: 未知事件類型
    """
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"
    FLIP = "FLIP"
    UNKNOWN = "UNKNOWN"


class Side(Enum):
    """
    交易方向枚舉
    
    LONG: 做多 - 預期價格上漲
    SHORT: 做空 - 預期價格下跌
    """
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class PositionEvent:
    """
    持倉變化事件
    
    當監聽的錢包有交易活動時，會產生這個事件
    """
    # 事件類型
    event_type: EventType
    # 交易對（如 ETH、BTC）
    symbol: str
    # 方向（LONG/SHORT）
    side: Side
    # 當前持倉數量
    size: Decimal
    # 進場/成交價格
    price: Decimal
    # 錢包地址
    wallet_address: str
    # 事件時間
    timestamp: datetime
    # 原始數據（調試用）
    raw_data: Optional[dict] = None
    
    def __str__(self) -> str:
        """格式化輸出"""
        return (
            f"[{self.event_type.value}] {self.symbol} {self.side.value} "
            f"| 數量: {self.size} | 價格: {self.price}"
        )


@dataclass
class WalletState:
    """
    錢包狀態
    
    存儲錢包的總資金和持倉信息
    """
    # 錢包地址
    address: str
    # 總權益（美元）
    account_value: Decimal
    # 可用餘額（美元）
    available_balance: Decimal
    # 持倉列表
    positions: list
    # 更新時間
    updated_at: datetime
    
    @property
    def total_position_value(self) -> Decimal:
        """計算總持倉價值"""
        total = Decimal("0")
        for pos in self.positions:
            if "positionValue" in pos:
                total += Decimal(str(pos["positionValue"]))
        return total
    
    @property
    def position_ratio(self) -> Decimal:
        """
        計算倉位比例
        公式：持倉價值 / 總權益
        """
        if self.account_value <= 0:
            return Decimal("0")
        return self.total_position_value / self.account_value

