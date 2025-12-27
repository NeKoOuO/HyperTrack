"""
Hyperliquid 追蹤器測試腳本
測試 WebSocket 連接和事件監聽
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


async def test_tracker():
    """測試追蹤器"""
    
    from core.hyperliquid_tracker import HyperliquidTracker
    from core.events import PositionEvent
    from utils.logger import logger
    
    # 測試用的錢包地址（這是一個活躍的 Hyperliquid 錢包）
    # 你可以替換成你想追蹤的地址
    TEST_WALLET = "0x1b816bfb23DE4ff1b30c71B3f7F30f1C43Dc626B"
    
    print("=" * 60)
    print("Hyperliquid 追蹤器測試")
    print("=" * 60)
    
    # 事件計數
    event_count = [0]
    
    def on_event(event: PositionEvent):
        """事件回調"""
        event_count[0] += 1
        print(f"\n🔔 事件 #{event_count[0]}: {event}")
    
    # 使用測試網
    use_testnet = os.getenv("HYPERLIQUID_TESTNET", "True").lower() == "true"
    
    print(f"\n📡 網絡: {'測試網' if use_testnet else '主網'}")
    print(f"👛 追蹤錢包: {TEST_WALLET[:20]}...")
    print(f"⏱️ 測試時長: 30 秒")
    print("-" * 60)
    
    try:
        # 創建追蹤器
        tracker = HyperliquidTracker(
            wallet_addresses=[TEST_WALLET],
            testnet=use_testnet,
            on_event=on_event
        )
        
        # 先獲取一次錢包狀態
        print("\n📊 獲取錢包初始狀態...")
        state = await tracker.get_wallet_state(TEST_WALLET)
        
        print(f"\n💰 錢包狀態:")
        print(f"   總權益: ${state.account_value:.2f}")
        print(f"   可用餘額: ${state.available_balance:.2f}")
        print(f"   倉位比例: {state.position_ratio * 100:.2f}%")
        print(f"   持倉數量: {len(state.positions)}")
        
        if state.positions:
            print(f"\n📈 當前持倉:")
            for pos in state.positions:
                position_data = pos.get("position", {})
                coin = position_data.get("coin", "")
                size = position_data.get("szi", "0")
                entry_px = position_data.get("entryPx", "0")
                pnl = position_data.get("unrealizedPnl", "0")
                
                if float(size) != 0:
                    direction = "LONG" if float(size) > 0 else "SHORT"
                    print(f"   • {coin}: {direction} | 數量: {abs(float(size)):.4f} | 入場: ${float(entry_px):.2f} | PnL: ${float(pnl):.2f}")
        else:
            print("\n📭 目前沒有持倉")
        
        print("\n" + "-" * 60)
        print("🔄 開始監聽持倉變化（30 秒）...")
        print("   如果該錢包有交易，會顯示事件")
        print("-" * 60)
        
        # 啟動追蹤器，運行 30 秒
        tracker_task = asyncio.create_task(tracker.start())
        
        # 等待 30 秒
        await asyncio.sleep(30)
        
        # 停止追蹤器
        await tracker.stop()
        tracker_task.cancel()
        
        try:
            await tracker_task
        except asyncio.CancelledError:
            pass
        
        print("\n" + "=" * 60)
        print(f"📊 測試完成！")
        print(f"   監聽時長: 30 秒")
        print(f"   檢測到的事件: {event_count[0]} 個")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_wallet_info():
    """測試錢包信息查詢（快速測試）"""
    
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    
    print("=" * 60)
    print("Hyperliquid 錢包信息查詢測試（快速）")
    print("=" * 60)
    
    # 使用主網查詢
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    
    print("\n📡 連接到 Hyperliquid 主網...")
    
    try:
        # 測試 API 連接 - 獲取所有交易對
        meta = info.meta()
        universe = meta.get("universe", [])
        print(f"✅ API 連接成功！")
        print(f"   可交易幣種: {len(universe)} 個")
        
        # 顯示幾個主要幣種
        print(f"\n📊 主要交易對:")
        for asset in universe[:5]:
            name = asset.get("name", "")
            print(f"   • {name}")
        
        # 查詢測試錢包
        print(f"\n" + "-" * 60)
        # 使用一個範例地址測試 API
        wallet = "0x0000000000000000000000000000000000000000"
        print(f"👛 測試查詢錢包 API...")
        
        if True:
            print(f"\n👛 查詢錢包: {wallet[:20]}...")
            user_state = info.user_state(wallet)
            
            margin_summary = user_state.get("marginSummary", {})
            account_value = float(margin_summary.get("accountValue", "0"))
            
            print(f"   總權益: ${account_value:.2f}")
            
            positions = user_state.get("assetPositions", [])
            active_positions = [p for p in positions if float(p.get("position", {}).get("szi", "0")) != 0]
            print(f"   持倉數量: {len(active_positions)}")
            
            if active_positions:
                print(f"\n📈 持倉詳情:")
                for pos in active_positions:
                    p = pos.get("position", {})
                    coin = p.get("coin", "")
                    size = float(p.get("szi", "0"))
                    entry = float(p.get("entryPx", "0"))
                    pnl = float(p.get("unrealizedPnl", "0"))
                    direction = "LONG" if size > 0 else "SHORT"
                    print(f"   • {coin}: {direction} | 數量: {abs(size):.4f} | 入場: ${entry:.2f} | PnL: ${pnl:.2f}")
        
        print(f"\n" + "=" * 60)
        print("✅ 測試完成！Hyperliquid SDK 運作正常")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 查詢失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n選擇測試模式:")
    print("1. 快速測試（只查詢錢包信息）")
    print("2. 完整測試（監聽 30 秒）")
    
    choice = input("\n請輸入選項 (1/2，預設 1): ").strip() or "1"
    
    if choice == "2":
        success = asyncio.run(test_tracker())
    else:
        success = asyncio.run(test_wallet_info())
    
    if not success:
        sys.exit(1)

