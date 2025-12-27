"""
策略引擎
處理跟單決策邏輯，包含倉位計算、交易對鎖定、跟單判斷
"""

import asyncio
from typing import Optional, Tuple, Dict
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from core.events import EventType, Side, PositionEvent, WalletState
from core.lighter_trader import LighterTrader, OrderSide, OrderResult
from database.db_manager import DatabaseManager
from utils.logger import logger


class FollowDecision(Enum):
    """跟單決策結果"""
    FOLLOW = "FOLLOW"           # 執行跟單
    SKIP = "SKIP"               # 跳過（不符合條件但非錯誤）
    REJECT = "REJECT"           # 拒絕（條件不滿足）
    ERROR = "ERROR"             # 錯誤


@dataclass
class FollowResult:
    """跟單結果"""
    decision: FollowDecision
    reason: str
    follow_size: Optional[Decimal] = None
    follow_side: Optional[OrderSide] = None
    order_result: Optional[OrderResult] = None


class StrategyEngine:
    """
    策略引擎
    
    負責處理跟單決策邏輯：
    1. 接收錢包事件
    2. 判斷是否跟單
    3. 計算跟單數量
    4. 執行交易
    """
    
    def __init__(
        self,
        db_manager: DatabaseManager,
        lighter_trader: LighterTrader,
        default_max_position_usd: Decimal = Decimal("1000"),
        default_stop_loss_ratio: Decimal = Decimal("0.5")
    ):
        """
        初始化策略引擎
        
        Args:
            db_manager: 數據庫管理器
            lighter_trader: Lighter 交易執行器
            default_max_position_usd: 預設單筆最大跟單金額
            default_stop_loss_ratio: 預設止損比例
        """
        self.db_manager = db_manager
        self.lighter_trader = lighter_trader
        self.default_max_position_usd = default_max_position_usd
        self.default_stop_loss_ratio = default_stop_loss_ratio
        
        # 緩存我的總資金（定期更新）
        self._my_balance: Decimal = Decimal("0")
        self._balance_updated_at: float = 0
        self._balance_cache_seconds: float = 60  # 餘額緩存時間
        
        logger.info("✅ 策略引擎初始化完成")
        logger.info(f"   預設最大跟單金額: ${default_max_position_usd}")
        logger.info(f"   預設止損比例: {default_stop_loss_ratio * 100}%")
    
    async def on_wallet_event(self, event: PositionEvent) -> FollowResult:
        """
        處理錢包事件入口
        
        這是策略引擎的主要入口點，當追蹤器檢測到錢包事件時調用
        
        Args:
            event: 持倉變化事件
            
        Returns:
            FollowResult 跟單結果
        """
        logger.info(f"📥 收到事件: {event}")
        
        try:
            # 步驟 1：判斷是否應該跟單
            should_follow, reason = await self.should_follow(event)
            
            if not should_follow:
                logger.info(f"⏭️ 跳過跟單: {reason}")
                return FollowResult(
                    decision=FollowDecision.SKIP,
                    reason=reason
                )
            
            # 步驟 2：計算跟單數量和方向
            follow_size, follow_side = await self.calculate_follow_params(event)
            
            if follow_size <= 0:
                logger.info("⏭️ 跳過跟單: 計算後跟單數量為 0")
                return FollowResult(
                    decision=FollowDecision.SKIP,
                    reason="計算後跟單數量為 0"
                )
            
            # 步驟 3：執行跟單
            result = await self.execute_follow(event, follow_size, follow_side)
            
            return result
            
        except Exception as e:
            logger.exception(f"❌ 處理事件時發生錯誤: {e}")
            return FollowResult(
                decision=FollowDecision.ERROR,
                reason=str(e)
            )
    
    async def should_follow(self, event: PositionEvent) -> Tuple[bool, str]:
        """
        判斷是否應該跟單
        
        檢查清單：
        1. 錢包是否啟用
        2. 交易對是否被其他錢包鎖定
        3. 餘額是否充足
        4. 事件類型是否需要跟單
        
        Args:
            event: 持倉變化事件
            
        Returns:
            (是否跟單, 原因)
        """
        # 檢查 1：錢包是否啟用
        wallet = await self.db_manager.get_wallet(event.wallet_address)
        
        if wallet is None:
            return False, f"錢包未在追蹤列表中: {event.wallet_address[:10]}..."
        
        if not wallet.get("enabled", False):
            return False, f"錢包已禁用: {event.wallet_address[:10]}..."
        
        # 檢查 2：交易對鎖定
        is_locked, lock_reason = await self.check_position_lock(
            event.symbol, 
            event.wallet_address
        )
        
        if is_locked:
            return False, lock_reason
        
        # 檢查 3：餘額是否充足
        my_balance = await self._get_my_balance()
        
        if my_balance <= 0:
            return False, "餘額不足"
        
        # 檢查 4：事件類型
        # UNKNOWN 事件不處理
        if event.event_type == EventType.UNKNOWN:
            return False, "未知事件類型"
        
        return True, "OK"
    
    async def check_position_lock(
        self, 
        symbol: str, 
        wallet_address: str
    ) -> Tuple[bool, str]:
        """
        檢查交易對是否被鎖定
        
        鎖定規則：
        - 同一交易對只能跟隨第一個開倉的錢包
        - 直到該錢包完全平倉後，其他錢包才能觸發該交易對的跟單
        
        Args:
            symbol: 交易對符號
            wallet_address: 當前事件的錢包地址
            
        Returns:
            (是否被鎖定, 原因)
        """
        # 查詢數據庫中該交易對的現有持倉
        existing_position = await self.db_manager.get_position(symbol)
        
        if existing_position is None:
            # 沒有持倉，不鎖定
            return False, ""
        
        # 有持倉，檢查來源錢包是否相同
        source_wallet = existing_position.get("source_wallet", "").lower()
        
        if source_wallet == wallet_address.lower():
            # 來源相同，不鎖定（允許加減倉）
            return False, ""
        
        # 來源不同，鎖定
        return True, f"{symbol} 已被其他錢包鎖定: {source_wallet[:10]}..."
    
    async def calculate_follow_params(
        self, 
        event: PositionEvent
    ) -> Tuple[Decimal, OrderSide]:
        """
        計算跟單參數（數量和方向）
        
        Args:
            event: 持倉變化事件
            
        Returns:
            (跟單數量, 跟單方向)
        """
        # 根據事件類型決定如何計算
        
        if event.event_type == EventType.CLOSE:
            # 平倉事件：全部平倉
            return await self._calculate_close_params(event)
        
        elif event.event_type == EventType.OPEN:
            # 開倉事件：計算新開倉數量
            return await self._calculate_open_params(event)
        
        elif event.event_type == EventType.INCREASE:
            # 加倉事件：計算加倉數量
            return await self._calculate_increase_params(event)
        
        elif event.event_type == EventType.DECREASE:
            # 減倉事件：計算減倉數量
            return await self._calculate_decrease_params(event)
        
        elif event.event_type == EventType.FLIP:
            # 翻轉事件：先平倉再開倉（這裡只計算平倉部分）
            return await self._calculate_flip_params(event)
        
        else:
            return Decimal("0"), OrderSide.BUY
    
    async def _calculate_close_params(
        self, 
        event: PositionEvent
    ) -> Tuple[Decimal, OrderSide]:
        """計算平倉參數"""
        # 查詢我當前在該交易對的持倉
        my_positions = await self.lighter_trader.get_positions()
        
        for pos in my_positions:
            if pos.symbol.upper() == event.symbol.upper():
                # 平倉方向：與持倉方向相反
                if pos.side == "LONG":
                    return pos.size, OrderSide.SELL
                else:
                    return pos.size, OrderSide.BUY
        
        # 沒有持倉
        return Decimal("0"), OrderSide.BUY
    
    async def _calculate_open_params(
        self, 
        event: PositionEvent
    ) -> Tuple[Decimal, OrderSide]:
        """計算開倉參數"""
        # 計算跟單金額
        follow_usd = await self.calculate_follow_size(event)
        
        if follow_usd <= 0:
            return Decimal("0"), OrderSide.BUY
        
        # 獲取當前價格
        price = await self.lighter_trader.get_market_price(event.symbol)
        
        if price is None or price <= 0:
            logger.warning(f"⚠️ 無法獲取 {event.symbol} 價格")
            return Decimal("0"), OrderSide.BUY
        
        # 計算數量 = 金額 / 價格
        follow_size = follow_usd / price
        
        # 確定方向
        if event.side == Side.LONG:
            follow_side = OrderSide.BUY
        else:
            follow_side = OrderSide.SELL
        
        return follow_size, follow_side
    
    async def _calculate_increase_params(
        self, 
        event: PositionEvent
    ) -> Tuple[Decimal, OrderSide]:
        """計算加倉參數（與開倉類似）"""
        return await self._calculate_open_params(event)
    
    async def _calculate_decrease_params(
        self, 
        event: PositionEvent
    ) -> Tuple[Decimal, OrderSide]:
        """計算減倉參數"""
        # 獲取我當前的持倉
        my_positions = await self.lighter_trader.get_positions()
        
        for pos in my_positions:
            if pos.symbol.upper() == event.symbol.upper():
                # 計算減倉比例
                # 這裡簡化處理：按比例減倉
                # 實際上可能需要更複雜的計算
                
                # 假設減倉 50%（簡化處理）
                reduce_size = pos.size * Decimal("0.5")
                
                # 減倉方向：與持倉方向相反
                if pos.side == "LONG":
                    return reduce_size, OrderSide.SELL
                else:
                    return reduce_size, OrderSide.BUY
        
        return Decimal("0"), OrderSide.BUY
    
    async def _calculate_flip_params(
        self, 
        event: PositionEvent
    ) -> Tuple[Decimal, OrderSide]:
        """計算翻轉參數（先平倉）"""
        # 翻轉時，先平掉現有持倉
        return await self._calculate_close_params(event)
    
    async def calculate_follow_size(self, event: PositionEvent) -> Decimal:
        """
        計算跟單金額
        
        公式：跟單金額 = 我的總資金 × 聰明錢包倉位比例
        
        Args:
            event: 持倉變化事件
            
        Returns:
            跟單金額（USD）
        """
        # 獲取我的餘額
        my_balance = await self._get_my_balance()
        
        if my_balance <= 0:
            return Decimal("0")
        
        # 獲取錢包配置
        wallet = await self.db_manager.get_wallet(event.wallet_address)
        max_position_usd = Decimal(str(
            wallet.get("max_position_usd") or self.default_max_position_usd
        ))
        
        # 計算聰明錢包的倉位比例
        # 這裡使用事件中的資訊（需要從追蹤器傳遞）
        # 簡化處理：使用固定的 10% 比例
        # TODO: 從追蹤器獲取實際的倉位比例
        position_ratio = Decimal("0.1")  # 10%
        
        # 計算跟單金額
        follow_usd = my_balance * position_ratio
        
        # 限制最大金額
        if follow_usd > max_position_usd:
            follow_usd = max_position_usd
            logger.info(f"⚠️ 跟單金額超過限制，調整為 ${max_position_usd}")
        
        logger.info(f"💰 計算跟單金額: ${follow_usd:.2f} (餘額 ${my_balance:.2f} × {position_ratio*100:.1f}%)")
        
        return follow_usd
    
    async def execute_follow(
        self, 
        event: PositionEvent,
        follow_size: Decimal,
        follow_side: OrderSide
    ) -> FollowResult:
        """
        執行跟單交易
        
        Args:
            event: 原始事件
            follow_size: 跟單數量
            follow_side: 跟單方向
            
        Returns:
            FollowResult 跟單結果
        """
        try:
            logger.info(f"📤 執行跟單: {follow_side.value} {follow_size} {event.symbol}")
            
            # 判斷是平倉還是開倉
            is_close = event.event_type in [EventType.CLOSE, EventType.FLIP]
            
            if is_close:
                # 平倉
                order_result = await self.lighter_trader.close_position(event.symbol)
            else:
                # 開倉/加倉
                order_result = await self.lighter_trader.place_market_order(
                    symbol=event.symbol,
                    side=follow_side,
                    size=follow_size
                )
            
            if order_result.success:
                # 更新數據庫
                await self._update_position_in_db(event, follow_size, follow_side, is_close)
                
                logger.info(f"✅ 跟單成功: {follow_side.value} {follow_size} {event.symbol}")
                
                return FollowResult(
                    decision=FollowDecision.FOLLOW,
                    reason="跟單成功",
                    follow_size=follow_size,
                    follow_side=follow_side,
                    order_result=order_result
                )
            else:
                logger.error(f"❌ 跟單失敗: {order_result.error}")
                
                return FollowResult(
                    decision=FollowDecision.ERROR,
                    reason=f"下單失敗: {order_result.error}",
                    order_result=order_result
                )
                
        except Exception as e:
            logger.exception(f"❌ 執行跟單時發生錯誤: {e}")
            return FollowResult(
                decision=FollowDecision.ERROR,
                reason=str(e)
            )
    
    async def _update_position_in_db(
        self, 
        event: PositionEvent,
        size: Decimal,
        side: OrderSide,
        is_close: bool
    ):
        """更新數據庫中的持倉記錄"""
        try:
            if is_close:
                # 平倉：移除持倉記錄
                await self.db_manager.remove_position(
                    event.symbol, 
                    event.wallet_address
                )
            else:
                # 開倉/加倉：添加或更新持倉記錄
                position_data = {
                    "symbol": event.symbol,
                    "side": "LONG" if side == OrderSide.BUY else "SHORT",
                    "size": float(size),
                    "entry_price": float(event.price),
                    "source_wallet": event.wallet_address
                }
                await self.db_manager.add_position(position_data)
                
        except Exception as e:
            logger.error(f"❌ 更新數據庫持倉記錄失敗: {e}")
    
    async def _get_my_balance(self) -> Decimal:
        """獲取我的餘額（帶緩存）"""
        import time
        current_time = time.time()
        
        # 檢查緩存是否過期
        if current_time - self._balance_updated_at > self._balance_cache_seconds:
            try:
                self._my_balance = await self.lighter_trader.get_balance()
                self._balance_updated_at = current_time
                logger.debug(f"💰 更新餘額緩存: ${self._my_balance:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ 獲取餘額失敗，使用緩存值: {e}")
        
        return self._my_balance
    
    async def check_stop_loss(self, symbol: str) -> bool:
        """
        檢查是否需要止損
        
        Args:
            symbol: 交易對符號
            
        Returns:
            是否需要止損
        """
        try:
            # 獲取我當前的持倉
            my_positions = await self.lighter_trader.get_positions()
            
            for pos in my_positions:
                if pos.symbol.upper() == symbol.upper():
                    # 計算虧損比例
                    if pos.position_value > 0:
                        loss_ratio = pos.unrealized_pnl / pos.position_value
                        
                        if loss_ratio <= -self.default_stop_loss_ratio:
                            logger.warning(
                                f"⚠️ {symbol} 觸發止損！"
                                f"虧損 {abs(loss_ratio)*100:.1f}% >= {self.default_stop_loss_ratio*100:.1f}%"
                            )
                            return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ 檢查止損失敗: {e}")
            return False
    
    async def force_stop_loss(self, symbol: str) -> OrderResult:
        """
        強制止損平倉
        
        Args:
            symbol: 交易對符號
            
        Returns:
            OrderResult 平倉結果
        """
        logger.warning(f"🛑 執行強制止損: {symbol}")
        return await self.lighter_trader.close_position(symbol)

