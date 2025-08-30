"""API Client for KTRDR Backend Integration"""

from typing import Any, Optional

import httpx
import structlog

from .config import API_TIMEOUT, KTRDR_API_URL

logger = structlog.get_logger()


class KTRDRAPIError(Exception):
    """Custom exception for KTRDR API errors"""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class KTRDRAPIClient:
    """API client for communicating with KTRDR backend"""

    def __init__(self, base_url: str = KTRDR_API_URL, timeout: float = API_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        logger.info("KTRDR API client initialized", base_url=self.base_url)

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()

    async def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request with error handling"""
        if not self.client:
            raise KTRDRAPIError(
                "API client not initialized. Use async context manager."
            )

        url = f"{endpoint}" if endpoint.startswith("/") else f"/{endpoint}"

        try:
            logger.debug("API request", method=method, url=url)
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()

            data = response.json()
            logger.debug(
                "API response",
                status=response.status_code,
                data_keys=(
                    list(data.keys()) if isinstance(data, dict) else type(data).__name__
                ),
            )
            return data

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error", status=e.response.status_code, url=url)
            try:
                error_data = e.response.json()
            except:
                error_data = {"detail": e.response.text}

            raise KTRDRAPIError(

                f"HTTP {e.response.status_code}: {error_data.get('detail', 'Unknown error')}",
                status_code=e.response.status_code,
                details=error_data,
            )
        except httpx.RequestError as e:
            logger.error("Request error", error=str(e), url=url)
            raise KTRDRAPIError(f"Request failed: {str(e)}") from e

    # Health and System Endpoints
    async def health_check(self) -> dict[str, Any]:
        """Check backend health"""
        return await self._request("GET", "/health")

    # Data Endpoints
    async def get_symbols(self) -> list[dict[str, Any]]:
        """Get available symbols with metadata"""
        response = await self._request("GET", "/symbols")
        return response.get("data", [])

    async def get_cached_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trading_hours_only: bool = False,
        include_extended: bool = False,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get cached OHLCV data for a symbol (fast, local only)"""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if trading_hours_only:
            params["trading_hours_only"] = trading_hours_only
        if include_extended:
            params["include_extended"] = include_extended

        response = await self._request(
            "GET", f"/data/{symbol}/{timeframe}", params=params
        )

        # Apply client-side limiting for Claude's response size constraints
        if limit and "data" in response and "dates" in response["data"]:
            data = response["data"]
            if len(data["dates"]) > limit:
                logger.info(
                    f"Limiting response from {len(data['dates'])} to {limit} data points"
                )
                data["dates"] = data["dates"][-limit:]  # Get most recent data
                data["ohlcv"] = data["ohlcv"][-limit:] if data["ohlcv"] else []
                if data.get("points"):
                    data["points"] = data["points"][-limit:]
                # Update metadata
                if "metadata" in data:
                    data["metadata"]["points"] = len(data["dates"])
                    data["metadata"]["limited_by_client"] = True

        return response

    async def load_data_operation(
        self,
        symbol: str,
        timeframe: str = "1h",
        mode: str = "local",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Perform data loading operation (can fetch from external sources)"""
        payload = {"symbol": symbol, "timeframe": timeframe, "mode": mode}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        return await self._request("POST", "/data/load", json=payload)

    async def get_data_info(self, symbol: str) -> dict[str, Any]:
        """Get data information for a symbol"""
        return await self._request("GET", f"/data/info/{symbol}")

    # Indicator Endpoints
    async def get_indicators(self) -> list[dict[str, Any]]:
        """Get available indicators"""
        response = await self._request("GET", "/indicators")
        return response.get("indicators", [])

    async def compute_indicator(
        self, symbol: str, indicator_type: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute indicator for symbol data"""
        payload = {"symbol": symbol, "indicator_type": indicator_type, "params": params}
        return await self._request("POST", "/indicators/compute", json=payload)

    # Fuzzy Logic Endpoints
    async def get_fuzzy_config(self) -> dict[str, Any]:
        """Get fuzzy logic configuration"""
        return await self._request("GET", "/fuzzy/config")

    async def compute_fuzzy_signals(
        self, symbol: str, config: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Compute fuzzy logic signals"""
        payload = {"symbol": symbol}
        if config:
            payload["config"] = config
        return await self._request("POST", "/fuzzy/compute", json=payload)

    # Strategy Endpoints
    async def get_strategies(self) -> list[dict[str, Any]]:
        """Get available strategies"""
        response = await self._request("GET", "/strategies")
        return response.get("strategies", [])

    async def load_strategy(self, strategy_name: str) -> dict[str, Any]:
        """Load a strategy configuration"""
        return await self._request("GET", f"/strategies/{strategy_name}")

    async def save_strategy(
        self, strategy_name: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Save a strategy configuration"""
        return await self._request("POST", f"/strategies/{strategy_name}", json=config)

    # Backtesting Endpoints (CORRECTED PATHS)
    async def run_backtest(
        self,
        strategy_name: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        commission: float = 0.001,
        slippage: float = 0.0005,
        data_mode: str = "local",
    ) -> dict[str, Any]:
        """Run backtest for a strategy"""
        payload = {
            "strategy_name": strategy_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "commission": commission,
            "slippage": slippage,
            "data_mode": data_mode,
        }
        return await self._request("POST", "/backtests/", json=payload)

    async def get_backtest_status(self, backtest_id: str) -> dict[str, Any]:
        """Get backtest status"""
        return await self._request("GET", f"/backtests/{backtest_id}")

    async def get_backtest_results(self, backtest_id: str) -> dict[str, Any]:
        """Get backtest results"""
        return await self._request("GET", f"/backtests/{backtest_id}/results")

    async def get_backtest_trades(self, backtest_id: str) -> dict[str, Any]:
        """Get backtest trades"""
        return await self._request("GET", f"/backtests/{backtest_id}/trades")

    # Neural Network Training Endpoints (TO BE IMPLEMENTED)
    async def start_neural_training(
        self,
        symbol: str,
        timeframe: str,
        config: dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Start neural network model training"""
        payload = {"symbol": symbol, "timeframe": timeframe, "config": config}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if task_id:
            payload["task_id"] = task_id

        return await self._request("POST", "/trainings/start", json=payload)

    async def get_training_status(self, task_id: str) -> dict[str, Any]:
        """Get neural network training status"""
        return await self._request("GET", f"/trainings/{task_id}")

    async def get_model_performance(self, task_id: str) -> dict[str, Any]:
        """Get trained model performance metrics"""
        return await self._request("GET", f"/trainings/{task_id}/performance")

    async def save_trained_model(
        self, task_id: str, model_name: str, description: str = ""
    ) -> dict[str, Any]:
        """Save a trained neural network model"""
        payload = {
            "task_id": task_id,
            "model_name": model_name,
            "description": description,
        }
        return await self._request("POST", "/models/save", json=payload)

    async def load_trained_model(self, model_name: str) -> dict[str, Any]:
        """Load a trained neural network model"""
        return await self._request("POST", f"/models/{model_name}/load")

    async def test_model_prediction(
        self,
        model_name: str,
        symbol: str,
        timeframe: str = "1h",
        test_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Test model prediction on specific data"""
        payload = {"model_name": model_name, "symbol": symbol, "timeframe": timeframe}
        if test_date:
            payload["test_date"] = test_date

        return await self._request("POST", "/models/predict", json=payload)

    async def list_trained_models(self) -> list[dict[str, Any]]:
        """List all trained neural network models"""
        response = await self._request("GET", "/models")
        return response.get("models", [])


# Singleton instance for easy access
_api_client: Optional[KTRDRAPIClient] = None


def get_api_client() -> KTRDRAPIClient:
    """Get singleton API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = KTRDRAPIClient()
    return _api_client
