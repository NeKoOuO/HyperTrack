# 實施計畫

## 階段 0：環境準備

### 步驟 0.1：創建專案結構
**指令**：
1. 在本地或伺服器上創建資料夾 `smart-wallet-copytrade`
2. 進入該資料夾
3. 創建以下子資料夾：`core/`, `bot/`, `database/`, `utils/`, `data/logs/`
4. 在每個子資料夾內創建空白 `__init__.py` 文件

**驗證**：
- 執行 `ls -R` 確認資料夾結構完整
- 確認每個資料夾都有 `__init__.py`

### 步驟 0.2：安裝 Python 環境
**指令**：
1. 確認 Python 版本為 3.10 或更高（執行 `python3 --version`）
2. 創建虛擬環境：`python3 -m venv venv`
3. 激活虛擬環境（Linux/Mac: `source venv/bin/activate`）

**驗證**：
- 命令行提示符出現 `(venv)` 前綴
- 執行 `which python` 確認路徑在 venv 內

### 步驟 0.3：創建依賴清單
**指令**：
1. 創建 `requirements.txt` 文件
2. 添加以下內容（每行一個依賴）：
   - `hyperliquid-python-sdk`
   - `git+https://github.com/elliottech/lighter-python.git`
   - `python-telegram-bot[job-queue]==20.7`
   - `aiohttp==3.9.1`
   - `asyncpg==0.29.0`
   - `sqlalchemy[asyncio]==2.0.23`
   - `python-dotenv==1.0.0`
   - `loguru==0.7.2`

**驗證**：
- 文件存在且內容正確
- 每個依賴佔一行

### 步驟 0.4：安裝依賴
**指令**：
1. 確保虛擬環境已激活
2. 升級 pip：`pip install --upgrade pip`
3. 安裝依賴：`pip install -r requirements.txt`
4. 等待安裝完成（可能需要 2-5 分鐘）

**驗證**：
- 執行 `pip list` 查看已安裝包
- 執行 `python -c "import hyperliquid; import telegram; print('OK')"` 應輸出 `OK`

### 步驟 0.5：配置環境變數
**指令**：
1. 創建 `.env.example` 文件作為模板
2. 添加以下配置項（值留空）：
   ```
   TELEGRAM_BOT_TOKEN=
   TELEGRAM_ADMIN_ID=
   HYPERLIQUID_TESTNET=True
   LIGHTER_API_KEY=
   LIGHTER_API_SECRET=
   LIGHTER_TESTNET=True
   DEFAULT_MAX_POSITION_USD=1000
   STOP_LOSS_RATIO=0.5
   ```
3. 複製 `.env.example` 為 `.env`
4. 到 Telegram 找 @BotFather 創建新 Bot，獲取 Token
5. 到 @userinfobot 獲取你的 User ID
6. 填入 `.env` 文件的對應位置

**驗證**：
- `.env` 文件存在且包含實際值
- 執行 `python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('TELEGRAM_BOT_TOKEN'))"` 能輸出 Token

### 步驟 0.6：創建 .gitignore
**指令**：
1. 創建 `.gitignore` 文件
2. 添加以下內容：
   ```
   __pycache__/
   *.pyc
   venv/
   .env
   *.db
   logs/
   ```

**驗證**：
- 文件存在
- 內容正確

---

## 階段 1：數據庫設計

### 步驟 1.1：在 Railway 添加 PostgreSQL
**指令**：
1. 登入 Railway Dashboard
2. 進入你的專案
3. 點擊 "New" → 選擇 "Database" → 選擇 "PostgreSQL"
4. 等待數據庫創建完成（約 1-2 分鐘）
5. 點擊 PostgreSQL 服務，查看 "Variables" 標籤
6. 複製 `DATABASE_URL` 環境變數（格式：postgresql://user:password@host:port/dbname）
7. 將 `DATABASE_URL` 添加到本地 `.env` 文件

**驗證**：
- Railway Dashboard 顯示 PostgreSQL 服務運行中
- `DATABASE_URL` 已複製到 `.env` 文件
- URL 格式正確包含用戶名、密碼、主機、端口、數據庫名

### 步驟 1.2：測試數據庫連接
**指令**：
1. 創建測試腳本 `test_db_connection.py` 在根目錄
2. 內容：
   - 載入 `.env` 中的 `DATABASE_URL`
   - 使用 `asyncpg` 建立連接
   - 執行簡單查詢 `SELECT version();`
   - 打印 PostgreSQL 版本號
   - 關閉連接
3. 執行測試腳本

**驗證**：
- 腳本執行無報錯
- 成功打印 PostgreSQL 版本信息（例如：PostgreSQL 15.x）
- 連接成功建立並關閉

### 步驟 1.3：設計數據表結構
**指令**：
1. 在 `database/` 資料夾創建 `schema.sql` 文件
2. 定義以下三個數據表的 SQL 創建語句：
   
   **wallets 表**：
   - id (SERIAL PRIMARY KEY)
   - address (VARCHAR(42) UNIQUE NOT NULL)
   - enabled (BOOLEAN DEFAULT TRUE)
   - max_position_usd (DECIMAL(10,2))
   - stop_loss_ratio (DECIMAL(5,4))
   - created_at (TIMESTAMP DEFAULT NOW())
   
   **positions 表**：
   - id (SERIAL PRIMARY KEY)
   - symbol (VARCHAR(20) NOT NULL)
   - side (VARCHAR(10) NOT NULL)
   - size (DECIMAL(20,8) NOT NULL)
   - entry_price (DECIMAL(20,8) NOT NULL)
   - source_wallet (VARCHAR(42) NOT NULL)
   - opened_at (TIMESTAMP DEFAULT NOW())
   - UNIQUE(symbol, source_wallet)
   
   **config 表**：
   - key (VARCHAR(50) PRIMARY KEY)
   - value (TEXT NOT NULL)
   - updated_at (TIMESTAMP DEFAULT NOW())

**驗證**：
- 文件存在
- SQL 語法正確（可以用線上 SQL 語法檢查器驗證）
- 每個表的欄位類型和約束清晰

### 步驟 1.4：實現數據庫管理器
**指令**：
1. 在 `database/` 資料夾創建 `db_manager.py` 文件
2. 實現 `DatabaseManager` 類，包含以下方法：
   - `__init__(database_url)` - 初始化連接池
   - `create_tables()` - 讀取 schema.sql 並創建表
   - `close()` - 關閉連接池
   - `add_wallet(address, config)` - 添加錢包（INSERT）
   - `remove_wallet(address)` - 移除錢包（DELETE）
   - `get_all_wallets()` - 獲取所有錢包（SELECT）
   - `update_wallet_status(address, enabled)` - 更新啟用狀態
   - `add_position(position_data)` - 記錄持倉（INSERT OR REPLACE）
   - `remove_position(symbol, source_wallet)` - 移除持倉（DELETE）
   - `get_position(symbol)` - 查詢特定交易對持倉
   - `get_all_positions()` - 獲取當前所有持倉
3. 使用 `asyncpg` 連接池
4. 所有數據庫操作需要異常處理（try-except）
5. 添加詳細的註解說明每個方法

**驗證**：
- 文件存在且代碼編譯無錯誤
- 執行 `python -c "from database.db_manager import DatabaseManager; print('OK')"` 無報錯
- 代碼中有完整的異常處理

### 步驟 1.5：初始化數據庫表
**指令**：
1. 創建初始化腳本 `init_db.py` 在根目錄
2. 內容：
   - 載入環境變數
   - 初始化 DatabaseManager
   - 調用 `create_tables()` 方法
   - 打印「數據庫初始化成功」
   - 關閉連接
3. 執行初始化腳本

**驗證**：
- 腳本執行成功無報錯
- 登入 Railway PostgreSQL Dashboard（或使用 pgAdmin）
- 確認三個表（wallets, positions, config）已創建
- 表結構與設計一致

### 步驟 1.6：測試 CRUD 操作
**指令**：
1. 創建測試腳本 `test_db_crud.py`
2. 測試以下操作：
   - 添加一個測試錢包（地址：0xtest123...）
   - 查詢錢包列表，確認已添加
   - 更新錢包狀態為禁用
   - 再次查詢確認狀態已更新
   - 添加一個測試持倉（ETH-PERP, LONG, 1.0）
   - 查詢持倉列表，確認已添加
   - 刪除測試持倉
   - 刪除測試錢包
   - 確認所有數據已清空
3. 每步打印操作結果
4. 執行測試腳本

**驗證**：
- 所有操作成功執行
- 打印結果符合預期
- 最終數據庫為空（測試數據已清理）
- 無報錯或異常

---

## 階段 2：Hyperliquid 追蹤器

> 💡 補充：官方 Python SDK 與文檔  
> - Python SDK: https://github.com/hyperliquid-dex/hyperliquid-python-sdk  
> - 官方文檔: https://hyperliquid.gitbook.io/hyperliquid-docs/

### 步驟 2.1：研究 Hyperliquid Python SDK 及事件結構

**指令：**
1. 詳讀 Hyperliquid Python SDK 的 [README](https://github.com/hyperliquid-dex/hyperliquid-python-sdk) 與 [官方文檔](https://hyperliquid.gitbook.io/hyperliquid-docs/)。
2. 特別掌握以下內容：
   - Python SDK 的安裝與基本用法（pip install hyperliquid-python-sdk）
   - WebSocket 訂閱「user_events」方法（如何建立連線並監聽事件）
   - 持倉（Position）/ 成交（fill, order）/ user_events JSON 結構  
     👉 建議參考 SDK 的 `examples` 目錄及 `info.user_state(wallet_address)` 回傳格式
3. 使用測試網建立一個專用測試錢包，記錄下錢包地址（或者用現有測試網錢包）。

**驗證：**
- 已安裝 SDK，能順利 import
- 取得測試錢包地址
- 能說明 user_events 事件格式（建議複製一個真實例子到筆記）

---

### 步驟 2.2：基礎追蹤器類別實作

**指令：**
1. 新建 `core/hyperliquid_tracker.py` 檔案。
2. 參考官方 SDK 與文檔，定義 `HyperliquidTracker` 類別，包括：
   - `__init__(wallet_address)`：初始化（紀錄錢包地址、可選參數）
   - `connect()`：建立 WebSocket 連線
   - `subscribe()`：訂閱指定錢包的 user_events
   - `on_message(message)`：處理接收到的訊息（暫時先直接 print）
   - `disconnect()`：關閉連線
3. 使用 Hyperliquid Python SDK 內建的 ws 客戶端（如 examples 內 `ws_user_events.py` 做法）
4. 加入例外處理（try-except）與自動重連機制（中斷時自動重試）

**驗證：**
- 沒有語法錯誤，可成功 import
- 連線異常自動重試

---

### 步驟 2.3：WebSocket 連線測試腳本

**指令：**
1. 新建 `test_tracker.py` 測試腳本。
2. 內容包含：
   - 實例化 HyperliquidTracker，連接至測試錢包
   - 訂閱 user_events，運行 30 秒後自動中斷
   - 期間把所有收到的訊息打印出來（建議含 timestamp）
   - 測試期間錢包可手動發一筆測試網交易

**驗證：**
- 能正常建立 WebSocket 連線
- 可打印事件內容（即使無交易，也應該有 ping/pong 或空資料）
- 30 秒後正常斷線

---

### 步驟 2.4：解析與分類事件資料

**指令：**
1. 優化 `on_message` 方法，讓其依據事件格式能：
   - 分辨「開倉（fill/order）」、「平倉」、「倉位調整」等事件類型
2. 抓取事件中必要資訊：
   - 交易對（symbol）
   - 方向（side: LONG/SHORT）
   - 數量（size）
   - 價格（price）
3. 建議將解析結果存入 class 成員變數，或以漂亮格式 print 出來（附類型說明）

**驗證：**
- 真實測試網持倉有改變時，能正確識別並解析事件
- 所有核心屬性皆被正確擷取

---

### 步驟 2.5：計算錢包倉位比例

**指令：**
1. 在 HyperliquidTracker 內新增 `calculate_position_ratio(wallet_address)` 方法
2. 利用 SDK 查詢錢包原始資料（`info.user_state(wallet_address)`）
3. 計算方式：
   - 取出所有持倉價值（每一持倉：`size * entryPrice`，USD 計算）
   - 查出總資金（Account Equity / 賬戶餘額）
   - 倉位比例 formula: `倉位比例 = 持倉總價值 / 總資金`
4. 回傳一個介於 0~1 的小數

**驗證：**
- 給定錢包測試資料，倉位比例計算正確
- 處理極端狀態：總資金為 0 時回傳 0；倉位超出資金時正確顯示

---

## 階段 3：Lighter 交易執行器

### 步驟 3.1：研究 Lighter SDK
**指令**：
1. 閱讀 Lighter API 文檔：https://apidocs.lighter.xyz/docs
2. 閱讀 Python SDK：https://github.com/elliottech/lighter-python
3. 重點了解：
   - 認證方式（API Key）
   - 下市價單方法
   - 查詢賬戶餘額
   - 查詢持倉

**驗證**：
- 記錄 API 認證步驟
- 了解下單的參數格式
- 知道如何查詢餘額

### 步驟 3.2：實現 Lighter 客戶端
**指令**：
1. 在 `core/` 資料夾創建 `lighter_trader.py` 文件
2. 實現 `LighterTrader` 類，包含：
   - `__init__(api_key, api_secret, testnet=True)` - 初始化
   - `get_balance()` - 查詢可用餘額
   - `get_positions()` - 查詢當前持倉
   - `place_market_order(symbol, side, size)` - 下市價單
   - `close_position(symbol)` - 平倉
3. 使用 Lighter Python SDK
4. 添加異常處理和重試邏輯（5 次，間隔 3 秒）

**驗證**：
- 代碼無語法錯誤
- 可以導入該模塊

### 步驟 3.3：測試 Lighter 連接
**指令**：
1. 創建測試腳本 `test_lighter.py`
2. 初始化 Lighter 客戶端（使用測試網）
3. 查詢賬戶餘額並打印
4. 查詢當前持倉並打印

**驗證**：
- 成功連接到 Lighter 測試網
- 餘額查詢返回正確數據
- 持倉查詢返回正確數據

### 步驟 3.4：測試下單功能
**指令**：
1. 在測試網賬戶確保有足夠餘額
2. 執行一筆小額測試訂單（例如 0.001 ETH）
3. 等待訂單成交
4. 查詢持倉確認訂單已成交
5. 平倉該測試訂單

**驗證**：
- 訂單成功提交
- 訂單成交確認
- 持倉正確顯示
- 平倉成功執行

---

## 階段 4：策略引擎

### 步驟 4.1：設計策略引擎架構
**指令**：
1. 在 `core/` 資料夾創建 `strategy_engine.py` 文件
2. 實現 `StrategyEngine` 類，包含：
   - `__init__(db_manager, lighter_trader)` - 初始化
   - `on_wallet_event(event)` - 處理錢包事件入口
   - `calculate_follow_size(event)` - 計算跟單數量
   - `check_position_lock(symbol)` - 檢查交易對鎖定
   - `should_follow(event)` - 判斷是否跟單
3. 定義事件類型枚舉：OPEN, CLOSE, INCREASE, DECREASE, FLIP

**驗證**：
- 代碼無語法錯誤
- 類結構清晰
- 方法職責明確

### 步驟 4.2：實現倉位計算邏輯
**指令**：
1. 實現 `calculate_follow_size` 方法
2. 邏輯：
   - 從數據庫獲取我的總資金
   - 計算聰明錢包的倉位比例
   - 計算跟單金額 = 我的總資金 × 倉位比例
   - 檢查是否超過單筆最大金額限制
   - 返回最終跟單數量
3. 處理邊界情況（資金為 0、比例異常等）

**驗證**：
- 單元測試：給定輸入，輸出正確
- 測試用例：
  - 總資金 $10000，倉位比例 20% → 跟單 $2000
  - 超過最大限制時正確截斷
  - 資金不足時返回 0

### 步驟 4.3：實現交易對鎖定邏輯
**指令**：
1. 實現 `check_position_lock` 方法
2. 邏輯：
   - 查詢數據庫中該交易對是否有持倉
   - 如果有持倉，檢查 source_wallet 是否與當前事件來源一致
   - 返回是否允許跟單（True/False）
3. 添加註解說明鎖定規則

**驗證**：
- 測試用例：
  - 無持倉時，允許跟單
  - 有持倉且來源相同時，允許跟單
  - 有持倉但來源不同時，拒絕跟單

### 步驟 4.4：實現跟單決策邏輯
**指令**：
1. 實現 `should_follow` 方法
2. 檢查清單：
   - 錢包是否啟用（從數據庫查詢）
   - 交易對是否鎖定
   - 餘額是否充足
   - 滑點是否在範圍內（暫時跳過，後續實現）
3. 返回布爾值和原因（如果拒絕）

**驗證**：
- 測試各種場景：
  - 所有條件滿足 → 返回 True
  - 錢包禁用 → 返回 False 和原因
  - 餘額不足 → 返回 False 和原因

---

## 階段 5：Telegram Bot 基礎

### 步驟 5.1：創建 Bot 框架
**指令**：
1. 在 `bot/` 資料夾創建 `telegram_bot.py` 文件
2. 實現 `TelegramBot` 類，包含：
   - `__init__(token, admin_id)` - 初始化
   - `start()` - 啟動 Bot
   - `stop()` - 停止 Bot
3. 註冊 `/start` 命令處理器
4. `/start` 命令回應歡迎消息

**驗證**：
- 代碼無語法錯誤
- 可以導入該模塊

### 步驟 5.2：測試 Bot 基礎功能
**指令**：
1. 創建測試腳本 `test_bot.py`
2. 啟動 Bot
3. 在 Telegram 中發送 `/start` 命令
4. 確認收到回應
5. 保持運行 30 秒後關閉

**驗證**：
- Bot 成功啟動
- 收到 `/start` 回應
- 無錯誤日誌

### 步驟 5.3：實現按鈕式主菜單
**指令**：
1. 在 `bot/` 資料夾創建 `keyboards.py` 文件
2. 創建主菜單按鈕佈局：
   - 「查看錢包列表」
   - 「添加錢包」
   - 「系統狀態」
   - 「設置」
3. 修改 `/start` 命令，返回主菜單按鈕
4. 實現按鈕回調處理（先只打印點擊的按鈕）

**驗證**：
- 發送 `/start` 看到按鈕菜單
- 點擊按鈕有反應（打印日誌或回應）

### 步驟 5.4：實現錢包管理命令
**指令**：
1. 在 `bot/` 資料夾創建 `handlers.py` 文件
2. 實現以下功能：
   - 查看錢包列表：從數據庫讀取並顯示
   - 添加錢包：引導用戶輸入地址，存入數據庫
   - 刪除錢包：顯示列表供選擇，確認後刪除
3. 每個功能使用按鈕引導，減少文字輸入

**驗證**：
- 測試添加錢包流程完整
- 測試查看列表顯示正確
- 測試刪除錢包功能正常

---

## 階段 6：主控制器整合

### 步驟 6.1：創建主程序入口
**指令**：
1. 在根目錄創建 `main.py` 文件
2. 實現主程序邏輯：
   - 載入環境變數
   - 初始化數據庫管理器
   - 初始化 Hyperliquid 追蹤器
   - 初始化 Lighter 交易執行器
   - 初始化策略引擎
   - 初始化 Telegram Bot
3. 使用 asyncio 並發運行：
   - WebSocket 監聽任務
   - Telegram Bot 任務
4. 添加優雅關閉處理（Ctrl+C）

**驗證**：
- 代碼無語法錯誤
- 可以執行 `python main.py`
- 程序正常啟動

### 步驟 6.2：連接事件流
**指令**：
1. 在主程序中連接各模塊：
   - Hyperliquid 追蹤器接收到事件 → 傳給策略引擎
   - 策略引擎判斷跟單 → 調用 Lighter 執行器
   - Lighter 執行結果 → 更新數據庫
   - 所有動作 → 通過 Telegram Bot 通知
2. 使用 asyncio 的 Queue 或回調機制傳遞事件

**驗證**：
- 啟動程序無錯誤
- 各模塊正常初始化
- 日誌顯示連接狀態

### 步驟 6.3：實現日誌系統
**指令**：
1. 在 `utils/` 資料夾創建 `logger.py` 文件
2. 配置 loguru：
   - INFO 級別日誌輸出到控制台
   - DEBUG 級別日誌輸出到 `data/logs/debug.log`
   - ERROR 級別日誌輸出到 `data/logs/error.log`
   - 日誌自動輪轉（每天或每 10MB）
3. 在所有模塊中使用統一的 logger

**驗證**：
- 啟動程序後生成日誌文件
- 不同級別日誌分別記錄
- 日誌格式清晰易讀

---

## 階段 7：端到端測試

### 步驟 7.1：模擬錢包活動測試
**指令**：
1. 在測試網環境運行完整程序
2. 添加一個測試錢包到追蹤列表
3. 在該錢包執行以下操作（手動或腳本）：
   - 開倉 ETH 多單
   - 加倉
   - 減倉
   - 平倉
4. 觀察系統反應：
   - 追蹤器是否接收到事件
   - 策略引擎是否正確計算
   - Lighter 是否執行訂單
   - Telegram 是否發送通知

**驗證**：
- 每個事件都被正確處理
- 跟單訂單正確執行
- 數據庫記錄準確
- Telegram 通知及時

### 步驟 7.2：異常情況測試
**指令**：
1. 測試以下異常場景：
   - 模擬網絡斷線（斷開 WiFi 10 秒）
   - 模擬 API 限流（快速發送多個請求）
   - 模擬餘額不足（清空測試賬戶）
   - 模擬滑點過大（在波動大的市場下單）
2. 觀察系統行為：
   - 是否有重試機制
   - 是否發送警告通知
   - 是否記錄錯誤日誌

**驗證**：
- 網絡恢復後自動重連
- API 失敗後正確重試
- 餘額不足時暫停跟單並通知
- 所有異常都有日誌記錄

### 步驟 7.3：長時間運行測試
**指令**：
1. 在測試網運行程序 24 小時
2. 期間執行多次交易操作
3. 監控以下指標：
   - 內存使用是否穩定
   - WebSocket 是否保持連接
   - 日誌是否正常輪轉
   - 是否有未捕獲的異常

**驗證**：
- 程序穩定運行無崩潰
- 內存無洩漏
- 所有功能正常

---

## 階段 8：Railway 部署

### 步驟 8.1：創建 Dockerfile
**指令**：
1. 在根目錄創建 `Dockerfile`
2. 內容：
   - 使用 `python:3.10-slim` 基礎鏡像
   - 複製專案文件到 `/app`
   - 安裝依賴
   - 設定工作目錄
   - 啟動命令 `python main.py`
3. 創建 `.dockerignore` 排除 `venv/`, `.env`, `*.db`

**驗證**：
- 文件語法正確
- 本地構建測試：`docker build -t copytrade .`
- 構建成功無報錯

### 步驟 8.2：配置 Railway 專案
**指令**：
1. 註冊 Railway 賬號：https://railway.app
2. 創建新專案（New Project）
3. 選擇 "Deploy from GitHub repo"（或 "Empty Project" 手動上傳）
4. 如果使用 GitHub：
   - 連接 GitHub 倉庫
   - 選擇包含專案的倉庫和分支
   - Railway 自動檢測 Dockerfile
5. 添加 PostgreSQL 數據庫：
   - 在專案中點擊 "New" → "Database" → "PostgreSQL"
   - 等待創建完成
6. 配置環境變數：
   - 點擊應用服務（不是數據庫）
   - 進入 "Variables" 標籤
   - 添加所有 `.env` 內容（除了 DATABASE_URL，這會自動注入）
   - 重要變數：TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, LIGHTER_API_KEY, LIGHTER_API_SECRET 等
7. 確認 DATABASE_URL 已自動添加到環境變數

**驗證**：
- 專案成功創建
- PostgreSQL 服務顯示為 "Active"
- 環境變數配置完整（至少 6-8 個變數）
- DATABASE_URL 存在且格式正確

### 步驟 8.3：部署並驗證
**指令**：
1. 在 Railway 點擊 "Deploy"
2. 等待部署完成（2-5 分鐘）
3. 查看部署日誌確認啟動成功
4. 在 Telegram 測試 Bot 是否響應
5. 添加測試錢包並執行交易驗證功能

**驗證**：
- 部署狀態顯示 "Active"
- 日誌無錯誤
- Telegram Bot 正常工作
- 跟單功能正常

### 步驟 8.4：監控和維護
**指令**：
1. 設置 Railway 日誌查看快捷方式
2. 配置 Telegram 發送系統啟動/關閉通知
3. 定期檢查 Railway 日誌（每週一次）
4. 使用 Railway 內建的數據庫備份功能
5. 設置數據庫自動備份計劃（如果需要）

**驗證**：
- 能隨時查看運行狀態
- 異常能及時收到通知
- 了解如何恢復數據庫備份

---

## 完成檢查清單

部署完成後，確認以下所有功能：

- [ ] WebSocket 實時監聽聰明錢包
- [ ] 開倉事件正確跟單
- [ ] 平倉事件正確跟隨
- [ ] 加減倉位正確同步
- [ ] 倉位比例計算準確
- [ ] 交易對鎖定邏輯正確
- [ ] 止損機制生效
- [ ] 餘額不足自動暫停
- [ ] API 失敗重試生效
- [ ] 滑點過大拒絕跟單
- [ ] Telegram 添加/刪除錢包功能
- [ ] Telegram 查看狀態功能
- [ ] Telegram 實時通知功能
- [ ] 數據持久化正常
- [ ] 系統長時間運行穩定

---

## 後續優化方向

基礎功能完成後，可以考慮添加：

1. **進階統計**：勝率、盈虧曲線、最大回撤
2. **多策略支持**：不同錢包不同跟單比例
3. **智能過濾**：根據市場狀況自動調整跟單
4. **Web 控制面板**：更直觀的管理界面
5. **多用戶支持**：允許他人使用你的系統

每個優化都應該有獨立的測試和驗證步驟。

