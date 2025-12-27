"""
數據庫初始化腳本
創建所有數據表
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


async def init_database():
    """初始化數據庫"""
    
    # 導入放在函數內，避免環境變數未載入
    from database.db_manager import DatabaseManager
    from utils.logger import logger
    
    # 獲取數據庫 URL
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("❌ 錯誤：找不到 DATABASE_URL 環境變數")
        print("請先執行 python test_db_connection.py 檢查配置")
        return False
    
    print("🚀 開始初始化數據庫...")
    
    try:
        # 創建數據庫管理器
        db = DatabaseManager(database_url)
        
        # 建立連接
        await db.connect()
        
        # 創建數據表
        await db.create_tables()
        
        # 驗證表是否創建成功
        async with db.pool.connection() as conn:
            result = await conn.execute(
                """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
            )
            tables = await result.fetchall()
            
            print("\n📋 已創建的數據表：")
            for table in tables:
                print(f"   ✅ {table['table_name']}")
        
        # 關閉連接
        await db.close()
        
        print("\n🎉 數據庫初始化成功！")
        return True
        
    except Exception as e:
        print(f"\n❌ 初始化失敗：{e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("HyperTrack 數據庫初始化")
    print("=" * 50)
    
    success = asyncio.run(init_database())
    
    print("\n" + "=" * 50)
    if success:
        print("✅ 數據庫已準備就緒！")
        print("下一步：可以開始開發核心功能了")
    else:
        print("❌ 請檢查錯誤後重試")
    print("=" * 50)

