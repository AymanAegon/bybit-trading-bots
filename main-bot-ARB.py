
import os
import logging
import time
from pybit.unified_trading import HTTP
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from dotenv import load_dotenv

import pandas as pd

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# Initialize the Bybit session
session = HTTP(
    testnet=False,
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET")
)

# Strategy parameters
symbol = "ARBUSDT"
fast_length = 9
slow_length = 21
rsi_length = 14
rsi_overbought = 70
rsi_oversold = 30
timeframe = "1"  # Use "1" for 1-minute; change to "5" for 5-minute timeframe

def fetch_klines(symbol, interval, limit=100):
    """Fetch historical kline data from Bybit."""
    try:
        response = session.get_kline(symbol=symbol, interval=interval, limit=limit)
        if response['retCode'] != 0:
            logging.error("Error fetching klines: %s", response)
            return None
        # print(response)
        # data = response['result']
        # df = pd.DataFrame(data)
        columns = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        df = pd.DataFrame(response['result']["list"], columns=columns)

        # df['open_time'] = pd.to_datetime(df['open_time'], unit='s')
        df['open_time'] = pd.to_datetime(df['open_time'].astype(float), unit='ms')
        df.set_index('open_time', inplace=True)
        df = df.astype(float)
        return df
    except Exception as e:
        logging.error("Exception in fetch_klines: %s", e)
        return None

def calculate_indicators(df):
    """Calculate SMA and RSI indicators for the dataframe."""
    df['fast_sma'] = SMAIndicator(close=df['close'], window=fast_length).sma_indicator()
    df['slow_sma'] = SMAIndicator(close=df['close'], window=slow_length).sma_indicator()
    df['rsi'] = RSIIndicator(close=df['close'], window=rsi_length).rsi()
    return df

def generate_signals(df):
    """
    Generate trading signals based on SMA crossover and RSI filter.
    - Long signal: fast SMA crosses above slow SMA and RSI is above the oversold threshold.
    - Short signal: fast SMA crosses below slow SMA and RSI is below the overbought threshold.
    """
    if df is None or len(df) < 2:
        return None
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    signal = None
    if (prev['fast_sma'] < prev['slow_sma']) and (last['fast_sma'] > last['slow_sma']) and (last['rsi'] > rsi_oversold):
        signal = 'long'
    elif (prev['fast_sma'] > prev['slow_sma']) and (last['fast_sma'] < last['slow_sma']) and (last['rsi'] < rsi_overbought):
        signal = 'short'
    return signal

def get_open_position():
    """Retrieve the current open position for the symbol, if any."""
    try:
        positions = session.get_positions(category="inverse", symbol=symbol)
        if positions['retCode'] != 0:
            logging.error("Error fetching positions: %s", positions)
            return None
        for pos in positions['result']['list']:
            if float(pos['size']) > 0:
                return pos
        return None
    except Exception as e:
        logging.error("Exception in get_open_position: %s", e)
        return None

def place_order(side, qty):
    """Place a market order."""
    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GTC",
            reduce_only=False,
            close_on_trigger=False
        )
        if order['retCode'] != 0:
            logging.error("Order error: %s", order)
        else:
            logging.info("Order placed: %s", order)
    except Exception as e:
        logging.error("Exception in place_order: %s", e)

def close_position(side, qty):
    """Close an existing position using a market order."""
    try:
        order = session.place_order(
            category="linear",
            symbol=symbol,
            side=side,
            order_type="Market",
            qty=qty,
            time_in_force="GTC",
            reduceOnly=True,
            closeOnTrigger=True
        )
        if order['retCode'] != 0:
            logging.error("Close order error: %s", order)
        else:
            logging.info("Position closed: %s", order)
    except Exception as e:
        logging.error("Exception in close_position: %s", e)

def main():
    qty = 16.3  # Adjust the trade quantity as needed
    while True:
        df = fetch_klines(symbol, interval=timeframe)
        if df is not None:
            df = calculate_indicators(df)
            signal = generate_signals(df)
            open_pos = get_open_position()
            # print(df)
            logging.info("Generated signal: %s", signal)
            # Manage open positions
            if open_pos:
                current_side = open_pos['side']  # "Buy" for long positions, "Sell" for short positions
                # If current position contradicts the new signal, close the position
                if signal == 'long' and current_side == "Sell":
                    logging.info("Signal reversal: Closing short position.")
                    close_position("Buy", abs(float(open_pos['size'])))
                elif signal == 'short' and current_side == "Buy":
                    logging.info("Signal reversal: Closing long position.")
                    close_position("Sell", abs(float(open_pos['size'])))
                else:
                    logging.info("No change in position. Holding current position.")
            else:
                # No open position, open a new one if there's a signal
                if signal == 'long':
                    logging.info("Placing new long order.")
                    place_order("Buy", qty)
                elif signal == 'short':
                    logging.info("Placing new short order.")
                    place_order("Sell", qty)
                else:
                    logging.info("No valid trading signal at this time.")
        else:
            logging.error("Failed to fetch kline data.")
        
        # Sleep duration: adjust sleep time based on timeframe (60 seconds for 1-min, 300 for 5-min)
        # sleep_time = 60 if timeframe == "1" else 300
        sleep_time = 60  # 15-minute timeframe
        time.sleep(sleep_time)

if __name__ == '__main__':
    main()
    # place_order("Buy", 16.3)
    # close_position("Sell", 16.3)
