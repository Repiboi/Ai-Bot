import MetaTrader5 as mt5
import pandas as pd
import time


# Connect to MetaTrader 5
def connect_mt5():
    if not mt5.initialize():
        print("Failed to initialize MT5, error:", mt5.last_error())
        return False
    print("Connected to MT5!")
    return True

# Get account balance
def get_balance():
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info, error:", mt5.last_error())
        return None
    return account_info.balance

# Fetch historical data with error handling
def fetch_data(symbol, timeframe, num_candles=100):
    try:
        # Check if symbol is available
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"Symbol {symbol} not found. Check broker naming conventions.")
            return None
        if not symbol_info.visible:
            # Enable the symbol in Market Watch
            if not mt5.symbol_select(symbol, True):
                print(f"Failed to select symbol {symbol}, error:", mt5.last_error())
                return None
        
        # Fetch historical data
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        if rates is None or len(rates) == 0:
            print(f"Failed to fetch rates for {symbol}, error:", mt5.last_error())
            return None
        
        return pd.DataFrame(rates)
    except Exception as e:
        print(f"Exception occurred while fetching data for {symbol}: {e}")
        return None

# Example strategy: Simple Moving Average crossover
def sma_strategy(data, short_window=10, long_window=30):
    data['SMA_short'] = data['close'].rolling(window=short_window).mean()
    data['SMA_long'] = data['close'].rolling(window=long_window).mean()
    if data['SMA_short'].iloc[-1] > data['SMA_long'].iloc[-1]:
        return "BUY"
    elif data['SMA_short'].iloc[-1] < data['SMA_long'].iloc[-1]:
        return "SELL"
    return "HOLD"

# Place order with volume validation
def place_order(symbol, action, volume, risk_percent=1):
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        return

    # Adjust volume to match broker requirements
    volume = max(symbol_info.volume_min, min(volume, symbol_info.volume_max))
    volume = round(volume / symbol_info.volume_step) * symbol_info.volume_step

    if volume < symbol_info.volume_min or volume > symbol_info.volume_max:
        print(f"Volume {volume} is invalid for {symbol}.")
        return

    # Get order type and price
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL
    price = mt5.symbol_info_tick(symbol).ask if action == "BUY" else mt5.symbol_info_tick(symbol).bid

    # Calculate stop loss
    balance = get_balance()
    if balance is None:
        print("Failed to fetch account balance. Aborting order.")
        return
    stop_loss = price - (risk_percent / 100 * balance) if action == "BUY" else price + (risk_percent / 100 * balance)

    # Create trade request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "sl": stop_loss,
        "deviation": 10,
        "magic": 123456,
        "comment": "Python Bot Trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Print the request for debugging
    print("Order request:", request)

    # Send the trade request
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed for {action} {symbol}, error:", result.retcode)
    else:
        print(f"Order placed successfully: {action} {volume} {symbol}")

# Main trading loop
def trading_bot(symbol, risk_percent=1, volume=0.01, timeframe=mt5.TIMEFRAME_M1):
    if not connect_mt5():
        return

    try:
        while True:
            # Get account balance and calculate stop loss
            balance = get_balance()
            if balance is None:
                break

            # Fetch historical data
            data = fetch_data(symbol, timeframe)
            if data is None or data.empty:
                print(f"No data available for {symbol}. Retrying...")
                time.sleep(60)
                continue

            # Check strategy
            action = sma_strategy(data)
            if action in ["BUY", "SELL"]:
                place_order(symbol, action, volume, risk_percent)
            else:
                print("No trading signal. Waiting...")

            # Wait before next check
            time.sleep(60)
    finally:    
        mt5.shutdown()

# Run the bot
if __name__ == "__main__":
    symbol = "XAUUSD"  
    trading_bot(symbol, risk_percent=1, volume=0.01)
