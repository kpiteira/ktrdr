"""
Simple mock API server for testing the frontend API integration
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Dict, List, Optional
import json
from datetime import datetime, timedelta
import numpy as np

app = FastAPI(title="KTRDR Mock API")

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock data
SYMBOLS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ", "type": "stock", "currency": "USD"},
    {"symbol": "EURUSD", "name": "Euro/US Dollar", "exchange": "FOREX", "type": "forex", "currency": "USD"},
    {"symbol": "BTC-USD", "name": "Bitcoin/US Dollar", "exchange": "CRYPTO", "type": "crypto", "currency": "USD"}
]

TIMEFRAMES = [
    {"id": "1m", "name": "1 Minute", "seconds": 60, "description": "One minute bars"},
    {"id": "5m", "name": "5 Minutes", "seconds": 300, "description": "Five minute bars"},
    {"id": "15m", "name": "15 Minutes", "seconds": 900, "description": "Fifteen minute bars"},
    {"id": "1h", "name": "1 Hour", "seconds": 3600, "description": "One hour bars"},
    {"id": "1d", "name": "Daily", "seconds": 86400, "description": "Daily bars"}
]

# Generate some mock OHLCV data
def generate_ohlcv_data(symbol: str, timeframe: str, start_date: str, end_date: str, page: int = 1, page_size: int = 100):
    # Parse dates
    start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else datetime.now() - timedelta(days=30)
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else datetime.now()
    
    # Generate dates
    if timeframe == "1d":
        delta = timedelta(days=1)
    elif timeframe == "1h":
        delta = timedelta(hours=1)
    elif timeframe == "15m":
        delta = timedelta(minutes=15)
    elif timeframe == "5m":
        delta = timedelta(minutes=5)
    else:  # 1m
        delta = timedelta(minutes=1)
    
    # Generate timestamps
    current = start
    dates = []
    while current <= end:
        # Skip weekends for stock data
        if symbol not in ["EURUSD", "BTC-USD"] and current.weekday() >= 5:
            current += delta
            continue
        dates.append(current.isoformat())
        current += delta
    
    # Apply pagination
    total_points = len(dates)
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_points)
    
    dates = dates[start_idx:end_idx]
    
    # Generate OHLCV data with some randomness but realistic patterns
    points = len(dates)
    if points == 0:
        return {
            "success": True,
            "data": {
                "dates": [],
                "ohlcv": [],
                "metadata": {
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "start_date": start_date,
                    "end_date": end_date,
                    "point_count": 0
                }
            }
        }
    
    # Start with a base price depending on the symbol
    if symbol == "AAPL":
        base_price = 180.0
    elif symbol == "MSFT":
        base_price = 350.0
    elif symbol == "EURUSD":
        base_price = 1.10
    elif symbol == "BTC-USD":
        base_price = 50000.0
    else:
        base_price = 100.0
        
    # Generate price movement with trend and volatility
    np.random.seed(hash(symbol + timeframe) % 10000)  # Consistent randomness per symbol/timeframe
    
    changes = np.random.normal(0, 0.01, points).cumsum()  # Random walk
    trend = np.linspace(0, 0.05, points)  # Slight upward trend
    
    # Create prices with the trend and changes
    closes = base_price * (1 + changes + trend)
    
    # Generate realistic OHLCV data
    ohlcv = []
    for i in range(points):
        close = closes[i]
        # More volatility for higher timeframes
        volatility = 0.005 if timeframe in ["1d", "1h"] else 0.002
        
        # Generate open, high, low based on close
        open_price = closes[i-1] if i > 0 else close * (1 + np.random.normal(0, volatility))
        high = max(open_price, close) * (1 + abs(np.random.normal(0, volatility)))
        low = min(open_price, close) * (1 - abs(np.random.normal(0, volatility)))
        
        # Volume is higher for more volatile bars
        volume = np.random.normal(1000000, 200000) * (1 + 5 * abs(high/low - 1))
        
        ohlcv.append([float(open_price), float(high), float(low), float(close), float(volume)])
    
    return {
        "success": True,
        "data": {
            "dates": dates,
            "ohlcv": ohlcv,
            "metadata": {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_date": dates[0],
                "end_date": dates[-1],
                "point_count": points
            }
        }
    }

# API endpoints
@app.get("/api/v1/symbols")
async def get_symbols():
    """Get available symbols"""
    return {"success": True, "data": SYMBOLS}

@app.get("/api/v1/timeframes")
async def get_timeframes():
    """Get available timeframes"""
    return {"success": True, "data": TIMEFRAMES}

@app.post("/api/v1/data/load")
async def load_data(request: Dict):
    """Load OHLCV data"""
    symbol = request.get("symbol")
    timeframe = request.get("timeframe")
    start_date = request.get("start_date")
    end_date = request.get("end_date")
    page = request.get("page", 1)
    page_size = request.get("page_size", 100)
    
    if not symbol or not timeframe:
        raise HTTPException(status_code=400, detail="Symbol and timeframe are required")
        
    # Check if symbol exists
    if not any(s["symbol"] == symbol for s in SYMBOLS):
        return {
            "success": False,
            "error": {
                "code": "SYMBOL_NOT_FOUND",
                "message": f"Symbol {symbol} not found",
                "details": {"symbol": symbol}
            }
        }
    
    # Check if timeframe exists
    if not any(t["id"] == timeframe for t in TIMEFRAMES):
        return {
            "success": False,
            "error": {
                "code": "TIMEFRAME_NOT_FOUND",
                "message": f"Timeframe {timeframe} not found",
                "details": {"timeframe": timeframe}
            }
        }
    
    # Generate mock data
    return generate_ohlcv_data(symbol, timeframe, start_date, end_date, page, page_size)

@app.post("/api/v1/data/range")
async def get_data_range(request: Dict):
    """Get data range for a symbol and timeframe"""
    symbol = request.get("symbol")
    timeframe = request.get("timeframe")
    
    if not symbol or not timeframe:
        raise HTTPException(status_code=400, detail="Symbol and timeframe are required")
    
    # Return mock data range
    if symbol == "AAPL":
        start = "2015-01-01T00:00:00"
        end = datetime.now().isoformat()
    elif symbol == "MSFT":
        start = "2010-01-01T00:00:00"
        end = datetime.now().isoformat()
    elif symbol == "EURUSD":
        start = "2005-01-01T00:00:00"
        end = datetime.now().isoformat()
    else:
        start = "2017-01-01T00:00:00"
        end = datetime.now().isoformat()
    
    return {
        "success": True,
        "data": {
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start,
            "end_date": end,
            "point_count": 1000
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)