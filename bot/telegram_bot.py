"""
Telegram Bot 主程式
管理 Bot 的啟動、停止和事件處理
"""

import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

from bot.handlers import BotHandlers, ConversationState
from bot.keyboards import CallbackData
from database.db_manager import DatabaseManager
from utils.logger import logger


class TelegramBot:
    """
    Telegram Bot 主程式
    
    負責管理 Bot 的生命週期和事件處理
    """
    
    def __init__(
        self,
        token: str,
        admin_id: int,
        db_manager: DatabaseManager
    ):
        """
        初始化 Telegram Bot
        
        Args:
            token: Bot Token（從 @BotFather 獲取）
            admin_id: 管理員 User ID
            db_manager: 數據庫管理器
        """
        self.token = token
        self.admin_id = admin_id
        self.db_manager = db_manager
        
        # 創建處理器
        self.handlers = BotHandlers(db_manager, admin_id)
        
        # 創建 Application
        self.app: Optional[Application] = None
        
        # 運行狀態
        self._running = False
        
        logger.info("✅ Telegram Bot 初始化完成")
        logger.info(f"   管理員 ID: {admin_id}")
    
    def _setup_handlers(self):
        """設置命令和回調處理器"""
        
        # 添加錢包的對話處理器
        add_wallet_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(
                    self.handlers._prompt_add_wallet,
                    pattern=f"^{CallbackData.MENU_ADD_WALLET}$|^{CallbackData.WALLET_ADD}$"
                )
            ],
            states={
                ConversationState.WAITING_WALLET_ADDRESS: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handlers.handle_wallet_address
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.handlers.cancel_conversation),
                CallbackQueryHandler(
                    self._cancel_and_show_menu,
                    pattern=f"^{CallbackData.BACK_MAIN}$"
                )
            ],
            per_message=False,
        )
        
        # 註冊處理器
        self.app.add_handler(add_wallet_handler)
        
        # 命令處理器
        self.app.add_handler(CommandHandler("start", self.handlers.start_command))
        self.app.add_handler(CommandHandler("help", self.handlers.help_command))
        self.app.add_handler(CommandHandler("status", self.handlers.status_command))
        self.app.add_handler(CommandHandler("wallets", self.handlers.wallets_command))
        
        # 回調處理器（處理所有按鈕點擊）
        self.app.add_handler(CallbackQueryHandler(self.handlers.button_callback))
        
        logger.debug("命令和回調處理器已設置")
    
    async def _cancel_and_show_menu(self, update: Update, context):
        """取消對話並顯示主菜單"""
        query = update.callback_query
        await query.answer()
        await self.handlers._show_main_menu(update, context)
        return ConversationHandler.END
    
    async def start(self):
        """
        啟動 Bot
        
        使用 polling 模式運行
        """
        if self._running:
            logger.warning("Bot 已經在運行中")
            return
        
        try:
            # 創建 Application
            self.app = Application.builder().token(self.token).build()
            
            # 設置處理器
            self._setup_handlers()
            
            # 初始化
            await self.app.initialize()
            
            # 啟動
            await self.app.start()
            
            # 開始輪詢
            await self.app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )
            
            self._running = True
            logger.info("🚀 Telegram Bot 已啟動")
            
            # 發送啟動通知
            await self._send_startup_notification()
            
        except Exception as e:
            logger.exception(f"❌ Bot 啟動失敗: {e}")
            raise
    
    async def stop(self):
        """停止 Bot"""
        if not self._running:
            return
        
        try:
            # 發送停止通知
            await self._send_shutdown_notification()
            
            # 停止更新
            if self.app and self.app.updater:
                await self.app.updater.stop()
            
            # 停止應用
            if self.app:
                await self.app.stop()
                await self.app.shutdown()
            
            self._running = False
            logger.info("⏹️ Telegram Bot 已停止")
            
        except Exception as e:
            logger.error(f"❌ Bot 停止時發生錯誤: {e}")
    
    async def _send_startup_notification(self):
        """發送啟動通知"""
        try:
            message = (
                "🟢 **HyperTrack 已啟動**\n\n"
                "機器人已成功啟動，開始監控交易。\n"
                "發送 /start 查看主菜單。"
            )
            
            await self.app.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"發送啟動通知失敗: {e}")
    
    async def _send_shutdown_notification(self):
        """發送停止通知"""
        try:
            message = "🔴 **HyperTrack 已停止**"
            
            await self.app.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"發送停止通知失敗: {e}")
    
    async def send_message(self, message: str, parse_mode: str = "Markdown"):
        """
        發送消息給管理員
        
        Args:
            message: 消息內容
            parse_mode: 解析模式
        """
        if not self.app:
            logger.warning("Bot 未啟動，無法發送消息")
            return
        
        try:
            await self.app.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"發送消息失敗: {e}")
    
    # ========== 通知快捷方法 ==========
    
    async def notify_new_trade(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        source_wallet: str
    ):
        """
        通知新交易
        
        Args:
            symbol: 交易對
            side: 方向
            size: 數量
            price: 價格
            source_wallet: 來源錢包
        """
        short_wallet = f"{source_wallet[:6]}...{source_wallet[-4:]}"
        
        side_emoji = "🟢" if side.upper() == "LONG" else "🔴"
        
        message = (
            f"📈 **跟單成功**\n\n"
            f"**交易對：** {symbol}\n"
            f"**方向：** {side_emoji} {side}\n"
            f"**數量：** {size}\n"
            f"**價格：** ${price:.2f}\n"
            f"**來源：** `{short_wallet}`"
        )
        
        await self.send_message(message)
    
    async def notify_close_trade(
        self,
        symbol: str,
        pnl: float,
        source_wallet: str
    ):
        """
        通知平倉
        
        Args:
            symbol: 交易對
            pnl: 盈虧
            source_wallet: 來源錢包
        """
        short_wallet = f"{source_wallet[:6]}...{source_wallet[-4:]}"
        
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        pnl_text = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        
        message = (
            f"📉 **平倉完成**\n\n"
            f"**交易對：** {symbol}\n"
            f"**盈虧：** {pnl_emoji} {pnl_text}\n"
            f"**來源：** `{short_wallet}`"
        )
        
        await self.send_message(message)
    
    async def notify_error(self, error_message: str):
        """
        通知錯誤
        
        Args:
            error_message: 錯誤消息
        """
        message = (
            f"⚠️ **系統警告**\n\n"
            f"{error_message}"
        )
        
        await self.send_message(message)
    
    async def notify_wallet_event(
        self,
        event_type: str,
        symbol: str,
        wallet: str,
        details: str = ""
    ):
        """
        通知錢包事件
        
        Args:
            event_type: 事件類型
            symbol: 交易對
            wallet: 錢包地址
            details: 詳細信息
        """
        short_wallet = f"{wallet[:6]}...{wallet[-4:]}"
        
        type_emoji = {
            "OPEN": "📈",
            "CLOSE": "📉",
            "INCREASE": "⬆️",
            "DECREASE": "⬇️",
            "FLIP": "🔄",
        }.get(event_type, "📋")
        
        message = (
            f"{type_emoji} **檢測到事件**\n\n"
            f"**類型：** {event_type}\n"
            f"**交易對：** {symbol}\n"
            f"**錢包：** `{short_wallet}`"
        )
        
        if details:
            message += f"\n**詳情：** {details}"
        
        await self.send_message(message)
    
    @property
    def is_running(self) -> bool:
        """是否正在運行"""
        return self._running

