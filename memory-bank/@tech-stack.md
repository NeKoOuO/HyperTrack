# 技術棧文檔

## 開發語言
- **Python 3.10+**：主要開發語言

## 核心依賴

### 1. 交易所 SDK
#### Hyperliquid Python SDK
- **倉庫**：https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- **用途**：
  - WebSocket 連接監聽錢包持倉
  - 查詢錢包歷史交易
  - 獲取市場數據
- **關鍵功能**：
  - `Hyperliquid.Info` - 查詢接口
  - `Hyperliquid.WebSocket` - 實時數據流

#### Lighter Python SDK
- **倉庫**：https://github.com/elliottech/lighter-python
- **用途**：
  - 執行交易訂單
  - 查詢賬戶餘額
  - 管理持倉
- **關鍵功能**：
  - 市價單/限價單下單
  - 持倉查詢和管理
  - 訂單狀態追蹤

### 2. Telegram Bot 框架
#### python-telegram-bot
- **版本**：20.7+
- **文檔**：https://docs.python-telegram-bot.org/
- **用途**：
  - 構建 Telegram 機器人
  - 處理用戶交互
  - 發送實時通知
- **關鍵組件**：
  - `Application` - Bot 主程序
  - `CallbackQueryHandler` - 按鈕回調處理
  - `InlineKeyboardButton` - 交互式按鈕

### 3. 異步處理
#### asyncio
- **用途**：並發處理多個任務
  - WebSocket 持續監聽
  - Telegram Bot 接收消息
  - 定時任務（心跳檢測）

#### aiohttp
- **用途**：異步 HTTP 請求
  - 調用 REST API
  - WebSocket 客戶端備用方案

### 4. 數據存儲
#### PostgreSQL + asyncpg
- **服務**：Railway PostgreSQL 插件
- **用途**：雲端關聯式數據庫
- **存儲內容**：
  - 追蹤錢包列表和配置
  - 當前持倉狀態
  - 用戶設定（止損比例等）
- **優點**：
  - Railway 一鍵添加，自動配置
  - 雲端存儲，數據安全
  - 支持複雜查詢和事務
  - 自動備份和恢復

### 5. 工具庫
#### python-dotenv
- **用途**：管理環境變數
- **配置項**：
  - API 密鑰
  - Bot Token
  - 交易參數

#### loguru
- **用途**：結構化日誌
- **功能**：
  - 分級日誌（DEBUG/INFO/ERROR）
  - 自動日誌輪轉
  - 異常追蹤

## 數據結構

### 錢包配置
```python
{
  "address": "0x...",
  "enabled": True,
  "max_position_usd": 1000,
  "stop_loss_ratio": 0.5
}
```

### 持倉記錄
```python
{
  "symbol": "ETH-PERP",
  "side": "LONG",
  "size": 1.5,
  "entry_price": 2000,
  "source_wallet": "0x...",
  "timestamp": 1234567890
}
```

## API 調用流程

### Hyperliquid WebSocket 監聽
```
1. 建立 WebSocket 連接
2. 訂閱錢包地址的 user_events
3. 接收持倉變化事件
4. 解析事件類型（開倉/平倉/調整）
5. 計算倉位變化比例
```

### Lighter 下單流程
```
1. 計算跟單數量
2. 檢查賬戶餘額
3. 驗證滑點範圍
4. 提交市價單
5. 等待成交確認
6. 更新本地持倉記錄
```

### Telegram 通知流程
```
1. 事件觸發（新單/異常）
2. 格式化消息內容
3. 構建交互按鈕
4. 推送到用戶
5. 處理用戶回調
```

## 部署技術

### Railway 部署
- **運行環境**：Docker 容器
- **持久化存儲**：Railway Volume 掛載 `/data` 目錄
- **環境變數**：通過 Railway Dashboard 配置
- **監控**：Railway 內建日誌查看

### Docker 配置
- **基礎鏡像**：python:3.10-slim
- **工作目錄**：/app
- **啟動命令**：python main.py
- **端口**：無需開放（僅出站連接）

## 安全考慮

### API 密鑰管理
- 使用環境變數，不寫入代碼
- Railway 加密存儲

### 錯誤處理
- 所有外部調用包裹 try-except
- 敏感錯誤不記錄完整內容

### 訪問控制
- Telegram Bot 驗證用戶 ID
- 僅允許管理員執行敏感操作

## 性能考量

### WebSocket 連接
- 斷線自動重連（指數退避）
- 心跳檢測保持連接

### API 速率限制
- 請求失敗重試機制
- 避免並發過多請求

### 內存使用
- 僅保留必要的歷史數據
- 定期清理過期記錄

## 測試策略

### 單元測試
- 倉位計算邏輯
- 風險檢查函數

### 集成測試
- 使用測試網環境
- 模擬錢包活動

### 壓力測試
- 長時間運行穩定性
- WebSocket 斷線恢復

