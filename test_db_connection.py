"""
數據庫連接測試腳本
用於驗證 PostgreSQL 連接是否正常
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
import psycopg

# Windows 需要使用 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 載入環境變數
load_dotenv()


async def test_connection():
    """測試數據庫連接"""
    
    # 獲取數據庫 URL
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ 錯誤：找不到 DATABASE_URL 環境變數")
        print("請確認：")
        print("1. 已創建 .env 文件")
        print("2. 已填入 DATABASE_URL=postgresql://user:password@host:port/dbname")
        return False
    
    print(f"📡 嘗試連接數據庫...")
    print(f"   URL: {database_url[:30]}...")  # 只顯示前 30 字符，隱藏密碼
    
    try:
        # 建立連接
        async with await psycopg.AsyncConnection.connect(database_url) as conn:
            # 執行測試查詢
            async with conn.cursor() as cur:
                await cur.execute("SELECT version();")
                version = await cur.fetchone()
                
                print(f"\n✅ 數據庫連接成功！")
                print(f"   PostgreSQL 版本: {version[0]}")
                
                # 測試時間
                await cur.execute("SELECT NOW();")
                now = await cur.fetchone()
                print(f"   服務器時間: {now[0]}")
                
        return True
        
    except psycopg.OperationalError as e:
        print(f"\n❌ 連接失敗：{e}")
        print("\n可能的原因：")
        print("1. DATABASE_URL 格式錯誤")
        print("2. 數據庫服務器未啟動")
        print("3. 網絡無法連接到數據庫")
        print("4. 用戶名或密碼錯誤")
        return False
        
    except Exception as e:
        print(f"\n❌ 發生錯誤：{e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("HyperTrack 數據庫連接測試")
    print("=" * 50)
    
    success = asyncio.run(test_connection())
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 測試通過！可以繼續下一步。")
        print("下一步：執行 python init_db.py 初始化數據表")
    else:
        print("😢 測試失敗，請檢查配置後重試。")
    print("=" * 50)

