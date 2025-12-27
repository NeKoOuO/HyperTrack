"""
Lighter 交易執行器測試腳本
測試 Lighter API 連接、查詢餘額和持倉

使用方式：
1. 確保 .env 文件已配置 Lighter 相關環境變數
2. 執行：python test_lighter.py
"""

import asyncio
import os
import sys
from decimal import Decimal
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.lighter_trader import LighterTrader, OrderSide
from utils.logger import logger


async def test_lighter_connection():
    """測試 Lighter 連接和基本功能"""
    
    print("\n" + "=" * 60)
    print("🧪 Lighter 交易執行器測試")
    print("=" * 60)
    
    # 從環境變數讀取配置
    api_private_key = os.getenv("LIGHTER_API_PRIVATE_KEY")
    account_index_str = os.getenv("LIGHTER_ACCOUNT_INDEX")
    api_key_index_str = os.getenv("LIGHTER_API_KEY_INDEX", "3")
    testnet_str = os.getenv("LIGHTER_TESTNET", "True")
    
    # 驗證環境變數
    if not api_private_key:
        print("\n❌ 錯誤：LIGHTER_API_PRIVATE_KEY 未設定")
        print("請在 .env 文件中設定 Lighter API 私鑰")
        print("\n💡 提示：如何獲取 Lighter API 私鑰？")
        print("   1. 前往 https://lighter.xyz")
        print("   2. 連接錢包並登入")
        print("   3. 到設定頁面生成 API 金鑰")
        print("   4. 將私鑰複製到 .env 文件")
        return False
    
    if not account_index_str:
        print("\n❌ 錯誤：LIGHTER_ACCOUNT_INDEX 未設定")
        print("請在 .env 文件中設定 Lighter 帳戶索引")
        print("\n💡 提示：帳戶索引通常可以在 Lighter 平台的帳戶設定中找到")
        return False
    
    try:
        account_index = int(account_index_str)
        api_key_index = int(api_key_index_str)
        testnet = testnet_str.lower() in ("true", "1", "yes")
    except ValueError as e:
        print(f"\n❌ 錯誤：環境變數格式錯誤 - {e}")
        return False
    
    print(f"\n📋 配置資訊：")
    print(f"   網絡：{'測試網' if testnet else '主網'}")
    print(f"   帳戶索引：{account_index}")
    print(f"   API 密鑰索引：{api_key_index}")
    
    # 創建交易執行器
    trader = LighterTrader(
        api_private_key=api_private_key,
        account_index=account_index,
        api_key_index=api_key_index,
        testnet=testnet
    )
    
    try:
        # 測試 1：獲取帳戶資訊
        print("\n" + "-" * 40)
        print("📊 測試 1：獲取帳戶資訊")
        print("-" * 40)
        
        account_info = await trader.get_account_info()
        
        if account_info:
            print(f"✅ 帳戶資訊獲取成功！")
            print(f"   帳戶索引：{account_info.account_index}")
            print(f"   總抵押品：${account_info.collateral:.2f}")
            print(f"   可用餘額：${account_info.available_balance:.2f}")
            print(f"   總持倉價值：${account_info.total_position_value:.2f}")
            print(f"   未實現盈虧：${account_info.unrealized_pnl:.2f}")
        else:
            print("⚠️ 無法獲取帳戶資訊（可能帳戶未初始化）")
        
        # 測試 2：獲取可用餘額
        print("\n" + "-" * 40)
        print("💰 測試 2：獲取可用餘額")
        print("-" * 40)
        
        balance = await trader.get_balance()
        print(f"✅ 可用餘額：${balance:.2f}")
        
        # 測試 3：獲取當前持倉
        print("\n" + "-" * 40)
        print("📈 測試 3：獲取當前持倉")
        print("-" * 40)
        
        positions = await trader.get_positions()
        
        if positions:
            print(f"✅ 找到 {len(positions)} 個持倉：")
            for pos in positions:
                print(f"   • {pos.symbol} {pos.side}")
                print(f"     數量：{pos.size}")
                print(f"     進場價：${pos.entry_price:.2f}")
                print(f"     持倉價值：${pos.position_value:.2f}")
                print(f"     未實現盈虧：${pos.unrealized_pnl:.2f}")
        else:
            print("ℹ️ 目前沒有持倉")
        
        # 測試 4：獲取市場價格
        print("\n" + "-" * 40)
        print("💲 測試 4：獲取市場價格")
        print("-" * 40)
        
        for symbol in ["ETH", "BTC"]:
            try:
                price = await trader.get_market_price(symbol)
                if price:
                    print(f"✅ {symbol} 當前價格：${price:.2f}")
                else:
                    print(f"⚠️ 無法獲取 {symbol} 價格")
            except Exception as e:
                print(f"⚠️ {symbol} 價格獲取失敗：{e}")
        
        print("\n" + "=" * 60)
        print("🎉 所有測試完成！Lighter 連接正常")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 測試過程中發生錯誤：{e}")
        logger.exception("測試失敗")
        return False
        
    finally:
        # 關閉連接
        await trader.close()


async def test_place_order_dry_run():
    """
    測試下單功能（乾跑模式，不實際下單）
    
    注意：這個測試只會打印下單參數，不會實際執行交易
    """
    print("\n" + "=" * 60)
    print("🧪 下單功能乾跑測試（不實際執行）")
    print("=" * 60)
    
    # 模擬下單參數
    symbol = "ETH"
    side = OrderSide.BUY
    size = Decimal("0.001")  # 非常小的數量
    
    print(f"\n📋 模擬下單參數：")
    print(f"   交易對：{symbol}")
    print(f"   方向：{side.value}")
    print(f"   數量：{size}")
    
    print("\n⚠️ 乾跑模式：不會實際執行交易")
    print("如果要測試實際下單，請取消下方程式碼的註解")
    
    # 實際下單測試（預設註解掉）
    # 如果要測試實際下單，請取消註解並確保測試網帳戶有足夠餘額
    """
    api_private_key = os.getenv("LIGHTER_API_PRIVATE_KEY")
    account_index = int(os.getenv("LIGHTER_ACCOUNT_INDEX"))
    
    trader = LighterTrader(
        api_private_key=api_private_key,
        account_index=account_index,
        testnet=True  # 使用測試網
    )
    
    try:
        result = await trader.place_market_order(
            symbol=symbol,
            side=side,
            size=size,
            max_slippage=0.02  # 2% 滑點
        )
        
        if result.success:
            print(f"✅ 下單成功！訂單 ID：{result.order_id}")
        else:
            print(f"❌ 下單失敗：{result.error}")
    finally:
        await trader.close()
    """
    
    print("\n✅ 乾跑測試完成")


async def main():
    """主函數"""
    # 測試連接
    success = await test_lighter_connection()
    
    if success:
        # 乾跑下單測試
        await test_place_order_dry_run()


if __name__ == "__main__":
    asyncio.run(main())

