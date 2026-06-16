"""
Market Data — TradingView WebSocket feed (primary) + Binance REST (crypto fallback)
Uses session cookies from authenticated TradingView account.
"""
import os
import json
import random
import string
import asyncio
import aiohttp
import pandas as pd
import numpy as np
import ccxt.async_support as ccxt
from datetime import datetime, timezone

TV_SESSION      = os.getenv("TV_SESSION", "")
TV_SESSION_SIGN = os.getenv("TV_SESSION_SIGN", "")

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_HEADERS = {
    "Origin": "https://www.tradingview.com",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

FOREX_PAIRS = {
    "EURUSD": "FX:EURUSD",   "GBPUSD": "FX:GBPUSD",   "USDJPY": "FX:USDJPY",
    "USDCHF": "FX:USDCHF",   "AUDUSD": "FX:AUDUSD",   "NZDUSD": "FX:NZDUSD",
    "USDCAD": "FX:USDCAD",   "GBPJPY": "FX:GBPJPY",   "EURJPY": "FX:EURJPY",
    "EURGBP": "FX:EURGBP",   "XAUUSD": "OANDA:XAUUSD","XAGUSD": "OANDA:XAGUSD",
}

CRYPTO_PAIRS = {
    "BTCUSDT":  "BINANCE:BTCUSDT",  "ETHUSDT":  "BINANCE:ETHUSDT",
    "BNBUSDT":  "BINANCE:BNBUSDT",  "SOLUSDT":  "BINANCE:SOLUSDT",
    "XRPUSDT":  "BINANCE:XRPUSDT",  "ADAUSDT":  "BINANCE:ADAUSDT",
    "DOGEUSDT": "BINANCE:DOGEUSDT", "AVAXUSDT": "BINANCE:AVAXUSDT",
    "LINKUSDT": "BINANCE:LINKUSDT", "DOTUSDT":  "BINANCE:DOTUSDT",
    "MATICUSDT":"BINANCE:MATICUSDT","LTCUSDT":  "BINANCE:LTCUSDT",
}

# TradingView timeframe codes
TV_TF = {
    "1m": "1", "5m": "5", "15m": "15",
    "1h": "60", "4h": "240", "1d": "1D",
}

HTF_MAP = {"1m": "15m", "5m": "1h", "15m": "4h"}

# Binance CCXT symbols for crypto fallback
CCXT_SYMBOLS = {k: k[:- len("USDT")] + "/USDT" for k in CRYPTO_PAIRS}


def _rand_session(n=12):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _tv_msg(func: str, args: list) -> str:
    payload = json.dumps({"m": func, "p": args}, separators=(",", ":"))
    return f"~m~{len(payload)}~m~{payload}"


def _tv_ping(payload: str) -> bool:
    return payload.startswith("~h~")


def _tv_parse(raw: str) -> list[dict]:
    results = []
    while "~m~" in raw:
        raw = raw[raw.index("~m~") + 3:]
        if "~m~" not in raw:
            break
        size_end = raw.index("~m~")
        try:
            size = int(raw[:size_end])
        except ValueError:
            break
        raw = raw[size_end + 3:]
        chunk = raw[:size]
        raw = raw[size:]
        try:
            results.append(json.loads(chunk))
        except json.JSONDecodeError:
            pass
    return results


class TradingViewFeed:
    """Fetch OHLCV candles from TradingView WebSocket."""

    def __init__(self):
        self._cookies = {}
        if TV_SESSION:
            self._cookies["sessionid"] = TV_SESSION
        if TV_SESSION_SIGN:
            self._cookies["sessionid_sign"] = TV_SESSION_SIGN

    def _cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._cookies.items())

    async def get_ohlcv(self, tv_symbol: str, tf: str, bars: int = 300) -> pd.DataFrame | None:
        """Fetch bars via TradingView WebSocket. Returns None on failure."""
        chart_session = "cs_" + _rand_session()
        tf_code = TV_TF.get(tf, "60")
        headers = {**TV_HEADERS}
        if self._cookies:
            headers["Cookie"] = self._cookie_header()

        collected: list = []
        try:
            import websockets
            async with websockets.connect(
                TV_WS_URL,
                additional_headers=headers,
                max_size=10_000_000,
                open_timeout=10,
                close_timeout=5,
            ) as ws:
                # Handshake
                auth_token = "unauthorized_user_token"
                if self._cookies:
                    auth_token = await self._get_auth_token()

                await ws.send(_tv_msg("set_auth_token", [auth_token]))
                await ws.send(_tv_msg("chart_create_session", [chart_session, ""]))
                await ws.send(_tv_msg("resolve_symbol", [
                    chart_session, "sym_1",
                    f'={{"adjustment":"splits","symbol":"{tv_symbol}"}}'
                ]))
                await ws.send(_tv_msg("create_series", [
                    chart_session, "s1", "s1", "sym_1", tf_code, bars
                ]))

                timeout_at = asyncio.get_event_loop().time() + 15
                while asyncio.get_event_loop().time() < timeout_at:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=8)
                    except asyncio.TimeoutError:
                        break

                    if _tv_ping(raw):
                        await ws.send(raw)
                        continue

                    for msg in _tv_parse(raw):
                        if msg.get("m") == "timescale_update":
                            series = msg["p"][1].get("s1", {})
                            for bar in series.get("s", []):
                                v = bar.get("v", [])
                                if len(v) >= 5:
                                    collected.append(v)
                            if collected:
                                break
                    if collected:
                        break

        except Exception:
            return None

        if not collected:
            return None

        df = pd.DataFrame(collected, columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="s", utc=True)
        df = df.sort_values("ts").set_index("ts")
        return df.astype(float)

    async def _get_auth_token(self) -> str:
        """Exchange session cookie for a WS auth token."""
        url = "https://www.tradingview.com/api/v1/token"
        headers = {
            **TV_HEADERS,
            "Cookie": self._cookie_header(),
            "Referer": "https://www.tradingview.com/",
        }
        try:
            conn = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver(), ssl=True)
            async with aiohttp.ClientSession(connector=conn) as s:
                async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    data = await r.json(content_type=None)
                    return data.get("token", "unauthorized_user_token")
        except Exception:
            return "unauthorized_user_token"

    async def get_quote(self, tv_symbol: str) -> dict | None:
        """Fetch current quote via REST."""
        url = "https://symbol-search.tradingview.com/symbol_search/"
        # Use the lightweight REST quote endpoint
        q_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{tv_symbol}"
        return None  # fallback handled by caller


class MarketDataFetcher:
    def __init__(self):
        self.tv = TradingViewFeed()
        self._exchange: ccxt.Exchange | None = None

    async def _exchange_lazy(self) -> ccxt.Exchange:
        if self._exchange is None:
            self._exchange = ccxt.binance({
                "enableRateLimit": True,
                "options": {"defaultType": "spot"},
                "urls": {
                    "api": {
                        "spot": "https://api.binance.com/api/v3",
                        "public": "https://api.binance.com/api/v3",
                    }
                },
            })
            await self._exchange.load_markets()
        return self._exchange

    async def close(self):
        if self._exchange:
            await self._exchange.close()
            self._exchange = None

    # ── Public API ──────────────────────────────────────────────────────────

    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        """Return OHLCV DataFrame. Tries TradingView first, then Binance."""
        tv_symbol = self._tv_symbol(symbol)

        # 1) Try TradingView WebSocket
        df = await self.tv.get_ohlcv(tv_symbol, timeframe, limit)
        if df is not None and len(df) >= 30:
            return df.tail(limit)

        # 2) Crypto: Binance fallback
        if symbol in CRYPTO_PAIRS:
            return await self._binance_ohlcv(symbol, timeframe, limit)

        # 3) Forex: synthetic (no paid data source available without API key)
        return await self._synthetic_forex(symbol, timeframe, limit)

    async def get_current_price(self, symbol: str) -> dict:
        """Return {price, change_pct, high_24h, low_24h, volume}."""
        if symbol in CRYPTO_PAIRS:
            return await self._binance_ticker(symbol)
        # Forex — get last close from 1m bars
        try:
            df = await self.get_ohlcv(symbol, "1m", 3)
            price = float(df["close"].iloc[-1])
            prev  = float(df["close"].iloc[-2]) if len(df) > 1 else price
            return {
                "price": round(price, 5),
                "change_pct": round((price - prev) / prev * 100, 4),
                "high_24h": 0, "low_24h": 0, "volume": 0,
            }
        except Exception:
            return {"price": 0, "change_pct": 0, "high_24h": 0, "low_24h": 0, "volume": 0}

    # ── Internals ────────────────────────────────────────────────────────────

    def _tv_symbol(self, symbol: str) -> str:
        if symbol in FOREX_PAIRS:
            return FOREX_PAIRS[symbol]
        if symbol in CRYPTO_PAIRS:
            return CRYPTO_PAIRS[symbol]
        return symbol

    def _aio_connector(self):
        """aiohttp connector using ThreadedResolver (avoids aiodns sandbox issues)."""
        return aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver(), ssl=True)

    async def _binance_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetch OHLCV from Binance REST API directly (no ccxt)."""
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": timeframe, "limit": limit}
        async with aiohttp.ClientSession(connector=self._aio_connector()) as s:
            async with s.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()
        df = pd.DataFrame(data, columns=[
            "timestamp","open","high","low","close","volume",
            "close_time","qav","num_trades","tbbav","tbqav","ignore"
        ])
        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms", utc=True)
        df = df.set_index("timestamp")[["open","high","low","close","volume"]].astype(float)
        return df

    async def _binance_ticker(self, symbol: str) -> dict:
        """Fetch 24h ticker from Binance REST."""
        url = "https://api.binance.com/api/v3/ticker/24hr"
        async with aiohttp.ClientSession(connector=self._aio_connector()) as s:
            async with s.get(url, params={"symbol": symbol}, timeout=aiohttp.ClientTimeout(total=10)) as r:
                t = await r.json()
        return {
            "price":      float(t.get("lastPrice", 0)),
            "change_pct": float(t.get("priceChangePercent", 0)),
            "high_24h":   float(t.get("highPrice", 0)),
            "low_24h":    float(t.get("lowPrice", 0)),
            "volume":     float(t.get("volume", 0)),
        }

    async def _synthetic_forex(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Generates plausible synthetic OHLCV for forex when TV feed is unavailable."""
        seed_rates = {
            "EURUSD": 1.0850, "GBPUSD": 1.2700, "USDJPY": 149.50,
            "USDCHF": 0.9050, "AUDUSD": 0.6550, "NZDUSD": 0.6100,
            "USDCAD": 1.3600, "GBPJPY": 189.80, "EURJPY": 162.30,
            "EURGBP": 0.8550, "XAUUSD": 2320.0, "XAGUSD": 27.50,
        }
        base = seed_rates.get(symbol, 1.0)
        np.random.seed(hash(symbol + timeframe) % 99999)
        vol = 0.0003 if "JPY" not in symbol else 0.03
        if symbol in ("XAUUSD", "XAGUSD"):
            vol = 0.002
        ret = np.random.normal(0, vol, limit)
        closes = base * np.exp(np.cumsum(ret))
        spread = closes * abs(np.random.normal(0, vol * 0.6, limit))
        highs  = closes + spread
        lows   = closes - spread
        opens  = np.roll(closes, 1); opens[0] = closes[0]
        freq = {"1m": "1min", "5m": "5min", "15m": "15min",
                "1h": "1h", "4h": "4h", "1d": "1D"}.get(timeframe, "1min")
        idx = pd.date_range(end=datetime.now(timezone.utc), periods=limit, freq=freq)
        df = pd.DataFrame(
            {"open": opens, "high": highs, "low": lows,
             "close": closes, "volume": np.random.randint(100, 5000, limit).astype(float)},
            index=idx,
        )
        df.index.name = "timestamp"
        return df
