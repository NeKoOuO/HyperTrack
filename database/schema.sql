-- ============================================
-- HyperTrack 數據庫結構定義
-- 使用 PostgreSQL
-- ============================================

-- 錢包追蹤表：存儲要追蹤的聰明錢包
CREATE TABLE IF NOT EXISTS wallets (
    id SERIAL PRIMARY KEY,
    -- 錢包地址（以太坊格式，42 字符含 0x）
    address VARCHAR(42) UNIQUE NOT NULL,
    -- 是否啟用追蹤
    enabled BOOLEAN DEFAULT TRUE,
    -- 單筆最大跟單金額（美元）
    max_position_usd DECIMAL(10, 2) DEFAULT 1000.00,
    -- 止損比例（0.5 = 虧損 50% 時強制平倉）
    stop_loss_ratio DECIMAL(5, 4) DEFAULT 0.5000,
    -- 錢包備註名稱（方便識別）
    nickname VARCHAR(50),
    -- 創建時間
    created_at TIMESTAMP DEFAULT NOW(),
    -- 更新時間
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 持倉記錄表：存儲當前跟單持倉
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    -- 交易對（如 ETH-PERP, BTC-PERP）
    symbol VARCHAR(20) NOT NULL,
    -- 方向（LONG 做多 / SHORT 做空）
    side VARCHAR(10) NOT NULL,
    -- 持倉數量
    size DECIMAL(20, 8) NOT NULL,
    -- 進場價格
    entry_price DECIMAL(20, 8) NOT NULL,
    -- 來源錢包地址（跟的是哪個聰明錢包）
    source_wallet VARCHAR(42) NOT NULL,
    -- 開倉時間
    opened_at TIMESTAMP DEFAULT NOW(),
    -- 更新時間
    updated_at TIMESTAMP DEFAULT NOW(),
    -- 同一交易對只能跟一個錢包（交易對鎖定）
    UNIQUE(symbol, source_wallet)
);

-- 系統配置表：存儲全局設定
CREATE TABLE IF NOT EXISTS config (
    -- 配置項名稱
    key VARCHAR(50) PRIMARY KEY,
    -- 配置值（JSON 格式存儲複雜數據）
    value TEXT NOT NULL,
    -- 配置描述
    description VARCHAR(200),
    -- 更新時間
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 交易歷史表：記錄所有交易（用於統計和追蹤）
CREATE TABLE IF NOT EXISTS trade_history (
    id SERIAL PRIMARY KEY,
    -- 交易對
    symbol VARCHAR(20) NOT NULL,
    -- 方向
    side VARCHAR(10) NOT NULL,
    -- 數量
    size DECIMAL(20, 8) NOT NULL,
    -- 成交價格
    price DECIMAL(20, 8) NOT NULL,
    -- 交易類型（OPEN 開倉 / CLOSE 平倉 / INCREASE 加倉 / DECREASE 減倉）
    trade_type VARCHAR(20) NOT NULL,
    -- 來源錢包
    source_wallet VARCHAR(42) NOT NULL,
    -- 盈虧（平倉時計算）
    pnl DECIMAL(20, 8),
    -- 交易時間
    created_at TIMESTAMP DEFAULT NOW()
);

-- 創建索引以提升查詢效能
CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets(address);
CREATE INDEX IF NOT EXISTS idx_wallets_enabled ON wallets(enabled);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_source ON positions(source_wallet);
CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_history_created ON trade_history(created_at);

-- 插入預設配置
INSERT INTO config (key, value, description) VALUES
    ('trading_enabled', 'true', '是否啟用自動跟單'),
    ('max_total_position_usd', '5000', '總持倉上限（美元）'),
    ('slippage_tolerance', '0.01', '滑點容忍度（1%）')
ON CONFLICT (key) DO NOTHING;

