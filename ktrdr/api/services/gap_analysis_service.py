"""
Gap Analysis Service

Provides comprehensive gap analysis functionality for the API layer.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, cast

import pandas as pd

from ktrdr.api.models.gap_analysis import (
    BatchGapAnalysisRequest,
    BatchGapAnalysisResponse,
    GapAnalysisMode,
    GapAnalysisRequest,
    GapAnalysisResponse,
    GapAnalysisSummary,
    GapInfoModel,
)
from ktrdr.data.gap_classifier import GapClassification, GapClassifier, GapInfo
from ktrdr.data.local_data_loader import LocalDataLoader
from ktrdr.data.timeframe_constants import TimeframeConstants
from ktrdr.logging import get_logger

logger = get_logger(__name__)


class GapAnalysisService:
    """Service for analyzing data gaps with trading hours awareness."""

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize the gap analysis service.

        Args:
            data_dir: Directory containing data files
        """
        self.data_dir = data_dir or "data"
        self.local_data_loader = LocalDataLoader(data_dir=self.data_dir)
        self.gap_classifier = GapClassifier()

        # Use centralized timeframe constants
        self.timeframe_minutes = TimeframeConstants.TIMEFRAME_MINUTES

        logger.info(f"Initialized GapAnalysisService with data_dir: {self.data_dir}")

    async def analyze_gaps(self, request: GapAnalysisRequest) -> GapAnalysisResponse:
        """
        Perform comprehensive gap analysis for a symbol/timeframe.

        Args:
            request: Gap analysis request

        Returns:
            Gap analysis response
        """
        try:
            # Parse dates
            start_date = self._parse_date(request.start_date)
            end_date = self._parse_date(request.end_date)

            # Validate date range
            if start_date >= end_date:
                raise ValueError("Start date must be before end date")

            # Load existing data
            df = self.local_data_loader.load(request.symbol, request.timeframe)

            if df is None or df.empty:
                return self._create_empty_response(
                    request, start_date, end_date, "No data found"
                )

            # Filter data to analysis period
            df_filtered = self._filter_data_to_period(df, start_date, end_date)

            # Get trading metadata
            trading_metadata = self.gap_classifier.get_symbol_trading_hours(
                request.symbol
            )

            # Detect gaps in the data
            gaps = self._detect_gaps_in_period(
                df_filtered, start_date, end_date, request.symbol, request.timeframe
            )

            # Filter gaps based on mode (default include_expected=True)
            filtered_gaps = self._filter_gaps_by_mode(
                gaps, request.mode, True
            )

            # Calculate summary statistics
            summary = self._calculate_summary_statistics(
                df_filtered,
                gaps,
                start_date,
                end_date,
                request.timeframe,
                trading_metadata,
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(gaps, summary)

            # Create response
            return GapAnalysisResponse(
                symbol=request.symbol,
                timeframe=request.timeframe,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                summary=summary,
                gaps=[self._gap_info_to_model(gap) for gap in filtered_gaps],
                analysis_mode=request.mode,
                generated_at=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(
                f"Gap analysis failed for {request.symbol}_{request.timeframe}: {e}"
            )
            raise

    async def analyze_gaps_batch(
        self, request: BatchGapAnalysisRequest
    ) -> BatchGapAnalysisResponse:
        """
        Perform batch gap analysis for multiple symbols.

        Args:
            request: Batch gap analysis request

        Returns:
            Batch gap analysis response
        """
        results = []
        errors = []

        for symbol in request.symbols:
            try:
                # Create individual request
                individual_request = GapAnalysisRequest(
                    symbol=symbol,
                    timeframe=request.timeframe,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    mode=request.mode,
                )

                # Analyze gaps for this symbol
                result = await self.analyze_gaps(individual_request)
                results.append(result)

            except Exception as e:
                logger.warning(f"Gap analysis failed for symbol {symbol}: {e}")
                errors.append({"symbol": symbol, "error": str(e)})

        # Calculate overall summary
        overall_summary = self._calculate_batch_summary(results)

        # Convert results list to dict keyed by symbol
        results_dict = {result.symbol: result for result in results}
        
        # Add request info to overall summary  
        enhanced_summary = {
            **overall_summary,
            "symbols_requested": len(request.symbols),
            "symbols_successful": len(results),
            "symbols_failed": len(errors),
            "mode": request.mode.value,
            "errors": errors  # Include error info in summary
        }
        
        return BatchGapAnalysisResponse(
            timeframe=request.timeframe,
            start_date=request.start_date or "",
            end_date=request.end_date or "",
            results=results_dict,
            overall_summary=enhanced_summary,
            generated_at=datetime.now().isoformat(),
        )

    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """Parse date string to UTC datetime."""
        if date_str is None:
            raise ValueError("Date string cannot be None")
        try:
            # Handle various ISO formats
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"

            dt = datetime.fromisoformat(date_str)

            # Convert to UTC if timezone-aware, otherwise assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)

            return dt

        except ValueError as e:
            raise ValueError(
                f"Invalid date format: {date_str}. Use ISO format: {e}"
            ) from e

    def _filter_data_to_period(
        self, df: pd.DataFrame, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Filter dataframe to analysis period."""
        if df.empty:
            return df

        # Convert timestamps to UTC for comparison
        df_utc = df.copy()
        if cast(pd.DatetimeIndex, df_utc.index).tz is None:
            df_utc.index = cast(pd.DatetimeIndex, df_utc.index).tz_localize("UTC")
        else:
            df_utc.index = cast(pd.DatetimeIndex, df_utc.index).tz_convert("UTC")

        # Filter to period
        mask = (df_utc.index >= start_date) & (df_utc.index <= end_date)
        return df_utc[mask]

    def _detect_gaps_in_period(
        self,
        df: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
        symbol: str,
        timeframe: str,
    ) -> list[GapInfo]:
        """Detect all gaps in the analysis period."""
        gaps = []

        if df.empty:
            # Entire period is a gap
            gap_info = self.gap_classifier.analyze_gap(
                start_date, end_date, symbol, timeframe
            )
            gaps.append(gap_info)
            return gaps

        # Convert index to ensure proper timezone handling
        if cast(pd.DatetimeIndex, df.index).tz is None:
            df.index = cast(pd.DatetimeIndex, df.index).tz_localize("UTC")
        else:
            df.index = cast(pd.DatetimeIndex, df.index).tz_convert("UTC")

        # Sort by timestamp
        df_sorted = df.sort_index()

        # Check for gap at the beginning
        first_timestamp = df_sorted.index[0]
        if first_timestamp > start_date:
            gap_info = self.gap_classifier.analyze_gap(
                start_date, first_timestamp, symbol, timeframe
            )
            gaps.append(gap_info)

        # Check for gaps between data points
        timeframe_delta = TimeframeConstants.get_timedelta(timeframe)

        for i in range(len(df_sorted) - 1):
            current_time = df_sorted.index[i]
            next_time = df_sorted.index[i + 1]
            expected_next = current_time + timeframe_delta

            # Calculate actual gap duration
            gap_duration = next_time - expected_next

            # Use minimal threshold - let GapClassifier determine significance
            # Only skip very small gaps that are clearly just timing variations
            min_threshold = timeframe_delta * 0.5  # 50% of timeframe

            if gap_duration > min_threshold:
                # Let GapClassifier handle all intelligence about whether this gap is significant
                gap_info = self.gap_classifier.analyze_gap(
                    expected_next, next_time, symbol, timeframe
                )
                gaps.append(gap_info)

        # Check for gap at the end
        last_timestamp = df_sorted.index[-1]
        expected_last = last_timestamp + timeframe_delta

        if expected_last < end_date:
            gap_info = self.gap_classifier.analyze_gap(
                expected_last, end_date, symbol, timeframe
            )
            gaps.append(gap_info)

        return gaps

    def _filter_gaps_by_mode(
        self, gaps: list[GapInfo], mode: GapAnalysisMode, include_expected: bool
    ) -> list[GapInfo]:
        """Filter gaps based on analysis mode and include_expected setting."""
        if mode == GapAnalysisMode.NORMAL:
            return []  # Normal mode shows no individual gaps

        if not include_expected:
            # Only show unexpected gaps
            return [
                gap
                for gap in gaps
                if gap.classification == GapClassification.UNEXPECTED
            ]

        if mode == GapAnalysisMode.EXTENDED:
            # Show unexpected gaps + market closures
            return [
                gap
                for gap in gaps
                if gap.classification
                in [GapClassification.UNEXPECTED, GapClassification.MARKET_CLOSURE]
            ]

        # Verbose mode shows all gaps
        return gaps

    def _calculate_summary_statistics(
        self,
        df: pd.DataFrame,
        gaps: list[GapInfo],
        start_date: datetime,
        end_date: datetime,
        timeframe: str,
        trading_metadata: Optional[dict],
    ) -> GapAnalysisSummary:
        """Calculate summary statistics for gap analysis."""
        # Calculate expected number of bars
        total_duration_minutes = (end_date - start_date).total_seconds() / 60
        timeframe_minutes = self.timeframe_minutes.get(timeframe, 60)
        expected_bars = int(total_duration_minutes / timeframe_minutes)

        # For daily+ timeframes, adjust for trading days only
        if timeframe in ["1d", "1w"] and trading_metadata:
            expected_bars = self._count_trading_days(
                start_date, end_date, trading_metadata
            )

        # Actual bars found
        actual_bars = len(df)

        # Calculate total missing bars
        total_missing = sum(gap.bars_missing for gap in gaps)

        # Calculate data completeness
        data_completeness_pct = (actual_bars / max(expected_bars, 1)) * 100

        # Break down missing bars by classification
        missing_breakdown = {}
        for classification in GapClassification:
            missing_breakdown[classification.value] = sum(
                gap.bars_missing for gap in gaps if gap.classification == classification
            )

        # Convert bars to hours for new model
        timeframe_hours = timeframe_minutes / 60
        total_missing_hours = total_missing * timeframe_hours
        
        # Calculate gap counts by severity
        critical_gaps = sum(1 for gap in gaps if gap.severity == "critical")
        major_gaps = sum(1 for gap in gaps if gap.severity == "major") 
        minor_gaps = sum(1 for gap in gaps if gap.severity == "minor")
        
        # Calculate data quality score (0-100)
        quality_score = max(0.0, min(100.0, data_completeness_pct * 0.8))
        
        return GapAnalysisSummary(
            total_gaps=len(gaps),
            critical_gaps=critical_gaps,
            major_gaps=major_gaps,
            minor_gaps=minor_gaps,
            total_missing_hours=total_missing_hours,
            coverage_percentage=data_completeness_pct,
            data_quality_score=quality_score,
        )

    def _count_trading_days(
        self, start_date: datetime, end_date: datetime, trading_metadata: Optional[dict]
    ) -> int:
        """Count trading days in the period."""
        if not trading_metadata:
            # Default: Monday-Friday
            trading_days = {0, 1, 2, 3, 4}  # Mon-Fri
        else:
            trading_days = set(trading_metadata.get("trading_days", [0, 1, 2, 3, 4]))

        # Count days in the period that are trading days
        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_normalized = end_date.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        trading_day_count = 0

        while current_date <= end_date_normalized:
            if current_date.weekday() in trading_days:
                trading_day_count += 1
            current_date += timedelta(days=1)

        return trading_day_count

    def _generate_recommendations(
        self, gaps: list[GapInfo], summary: GapAnalysisSummary
    ) -> list[str]:
        """Generate actionable recommendations based on gap analysis."""
        recommendations = []

        # Data completeness recommendations
        if summary.data_completeness_pct >= 99:
            recommendations.append("Excellent data completeness - no action needed")
        elif summary.data_completeness_pct >= 95:
            recommendations.append("Good data completeness - monitor for trends")
        elif summary.data_completeness_pct >= 90:
            recommendations.append(
                "Acceptable data completeness - consider improving data collection"
            )
        else:
            recommendations.append(
                "Poor data completeness - immediate attention required"
            )

        # Unexpected gap recommendations
        unexpected_gaps = [
            g for g in gaps if g.classification == GapClassification.UNEXPECTED
        ]
        if unexpected_gaps:
            if len(unexpected_gaps) == 1:
                recommendations.append("1 unexpected gap requires investigation")
            else:
                recommendations.append(
                    f"{len(unexpected_gaps)} unexpected gaps require investigation"
                )

        # Market closure recommendations
        market_closures = [
            g for g in gaps if g.classification == GapClassification.MARKET_CLOSURE
        ]
        if market_closures:
            recommendations.append(
                "Extended market closures detected - verify with broker/exchange"
            )

        # Holiday pattern recommendations
        holiday_gaps = [
            g for g in gaps if g.classification == GapClassification.EXPECTED_HOLIDAY
        ]
        if len(holiday_gaps) > 5:
            recommendations.append(
                "Many holiday gaps detected - verify trading calendar"
            )

        return recommendations

    def _gap_info_to_model(self, gap_info: GapInfo) -> GapInfoModel:
        """Convert GapInfo to API model."""
        # Map classification to gap_type 
        gap_type = gap_info.classification.value if hasattr(gap_info.classification, 'value') else str(gap_info.classification)
        
        # Determine severity based on duration or classification
        if gap_info.duration_hours > 24:
            severity = "critical"
        elif gap_info.duration_hours > 4:
            severity = "major" 
        else:
            severity = "minor"
        
        # Determine if during market hours (simplified logic)
        market_hours = getattr(gap_info, 'market_hours', True)
        
        return GapInfoModel(
            start_time=gap_info.start_time,
            end_time=gap_info.end_time,
            duration_hours=gap_info.duration_hours,
            gap_type=gap_type,
            severity=severity,
            market_hours=market_hours,
            trading_session=getattr(gap_info, 'day_context', None),
            volume_impact=None,
            price_impact=None,
        )

    def _create_empty_response(
        self,
        request: GapAnalysisRequest,
        start_date: datetime,
        end_date: datetime,
        reason: str,
    ) -> GapAnalysisResponse:
        """Create response for cases with no data."""
        # Calculate expected bars for empty dataset
        total_duration_minutes = (end_date - start_date).total_seconds() / 60
        timeframe_minutes = self.timeframe_minutes.get(request.timeframe, 60)
        expected_bars = int(total_duration_minutes / timeframe_minutes)

        # Convert bars to hours for empty dataset
        timeframe_hours = timeframe_minutes / 60
        total_missing_hours = expected_bars * timeframe_hours
        
        summary = GapAnalysisSummary(
            total_gaps=0,  # No data means no specific gaps identified
            critical_gaps=0,
            major_gaps=0, 
            minor_gaps=0,
            total_missing_hours=total_missing_hours,
            coverage_percentage=0.0,
            data_quality_score=0.0,
        )

        return GapAnalysisResponse(
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            summary=summary,
            gaps=[],
            analysis_mode=request.mode,
            generated_at=datetime.now().isoformat(),
        )

    def _calculate_batch_summary(
        self, results: list[GapAnalysisResponse]
    ) -> dict[str, Any]:
        """Calculate aggregated statistics for batch analysis."""
        if not results:
            return {}

        total_expected = sum(r.summary.expected_bars for r in results)
        total_actual = sum(r.summary.actual_bars for r in results)
        total_missing = sum(r.summary.total_missing for r in results)

        # Calculate average completeness
        avg_completeness = sum(r.summary.data_completeness_pct for r in results) / len(
            results
        )

        # Aggregate missing breakdown
        aggregated_breakdown = {}
        for classification in GapClassification:
            aggregated_breakdown[classification.value] = sum(
                r.summary.missing_breakdown.get(classification.value, 0)
                for r in results
            )

        return {
            "total_symbols": len(results),
            "total_expected_bars": total_expected,
            "total_actual_bars": total_actual,
            "total_missing_bars": total_missing,
            "average_completeness_pct": round(avg_completeness, 2),
            "overall_completeness_pct": round(
                (total_actual / max(total_expected, 1)) * 100, 2
            ),
            "aggregated_missing_breakdown": aggregated_breakdown,
        }
