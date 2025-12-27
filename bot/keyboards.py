"""
Telegram Bot 鍵盤佈局
定義各種按鈕和選單
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


# ========== 回調數據前綴 ==========
# 用於識別按鈕點擊的來源

class CallbackData:
    """回調數據常量"""
    # 主菜單
    MENU_WALLETS = "menu:wallets"
    MENU_ADD_WALLET = "menu:add_wallet"
    MENU_STATUS = "menu:status"
    MENU_SETTINGS = "menu:settings"
    
    # 錢包操作
    WALLET_LIST = "wallet:list"
    WALLET_ADD = "wallet:add"
    WALLET_DELETE = "wallet:delete"
    WALLET_TOGGLE = "wallet:toggle"
    WALLET_DETAIL = "wallet:detail"
    
    # 確認操作
    CONFIRM_YES = "confirm:yes"
    CONFIRM_NO = "confirm:no"
    
    # 返回
    BACK_MAIN = "back:main"
    BACK_WALLETS = "back:wallets"
    
    # 設置
    SETTINGS_MAX_POSITION = "settings:max_position"
    SETTINGS_STOP_LOSS = "settings:stop_loss"
    
    # 控制
    CONTROL_PAUSE = "control:pause"
    CONTROL_RESUME = "control:resume"
    CONTROL_EMERGENCY_STOP = "control:emergency"


# ========== 主菜單 ==========

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    獲取主菜單鍵盤
    
    佈局：
    [📋 錢包列表] [➕ 添加錢包]
    [📊 系統狀態] [⚙️ 設置]
    """
    keyboard = [
        [
            InlineKeyboardButton("📋 錢包列表", callback_data=CallbackData.MENU_WALLETS),
            InlineKeyboardButton("➕ 添加錢包", callback_data=CallbackData.MENU_ADD_WALLET),
        ],
        [
            InlineKeyboardButton("📊 系統狀態", callback_data=CallbackData.MENU_STATUS),
            InlineKeyboardButton("⚙️ 設置", callback_data=CallbackData.MENU_SETTINGS),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ========== 錢包管理 ==========

def get_wallets_menu_keyboard() -> InlineKeyboardMarkup:
    """
    獲取錢包管理菜單
    
    佈局：
    [📋 查看列表]
    [➕ 添加錢包] [🗑️ 刪除錢包]
    [🔙 返回主菜單]
    """
    keyboard = [
        [
            InlineKeyboardButton("📋 查看列表", callback_data=CallbackData.WALLET_LIST),
        ],
        [
            InlineKeyboardButton("➕ 添加錢包", callback_data=CallbackData.WALLET_ADD),
            InlineKeyboardButton("🗑️ 刪除錢包", callback_data=CallbackData.WALLET_DELETE),
        ],
        [
            InlineKeyboardButton("🔙 返回主菜單", callback_data=CallbackData.BACK_MAIN),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_wallet_list_keyboard(wallets: list) -> InlineKeyboardMarkup:
    """
    獲取錢包列表鍵盤
    每個錢包一個按鈕，點擊可查看詳情
    
    Args:
        wallets: 錢包列表，每個元素包含 address 和 enabled
    """
    keyboard = []
    
    for wallet in wallets:
        address = wallet.get("address", "")
        enabled = wallet.get("enabled", True)
        
        # 顯示前後各6個字符
        short_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        
        # 狀態圖標
        status_icon = "✅" if enabled else "❌"
        
        button_text = f"{status_icon} {short_addr}"
        callback_data = f"{CallbackData.WALLET_DETAIL}:{address}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    # 添加返回按鈕
    keyboard.append([
        InlineKeyboardButton("🔙 返回", callback_data=CallbackData.BACK_WALLETS)
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_wallet_detail_keyboard(address: str, enabled: bool) -> InlineKeyboardMarkup:
    """
    獲取錢包詳情鍵盤
    
    Args:
        address: 錢包地址
        enabled: 是否啟用
    """
    toggle_text = "❌ 禁用錢包" if enabled else "✅ 啟用錢包"
    
    keyboard = [
        [
            InlineKeyboardButton(toggle_text, callback_data=f"{CallbackData.WALLET_TOGGLE}:{address}"),
        ],
        [
            InlineKeyboardButton("🗑️ 刪除錢包", callback_data=f"{CallbackData.WALLET_DELETE}:{address}"),
        ],
        [
            InlineKeyboardButton("🔙 返回列表", callback_data=CallbackData.WALLET_LIST),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delete_wallet_keyboard(wallets: list) -> InlineKeyboardMarkup:
    """
    獲取刪除錢包選擇鍵盤
    
    Args:
        wallets: 錢包列表
    """
    keyboard = []
    
    for wallet in wallets:
        address = wallet.get("address", "")
        short_addr = f"{address[:6]}...{address[-4:]}" if len(address) > 10 else address
        
        callback_data = f"{CallbackData.WALLET_DELETE}:{address}"
        keyboard.append([InlineKeyboardButton(f"🗑️ {short_addr}", callback_data=callback_data)])
    
    keyboard.append([
        InlineKeyboardButton("🔙 取消", callback_data=CallbackData.BACK_WALLETS)
    ])
    
    return InlineKeyboardMarkup(keyboard)


# ========== 確認對話框 ==========

def get_confirm_keyboard(action_data: str = "") -> InlineKeyboardMarkup:
    """
    獲取確認對話框鍵盤
    
    Args:
        action_data: 確認後要執行的操作數據
    """
    keyboard = [
        [
            InlineKeyboardButton("✅ 確認", callback_data=f"{CallbackData.CONFIRM_YES}:{action_data}"),
            InlineKeyboardButton("❌ 取消", callback_data=CallbackData.CONFIRM_NO),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ========== 設置菜單 ==========

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """
    獲取設置菜單鍵盤
    """
    keyboard = [
        [
            InlineKeyboardButton("💰 最大跟單金額", callback_data=CallbackData.SETTINGS_MAX_POSITION),
        ],
        [
            InlineKeyboardButton("🛑 止損比例", callback_data=CallbackData.SETTINGS_STOP_LOSS),
        ],
        [
            InlineKeyboardButton("🔙 返回主菜單", callback_data=CallbackData.BACK_MAIN),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ========== 系統狀態 ==========

def get_status_keyboard() -> InlineKeyboardMarkup:
    """
    獲取系統狀態頁面鍵盤
    """
    keyboard = [
        [
            InlineKeyboardButton("🔄 刷新", callback_data=CallbackData.MENU_STATUS),
        ],
        [
            InlineKeyboardButton("⏸️ 暫停跟單", callback_data=CallbackData.CONTROL_PAUSE),
            InlineKeyboardButton("▶️ 繼續跟單", callback_data=CallbackData.CONTROL_RESUME),
        ],
        [
            InlineKeyboardButton("🚨 緊急停止", callback_data=CallbackData.CONTROL_EMERGENCY_STOP),
        ],
        [
            InlineKeyboardButton("🔙 返回主菜單", callback_data=CallbackData.BACK_MAIN),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ========== 取消鍵盤 ==========

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    獲取取消操作鍵盤
    """
    keyboard = [
        [
            InlineKeyboardButton("❌ 取消", callback_data=CallbackData.BACK_MAIN),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

