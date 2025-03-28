
import os
from datetime import datetime
import math
import statistics
import time
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Bybit session
session = HTTP(
    testnet=True,
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)

def fetch_klines(symbol, interval, limit=500):
    """
    Fetch historical klines from Bybit.
    """
    response = session.get_kline(symbol=symbol, interval=interval, limit=limit)
    data = response["result"]["list"]
    # Ensure the data is sorted by open_time ascending
    data.sort(key=lambda x: int(x[0]))
    # print(data)

    # Convert numeric strings to float and open_time to int
    klines = []
    for d in data:
        klines.append({
            "open_time": int(d[0]),
            "open": float(d[1]),
            "high": float(d[2]),
            "low": float(d[3]),
            "close": float(d[4]),
            "volume": float(d[5])
        })
    return klines

def moving_average(values, length, ma_type="SMA", volumes=None):
    """
    Calculate moving average for a list of values.
    Supported types: "SMA", "EMA", "SMMA (RMA)", "WMA", "VWMA".
    For VWMA, a list of volumes must be provided.
    Returns a list with None for indices where the average cannot be computed.
    """
    ma = [None] * len(values)
    
    if ma_type == "SMA":
        for i in range(len(values)):
            if i + 1 >= length:
                window = values[i - length + 1: i + 1]
                ma[i] = sum(window) / length

    elif ma_type == "EMA":
        alpha = 2 / (length + 1)
        for i in range(len(values)):
            if i == 0:
                ma[i] = values[i]
            else:
                if ma[i-1] is None and i + 1 >= length:
                    # Initialize with SMA if previous EMA is not set yet
                    window = values[i - length + 1: i + 1]
                    ma[i] = sum(window) / length
                else:
                    ma[i] = alpha * values[i] + (1 - alpha) * (ma[i-1] if ma[i-1] is not None else values[i])
    elif ma_type == "SMMA (RMA)":
        # Recursive Moving Average: first value is SMA then recursive formula with alpha=1/length
        alpha = 1 / length
        for i in range(len(values)):
            if i + 1 == length:
                window = values[0: length]
                ma[i] = sum(window) / length
            elif i + 1 > length:
                ma[i] = alpha * values[i] + (1 - alpha) * ma[i-1]
    elif ma_type == "WMA":
        weights = list(range(1, length + 1))
        weight_sum = sum(weights)
        for i in range(len(values)):
            if i + 1 >= length:
                window = values[i - length + 1: i + 1]
                weighted = sum(w * v for w, v in zip(weights, window))
                ma[i] = weighted / weight_sum
    elif ma_type == "VWMA":
        if volumes is None:
            raise ValueError("Volumes are required for VWMA")
        for i in range(len(values)):
            if i + 1 >= length:
                price_window = values[i - length + 1: i + 1]
                vol_window = volumes[i - length + 1: i + 1]
                weighted_sum = sum(p * v for p, v in zip(price_window, vol_window))
                vol_sum = sum(vol_window)
                ma[i] = weighted_sum / vol_sum if vol_sum != 0 else None
    else:
        raise ValueError("Unsupported moving average type")
    return ma

def calculate_stdev(values, length):
    """
    Calculate rolling sample standard deviation for a list of values.
    Returns a list with None for indices where it cannot be computed.
    """
    stdev = [None] * len(values)
    for i in range(len(values)):
        if i + 1 >= length:
            window = values[i - length + 1: i + 1]
            # statistics.stdev uses sample standard deviation (n-1 in denominator)
            if len(window) > 1:
                stdev[i] = statistics.stdev(window)
            else:
                stdev[i] = 0.0
    return stdev

def calculate_bollinger_bands(klines, length=20, ma_type="SMA", mult=2.0):
    """
    Calculate Bollinger Bands based on closing prices.
    Returns four lists: basis, upper, lower, and dev.
    """
    closes = [k["close"] for k in klines]
    volumes = [k["volume"] for k in klines]
    
    basis = moving_average(closes, length, ma_type, volumes if ma_type=="VWMA" else None)
    stdev_list = calculate_stdev(closes, length)
    dev = [None if s is None else s * mult for s in stdev_list]
    upper = [None if b is None or d is None else b + d for b, d in zip(basis, dev)]
    lower = [None if b is None or d is None else b - d for b, d in zip(basis, dev)]
    return basis, upper, lower, dev

def generate_signals(klines, basis, upper, lower, dev, start_ts, end_ts):
    """
    Generate trading signals based on Bollinger Bands.
    Returns a list of trade signals as tuples:
    (timestamp, action, price, stop_loss, take_profit)
    """
    signals = []
    position = 0  # 0: no position, 1: long, -1: short
    
    # Iterate over klines starting from index 1 to check for crossovers
    for i in range(1, len(klines)):
        ts = klines[i]["open_time"]
        # Only consider candles within date range
        if ts < start_ts or ts > end_ts:
            continue
        
        prev_close = klines[i-1]["close"]
        curr_close = klines[i]["close"]
        prev_basis = basis[i-1]
        curr_basis = basis[i]
        prev_lower = lower[i-1]
        curr_lower = lower[i]
        prev_upper = upper[i-1]
        curr_upper = upper[i]
        
        # Skip if any indicator is None
        if None in (prev_close, curr_close, prev_basis, curr_basis, prev_lower, curr_lower, prev_upper, curr_upper, dev[i]):
            continue

        # Long Entry: crossover of close above lower band
        if position == 0 and prev_close <= prev_lower and curr_close > curr_lower:
            entry_price = curr_close
            stop_loss = lower[i] - (dev[i] * 0.5)
            take_profit = curr_basis + (dev[i] * 1.5)
            signals.append((ts, "Long Entry", entry_price, stop_loss, take_profit))
            position = 1
        # Long Exit: crossunder of close below basis
        elif position == 1 and prev_close >= prev_basis and curr_close < curr_basis:
            exit_price = curr_close
            signals.append((ts, "Long Exit", exit_price, None, None))
            position = 0
        # Short Entry: crossunder of close below upper band
        elif position == 0 and prev_close >= prev_upper and curr_close < curr_upper:
            entry_price = curr_close
            stop_loss = upper[i] + (dev[i] * 0.5)
            take_profit = curr_basis - (dev[i] * 1.5)
            signals.append((ts, "Short Entry", entry_price, stop_loss, take_profit))
            position = -1
        # Short Exit: crossover of close above basis
        elif position == -1 and prev_close <= prev_basis and curr_close > curr_basis:
            exit_price = curr_close
            signals.append((ts, "Short Exit", exit_price, None, None))
            position = 0
    return signals

def place_order(symbol, side, qty, price=None):
    """
    Place an order using pybit.
    For market orders, price is omitted.
    """
    order_type = "market" if price is None else "limit"
    order = session.place_order(
        category="linear",
        symbol=symbol,
        side=side,
        orderType=order_type,
        qty=qty,
        timeInForce="GTC"
    )
    print(f"Placed {side} order: {order}")
    return order

def main():
    # Parameters (adjust as necessary)
    symbol = "BTCUSDT"
    interval = "15"  # 60-minute candles
    length = 5
    ma_type = "SMA"  # Options: "SMA", "EMA", "SMMA (RMA)", "WMA", "VWMA"
    mult = 2.0

    # Define date range (convert to epoch seconds)
    start_date = datetime(2018, 1, 1)
    end_date = datetime(2069, 12, 31)
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())

    # Fetch historical data
    klines = fetch_klines(symbol, interval)
    
    # Calculate Bollinger Bands
    basis, upper, lower, dev = calculate_bollinger_bands(klines, length, ma_type, mult)
    # print(basis, upper, lower, dev)
    # print(basis)
    
    # Generate signals based on our strategy
    signals = generate_signals(klines, basis, upper, lower, dev, start_ts, end_ts)
    
    print("Trade signals generated:")
    print(signals)
    for sig in signals:
        ts, action, price, stop_loss, take_profit = sig
        time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        print(f"{time_str} - {action}: Price={price}, StopLoss={stop_loss}, TakeProfit={take_profit}")

    # Example: Place an order based on the latest signal (for live trading, implement continuous monitoring)
    # if signals:
    #     last_signal = signals[-1]
    #     ts, action, price, stop_loss, take_profit = last_signal
    #     print(f"Latest signal at {datetime.fromtimestamp(ts)}: {action} at price {price}")
    #     if "Entry" in action:
    #         qty = 1  # Set desired quantity
    #         side = "Buy" if "Long" in action else "Sell"
    #         place_order(symbol, side, qty)

if __name__ == "__main__":
    main()

