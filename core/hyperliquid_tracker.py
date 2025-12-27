"""
Hyperliquid 錢包追蹤器
監聽指定錢包的持倉變化
"""

import asyncio
import json
from typing import Optional, Callable, List
from decimal import Decimal
from datetime import datetime

from hyperliquid.info import Info
from hyperliquid.utils import constants

from utils.logger import logger
from core.events import EventType, Side, PositionEvent, WalletState


class HyperliquidTracker:
    """
    Hyperliquid 錢包追蹤器
    
    監聯指定錢包的持倉變化，當有交易發生時觸發回調
    """
    
    def __init__(
        self,
        wallet_addresses: List[str],
        testnet: bool = True,
        on_event: Optional[Callable[[PositionEvent], None]] = None
    ):
        """
        初始化追蹤器
        
        Args:
            wallet_addresses: 要追蹤的錢包地址列表
            testnet: 是否使用測試網（預設 True）
            on_event: 事件回調函數
        """
        self.wallet_addresses = [addr.lower() for addr in wallet_addresses]
        self.testnet = testnet
        self.on_event = on_event
        
        # 設定 API 端點
        self.base_url = constants.TESTNET_API_URL if testnet else constants.MAINNET_API_URL
        
        # Info API 客戶端
        self.info = Info(self.base_url, skip_ws=True)
        
        # 追蹤狀態
        self._running = False
        self._last_states: dict[str, WalletState] = {}
        
        # 輪詢間隔（秒）
        self.poll_interval = 2.0
        
        logger.info(f"✅ Hyperliquid 追蹤器初始化完成")
        logger.info(f"   網絡: {'測試網' if testnet else '主網'}")
        logger.info(f"   追蹤錢包數: {len(wallet_addresses)}")
    
    async def start(self) -> None:
        """
        啟動追蹤器
        使用輪詢方式監聽錢包狀態變化
        """
        self._running = True
        logger.info("🚀 追蹤器已啟動")
        
        # 初始化所有錢包的狀態
        for address in self.wallet_addresses:
            try:
                state = await self.get_wallet_state(address)
                self._last_states[address] = state
                logger.info(f"📊 初始狀態 {address[:10]}...: 權益=${state.account_value:.2f}")
            except Exception as e:
                logger.error(f"❌ 獲取初始狀態失敗 {address[:10]}...: {e}")
        
        # 開始輪詢
        while self._running:
            try:
                await self._poll_all_wallets()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 輪詢錯誤: {e}")
                await asyncio.sleep(5)  # 錯誤後等待 5 秒再重試
    
    async def stop(self) -> None:
        """停止追蹤器"""
        self._running = False
        logger.info("⏹️ 追蹤器已停止")
    
    async def _poll_all_wallets(self) -> None:
        """輪詢所有錢包"""
        for address in self.wallet_addresses:
            try:
                new_state = await self.get_wallet_state(address)
                old_state = self._last_states.get(address)
                
                if old_state:
                    # 比較狀態變化
                    events = self._detect_changes(old_state, new_state)
                    for event in events:
                        logger.info(f"📢 {event}")
                        if self.on_event:
                            self.on_event(event)
                
                self._last_states[address] = new_state
                
            except Exception as e:
                logger.error(f"❌ 輪詢 {address[:10]}... 失敗: {e}")
    
    async def get_wallet_state(self, address: str) -> WalletState:
        """
        獲取錢包狀態
        
        Args:
            address: 錢包地址
            
        Returns:
            WalletState 對象
        """
        # 使用同步 API（SDK 目前只支持同步）
        loop = asyncio.get_event_loop()
        user_state = await loop.run_in_executor(
            None,
            lambda: self.info.user_state(address)
        )
        
        # 解析數據
        margin_summary = user_state.get("marginSummary", {})
        account_value = Decimal(str(margin_summary.get("accountValue", "0")))
        
        # 計算可用餘額
        total_margin_used = Decimal(str(margin_summary.get("totalMarginUsed", "0")))
        available_balance = account_value - total_margin_used
        
        # 獲取持倉
        positions = user_state.get("assetPositions", [])
        
        return WalletState(
            address=address.lower(),
            account_value=account_value,
            available_balance=available_balance,
            positions=positions,
            updated_at=datetime.now()
        )
    
    def _detect_changes(
        self,
        old_state: WalletState,
        new_state: WalletState
    ) -> List[PositionEvent]:
        """
        檢測狀態變化
        
        比較新舊狀態，返回發生的事件列表
        """
        events = []
        
        # 將持倉轉換為字典方便比較
        old_positions = self._positions_to_dict(old_state.positions)
        new_positions = self._positions_to_dict(new_state.positions)
        
        # 檢查所有交易對
        all_symbols = set(old_positions.keys()) | set(new_positions.keys())
        
        for symbol in all_symbols:
            old_pos = old_positions.get(symbol)
            new_pos = new_positions.get(symbol)
            
            event = self._compare_position(
                symbol=symbol,
                old_pos=old_pos,
                new_pos=new_pos,
                wallet_address=new_state.address
            )
            
            if event:
                events.append(event)
        
        return events
    
    def _positions_to_dict(self, positions: list) -> dict:
        """將持倉列表轉換為字典（以 symbol 為 key）"""
        result = {}
        for pos in positions:
            position_data = pos.get("position", {})
            coin = position_data.get("coin", "")
            if coin:
                result[coin] = position_data
        return result
    
    def _compare_position(
        self,
        symbol: str,
        old_pos: Optional[dict],
        new_pos: Optional[dict],
        wallet_address: str
    ) -> Optional[PositionEvent]:
        """
        比較單個交易對的倉位變化
        
        返回對應的事件，如果沒有變化返回 None
        """
        old_size = Decimal(str(old_pos.get("szi", "0"))) if old_pos else Decimal("0")
        new_size = Decimal(str(new_pos.get("szi", "0"))) if new_pos else Decimal("0")
        
        # 沒有變化
        if old_size == new_size:
            return None
        
        # 確定方向和事件類型
        new_entry_price = Decimal(str(new_pos.get("entryPx", "0"))) if new_pos else Decimal("0")
        
        # 判斷方向
        if new_size > 0:
            side = Side.LONG
        elif new_size < 0:
            side = Side.SHORT
        else:
            # 新倉位為 0，使用舊倉位的方向
            side = Side.LONG if old_size > 0 else Side.SHORT
        
        # 判斷事件類型
        event_type = self._determine_event_type(old_size, new_size)
        
        return PositionEvent(
            event_type=event_type,
            symbol=symbol,
            side=side,
            size=abs(new_size),
            price=new_entry_price,
            wallet_address=wallet_address,
            timestamp=datetime.now(),
            raw_data=new_pos
        )
    
    def _determine_event_type(
        self,
        old_size: Decimal,
        new_size: Decimal
    ) -> EventType:
        """判斷事件類型"""
        # 之前沒有倉位 → 開倉
        if old_size == 0 and new_size != 0:
            return EventType.OPEN
        
        # 現在沒有倉位 → 平倉
        if old_size != 0 and new_size == 0:
            return EventType.CLOSE
        
        # 方向改變（從正變負或從負變正）→ 翻轉
        if (old_size > 0 and new_size < 0) or (old_size < 0 and new_size > 0):
            return EventType.FLIP
        
        # 同方向，數量增加 → 加倉
        if abs(new_size) > abs(old_size):
            return EventType.INCREASE
        
        # 同方向，數量減少 → 減倉
        if abs(new_size) < abs(old_size):
            return EventType.DECREASE
        
        return EventType.UNKNOWN

