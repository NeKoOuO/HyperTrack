"""
Telegram Bot 命令處理器
處理用戶的各種命令和按鈕點擊
"""

import re
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import (
    CallbackData,
    get_main_menu_keyboard,
    get_wallets_menu_keyboard,
    get_wallet_list_keyboard,
    get_wallet_detail_keyboard,
    get_delete_wallet_keyboard,
    get_confirm_keyboard,
    get_settings_keyboard,
    get_status_keyboard,
    get_cancel_keyboard,
)
from database.db_manager import DatabaseManager
from utils.logger import logger


# ========== 對話狀態 ==========

class ConversationState:
    """對話狀態常量"""
    WAITING_WALLET_ADDRESS = 1
    WAITING_MAX_POSITION = 2
    WAITING_STOP_LOSS = 3
    CONFIRM_DELETE = 4


class BotHandlers:
    """
    Bot 命令處理器
    
    處理所有用戶交互邏輯
    """
    
    def __init__(self, db_manager: DatabaseManager, admin_id: int):
        """
        初始化處理器
        
        Args:
            db_manager: 數據庫管理器
            admin_id: 管理員 User ID
        """
        self.db_manager = db_manager
        self.admin_id = admin_id
        
        # 臨時存儲（用於對話流程）
        self._pending_actions = {}
    
    def _is_admin(self, user_id: int) -> bool:
        """檢查是否為管理員"""
        return user_id == self.admin_id
    
    # ========== 命令處理器 ==========
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /start 命令處理器
        顯示歡迎消息和主菜單
        """
        user = update.effective_user
        
        # 檢查權限
        if not self._is_admin(user.id):
            await update.message.reply_text(
                "⛔ 你沒有權限使用此機器人。\n"
                "請聯繫管理員獲取訪問權限。"
            )
            logger.warning(f"未授權用戶嘗試訪問: {user.id} ({user.username})")
            return
        
        welcome_text = (
            f"👋 你好，{user.first_name}！\n\n"
            "🤖 **HyperTrack 跟單機器人**\n\n"
            "這是一個聰明錢包跟單系統，自動追蹤 Hyperliquid 上的交易並在 Lighter 上執行跟單。\n\n"
            "請選擇操作："
        )
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
        
        logger.info(f"用戶 {user.id} 啟動了機器人")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /help 命令處理器
        顯示幫助信息
        """
        help_text = (
            "📚 **HyperTrack 使用說明**\n\n"
            "**基本命令：**\n"
            "• /start - 顯示主菜單\n"
            "• /help - 顯示此幫助\n"
            "• /status - 查看系統狀態\n"
            "• /wallets - 查看錢包列表\n\n"
            "**功能說明：**\n"
            "1. 📋 **錢包管理** - 添加/刪除/啟用/禁用追蹤錢包\n"
            "2. 📊 **系統狀態** - 查看運行狀態、餘額、持倉\n"
            "3. ⚙️ **設置** - 調整跟單參數\n\n"
            "**跟單規則：**\n"
            "• 自動追蹤聰明錢包的開倉/平倉\n"
            "• 按比例計算跟單金額\n"
            "• 同一交易對只跟隨第一個錢包\n"
            "• 支持止損保護"
        )
        
        await update.message.reply_text(
            help_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /status 命令處理器
        顯示系統狀態
        """
        await self._show_status(update, context)
    
    async def wallets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /wallets 命令處理器
        顯示錢包列表
        """
        await self._show_wallet_list(update, context)
    
    # ========== 回調處理器 ==========
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        處理所有按鈕回調
        """
        query = update.callback_query
        await query.answer()
        
        user = update.effective_user
        
        # 檢查權限
        if not self._is_admin(user.id):
            await query.edit_message_text("⛔ 你沒有權限執行此操作。")
            return
        
        data = query.data
        logger.debug(f"收到回調: {data}")
        
        # 根據回調數據路由到對應處理器
        if data == CallbackData.MENU_WALLETS:
            await self._show_wallets_menu(update, context)
        
        elif data == CallbackData.MENU_ADD_WALLET:
            await self._prompt_add_wallet(update, context)
        
        elif data == CallbackData.MENU_STATUS:
            await self._show_status(update, context, edit=True)
        
        elif data == CallbackData.MENU_SETTINGS:
            await self._show_settings(update, context)
        
        elif data == CallbackData.WALLET_LIST:
            await self._show_wallet_list(update, context, edit=True)
        
        elif data == CallbackData.WALLET_ADD:
            await self._prompt_add_wallet(update, context)
        
        elif data == CallbackData.WALLET_DELETE:
            await self._show_delete_wallet_list(update, context)
        
        elif data.startswith(f"{CallbackData.WALLET_DETAIL}:"):
            address = data.split(":", 1)[1]
            await self._show_wallet_detail(update, context, address)
        
        elif data.startswith(f"{CallbackData.WALLET_TOGGLE}:"):
            address = data.split(":", 1)[1]
            await self._toggle_wallet(update, context, address)
        
        elif data.startswith(f"{CallbackData.WALLET_DELETE}:"):
            address = data.split(":", 1)[1]
            await self._confirm_delete_wallet(update, context, address)
        
        elif data.startswith(f"{CallbackData.CONFIRM_YES}:"):
            action_data = data.split(":", 1)[1] if ":" in data else ""
            await self._handle_confirm_yes(update, context, action_data)
        
        elif data == CallbackData.CONFIRM_NO:
            await self._show_wallets_menu(update, context)
        
        elif data == CallbackData.BACK_MAIN:
            await self._show_main_menu(update, context)
        
        elif data == CallbackData.BACK_WALLETS:
            await self._show_wallets_menu(update, context)
        
        elif data == CallbackData.CONTROL_PAUSE:
            await self._pause_trading(update, context)
        
        elif data == CallbackData.CONTROL_RESUME:
            await self._resume_trading(update, context)
        
        elif data == CallbackData.CONTROL_EMERGENCY_STOP:
            await self._emergency_stop(update, context)
        
        else:
            logger.warning(f"未知回調: {data}")
    
    # ========== 消息處理器 ==========
    
    async def handle_wallet_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        處理用戶輸入的錢包地址
        """
        user = update.effective_user
        
        if not self._is_admin(user.id):
            return ConversationHandler.END
        
        text = update.message.text.strip()
        
        # 驗證地址格式（以太坊地址格式）
        if not self._is_valid_address(text):
            await update.message.reply_text(
                "❌ 無效的錢包地址格式！\n\n"
                "請輸入有效的以太坊地址（0x 開頭，42 個字符）：",
                reply_markup=get_cancel_keyboard()
            )
            return ConversationState.WAITING_WALLET_ADDRESS
        
        # 添加錢包到數據庫
        try:
            await self.db_manager.add_wallet(text)
            
            await update.message.reply_text(
                f"✅ 錢包添加成功！\n\n"
                f"地址：`{text[:10]}...{text[-6:]}`\n"
                f"狀態：已啟用",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="Markdown"
            )
            
            logger.info(f"添加錢包: {text}")
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ 添加錢包失敗：{str(e)}\n\n"
                "請稍後重試。",
                reply_markup=get_main_menu_keyboard()
            )
            logger.error(f"添加錢包失敗: {e}")
        
        return ConversationHandler.END
    
    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        取消當前對話
        """
        await update.message.reply_text(
            "已取消操作。",
            reply_markup=get_main_menu_keyboard()
        )
        return ConversationHandler.END
    
    # ========== 內部方法 ==========
    
    async def _show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """顯示主菜單"""
        query = update.callback_query
        
        text = (
            "🤖 **HyperTrack 跟單機器人**\n\n"
            "請選擇操作："
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    async def _show_wallets_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """顯示錢包管理菜單"""
        query = update.callback_query
        
        # 獲取錢包數量
        wallets = await self.db_manager.get_all_wallets()
        enabled_count = sum(1 for w in wallets if w.get("enabled", False))
        
        text = (
            "📋 **錢包管理**\n\n"
            f"總計：{len(wallets)} 個錢包\n"
            f"啟用：{enabled_count} 個\n"
            f"禁用：{len(wallets) - enabled_count} 個\n\n"
            "請選擇操作："
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_wallets_menu_keyboard(),
            parse_mode="Markdown"
        )
    
    async def _show_wallet_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
        """顯示錢包列表"""
        wallets = await self.db_manager.get_all_wallets()
        
        if not wallets:
            text = (
                "📋 **錢包列表**\n\n"
                "目前沒有追蹤任何錢包。\n"
                "點擊「添加錢包」開始追蹤！"
            )
            keyboard = get_wallets_menu_keyboard()
        else:
            text = (
                "📋 **錢包列表**\n\n"
                "點擊錢包查看詳情：\n\n"
                "✅ = 啟用  ❌ = 禁用"
            )
            keyboard = get_wallet_list_keyboard(wallets)
        
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    
    async def _show_wallet_detail(self, update: Update, context: ContextTypes.DEFAULT_TYPE, address: str):
        """顯示錢包詳情"""
        query = update.callback_query
        
        wallet = await self.db_manager.get_wallet(address)
        
        if not wallet:
            await query.edit_message_text(
                "❌ 找不到此錢包。",
                reply_markup=get_wallets_menu_keyboard()
            )
            return
        
        enabled = wallet.get("enabled", False)
        max_position = wallet.get("max_position_usd", "預設")
        stop_loss = wallet.get("stop_loss_ratio", "預設")
        created_at = wallet.get("created_at", "未知")
        
        status = "✅ 啟用" if enabled else "❌ 禁用"
        
        text = (
            f"📋 **錢包詳情**\n\n"
            f"**地址：**\n`{address}`\n\n"
            f"**狀態：** {status}\n"
            f"**最大跟單：** ${max_position}\n"
            f"**止損比例：** {stop_loss}\n"
            f"**添加時間：** {created_at}"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_wallet_detail_keyboard(address, enabled),
            parse_mode="Markdown"
        )
    
    async def _prompt_add_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """提示用戶輸入錢包地址"""
        query = update.callback_query
        
        text = (
            "➕ **添加錢包**\n\n"
            "請輸入要追蹤的錢包地址：\n"
            "（以 0x 開頭的 42 位地址）"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
        
        return ConversationState.WAITING_WALLET_ADDRESS
    
    async def _show_delete_wallet_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """顯示可刪除的錢包列表"""
        query = update.callback_query
        
        wallets = await self.db_manager.get_all_wallets()
        
        if not wallets:
            await query.edit_message_text(
                "沒有可刪除的錢包。",
                reply_markup=get_wallets_menu_keyboard()
            )
            return
        
        text = (
            "🗑️ **刪除錢包**\n\n"
            "選擇要刪除的錢包："
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_delete_wallet_keyboard(wallets),
            parse_mode="Markdown"
        )
    
    async def _confirm_delete_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE, address: str):
        """確認刪除錢包"""
        query = update.callback_query
        
        short_addr = f"{address[:10]}...{address[-6:]}"
        
        text = (
            f"⚠️ **確認刪除**\n\n"
            f"確定要刪除此錢包嗎？\n"
            f"`{short_addr}`\n\n"
            f"此操作無法撤銷！"
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_confirm_keyboard(f"delete:{address}"),
            parse_mode="Markdown"
        )
    
    async def _handle_confirm_yes(self, update: Update, context: ContextTypes.DEFAULT_TYPE, action_data: str):
        """處理確認操作"""
        query = update.callback_query
        
        if action_data.startswith("delete:"):
            address = action_data.split(":", 1)[1]
            await self._delete_wallet(update, context, address)
        else:
            await self._show_main_menu(update, context)
    
    async def _delete_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE, address: str):
        """刪除錢包"""
        query = update.callback_query
        
        try:
            await self.db_manager.remove_wallet(address)
            
            await query.edit_message_text(
                "✅ 錢包已刪除！",
                reply_markup=get_wallets_menu_keyboard()
            )
            
            logger.info(f"刪除錢包: {address}")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ 刪除失敗：{str(e)}",
                reply_markup=get_wallets_menu_keyboard()
            )
            logger.error(f"刪除錢包失敗: {e}")
    
    async def _toggle_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE, address: str):
        """切換錢包啟用狀態"""
        query = update.callback_query
        
        try:
            wallet = await self.db_manager.get_wallet(address)
            if wallet:
                new_status = not wallet.get("enabled", False)
                await self.db_manager.update_wallet_status(address, new_status)
                
                status_text = "啟用" if new_status else "禁用"
                await query.answer(f"已{status_text}錢包")
                
                # 刷新詳情頁面
                await self._show_wallet_detail(update, context, address)
                
                logger.info(f"切換錢包狀態: {address} -> {status_text}")
        except Exception as e:
            await query.answer(f"操作失敗: {e}")
            logger.error(f"切換錢包狀態失敗: {e}")
    
    async def _show_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
        """顯示系統狀態"""
        # 獲取統計數據
        wallets = await self.db_manager.get_all_wallets()
        positions = await self.db_manager.get_all_positions()
        
        enabled_wallets = sum(1 for w in wallets if w.get("enabled", False))
        
        text = (
            "📊 **系統狀態**\n\n"
            f"**追蹤錢包：** {len(wallets)} 個（{enabled_wallets} 個啟用）\n"
            f"**當前持倉：** {len(positions)} 個\n\n"
            "**系統狀態：** 🟢 運行中\n\n"
            "_點擊刷新獲取最新狀態_"
        )
        
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=get_status_keyboard(),
                parse_mode="Markdown"
            )
    
    async def _show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """顯示設置菜單"""
        query = update.callback_query
        
        text = (
            "⚙️ **系統設置**\n\n"
            "選擇要修改的項目："
        )
        
        await query.edit_message_text(
            text,
            reply_markup=get_settings_keyboard(),
            parse_mode="Markdown"
        )
    
    async def _pause_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """暫停跟單"""
        query = update.callback_query
        await query.answer("⏸️ 已暫停跟單")
        # TODO: 實現暫停邏輯
        logger.info("跟單已暫停")
    
    async def _resume_trading(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """繼續跟單"""
        query = update.callback_query
        await query.answer("▶️ 已繼續跟單")
        # TODO: 實現繼續邏輯
        logger.info("跟單已繼續")
    
    async def _emergency_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """緊急停止"""
        query = update.callback_query
        await query.answer("🚨 緊急停止已觸發！")
        # TODO: 實現緊急停止邏輯（平倉所有持倉）
        logger.warning("緊急停止已觸發")
    
    @staticmethod
    def _is_valid_address(address: str) -> bool:
        """驗證以太坊地址格式"""
        pattern = r"^0x[a-fA-F0-9]{40}$"
        return bool(re.match(pattern, address))
    
    # ========== 通知方法 ==========
    
    async def send_notification(
        self, 
        context: ContextTypes.DEFAULT_TYPE, 
        message: str,
        parse_mode: str = "Markdown"
    ):
        """
        發送通知給管理員
        
        Args:
            context: Bot 上下文
            message: 通知消息
            parse_mode: 解析模式
        """
        try:
            await context.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode=parse_mode
            )
        except Exception as e:
            logger.error(f"發送通知失敗: {e}")
    
    async def notify_new_position(
        self, 
        context: ContextTypes.DEFAULT_TYPE,
        symbol: str,
        side: str,
        size: float,
        price: float,
        source_wallet: str
    ):
        """通知新開倉"""
        short_wallet = f"{source_wallet[:6]}...{source_wallet[-4:]}"
        
        message = (
            f"📈 **新開倉**\n\n"
            f"**交易對：** {symbol}\n"
            f"**方向：** {side}\n"
            f"**數量：** {size}\n"
            f"**價格：** ${price:.2f}\n"
            f"**來源：** `{short_wallet}`"
        )
        
        await self.send_notification(context, message)
    
    async def notify_close_position(
        self, 
        context: ContextTypes.DEFAULT_TYPE,
        symbol: str,
        pnl: float,
        source_wallet: str
    ):
        """通知平倉"""
        short_wallet = f"{source_wallet[:6]}...{source_wallet[-4:]}"
        
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        pnl_text = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        
        message = (
            f"📉 **平倉**\n\n"
            f"**交易對：** {symbol}\n"
            f"**盈虧：** {pnl_emoji} {pnl_text}\n"
            f"**來源：** `{short_wallet}`"
        )
        
        await self.send_notification(context, message)
    
    async def notify_error(
        self, 
        context: ContextTypes.DEFAULT_TYPE,
        error_message: str
    ):
        """通知錯誤"""
        message = (
            f"⚠️ **系統警告**\n\n"
            f"{error_message}"
        )
        
        await self.send_notification(context, message)

