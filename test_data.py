import asyncio, sys, os
sys.path.insert(0, ".")
from dotenv import load_dotenv; load_dotenv()

from analysis.market_data import TradingViewFeed, MarketDataFetcher

async def test():
    f = MarketDataFetcher()

    print("=== Testing BTCUSDT 5m ===")
    df = await f.get_ohlcv("BTCUSDT", "5m", 100)
    print(f"Bars: {len(df)}, last close: {df['close'].iloc[-1]:.2f}")

    print("=== Ticker ===")
    p = await f.get_current_price("BTCUSDT")
    print(f"BTC: ${p['price']:,.2f}  Change: {p['change_pct']:+.2f}%")

    print("=== TV WebSocket: EURUSD 15m ===")
    tv = TradingViewFeed()
    df_tv = await tv.get_ohlcv("FX:EURUSD", "15m", 100)
    if df_tv is not None:
        print(f"TV EUR/USD: {len(df_tv)} bars, last: {df_tv['close'].iloc[-1]:.5f}")
    else:
        print("TV WS failed (trying synthetic fallback)")

    print("=== EURUSD fallback ===")
    df2 = await f.get_ohlcv("EURUSD", "15m", 100)
    print(f"EUR/USD bars: {len(df2)}, last: {df2['close'].iloc[-1]:.5f}")

    await f.close()
    print("\n=== ALL OK ===")

asyncio.run(test())
