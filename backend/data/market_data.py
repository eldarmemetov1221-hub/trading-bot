import aiohttp
import asyncio
import pandas as pd
import numpy as np
from typing import Optional
import time

CRYPTO_PAIRS = {
    "BTC/USDT": "BTCUSDT",
    "ETH/USDT": "ETHUSDT",
    "BNB/USDT": "BNBUSDT",
    "SOL/USDT": "SOLUSDT",
    "XRP/USDT": "XRPUSDT",
    "ADA/USDT": "ADAUSDT",
    "DOGE/USDT": "DOGEUSDT",
    "AVAX/USDT": "AVAXUSDT",
    "DOT/USDT": "DOTUSDT",
    "LINK/USDT": "LINKUSDT",
    "MATIC/USDT": "MATICUSDT",
    "LTC/USDT": "LTCUSDT",
}

FOREX_PAIRS = {
    "EUR/USD": "EURUSD",
    "GBP/USD": "GBPUSD",
    "USD/JPY": "USDJPY",
    "USD/CHF": "USDCHF",
    "AUD/USD": "AUDUSD",
    "USD/CAD": "USDCAD",
    "NZD/USD": "NZDUSD",
    "EUR/GBP": "EURGBP",
    "EUR/JPY": "EURJPY",
    "GBP/JPY": "GBPJPY",
}

TF_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1d": "1d",
}

BINANCE_TF = {
    "1m": "1m", "5m": "5m", "15m": "15m",
    "1h": "1h", "4h": "4h", "1d": "1d",
}

async def get_crypto_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> Optional[pd.DataFrame]:
    binance_symbol = CRYPTO_PAIRS.get(symbol, symbol.replace("/", ""))
    interval = BINANCE_TF.get(timeframe, "15m")
    url = f"https://api.binance.com/api/v3/klines?symbol={binance_symbol}&interval={interval}&limit={limit}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
        df = pd.DataFrame(data, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","qav","num_trades","taker_buy_base","taker_buy_quote","ignore"
        ])
        df = df[["timestamp","open","high","low","close","volume"]].astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df
    except Exception as e:
        print(f"[market_data] crypto error: {e}")
        return None

async def get_forex_ohlcv(symbol: str, timeframe: str, limit: int = 500) -> Optional[pd.DataFrame]:
    # Use Alpha Vantage free tier or Twelve Data for forex
    # Fallback: generate synthetic data based on known price ranges for demo
    # Replace with real API when key is provided
    pair = FOREX_PAIRS.get(symbol, "EURUSD")

    base_prices = {
        "EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 149.50,
        "USDCHF": 0.8900, "AUDUSD": 0.6550, "USDCAD": 1.3600,
        "NZDUSD": 0.6050, "EURGBP": 0.8550, "EURJPY": 162.00, "GBPJPY": 189.50,
    }

    tf_minutes = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
    minutes = tf_minutes.get(timeframe, 15)

    base = base_prices.get(pair, 1.0)
    volatility = base * 0.0002 * (minutes ** 0.5)

    np.random.seed(int(time.time()) % 1000)
    closes = [base]
    for _ in range(limit - 1):
        change = np.random.normal(0, volatility)
        closes.append(closes[-1] + change)

    timestamps = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq=f"{minutes}min")
    opens, highs, lows = [], [], []
    for i, c in enumerate(closes):
        o = closes[i-1] if i > 0 else c
        h = max(o, c) + abs(np.random.normal(0, volatility * 0.5))
        l = min(o, c) - abs(np.random.normal(0, volatility * 0.5))
        opens.append(o); highs.append(h); lows.append(l)

    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows, "close": closes,
        "volume": np.random.randint(1000, 50000, limit).astype(float)
    }, index=timestamps)
    return df

async def get_ohlcv(symbol: str, timeframe: str, limit: int = 500, asset_type: str = "crypto") -> Optional[pd.DataFrame]:
    if asset_type == "crypto":
        return await get_crypto_ohlcv(symbol, timeframe, limit)
    else:
        return await get_forex_ohlcv(symbol, timeframe, limit)
