"""
Lighter 交易執行器
在 Lighter 交易所執行跟單交易
"""

import asyncio
import time
from typing import Optional, Dict, List, Tuple
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

from lighter import ApiClient, AccountApi, OrderApi, InfoApi
from lighter.configuration import Configuration
from lighter.signer_client import SignerClient

from utils.logger import logger


class OrderSide(Enum):
    """訂單方向"""
    BUY = "BUY"    # 買入（做多）
    SELL = "SELL"  # 賣出（做空）


@dataclass
class AccountInfo:
    """帳戶資訊"""
    account_index: int
    collateral: Decimal           # 總抵押品（USDC）
    available_balance: Decimal    # 可用餘額
    total_position_value: Decimal # 總持倉價值
    unrealized_pnl: Decimal       # 未實現盈虧


@dataclass
class Position:
    """持倉資訊"""
    market_index: int        # 市場索引
    symbol: str              # 交易對符號
    side: str                # 方向（LONG/SHORT）
    size: Decimal            # 持倉數量
    entry_price: Decimal     # 平均進場價
    position_value: Decimal  # 持倉價值
    unrealized_pnl: Decimal  # 未實現盈虧


@dataclass
class OrderResult:
    """訂單結果"""
    success: bool
    order_id: Optional[str] = None
    tx_hash: Optional[str] = None
    error: Optional[str] = None


class LighterTrader:
    """
    Lighter 交易執行器
    
    負責在 Lighter 交易所上執行交易操作
    """
    
    # 預設 API URL
    MAINNET_URL = "https://mainnet.zklighter.elliot.ai"
    TESTNET_URL = "https://testnet.zklighter.elliot.ai"
    
    # 價格精度（小數點位數）
    PRICE_SCALE = 1e8
    # USDC 精度
    USDC_SCALE = 1e6
    
    # 市場索引對照表（需要根據實際 Lighter 市場更新）
    MARKET_INDEX = {
        "BTC": 0,
        "ETH": 1,
        # 其他市場索引可以之後添加
    }
    
    def __init__(
        self,
        api_private_key: str,
        account_index: int,
        api_key_index: int = 3,
        testnet: bool = True,
        max_retries: int = 5,
        retry_delay: float = 3.0
    ):
        """
        初始化 Lighter 交易執行器
        
        Args:
            api_private_key: API 私鑰（用於簽名交易）
            account_index: Lighter 帳戶索引
            api_key_index: API 密鑰索引（3-254 可用，預設 3）
            testnet: 是否使用測試網（預設 True）
            max_retries: 最大重試次數（預設 5）
            retry_delay: 重試間隔秒數（預設 3.0）
        """
        self.api_private_key = api_private_key
        self.account_index = account_index
        self.api_key_index = api_key_index
        self.testnet = testnet
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # API URL
        self.url = self.TESTNET_URL if testnet else self.MAINNET_URL
        
        # API 客戶端（用於查詢）
        self.config = Configuration(host=self.url)
        self.api_client = ApiClient(configuration=self.config)
        self.account_api = AccountApi(self.api_client)
        self.order_api = OrderApi(self.api_client)
        self.info_api = InfoApi(self.api_client)
        
        # SignerClient（用於下單）- 延遲初始化
        self._signer_client: Optional[SignerClient] = None
        
        # 訂單計數器（用於生成唯一的 client_order_index）
        self._order_counter = int(time.time() * 1000)
        
        logger.info(f"✅ Lighter 交易執行器初始化完成")
        logger.info(f"   網絡: {'測試網' if testnet else '主網'}")
        logger.info(f"   帳戶索引: {account_index}")
    
    def _get_signer_client(self) -> SignerClient:
        """
        獲取或創建 SignerClient
        延遲初始化，只在需要下單時才創建
        """
        if self._signer_client is None:
            self._signer_client = SignerClient(
                url=self.url,
                account_index=self.account_index,
                api_private_keys={self.api_key_index: self.api_private_key}
            )
            logger.debug("SignerClient 初始化完成")
        return self._signer_client
    
    def _generate_client_order_index(self) -> int:
        """生成唯一的 client_order_index"""
        self._order_counter += 1
        return self._order_counter
    
    async def _retry_operation(self, operation, operation_name: str):
        """
        帶重試機制的操作執行器
        
        Args:
            operation: 要執行的異步操作
            operation_name: 操作名稱（用於日誌）
        """
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ {operation_name} 失敗（第 {attempt}/{self.max_retries} 次）: {e}")
                
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
        
        logger.error(f"❌ {operation_name} 最終失敗: {last_error}")
        raise last_error
    
    async def get_account_info(self) -> Optional[AccountInfo]:
        """
        獲取帳戶資訊
        
        Returns:
            AccountInfo 對象，或 None（如果查詢失敗）
        """
        try:
            async def _get_account():
                result = await self.account_api.account(
                    by="index",
                    value=str(self.account_index)
                )
                return result
            
            result = await self._retry_operation(_get_account, "獲取帳戶資訊")
            
            if result and result.accounts and len(result.accounts) > 0:
                account = result.accounts[0]
                
                # 解析餘額資訊
                collateral = Decimal(str(account.collateral or "0"))
                
                # 計算總持倉價值和未實現盈虧
                total_position_value = Decimal("0")
                unrealized_pnl = Decimal("0")
                
                if account.positions:
                    for pos in account.positions:
                        if pos.position_value:
                            total_position_value += Decimal(str(pos.position_value))
                        if pos.unrealized_pn_l:
                            unrealized_pnl += Decimal(str(pos.unrealized_pn_l))
                
                # 計算可用餘額（簡化計算）
                available_balance = collateral + unrealized_pnl
                
                return AccountInfo(
                    account_index=self.account_index,
                    collateral=collateral,
                    available_balance=available_balance,
                    total_position_value=total_position_value,
                    unrealized_pnl=unrealized_pnl
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 獲取帳戶資訊失敗: {e}")
            return None
    
    async def get_balance(self) -> Decimal:
        """
        獲取可用餘額
        
        Returns:
            可用餘額（USDC）
        """
        account_info = await self.get_account_info()
        if account_info:
            return account_info.available_balance
        return Decimal("0")
    
    async def get_positions(self) -> List[Position]:
        """
        獲取當前所有持倉
        
        Returns:
            持倉列表
        """
        positions = []
        
        try:
            async def _get_account():
                return await self.account_api.account(
                    by="index",
                    value=str(self.account_index)
                )
            
            result = await self._retry_operation(_get_account, "獲取持倉")
            
            if result and result.accounts and len(result.accounts) > 0:
                account = result.accounts[0]
                
                if account.positions:
                    for pos in account.positions:
                        # 只處理有持倉的市場
                        position_size = Decimal(str(pos.position or "0"))
                        if position_size == 0:
                            continue
                        
                        # 判斷方向：sign = 1 是 LONG，-1 是 SHORT
                        sign = int(pos.sign or 0)
                        side = "LONG" if sign > 0 else "SHORT"
                        
                        positions.append(Position(
                            market_index=int(pos.market_index or 0),
                            symbol=self._get_symbol_by_market_index(int(pos.market_index or 0)),
                            side=side,
                            size=abs(position_size),
                            entry_price=Decimal(str(pos.avg_entry_price or "0")),
                            position_value=Decimal(str(pos.position_value or "0")),
                            unrealized_pnl=Decimal(str(pos.unrealized_pn_l or "0"))
                        ))
            
        except Exception as e:
            logger.error(f"❌ 獲取持倉失敗: {e}")
        
        return positions
    
    def _get_symbol_by_market_index(self, market_index: int) -> str:
        """根據市場索引獲取交易對符號"""
        for symbol, index in self.MARKET_INDEX.items():
            if index == market_index:
                return symbol
        return f"UNKNOWN_{market_index}"
    
    def _get_market_index(self, symbol: str) -> int:
        """根據交易對符號獲取市場索引"""
        # 移除常見後綴
        clean_symbol = symbol.upper().replace("-PERP", "").replace("/USDC", "").replace("-USD", "")
        
        if clean_symbol in self.MARKET_INDEX:
            return self.MARKET_INDEX[clean_symbol]
        
        raise ValueError(f"未知的交易對: {symbol}")
    
    async def get_market_price(self, symbol: str) -> Optional[Decimal]:
        """
        獲取當前市場價格
        
        Args:
            symbol: 交易對符號（如 "ETH"）
            
        Returns:
            當前價格，或 None（如果查詢失敗）
        """
        try:
            market_index = self._get_market_index(symbol)
            
            async def _get_orderbook():
                return await self.order_api.order_book_orders(
                    market_index=market_index,
                    limit=1
                )
            
            orderbook = await self._retry_operation(_get_orderbook, f"獲取 {symbol} 價格")
            
            if orderbook:
                # 取買賣盤中間價
                best_bid = Decimal(str(orderbook.bids[0].price).replace(".", "")) if orderbook.bids else None
                best_ask = Decimal(str(orderbook.asks[0].price).replace(".", "")) if orderbook.asks else None
                
                if best_bid and best_ask:
                    return (best_bid + best_ask) / 2
                elif best_bid:
                    return best_bid
                elif best_ask:
                    return best_ask
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 獲取 {symbol} 價格失敗: {e}")
            return None
    
    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        size: Decimal,
        reduce_only: bool = False,
        max_slippage: float = 0.01  # 預設 1% 滑點
    ) -> OrderResult:
        """
        下市價單
        
        Args:
            symbol: 交易對符號（如 "ETH"）
            side: 訂單方向（BUY/SELL）
            size: 數量（以基礎資產計）
            reduce_only: 是否僅減倉
            max_slippage: 最大滑點（預設 1%）
            
        Returns:
            OrderResult 對象
        """
        try:
            market_index = self._get_market_index(symbol)
            client_order_index = self._generate_client_order_index()
            
            # 轉換數量為整數（乘以精度）
            base_amount = int(size * Decimal(str(self.PRICE_SCALE)))
            
            # 獲取當前價格來計算執行價格
            current_price = await self.get_market_price(symbol)
            if current_price is None:
                return OrderResult(success=False, error="無法獲取當前價格")
            
            # 計算帶滑點的執行價格
            # is_ask = True 表示賣出，價格應該往下（乘以 1-slippage）
            # is_ask = False 表示買入，價格應該往上（乘以 1+slippage）
            is_ask = (side == OrderSide.SELL)
            
            if is_ask:
                # 賣出：接受更低的價格
                execution_price = int(current_price * Decimal(str(1 - max_slippage)))
            else:
                # 買入：接受更高的價格
                execution_price = int(current_price * Decimal(str(1 + max_slippage)))
            
            logger.info(f"📤 下單: {side.value} {size} {symbol} @ 市價（滑點 {max_slippage*100}%）")
            
            # 下市價單
            signer = self._get_signer_client()
            
            async def _place_order():
                return await signer.create_market_order(
                    market_index=market_index,
                    client_order_index=client_order_index,
                    base_amount=base_amount,
                    avg_execution_price=execution_price,
                    is_ask=is_ask,
                    reduce_only=reduce_only
                )
            
            created_order, response, error = await self._retry_operation(_place_order, "下單")
            
            if error:
                logger.error(f"❌ 下單失敗: {error}")
                return OrderResult(success=False, error=error)
            
            if response and response.code == 200:
                logger.info(f"✅ 下單成功: {side.value} {size} {symbol}")
                return OrderResult(
                    success=True,
                    order_id=str(client_order_index),
                    tx_hash=response.tx_hash if hasattr(response, 'tx_hash') else None
                )
            else:
                error_msg = f"下單響應異常: {response}"
                logger.error(f"❌ {error_msg}")
                return OrderResult(success=False, error=error_msg)
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 下單異常: {error_msg}")
            return OrderResult(success=False, error=error_msg)
    
    async def close_position(self, symbol: str) -> OrderResult:
        """
        平倉指定交易對的持倉
        
        Args:
            symbol: 交易對符號（如 "ETH"）
            
        Returns:
            OrderResult 對象
        """
        try:
            # 獲取當前持倉
            positions = await self.get_positions()
            
            # 找到對應的持倉
            target_position = None
            for pos in positions:
                if pos.symbol.upper() == symbol.upper():
                    target_position = pos
                    break
            
            if target_position is None:
                logger.warning(f"⚠️ 沒有 {symbol} 的持倉需要平倉")
                return OrderResult(success=True)  # 沒有持倉也算成功
            
            # 平倉：方向相反，reduce_only = True
            if target_position.side == "LONG":
                close_side = OrderSide.SELL
            else:
                close_side = OrderSide.BUY
            
            logger.info(f"📤 平倉: {target_position.side} {target_position.size} {symbol}")
            
            return await self.place_market_order(
                symbol=symbol,
                side=close_side,
                size=target_position.size,
                reduce_only=True
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 平倉失敗: {error_msg}")
            return OrderResult(success=False, error=error_msg)
    
    async def close_all_positions(self) -> Dict[str, OrderResult]:
        """
        平倉所有持倉
        
        Returns:
            字典，key 為交易對符號，value 為 OrderResult
        """
        results = {}
        positions = await self.get_positions()
        
        for position in positions:
            result = await self.close_position(position.symbol)
            results[position.symbol] = result
        
        return results
    
    async def close(self):
        """關閉客戶端連接"""
        try:
            if self._signer_client:
                await self._signer_client.close()
                self._signer_client = None
            
            if self.api_client:
                await self.api_client.close()
            
            logger.info("⏹️ Lighter 交易執行器已關閉")
        except Exception as e:
            logger.error(f"❌ 關閉客戶端時發生錯誤: {e}")

