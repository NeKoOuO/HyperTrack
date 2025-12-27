"""
Telegram Bot 測試腳本
測試 Bot 基礎功能

使用方式：
1. 確保 .env 文件已配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_ADMIN_ID
2. 執行：python test_bot.py
3. 在 Telegram 中向機器人發送 /start
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bot.telegram_bot import TelegramBot
from database.db_manager import DatabaseManager
from utils.logger import logger


async def test_bot():
    """測試 Telegram Bot"""
    
    print("\n" + "=" * 60)
    print("🧪 Telegram Bot 測試")
    print("=" * 60)
    
    # 從環境變數讀取配置
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")
    database_url = os.getenv("DATABASE_URL")
    
    # 驗證環境變數
    if not bot_token:
        print("\n❌ 錯誤：TELEGRAM_BOT_TOKEN 未設定")
        print("請在 .env 文件中設定 Telegram Bot Token")
        print("\n💡 提示：如何獲取 Bot Token？")
        print("   1. 在 Telegram 搜索 @BotFather")
        print("   2. 發送 /newbot 創建新機器人")
        print("   3. 複製 Token 到 .env 文件")
        return False
    
    if not admin_id_str:
        print("\n❌ 錯誤：TELEGRAM_ADMIN_ID 未設定")
        print("請在 .env 文件中設定管理員 User ID")
        print("\n💡 提示：如何獲取 User ID？")
        print("   1. 在 Telegram 搜索 @userinfobot")
        print("   2. 向它發送任何消息")
        print("   3. 複製回覆中的 ID 到 .env 文件")
        return False
    
    try:
        admin_id = int(admin_id_str)
    except ValueError:
        print(f"\n❌ 錯誤：TELEGRAM_ADMIN_ID 格式錯誤：{admin_id_str}")
        return False
    
    print(f"\n📋 配置資訊：")
    print(f"   Bot Token：{bot_token[:10]}...{bot_token[-5:]}")
    print(f"   管理員 ID：{admin_id}")
    
    # 初始化數據庫管理器
    if database_url:
        print(f"   數據庫：已配置")
        db_manager = DatabaseManager(database_url)
    else:
        print(f"   數據庫：未配置（使用模擬模式）")
        db_manager = MockDatabaseManager()
    
    # 創建 Bot
    bot = TelegramBot(
        token=bot_token,
        admin_id=admin_id,
        db_manager=db_manager
    )
    
    print("\n" + "-" * 40)
    print("🚀 啟動 Bot...")
    print("-" * 40)
    
    try:
        # 啟動 Bot
        await bot.start()
        
        print("\n✅ Bot 已啟動！")
        print("\n📱 請在 Telegram 中測試：")
        print("   1. 搜索你的機器人")
        print("   2. 發送 /start")
        print("   3. 測試各項功能")
        print("\n⏰ Bot 將運行 60 秒後自動停止...")
        print("   （按 Ctrl+C 可提前停止）")
        
        # 運行 60 秒
        await asyncio.sleep(60)
        
    except KeyboardInterrupt:
        print("\n\n⏹️ 收到停止信號...")
    
    except Exception as e:
        print(f"\n❌ 錯誤：{e}")
        logger.exception("Bot 測試失敗")
        return False
    
    finally:
        # 停止 Bot
        print("\n正在停止 Bot...")
        await bot.stop()
        
        # 關閉數據庫連接
        if hasattr(db_manager, 'close'):
            await db_manager.close()
    
    print("\n" + "=" * 60)
    print("🎉 測試完成！")
    print("=" * 60)
    
    return True


class MockDatabaseManager:
    """模擬數據庫管理器（用於沒有數據庫時的測試）"""
    
    def __init__(self):
        self._wallets = []
        self._positions = []
    
    async def init(self):
        pass
    
    async def close(self):
        pass
    
    async def get_all_wallets(self):
        return self._wallets
    
    async def get_wallet(self, address):
        for w in self._wallets:
            if w.get("address", "").lower() == address.lower():
                return w
        return None
    
    async def add_wallet(self, address, config=None):
        self._wallets.append({
            "address": address,
            "enabled": True,
            "max_position_usd": 1000,
            "stop_loss_ratio": 0.5,
            "created_at": "just now"
        })
    
    async def remove_wallet(self, address):
        self._wallets = [w for w in self._wallets if w.get("address", "").lower() != address.lower()]
    
    async def update_wallet_status(self, address, enabled):
        for w in self._wallets:
            if w.get("address", "").lower() == address.lower():
                w["enabled"] = enabled
                break
    
    async def get_all_positions(self):
        return self._positions
    
    async def get_position(self, symbol):
        for p in self._positions:
            if p.get("symbol", "").upper() == symbol.upper():
                return p
        return None
    
    async def add_position(self, position_data):
        self._positions.append(position_data)
    
    async def remove_position(self, symbol, source_wallet):
        self._positions = [
            p for p in self._positions 
            if not (p.get("symbol", "").upper() == symbol.upper() 
                   and p.get("source_wallet", "").lower() == source_wallet.lower())
        ]


if __name__ == "__main__":
    asyncio.run(test_bot())

