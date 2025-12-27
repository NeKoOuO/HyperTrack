"""
HyperTrack 主程式入口
聰明錢包跟單交易系統

使用方式：
    python main.py

環境變數（.env）：
    - TELEGRAM_BOT_TOKEN: Telegram Bot Token
    - TELEGRAM_ADMIN_ID: 管理員 User ID
    - DATABASE_URL: PostgreSQL 連接 URL
    - LIGHTER_API_PRIVATE_KEY: Lighter API 私鑰
    - LIGHTER_ACCOUNT_INDEX: Lighter 帳戶索引
    - HYPERLIQUID_TESTNET: 是否使用測試網
"""

import asyncio
import signal
import sys
import os
from decimal import Decimal
from typing import Optional, List

from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

from utils.logger import logger
from database.db_manager import DatabaseManager
from core.hyperliquid_tracker import HyperliquidTracker
from core.lighter_trader import LighterTrader
from core.strategy_engine import StrategyEngine, FollowDecision
from core.events import PositionEvent
from bot.telegram_bot import TelegramBot


class HyperTrack:
    """
    HyperTrack 主控制器
    
    整合所有模組，協調運行
    """
    
    def __init__(self):
        """初始化主控制器"""
        self.db_manager: Optional[DatabaseManager] = None
        self.tracker: Optional[HyperliquidTracker] = None
        self.trader: Optional[LighterTrader] = None
        self.strategy: Optional[StrategyEngine] = None
        self.bot: Optional[TelegramBot] = None
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # 從環境變數讀取配置
        self._load_config()
    
    def _load_config(self):
        """載入配置"""
        # Telegram
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_admin_id = os.getenv("TELEGRAM_ADMIN_ID")
        
        # Database
        self.database_url = os.getenv("DATABASE_URL")
        
        # Lighter
        self.lighter_api_key = os.getenv("LIGHTER_API_PRIVATE_KEY")
        self.lighter_account_index = os.getenv("LIGHTER_ACCOUNT_INDEX")
        self.lighter_api_key_index = int(os.getenv("LIGHTER_API_KEY_INDEX", "3"))
        self.lighter_testnet = os.getenv("LIGHTER_TESTNET", "True").lower() in ("true", "1", "yes")
        
        # Hyperliquid
        self.hyperliquid_testnet = os.getenv("HYPERLIQUID_TESTNET", "True").lower() in ("true", "1", "yes")
        
        # Trading
        self.max_position_usd = Decimal(os.getenv("DEFAULT_MAX_POSITION_USD", "1000"))
        self.stop_loss_ratio = Decimal(os.getenv("STOP_LOSS_RATIO", "0.5"))
    
    def _validate_config(self) -> bool:
        """驗證配置是否完整"""
        errors = []
        
        if not self.telegram_token:
            errors.append("TELEGRAM_BOT_TOKEN 未設定")
        
        if not self.telegram_admin_id:
            errors.append("TELEGRAM_ADMIN_ID 未設定")
        
        if not self.database_url:
            errors.append("DATABASE_URL 未設定")
        
        # Lighter 配置是可選的（如果沒有就不啟用交易）
        if self.lighter_api_key and not self.lighter_account_index:
            errors.append("LIGHTER_ACCOUNT_INDEX 未設定")
        
        if errors:
            for error in errors:
                logger.error(f"❌ 配置錯誤: {error}")
            return False
        
        return True
    
    async def _init_components(self):
        """初始化所有組件"""
        logger.info("=" * 50)
        logger.info("🚀 HyperTrack 啟動中...")
        logger.info("=" * 50)
        
        # 1. 初始化數據庫
        logger.info("📦 初始化數據庫...")
        self.db_manager = DatabaseManager(self.database_url)
        
        # 2. 初始化 Telegram Bot
        logger.info("🤖 初始化 Telegram Bot...")
        self.bot = TelegramBot(
            token=self.telegram_token,
            admin_id=int(self.telegram_admin_id),
            db_manager=self.db_manager
        )
        
        # 3. 初始化 Lighter 交易執行器（如果配置了）
        if self.lighter_api_key and self.lighter_account_index:
            logger.info("💹 初始化 Lighter 交易執行器...")
            self.trader = LighterTrader(
                api_private_key=self.lighter_api_key,
                account_index=int(self.lighter_account_index),
                api_key_index=self.lighter_api_key_index,
                testnet=self.lighter_testnet
            )
        else:
            logger.warning("⚠️ Lighter API 未配置，交易功能已禁用")
            self.trader = None
        
        # 4. 初始化策略引擎（如果有交易執行器）
        if self.trader:
            logger.info("🧠 初始化策略引擎...")
            self.strategy = StrategyEngine(
                db_manager=self.db_manager,
                lighter_trader=self.trader,
                default_max_position_usd=self.max_position_usd,
                default_stop_loss_ratio=self.stop_loss_ratio
            )
        else:
            self.strategy = None
        
        logger.info("✅ 所有組件初始化完成")
    
    async def _on_wallet_event(self, event: PositionEvent):
        """
        處理錢包事件
        
        當追蹤器檢測到錢包變化時調用
        """
        logger.info(f"📢 收到錢包事件: {event}")
        
        # 發送通知
        if self.bot and self.bot.is_running:
            await self.bot.notify_wallet_event(
                event_type=event.event_type.value,
                symbol=event.symbol,
                wallet=event.wallet_address,
                details=f"數量: {event.size}, 價格: ${event.price:.2f}"
            )
        
        # 如果策略引擎可用，處理跟單
        if self.strategy:
            try:
                result = await self.strategy.on_wallet_event(event)
                
                if result.decision == FollowDecision.FOLLOW:
                    # 跟單成功，發送通知
                    if self.bot and self.bot.is_running:
                        await self.bot.notify_new_trade(
                            symbol=event.symbol,
                            side=result.follow_side.value if result.follow_side else "UNKNOWN",
                            size=float(result.follow_size) if result.follow_size else 0,
                            price=float(event.price),
                            source_wallet=event.wallet_address
                        )
                        
                elif result.decision == FollowDecision.ERROR:
                    # 跟單失敗，發送錯誤通知
                    if self.bot and self.bot.is_running:
                        await self.bot.notify_error(f"跟單失敗: {result.reason}")
                        
            except Exception as e:
                logger.exception(f"處理事件時發生錯誤: {e}")
                if self.bot and self.bot.is_running:
                    await self.bot.notify_error(f"處理事件錯誤: {str(e)}")
    
    async def _start_tracker(self):
        """啟動追蹤器"""
        # 從數據庫獲取要追蹤的錢包
        wallets = await self.db_manager.get_all_wallets()
        enabled_wallets = [w["address"] for w in wallets if w.get("enabled", False)]
        
        if not enabled_wallets:
            logger.warning("⚠️ 沒有啟用的錢包，追蹤器未啟動")
            logger.info("💡 請通過 Telegram Bot 添加錢包")
            return
        
        logger.info(f"📡 啟動追蹤器，監控 {len(enabled_wallets)} 個錢包...")
        
        # 創建追蹤器
        self.tracker = HyperliquidTracker(
            wallet_addresses=enabled_wallets,
            testnet=self.hyperliquid_testnet,
            on_event=self._on_wallet_event
        )
        
        # 啟動追蹤
        await self.tracker.start()
    
    async def _run_bot(self):
        """運行 Telegram Bot"""
        await self.bot.start()
        
        # 保持運行直到被停止
        while self._running:
            await asyncio.sleep(1)
    
    async def start(self):
        """啟動 HyperTrack"""
        # 驗證配置
        if not self._validate_config():
            logger.error("❌ 配置驗證失敗，請檢查 .env 文件")
            return
        
        try:
            # 初始化組件
            await self._init_components()
            
            self._running = True
            
            # 創建並啟動任務
            logger.info("🏃 啟動服務...")
            
            # Bot 任務
            bot_task = asyncio.create_task(self._run_bot())
            self._tasks.append(bot_task)
            
            # 追蹤器任務
            tracker_task = asyncio.create_task(self._start_tracker())
            self._tasks.append(tracker_task)
            
            logger.info("=" * 50)
            logger.info("🎉 HyperTrack 已啟動！")
            logger.info("=" * 50)
            
            # 等待所有任務
            await asyncio.gather(*self._tasks, return_exceptions=True)
            
        except Exception as e:
            logger.exception(f"❌ 啟動失敗: {e}")
            await self.stop()
    
    async def stop(self):
        """停止 HyperTrack"""
        logger.info("⏹️ 正在停止 HyperTrack...")
        
        self._running = False
        
        # 停止追蹤器
        if self.tracker:
            await self.tracker.stop()
        
        # 停止 Bot
        if self.bot:
            await self.bot.stop()
        
        # 關閉交易執行器
        if self.trader:
            await self.trader.close()
        
        # 關閉數據庫連接
        if self.db_manager:
            await self.db_manager.close()
        
        # 取消所有任務
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        logger.info("👋 HyperTrack 已停止")


async def main():
    """主函數"""
    # 創建主控制器
    app = HyperTrack()
    
    # 設置信號處理（優雅關閉）
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("📴 收到停止信號...")
        asyncio.create_task(app.stop())
    
    # 註冊信號處理器
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows 不支援 add_signal_handler
            pass
    
    try:
        await app.start()
    except KeyboardInterrupt:
        logger.info("📴 收到鍵盤中斷...")
    finally:
        await app.stop()


if __name__ == "__main__":
    # Windows 需要特殊處理
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 再見！")

