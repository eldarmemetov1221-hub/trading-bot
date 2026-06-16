import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio
from dotenv import load_dotenv

load_dotenv()

from analysis import SignalGenerator, FOREX_PAIRS, CRYPTO_PAIRS
from analysis.risk_management import RiskManager

generator: SignalGenerator = None
risk_mgr = RiskManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global generator
    generator = SignalGenerator()
    yield
    await generator.close()


app = FastAPI(title="SMC Trading Bot API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

webapp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp")


@app.get("/")
async def root():
    return FileResponse(os.path.join(webapp_dir, "index.html"))

@app.get("/style.css")
async def css():
    return FileResponse(os.path.join(webapp_dir, "style.css"), media_type="text/css")

@app.get("/app.js")
async def js():
    return FileResponse(os.path.join(webapp_dir, "app.js"), media_type="application/javascript")


@app.get("/api/pairs")
async def get_pairs():
    return {
        "forex": [
            {"symbol": k, "name": v, "type": "forex"}
            for k, v in FOREX_PAIRS.items()
        ],
        "crypto": [
            {"symbol": k, "name": v, "type": "crypto"}
            for k, v in CRYPTO_PAIRS.items()
        ],
    }


@app.get("/api/price/{symbol}")
async def get_price(symbol: str):
    if not generator:
        raise HTTPException(503, "Service initializing")
    try:
        price_data = await generator.fetcher.get_current_price(symbol)
        return {"symbol": symbol, **price_data}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/signal/{symbol}/{timeframe}")
async def get_signal(symbol: str, timeframe: str):
    if timeframe not in ("1m", "5m", "15m"):
        raise HTTPException(400, "Timeframe must be 1m, 5m, or 15m")
    if not generator:
        raise HTTPException(503, "Service initializing")
    try:
        signal = await generator.generate_signal(symbol, timeframe)
        if not signal:
            raise HTTPException(404, "Could not generate signal — no clear setup")
        risk_info = risk_mgr.calc_position_size(
            account_balance=1000,
            entry=signal.entry,
            sl=signal.sl,
        )
        quality = risk_mgr.get_risk_label(signal.confidence)
        return {
            "symbol": signal.symbol,
            "type": signal.signal_type.value,
            "entry": signal.entry,
            "sl": signal.sl,
            "tp1": signal.tp1,
            "tp2": signal.tp2,
            "tp3": signal.tp3,
            "rr_ratio": signal.rr_ratio,
            "confidence": signal.confidence,
            "timeframe": signal.timeframe,
            "htf_bias": signal.htf_bias,
            "setup_type": signal.setup_type,
            "description": signal.description,
            "confluences": signal.confluences,
            "market_phase": signal.market_phase,
            "session": signal.session,
            "timestamp": signal.timestamp,
            "quality": quality,
            "risk_info": risk_info,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
