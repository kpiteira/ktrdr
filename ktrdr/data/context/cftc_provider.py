"""CFTC Commitment of Traders (COT) context data provider.

Fetches weekly COT positioning data from CFTC public reports, extracts
net speculative positioning for currency futures, and computes rolling
percentile ranks over 52-week and 156-week windows.

Data source: CFTC Traders in Financial Futures (TFF) reports.
Weekly frequency (Tuesday snapshot, Friday release, ~3-day lag).
"""

import json
import logging
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from .base import ContextDataProvider, ContextDataResult

logger = logging.getLogger(__name__)

# CFTC currency futures contract mapping
# Maps currency codes to CFTC contract market names (as they appear in TFF reports)
CURRENCY_CONTRACT_MAP: dict[str, str] = {
    "EUR": "EURO FX",
    "GBP": "BRITISH POUND",
    "JPY": "JAPANESE YEN",
    "CHF": "SWISS FRANC",
    "AUD": "AUSTRALIAN DOLLAR",
    "NZD": "NEW ZEALAND DOLLAR",
    "CAD": "CANADIAN DOLLAR",
    "MXN": "MEXICAN PESO",
}

VALID_CURRENCY_CODES = set(CURRENCY_CONTRACT_MAP.keys())

# CFTC TFF report URL (annual zip files with CSV data)
CFTC_TFF_CURRENT_URL = (
    "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
)


class CftcCotProvider(ContextDataProvider):
    """Fetches CFTC Commitment of Traders positioning data.

    Extracts net speculative positioning for currency futures and computes
    rolling percentile ranks. Extreme percentiles (>90 or <10) indicate
    crowded positioning — potential contrarian signals.

    Produces two source_ids per currency:
    - cot_{report}_net_pos: Raw net position (close column)
    - cot_{report}_net_pct: 52-week percentile (close column, with net_pct_156w extra)
    """

    def get_source_ids(self, config: Any) -> list[str]:
        """Return source IDs for this config.

        Args:
            config: ContextDataEntry with report field (currency code).

        Returns:
            ["cot_{report}_net_pos", "cot_{report}_net_pct"]
        """
        report = config.report
        return [f"cot_{report}_net_pos", f"cot_{report}_net_pct"]

    async def validate(self, config: Any, **kwargs: Any) -> list[str]:
        """Validate CFTC COT config entry.

        Checks that report field is a valid currency code.
        """
        errors: list[str] = []

        report = getattr(config, "report", None)
        if not report:
            errors.append("CFTC COT provider requires 'report' field (currency code)")
            return errors

        if report not in VALID_CURRENCY_CODES:
            errors.append(
                f"Unknown currency code '{report}'. "
                f"Valid codes: {sorted(VALID_CURRENCY_CODES)}"
            )

        return errors

    async def fetch(
        self,
        config: Any,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ContextDataResult]:
        """Fetch COT data, compute percentiles, return results.

        Args:
            config: ContextDataEntry with report (currency code).
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            Two ContextDataResults: net_pos and net_pct.

        Raises:
            RuntimeError: If data cannot be fetched or parsed.
        """
        report = config.report
        contract_name = CURRENCY_CONTRACT_MAP.get(report, report)

        # Fetch raw COT data (from cache or CFTC)
        raw_data = await self._fetch_cot_data(report, contract_name, start_date, end_date)

        if raw_data.empty:
            raise RuntimeError(
                f"No CFTC COT data found for '{report}' ({contract_name}). "
                f"Check currency code or date range."
            )

        # Compute percentiles
        with_pct = self._compute_percentiles(raw_data)

        # Build net_pos result: raw net position as 'close' for indicator compat
        net_pos_df = pd.DataFrame(
            {"close": raw_data["net_position"]},
            index=raw_data.index,
        )

        # Build net_pct result: 52w percentile as 'close', keep 156w as extra column
        # Use 52w as primary (more responsive) — 156w available for multi-input strategies
        net_pct_df = pd.DataFrame(
            {
                "close": with_pct["net_pct_52w"],
                "net_pct_156w": with_pct["net_pct_156w"],
            },
            index=with_pct.index,
        )
        # Drop rows where percentile is NaN (warm-up period)
        net_pct_df = net_pct_df.dropna(subset=["close"])

        results = [
            ContextDataResult(
                source_id=f"cot_{report}_net_pos",
                data=net_pos_df,
                frequency="weekly",
                provider="cftc_cot",
                metadata={"report": report, "contract": contract_name},
            ),
            ContextDataResult(
                source_id=f"cot_{report}_net_pct",
                data=net_pct_df,
                frequency="weekly",
                provider="cftc_cot",
                metadata={
                    "report": report,
                    "contract": contract_name,
                    "windows": [52, 156],
                },
            ),
        ]

        logger.info(
            f"CFTC COT '{report}': {len(raw_data)} weeks raw, "
            f"{len(net_pct_df)} weeks with percentile"
        )

        return results

    def _compute_percentiles(self, data: pd.DataFrame) -> pd.DataFrame:
        """Compute rolling percentile rank of net position.

        Args:
            data: DataFrame with 'net_position' column, weekly frequency.

        Returns:
            DataFrame with net_pct_52w and net_pct_156w columns (0-100 scale).
        """
        result = data.copy()
        net_pos = data["net_position"]

        for window, col_name in [(52, "net_pct_52w"), (156, "net_pct_156w")]:
            # Rolling rank: what percentile is the current value within the window?
            rolling = net_pos.rolling(window=window, min_periods=window)
            result[col_name] = rolling.apply(
                lambda x: (x.values < x.values[-1]).sum() / (len(x) - 1) * 100,
                raw=False,
            )

        return result

    async def _fetch_cot_data(
        self,
        report: str,
        contract_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pd.DataFrame:
        """Fetch COT data from cache or CFTC.

        Args:
            report: Currency code (e.g., "EUR").
            contract_name: CFTC contract name (e.g., "EURO FX").
            start_date: Start of date range.
            end_date: End of date range.

        Returns:
            DataFrame with 'net_position' column, weekly DatetimeIndex.
        """
        # Try cache first
        cached = self._load_from_cache(report)
        if cached is not None and not cached.empty:
            # Filter to date range
            filtered = cached[
                (cached.index >= pd.Timestamp(start_date))
                & (cached.index <= pd.Timestamp(end_date))
            ]
            if not filtered.empty:
                logger.debug("Cache hit for CFTC COT %s", report)
                return filtered

        # Fetch from CFTC
        raw_text = await self._download_tff_report()
        all_data = self._parse_tff_report(raw_text, contract_name)

        if not all_data.empty:
            self._save_to_cache(report, all_data)

        # Filter to date range
        return all_data[
            (all_data.index >= pd.Timestamp(start_date))
            & (all_data.index <= pd.Timestamp(end_date))
        ]

    async def _download_tff_report(self) -> str:
        """Download current TFF report from CFTC."""
        async with httpx.AsyncClient() as client:
            response = await client.get(CFTC_TFF_CURRENT_URL, timeout=60.0)
            response.raise_for_status()
            return response.text

    def _parse_tff_report(
        self, raw_text: str, contract_name: str
    ) -> pd.DataFrame:
        """Parse TFF report text, extract positioning for target contract.

        The TFF report is a fixed-width or comma-delimited text file with
        columns including market name, date, and various position categories.

        Args:
            raw_text: Raw text from CFTC TFF report download.
            contract_name: Contract market name to filter for.

        Returns:
            DataFrame with 'net_position' column, weekly DatetimeIndex.
        """
        try:
            df = pd.read_csv(StringIO(raw_text))
        except Exception as e:
            logger.error(f"Failed to parse CFTC TFF report: {e}")
            return pd.DataFrame(columns=["net_position"])

        # Column names vary by report format — normalize
        df.columns = [c.strip() for c in df.columns]

        # Find the market name column
        market_col = None
        for candidate in ["Market_and_Exchange_Names", "Market and Exchange Names"]:
            if candidate in df.columns:
                market_col = candidate
                break

        if market_col is None:
            logger.error(
                f"Could not find market name column in TFF report. "
                f"Available: {list(df.columns[:5])}"
            )
            return pd.DataFrame(columns=["net_position"])

        # Filter for target contract
        mask = df[market_col].str.contains(contract_name, case=False, na=False)
        filtered = df[mask].copy()

        if filtered.empty:
            logger.warning(f"No data found for contract '{contract_name}' in TFF report")
            return pd.DataFrame(columns=["net_position"])

        # Extract date column
        date_col = None
        for candidate in ["Report_Date_as_YYYY-MM-DD", "As of Date in Form YYYY-MM-DD"]:
            if candidate in filtered.columns:
                date_col = candidate
                break

        if date_col is None:
            logger.error("Could not find date column in TFF report")
            return pd.DataFrame(columns=["net_position"])

        # Extract dealer/asset manager long and short positions
        # TFF reports have: Dealer_Positions_Long, Dealer_Positions_Short,
        # Asset_Mgr_Positions_Long, Asset_Mgr_Positions_Short, etc.
        # "Leveraged Funds" = speculative positioning
        long_col = None
        short_col = None
        for prefix in ["Lev_Money_Positions_Long", "Leveraged_Funds_Positions_Long"]:
            if prefix in filtered.columns:
                long_col = prefix
                break
        for prefix in ["Lev_Money_Positions_Short", "Leveraged_Funds_Positions_Short"]:
            if prefix in filtered.columns:
                short_col = prefix
                break

        if long_col is None or short_col is None:
            # Fallback: try non-commercial positions
            for col in filtered.columns:
                if "long" in col.lower() and "lev" in col.lower():
                    long_col = col
                elif "short" in col.lower() and "lev" in col.lower():
                    short_col = col

        if long_col is None or short_col is None:
            logger.error(
                f"Could not find leveraged fund position columns. "
                f"Available: {[c for c in filtered.columns if 'ong' in c or 'hort' in c]}"
            )
            return pd.DataFrame(columns=["net_position"])

        # Build result DataFrame
        result = pd.DataFrame(
            {
                "net_position": (
                    pd.to_numeric(filtered[long_col], errors="coerce")
                    - pd.to_numeric(filtered[short_col], errors="coerce")
                ).values,
            },
            index=pd.DatetimeIndex(pd.to_datetime(filtered[date_col].values)),
        )
        result = result.sort_index()
        result = result.dropna()

        return result

    # -- Caching --

    def _cache_dir(self) -> Path:
        """Get or create CFTC cache directory."""
        cache_path = Path("data/context/cftc")
        cache_path.mkdir(parents=True, exist_ok=True)
        return cache_path

    def _load_from_cache(self, report: str) -> pd.DataFrame | None:
        """Load cached COT data for a currency."""
        cache_file = self._cache_dir() / f"{report}.csv"
        if not cache_file.exists():
            return None

        try:
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return df
        except Exception as e:
            logger.warning(f"Failed to load CFTC cache for {report}: {e}")
            return None

    def _save_to_cache(self, report: str, data: pd.DataFrame) -> None:
        """Save COT data to local cache."""
        cache_file = self._cache_dir() / f"{report}.csv"
        data.to_csv(cache_file)

        # Update metadata
        meta_path = self._cache_dir() / "metadata.json"
        metadata: dict[str, Any] = {}
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text())

        metadata[report] = {
            "rows": len(data),
            "start_date": str(data.index[0]),
            "end_date": str(data.index[-1]),
            "last_fetched": datetime.now().isoformat(),
        }
        meta_path.write_text(json.dumps(metadata, indent=2))
        logger.debug(f"Cached CFTC COT {report} ({len(data)} rows)")
