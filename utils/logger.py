"""
日誌系統模組
使用 loguru 提供結構化日誌
"""

import sys
from pathlib import Path
from loguru import logger

# 移除預設的 handler
logger.remove()

# 創建日誌目錄
LOG_DIR = Path(__file__).parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 添加控制台輸出（INFO 級別以上）
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True
)

# 添加 DEBUG 日誌文件（包含所有級別）
logger.add(
    LOG_DIR / "debug.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG",
    rotation="10 MB",      # 每 10MB 輪轉
    retention="7 days",    # 保留 7 天
    compression="zip",     # 壓縮舊日誌
    encoding="utf-8"
)

# 添加 ERROR 日誌文件（只記錄錯誤）
logger.add(
    LOG_DIR / "error.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
    level="ERROR",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    encoding="utf-8",
    backtrace=True,        # 記錄完整堆疊
    diagnose=True          # 記錄變量值
)

# 導出 logger
__all__ = ["logger"]

