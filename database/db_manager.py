"""
數據庫管理器模組
負責所有數據庫操作：連接、CRUD、關閉
使用 psycopg（PostgreSQL 異步驅動）
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from utils.logger import logger


class DatabaseManager:
    """
    數據庫管理器
    
    負責管理 PostgreSQL 數據庫連接和所有 CRUD 操作
    使用連接池提高效能
    """
    
    def __init__(self, database_url: str):
        """
        初始化數據庫管理器
        
        Args:
            database_url: PostgreSQL 連接字串
                         格式：postgresql://user:password@host:port/dbname
        """
        self.database_url = database_url
        self.pool: Optional[AsyncConnectionPool] = None
        logger.info("數據庫管理器初始化完成")
    
    async def connect(self) -> None:
        """
        建立數據庫連接池
        """
        try:
            self.pool = AsyncConnectionPool(
                self.database_url,
                min_size=1,
                max_size=10,
                kwargs={"row_factory": dict_row}
            )
            await self.pool.open()
            logger.info("✅ 數據庫連接池建立成功")
        except Exception as e:
            logger.error(f"❌ 數據庫連接失敗: {e}")
            raise
    
    async def close(self) -> None:
        """
        關閉數據庫連接池
        """
        if self.pool:
            await self.pool.close()
            logger.info("數據庫連接池已關閉")
    
    async def create_tables(self) -> None:
        """
        創建數據表
        讀取 schema.sql 並執行
        """
        try:
            # 找到 schema.sql 的路徑
            schema_path = Path(__file__).parent / "schema.sql"
            
            if not schema_path.exists():
                raise FileNotFoundError(f"找不到 schema.sql: {schema_path}")
            
            # 讀取 SQL 文件
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            
            # 執行 SQL
            async with self.pool.connection() as conn:
                await conn.execute(schema_sql)
                await conn.commit()
            
            logger.info("✅ 數據表創建成功")
        except Exception as e:
            logger.error(f"❌ 創建數據表失敗: {e}")
            raise
    
    # ==================== 錢包管理 ====================
    
    async def add_wallet(
        self,
        address: str,
        max_position_usd: float = 1000.0,
        stop_loss_ratio: float = 0.5,
        nickname: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        添加追蹤錢包
        
        Args:
            address: 錢包地址（0x 開頭，42 字符）
            max_position_usd: 最大跟單金額
            stop_loss_ratio: 止損比例
            nickname: 錢包備註名稱
            
        Returns:
            新增的錢包記錄
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    """
                    INSERT INTO wallets (address, max_position_usd, stop_loss_ratio, nickname)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                    """,
                    (address.lower(), max_position_usd, stop_loss_ratio, nickname)
                )
                wallet = await result.fetchone()
                await conn.commit()
                logger.info(f"✅ 添加錢包成功: {address[:10]}...")
                return dict(wallet)
        except psycopg.errors.UniqueViolation:
            logger.warning(f"⚠️ 錢包已存在: {address[:10]}...")
            raise ValueError("錢包地址已存在")
        except Exception as e:
            logger.error(f"❌ 添加錢包失敗: {e}")
            raise
    
    async def remove_wallet(self, address: str) -> bool:
        """
        移除追蹤錢包
        
        Args:
            address: 錢包地址
            
        Returns:
            是否成功移除
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    "DELETE FROM wallets WHERE address = %s",
                    (address.lower(),)
                )
                await conn.commit()
                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"✅ 移除錢包成功: {address[:10]}...")
                else:
                    logger.warning(f"⚠️ 錢包不存在: {address[:10]}...")
                return deleted
        except Exception as e:
            logger.error(f"❌ 移除錢包失敗: {e}")
            raise
    
    async def get_wallet(self, address: str) -> Optional[Dict[str, Any]]:
        """
        獲取單個錢包資訊
        
        Args:
            address: 錢包地址
            
        Returns:
            錢包記錄，不存在則返回 None
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    "SELECT * FROM wallets WHERE address = %s",
                    (address.lower(),)
                )
                wallet = await result.fetchone()
                return dict(wallet) if wallet else None
        except Exception as e:
            logger.error(f"❌ 獲取錢包失敗: {e}")
            raise
    
    async def get_all_wallets(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        獲取所有錢包
        
        Args:
            enabled_only: 是否只返回啟用的錢包
            
        Returns:
            錢包列表
        """
        try:
            async with self.pool.connection() as conn:
                if enabled_only:
                    result = await conn.execute(
                        "SELECT * FROM wallets WHERE enabled = TRUE ORDER BY created_at"
                    )
                else:
                    result = await conn.execute(
                        "SELECT * FROM wallets ORDER BY created_at"
                    )
                wallets = await result.fetchall()
                return [dict(w) for w in wallets]
        except Exception as e:
            logger.error(f"❌ 獲取錢包列表失敗: {e}")
            raise
    
    async def update_wallet_status(self, address: str, enabled: bool) -> bool:
        """
        更新錢包啟用狀態
        
        Args:
            address: 錢包地址
            enabled: 是否啟用
            
        Returns:
            是否成功更新
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    """
                    UPDATE wallets 
                    SET enabled = %s, updated_at = NOW() 
                    WHERE address = %s
                    """,
                    (enabled, address.lower())
                )
                await conn.commit()
                updated = result.rowcount > 0
                status = "啟用" if enabled else "停用"
                if updated:
                    logger.info(f"✅ 錢包{status}成功: {address[:10]}...")
                return updated
        except Exception as e:
            logger.error(f"❌ 更新錢包狀態失敗: {e}")
            raise
    
    # ==================== 持倉管理 ====================
    
    async def add_position(
        self,
        symbol: str,
        side: str,
        size: float,
        entry_price: float,
        source_wallet: str
    ) -> Dict[str, Any]:
        """
        添加或更新持倉
        
        Args:
            symbol: 交易對（如 ETH-PERP）
            side: 方向（LONG/SHORT）
            size: 數量
            entry_price: 進場價格
            source_wallet: 來源錢包
            
        Returns:
            持倉記錄
        """
        try:
            async with self.pool.connection() as conn:
                # 使用 UPSERT（存在則更新，不存在則插入）
                result = await conn.execute(
                    """
                    INSERT INTO positions (symbol, side, size, entry_price, source_wallet)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (symbol, source_wallet) 
                    DO UPDATE SET 
                        side = EXCLUDED.side,
                        size = EXCLUDED.size,
                        entry_price = EXCLUDED.entry_price,
                        updated_at = NOW()
                    RETURNING *
                    """,
                    (symbol.upper(), side.upper(), size, entry_price, source_wallet.lower())
                )
                position = await result.fetchone()
                await conn.commit()
                logger.info(f"✅ 持倉更新: {symbol} {side} {size}")
                return dict(position)
        except Exception as e:
            logger.error(f"❌ 添加持倉失敗: {e}")
            raise
    
    async def remove_position(self, symbol: str, source_wallet: str) -> bool:
        """
        移除持倉
        
        Args:
            symbol: 交易對
            source_wallet: 來源錢包
            
        Returns:
            是否成功移除
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    "DELETE FROM positions WHERE symbol = %s AND source_wallet = %s",
                    (symbol.upper(), source_wallet.lower())
                )
                await conn.commit()
                deleted = result.rowcount > 0
                if deleted:
                    logger.info(f"✅ 持倉已平倉: {symbol}")
                return deleted
        except Exception as e:
            logger.error(f"❌ 移除持倉失敗: {e}")
            raise
    
    async def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        獲取特定交易對的持倉
        
        Args:
            symbol: 交易對
            
        Returns:
            持倉記錄，不存在則返回 None
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    "SELECT * FROM positions WHERE symbol = %s",
                    (symbol.upper(),)
                )
                position = await result.fetchone()
                return dict(position) if position else None
        except Exception as e:
            logger.error(f"❌ 獲取持倉失敗: {e}")
            raise
    
    async def get_all_positions(self) -> List[Dict[str, Any]]:
        """
        獲取所有持倉
        
        Returns:
            持倉列表
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    "SELECT * FROM positions ORDER BY opened_at"
                )
                positions = await result.fetchall()
                return [dict(p) for p in positions]
        except Exception as e:
            logger.error(f"❌ 獲取持倉列表失敗: {e}")
            raise
    
    async def check_position_lock(self, symbol: str, source_wallet: str) -> bool:
        """
        檢查交易對是否被鎖定
        
        交易對鎖定規則：
        - 如果該交易對沒有持倉，返回 True（可以跟單）
        - 如果有持倉且來源相同，返回 True（可以調整）
        - 如果有持倉但來源不同，返回 False（被鎖定）
        
        Args:
            symbol: 交易對
            source_wallet: 來源錢包
            
        Returns:
            True = 可以跟單，False = 被鎖定
        """
        try:
            position = await self.get_position(symbol)
            
            if position is None:
                # 沒有持倉，可以跟單
                return True
            
            # 有持倉，檢查來源是否相同
            return position["source_wallet"] == source_wallet.lower()
        except Exception as e:
            logger.error(f"❌ 檢查交易對鎖定失敗: {e}")
            raise
    
    # ==================== 配置管理 ====================
    
    async def get_config(self, key: str) -> Optional[str]:
        """
        獲取配置值
        
        Args:
            key: 配置項名稱
            
        Returns:
            配置值，不存在則返回 None
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    "SELECT value FROM config WHERE key = %s",
                    (key,)
                )
                row = await result.fetchone()
                return row["value"] if row else None
        except Exception as e:
            logger.error(f"❌ 獲取配置失敗: {e}")
            raise
    
    async def set_config(self, key: str, value: str, description: str = None) -> None:
        """
        設置配置值
        
        Args:
            key: 配置項名稱
            value: 配置值
            description: 配置描述
        """
        try:
            async with self.pool.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO config (key, value, description)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (key) 
                    DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (key, value, description)
                )
                await conn.commit()
                logger.info(f"✅ 配置更新: {key} = {value}")
        except Exception as e:
            logger.error(f"❌ 設置配置失敗: {e}")
            raise
    
    # ==================== 交易歷史 ====================
    
    async def add_trade_history(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        trade_type: str,
        source_wallet: str,
        pnl: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        添加交易歷史記錄
        
        Args:
            symbol: 交易對
            side: 方向
            size: 數量
            price: 成交價格
            trade_type: 交易類型（OPEN/CLOSE/INCREASE/DECREASE）
            source_wallet: 來源錢包
            pnl: 盈虧（平倉時）
            
        Returns:
            交易記錄
        """
        try:
            async with self.pool.connection() as conn:
                result = await conn.execute(
                    """
                    INSERT INTO trade_history 
                    (symbol, side, size, price, trade_type, source_wallet, pnl)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (symbol.upper(), side.upper(), size, price, 
                     trade_type.upper(), source_wallet.lower(), pnl)
                )
                trade = await result.fetchone()
                await conn.commit()
                logger.info(f"✅ 交易記錄: {trade_type} {symbol} {side} {size}@{price}")
                return dict(trade)
        except Exception as e:
            logger.error(f"❌ 添加交易記錄失敗: {e}")
            raise
    
    async def get_trade_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        獲取交易歷史
        
        Args:
            symbol: 篩選特定交易對（可選）
            limit: 返回數量限制
            
        Returns:
            交易歷史列表
        """
        try:
            async with self.pool.connection() as conn:
                if symbol:
                    result = await conn.execute(
                        """
                        SELECT * FROM trade_history 
                        WHERE symbol = %s 
                        ORDER BY created_at DESC 
                        LIMIT %s
                        """,
                        (symbol.upper(), limit)
                    )
                else:
                    result = await conn.execute(
                        """
                        SELECT * FROM trade_history 
                        ORDER BY created_at DESC 
                        LIMIT %s
                        """,
                        (limit,)
                    )
                trades = await result.fetchall()
                return [dict(t) for t in trades]
        except Exception as e:
            logger.error(f"❌ 獲取交易歷史失敗: {e}")
            raise

