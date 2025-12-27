"""
數據庫 CRUD 操作測試腳本
測試所有基本的增刪改查功能
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Windows 需要使用 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 載入環境變數
load_dotenv()


async def test_crud():
    """測試 CRUD 操作"""
    
    from database.db_manager import DatabaseManager
    from utils.logger import logger
    
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ 錯誤：找不到 DATABASE_URL")
        return False
    
    db = DatabaseManager(database_url)
    
    try:
        # 建立連接
        await db.connect()
        print("✅ 數據庫連接成功\n")
        
        # ==================== 測試錢包 CRUD ====================
        print("📝 測試錢包操作...")
        
        # 1. 添加測試錢包
        test_address = "0x1234567890abcdef1234567890abcdef12345678"
        wallet = await db.add_wallet(
            address=test_address,
            max_position_usd=500.0,
            stop_loss_ratio=0.3,
            nickname="測試錢包"
        )
        print(f"   ✅ 添加錢包: {wallet['address'][:20]}...")
        
        # 2. 查詢錢包
        wallet = await db.get_wallet(test_address)
        print(f"   ✅ 查詢錢包: nickname={wallet['nickname']}, enabled={wallet['enabled']}")
        
        # 3. 更新錢包狀態
        await db.update_wallet_status(test_address, enabled=False)
        wallet = await db.get_wallet(test_address)
        print(f"   ✅ 停用錢包: enabled={wallet['enabled']}")
        
        # 4. 獲取所有錢包
        wallets = await db.get_all_wallets()
        print(f"   ✅ 錢包總數: {len(wallets)}")
        
        # ==================== 測試持倉 CRUD ====================
        print("\n📝 測試持倉操作...")
        
        # 1. 添加持倉
        position = await db.add_position(
            symbol="ETH-PERP",
            side="LONG",
            size=1.5,
            entry_price=2000.0,
            source_wallet=test_address
        )
        print(f"   ✅ 開倉: {position['symbol']} {position['side']} {position['size']}")
        
        # 2. 查詢持倉
        position = await db.get_position("ETH-PERP")
        print(f"   ✅ 查詢持倉: entry_price={position['entry_price']}")
        
        # 3. 更新持倉（加倉）
        position = await db.add_position(
            symbol="ETH-PERP",
            side="LONG",
            size=2.0,  # 加倉到 2.0
            entry_price=2050.0,
            source_wallet=test_address
        )
        print(f"   ✅ 加倉: size={position['size']}, entry_price={position['entry_price']}")
        
        # 4. 檢查交易對鎖定
        is_unlocked = await db.check_position_lock("ETH-PERP", test_address)
        print(f"   ✅ 交易對鎖定檢查（同錢包）: {'可交易' if is_unlocked else '被鎖定'}")
        
        other_wallet = "0xabcdef1234567890abcdef1234567890abcdef12"
        is_unlocked = await db.check_position_lock("ETH-PERP", other_wallet)
        print(f"   ✅ 交易對鎖定檢查（其他錢包）: {'可交易' if is_unlocked else '被鎖定'}")
        
        # 5. 獲取所有持倉
        positions = await db.get_all_positions()
        print(f"   ✅ 持倉總數: {len(positions)}")
        
        # ==================== 測試交易歷史 ====================
        print("\n📝 測試交易歷史...")
        
        # 1. 添加交易記錄
        trade = await db.add_trade_history(
            symbol="ETH-PERP",
            side="LONG",
            size=1.5,
            price=2000.0,
            trade_type="OPEN",
            source_wallet=test_address
        )
        print(f"   ✅ 記錄交易: {trade['trade_type']} {trade['symbol']}")
        
        # 2. 查詢交易歷史
        trades = await db.get_trade_history(limit=10)
        print(f"   ✅ 交易歷史數量: {len(trades)}")
        
        # ==================== 測試配置 ====================
        print("\n📝 測試配置操作...")
        
        # 1. 讀取配置
        trading_enabled = await db.get_config("trading_enabled")
        print(f"   ✅ 讀取配置: trading_enabled={trading_enabled}")
        
        # 2. 設置配置
        await db.set_config("test_key", "test_value", "測試配置")
        value = await db.get_config("test_key")
        print(f"   ✅ 設置配置: test_key={value}")
        
        # ==================== 清理測試數據 ====================
        print("\n🧹 清理測試數據...")
        
        # 刪除持倉
        await db.remove_position("ETH-PERP", test_address)
        print("   ✅ 刪除持倉")
        
        # 刪除錢包
        await db.remove_wallet(test_address)
        print("   ✅ 刪除錢包")
        
        # 刪除測試配置
        async with db.pool.connection() as conn:
            await conn.execute("DELETE FROM config WHERE key = 'test_key'")
            await conn.execute("DELETE FROM trade_history WHERE source_wallet = %s", (test_address.lower(),))
            await conn.commit()
        print("   ✅ 刪除測試配置和交易記錄")
        
        # 驗證清理
        wallets = await db.get_all_wallets()
        positions = await db.get_all_positions()
        print(f"\n📊 清理後狀態: 錢包={len(wallets)}, 持倉={len(positions)}")
        
        await db.close()
        return True
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("HyperTrack 數據庫 CRUD 測試")
    print("=" * 50 + "\n")
    
    success = asyncio.run(test_crud())
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有測試通過！")
    else:
        print("❌ 測試失敗，請檢查錯誤")
    print("=" * 50)

