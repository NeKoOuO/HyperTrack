# 系統架構文檔

> 最後更新：2024-12-27
> 當前階段：階段 4 - 策略引擎（已完成）

## 專案概述

HyperTrack 是一個聰明錢包跟單交易系統，自動追蹤 Hyperliquid 上聰明錢包的交易行為，並在 Lighter 交易所上進行比例跟單。

## 系統架構圖

```
┌─────────────────┐
│  Telegram Bot   │ ◄─── 用戶交互
└────────┬────────┘
         │
    ┌────▼────────────────┐
    │   主控制器 (Main)    │
    └────┬────────────────┘
         │
    ┌────▼─────┐  ┌────────┐  ┌──────────────┐
    │ WebSocket│  │ Lighter │  │  PostgreSQL  │
    │ Tracker  │  │ Trader  │  │  (Railway)   │
    └──────────┘  └────────┘  └──────────────┘
         │             │              │
         ▼             ▼              ▼
    Hyperliquid    Lighter API    雲端數據庫
```

## 模組結構

```
HyperTrack/
├── .cursor/rules/          # AI 規則
│   └── project-rules.mdc        # 專案開發規則
├── memory-bank/            # 核心文檔（AI 必讀）
│   ├── @architecture.md         # 系統架構（本文件）
│   ├── @design-doc.md           # 設計文檔
│   ├── @implementation-plan.md  # 實施計畫
│   ├── @progress.md             # 進度追蹤
│   └── @tech-stack.md           # 技術棧
├── core/                   # 核心邏輯
│   ├── __init__.py
│   ├── hyperliquid_tracker.py   # Hyperliquid WebSocket 追蹤器
│   ├── lighter_trader.py        # Lighter 交易執行器
│   └── strategy_engine.py       # 策略引擎
├── bot/                    # Telegram Bot
│   ├── __init__.py
│   ├── telegram_bot.py          # Bot 主程式
│   ├── handlers.py              # 命令處理器
│   └── keyboards.py             # 按鈕鍵盤
├── database/               # 資料庫
│   ├── __init__.py
│   ├── schema.sql               # 資料表結構
│   └── db_manager.py            # 資料庫管理器
├── utils/                  # 工具
│   ├── __init__.py
│   └── logger.py                # 日誌系統
├── data/logs/              # 日誌檔案
├── main.py                 # 程式入口
├── requirements.txt        # 依賴清單
├── .env                    # 環境變數（不上傳 Git）
├── .env.example            # 環境變數範本
└── .gitignore              # Git 忽略清單
```

## 資料庫結構

### wallets 表（追蹤的錢包）
| 欄位 | 類型 | 約束 | 說明 |
|------|------|------|------|
| id | SERIAL | PRIMARY KEY | 主鍵 |
| address | VARCHAR(42) | UNIQUE NOT NULL | 錢包地址 |
| enabled | BOOLEAN | DEFAULT TRUE | 是否啟用 |
| max_position_usd | DECIMAL(10,2) | - | 最大持倉金額 |
| stop_loss_ratio | DECIMAL(5,4) | - | 止損比例 |
| created_at | TIMESTAMP | DEFAULT NOW() | 創建時間 |

### positions 表（當前持倉）
| 欄位 | 類型 | 約束 | 說明 |
|------|------|------|------|
| id | SERIAL | PRIMARY KEY | 主鍵 |
| symbol | VARCHAR(20) | NOT NULL | 交易對 (如 ETH-PERP) |
| side | VARCHAR(10) | NOT NULL | 方向 (LONG/SHORT) |
| size | DECIMAL(20,8) | NOT NULL | 數量 |
| entry_price | DECIMAL(20,8) | NOT NULL | 進場價格 |
| source_wallet | VARCHAR(42) | NOT NULL | 來源錢包 |
| opened_at | TIMESTAMP | DEFAULT NOW() | 開倉時間 |
| - | - | UNIQUE(symbol, source_wallet) | 複合唯一鍵 |

### config 表（系統配置）
| 欄位 | 類型 | 約束 | 說明 |
|------|------|------|------|
| key | VARCHAR(50) | PRIMARY KEY | 配置項名稱 |
| value | TEXT | NOT NULL | 配置值 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新時間 |

## 核心類別說明

### HyperliquidTracker ✅ 已實現
- **職責**：監聽 Hyperliquid 錢包的持倉變化
- **檔案**：`core/hyperliquid_tracker.py`
- **方法**：
  - `__init__(wallet_addresses, testnet, on_event)` - 初始化
  - `start()` - 啟動輪詢監聽
  - `stop()` - 停止監聽
  - `get_wallet_state(address)` - 獲取錢包狀態
  - `_detect_changes()` - 檢測倉位變化
- **依賴**：`core/events.py`（事件類型定義）

### LighterTrader ✅ 已實現
- **職責**：在 Lighter 交易所執行交易
- **檔案**：`core/lighter_trader.py`
- **方法**：
  - `__init__(api_private_key, account_index, api_key_index, testnet)` - 初始化
  - `get_account_info()` - 獲取帳戶資訊
  - `get_balance()` - 查詢可用餘額
  - `get_positions()` - 查詢當前持倉
  - `get_market_price(symbol)` - 獲取市場價格
  - `place_market_order(symbol, side, size, reduce_only, max_slippage)` - 下市價單
  - `close_position(symbol)` - 平倉指定交易對
  - `close_all_positions()` - 平倉所有持倉
  - `close()` - 關閉客戶端連接
- **依賴**：`lighter-sdk` (SignerClient, AccountApi, OrderApi)
- **配置**：需要 API 私鑰、帳戶索引、API 密鑰索引

### StrategyEngine ✅ 已實現
- **職責**：處理跟單決策邏輯
- **檔案**：`core/strategy_engine.py`
- **方法**：
  - `__init__(db_manager, lighter_trader, default_max_position_usd, default_stop_loss_ratio)` - 初始化
  - `on_wallet_event(event)` - 處理錢包事件入口
  - `should_follow(event)` - 判斷是否跟單（檢查錢包啟用、交易對鎖定、餘額）
  - `check_position_lock(symbol, wallet_address)` - 檢查交易對鎖定
  - `calculate_follow_params(event)` - 計算跟單參數（數量和方向）
  - `calculate_follow_size(event)` - 計算跟單金額
  - `execute_follow(event, follow_size, follow_side)` - 執行跟單交易
  - `check_stop_loss(symbol)` - 檢查是否需要止損
  - `force_stop_loss(symbol)` - 強制止損平倉
- **依賴**：`DatabaseManager`, `LighterTrader`, `core.events`

### DatabaseManager（待實現）
- **職責**：管理資料庫操作
- **方法**：
  - `create_tables()` - 創建表
  - `add_wallet(address, config)` - 添加錢包
  - `remove_wallet(address)` - 移除錢包
  - `get_all_wallets()` - 獲取所有錢包
  - `add_position(data)` - 記錄持倉
  - `remove_position(symbol, wallet)` - 移除持倉

### TelegramBot（待實現）
- **職責**：處理用戶交互和通知
- **方法**：
  - `start()` - 啟動 Bot
  - `stop()` - 停止 Bot
  - 各種命令處理器

## 資料流

1. **WebSocket 監聽** → HyperliquidTracker 接收錢包事件
2. **事件傳遞** → 傳給 StrategyEngine 處理
3. **決策計算** → StrategyEngine 判斷是否跟單
4. **執行交易** → LighterTrader 下單
5. **記錄結果** → DatabaseManager 更新資料庫
6. **通知用戶** → TelegramBot 發送消息

## 技術變更說明

| 原計畫 | 實際使用 | 原因 |
|--------|----------|------|
| asyncpg | psycopg[binary] | Python 3.14 相容性更好，有預編譯版本 |
| aiohttp | httpx | 由 lighter-sdk 自動引入，功能相同 |

## 更新日誌

| 日期 | 更新內容 |
|------|----------|
| 2024-12-27 | 完成 StrategyEngine 策略引擎實現 |
| 2024-12-27 | 完成 LighterTrader 類別實現 |
| 2024-12-27 | 完成環境設定，調整部分依賴套件 |
| 2024-12-26 | 初始化架構文檔，定義模組結構和資料庫結構 |

