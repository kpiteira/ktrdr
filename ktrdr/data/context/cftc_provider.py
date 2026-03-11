"""CFTC Commitment of Traders (COT) context data provider.

Fetches weekly COT positioning data from CFTC public reports, extracts
net speculative positioning for currency futures, and computes rolling
percentile ranks over 52-week and 156-week windows.

Data source: CFTC Traders in Financial Futures (TFF) reports.
Weekly frequency (Tuesday snapshot, Friday release, ~3-day lag).
"""

import json
import logging
import zipfile
from datetime import datetime
from io import BytesIO, StringIO
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

# CFTC TFF report URLs
# Weekly file (current week only, no headers)
CFTC_TFF_CURRENT_URL = "https://www.cftc.gov/dea/newcot/FinFutWk.txt"
# Annual files (full year history, with headers)
CFTC_TFF_ANNUAL_URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"


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

        # Fetch ALL available COT data (percentile needs 52w+ history before start_date)
        # Use a wider window to allow percentile warm-up
        from datetime import timedelta

        lookback_start = start_date - timedelta(weeks=160)  # 156w + buffer
        raw_data = await self._fetch_cot_data(
            report, contract_name, lookback_start, end_date
        )

        if raw_data.empty:
            raise RuntimeError(
                f"No CFTC COT data found for '{report}' ({contract_name}). "
                f"Check currency code or date range."
            )

        # Compute percentiles on FULL history (needs warm-up period)
        with_pct = self._compute_percentiles(raw_data)

        # Filter to requested date range (raw_data may extend before start_date for warm-up)
        ts_start = pd.Timestamp(start_date)
        ts_end = pd.Timestamp(end_date)

        # Build net_pos result: raw net position as 'close' for indicator compat
        net_pos_df = pd.DataFrame(
            {"close": raw_data["net_position"]},
            index=raw_data.index,
        )
        net_pos_df = net_pos_df[(net_pos_df.index >= ts_start) & (net_pos_df.index <= ts_end)]

        # Build net_pct result: 52w percentile as 'close', keep 156w as extra column
        # Use 52w as primary (more responsive) — 156w available for multi-input strategies
        net_pct_df = pd.DataFrame(
            {
                "close": with_pct["net_pct_52w"],
                "net_pct_156w": with_pct["net_pct_156w"],
            },
            index=with_pct.index,
        )
        # Drop rows where percentile is NaN (warm-up period), then filter to date range
        net_pct_df = net_pct_df.dropna(subset=["close"])
        net_pct_df = net_pct_df[(net_pct_df.index >= ts_start) & (net_pct_df.index <= ts_end)]

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
        if cached is not None and not cached.empty and isinstance(cached.index, pd.DatetimeIndex):
            # Filter to date range
            filtered = cached[
                (cached.index >= pd.Timestamp(start_date))
                & (cached.index <= pd.Timestamp(end_date))
            ]
            if not filtered.empty:
                logger.debug("Cache hit for CFTC COT %s", report)
                return filtered

        # Fetch from CFTC
        raw_text = await self._download_tff_report(start_date, end_date)
        all_data = self._parse_tff_report(raw_text, contract_name)

        if not all_data.empty:
            self._save_to_cache(report, all_data)

        # Filter to date range (guard against empty DataFrame with RangeIndex)
        if all_data.empty:
            return all_data
        return all_data[
            (all_data.index >= pd.Timestamp(start_date))
            & (all_data.index <= pd.Timestamp(end_date))
        ]

    async def _download_tff_report(
        self, start_date: datetime, end_date: datetime
    ) -> str:
        """Download TFF report data covering the requested date range.

        Downloads annual zip files from CFTC for each year in the range,
        plus the current weekly file for the most recent data. Annual files
        have headers; weekly file does not (handled by parser).
        """
        frames: list[pd.DataFrame] = []
        start_year = start_date.year
        # Need 3+ years back for 156-week percentile window
        fetch_from_year = max(start_year - 4, 2017)
        current_year = datetime.now().year

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Fetch annual files for history
            for year in range(fetch_from_year, current_year + 1):
                url = CFTC_TFF_ANNUAL_URL.format(year=year)
                try:
                    response = await client.get(url)
                    if response.status_code == 200:
                        zf = zipfile.ZipFile(BytesIO(response.content))
                        for name in zf.namelist():
                            if name.endswith(".txt"):
                                csv_text = zf.read(name).decode("utf-8", errors="replace")
                                df = pd.read_csv(StringIO(csv_text))
                                frames.append(df)
                                logger.debug(f"Loaded CFTC TFF {year}: {len(df)} rows")
                except Exception as e:
                    logger.warning(f"Failed to fetch CFTC TFF for {year}: {e}")

            # Also fetch current weekly file for most recent data
            try:
                response = await client.get(CFTC_TFF_CURRENT_URL)
                if response.status_code == 200:
                    # Weekly file has no headers — read with header=None
                    df = pd.read_csv(StringIO(response.text), header=None)
                    frames.append(df)
                    logger.debug(f"Loaded CFTC TFF current week: {len(df)} rows")
            except Exception as e:
                logger.warning(f"Failed to fetch current CFTC TFF: {e}")

        if not frames:
            return ""

        # Combine all frames — handle mixed formats (with/without headers)
        # Annual files have named columns; weekly file has integer columns
        # Return the raw text of annual data only (has headers for parser)
        # Weekly data is too different to merge easily
        header_frames = [f for f in frames if isinstance(f.columns[0], str)]
        if header_frames:
            combined = pd.concat(header_frames, ignore_index=True)
            return combined.to_csv(index=False)

        # Fallback: return empty
        return ""

    def _parse_tff_report(self, raw_text: str, contract_name: str) -> pd.DataFrame:
        """Parse TFF report text, extract positioning for target contract.

        The CFTC FinFutWk.txt file has NO header row — all rows are data.
        Columns are positional per the TFF report specification:
          0: Market_and_Exchange_Names
          2: Report_Date (YYYY-MM-DD)
          7: Open_Interest_All
          8-10: Dealer Long, Short, Spreading
          11-13: Asset_Mgr Long, Short, Spreading
          14-16: Leveraged_Funds Long, Short, Spreading
          17-19: Other_Rpt Long, Short, Spreading

        Args:
            raw_text: Raw text from CFTC TFF report download.
            contract_name: Contract market name to filter for.

        Returns:
            DataFrame with 'net_position' column, weekly DatetimeIndex.
        """
        # TFF column positions (0-indexed)
        COL_MARKET = 0
        COL_DATE = 2
        COL_LEV_LONG = 14
        COL_LEV_SHORT = 15

        try:
            # Try with headers first (annual CSV files have them)
            df = pd.read_csv(StringIO(raw_text))
            has_headers = any(
                c in df.columns
                for c in [
                    "Market_and_Exchange_Names",
                    "Market and Exchange Names",
                ]
            )
            if not has_headers:
                # Weekly .txt files have no header — re-read with header=None
                df = pd.read_csv(StringIO(raw_text), header=None)
        except Exception as e:
            logger.error(f"Failed to parse CFTC TFF report: {e}")
            return pd.DataFrame(columns=["net_position"])

        if has_headers:
            # Named-column path (annual CSV files)
            return self._parse_tff_with_headers(df, contract_name)

        # Positional-column path (weekly .txt files, no headers)
        if df.shape[1] < COL_LEV_SHORT + 1:
            logger.error(
                f"TFF report has {df.shape[1]} columns, expected >= {COL_LEV_SHORT + 1}"
            )
            return pd.DataFrame(columns=["net_position"])

        # Filter for target contract
        mask = df[COL_MARKET].astype(str).str.contains(contract_name, case=False, na=False)
        filtered = df[mask].copy()

        if filtered.empty:
            logger.warning(
                f"No data found for contract '{contract_name}' in TFF report"
            )
            return pd.DataFrame(columns=["net_position"])

        # Build result DataFrame using positional columns
        long_vals = pd.to_numeric(filtered[COL_LEV_LONG], errors="coerce")
        short_vals = pd.to_numeric(filtered[COL_LEV_SHORT], errors="coerce")

        result = pd.DataFrame(
            {"net_position": (long_vals - short_vals).values},
            index=pd.DatetimeIndex(pd.to_datetime(filtered[COL_DATE].values)),
        )
        result = result.sort_index()
        result = result.dropna()

        logger.debug(
            f"Parsed CFTC TFF for '{contract_name}': {len(result)} rows, "
            f"date range {result.index[0]} to {result.index[-1]}"
        )
        return result

    def _parse_tff_with_headers(
        self, df: pd.DataFrame, contract_name: str
    ) -> pd.DataFrame:
        """Parse TFF report that has named column headers (annual CSV format)."""
        df.columns = [c.strip() for c in df.columns]

        # Find market name column
        market_col = None
        for candidate in ["Market_and_Exchange_Names", "Market and Exchange Names"]:
            if candidate in df.columns:
                market_col = candidate
                break

        if market_col is None:
            logger.error(
                f"Could not find market name column. Available: {list(df.columns[:5])}"
            )
            return pd.DataFrame(columns=["net_position"])

        mask = df[market_col].str.contains(contract_name, case=False, na=False)
        filtered = df[mask].copy()

        if filtered.empty:
            logger.warning(f"No data for '{contract_name}' in TFF report")
            return pd.DataFrame(columns=["net_position"])

        # Find date column
        date_col = None
        for candidate in ["Report_Date_as_YYYY-MM-DD", "As of Date in Form YYYY-MM-DD"]:
            if candidate in filtered.columns:
                date_col = candidate
                break

        if date_col is None:
            logger.error("Could not find date column in TFF report")
            return pd.DataFrame(columns=["net_position"])

        # Find leveraged fund columns
        long_col = short_col = None
        for prefix in ["Lev_Money_Positions_Long", "Leveraged_Funds_Positions_Long"]:
            if prefix in filtered.columns:
                long_col = prefix
                break
        for prefix in ["Lev_Money_Positions_Short", "Leveraged_Funds_Positions_Short"]:
            if prefix in filtered.columns:
                short_col = prefix
                break

        if long_col is None or short_col is None:
            for col in filtered.columns:
                if "long" in col.lower() and "lev" in col.lower():
                    long_col = col
                elif "short" in col.lower() and "lev" in col.lower():
                    short_col = col

        if long_col is None or short_col is None:
            logger.error(
                f"Could not find leveraged fund columns. "
                f"Available: {[c for c in filtered.columns if 'ong' in c or 'hort' in c]}"
            )
            return pd.DataFrame(columns=["net_position"])

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
