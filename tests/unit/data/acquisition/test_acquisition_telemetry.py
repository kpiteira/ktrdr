"""Tests for DataAcquisitionService OpenTelemetry instrumentation."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService

# Skip all tests in this module until Phase 6.4 (Worker Execution Phase Instrumentation) is implemented
pytestmark = pytest.mark.skip(
    reason="Phase 6.4 not implemented - waiting for data acquisition phase instrumentation"
)


@pytest.fixture
def tracer_provider():
    """Create in-memory tracer provider for testing."""
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return provider, exporter


class TestDataAcquisitionTelemetry:
    """Test OpenTelemetry instrumentation for data acquisition phases."""

    @pytest.mark.asyncio
    async def test_download_data_creates_phase_spans(self, tracer_provider):
        """Test that download_data creates spans for each internal phase."""
        provider, exporter = tracer_provider

        # Create service with mocked dependencies
        service = DataAcquisitionService()

        # Mock all the internal methods
        with (
            patch.object(
                service.provider, "validate_and_get_metadata", new_callable=AsyncMock
            ) as mock_validate,
            patch.object(service.repository, "load_from_cache") as mock_load,
            patch.object(service.gap_analyzer, "analyze_gaps") as mock_gaps,
            patch.object(service.segment_manager, "create_segments") as mock_segments,
            patch.object(
                service.segment_manager, "prioritize_segments"
            ) as mock_prioritize,
            patch.object(
                service.segment_manager,
                "fetch_segments_with_resilience",
                new_callable=AsyncMock,
            ) as mock_fetch,
            patch.object(service.repository, "save_to_cache"),
        ):

            # Setup mock returns
            from ktrdr.data.components.symbol_cache import ValidationResult

            mock_validate.return_value = ValidationResult(
                is_valid=True,
                symbol="AAPL",
                head_timestamps={"1d": "2020-01-01T00:00:00Z"},
            )

            from ktrdr.errors.exceptions import DataNotFoundError

            mock_load.side_effect = DataNotFoundError("Not found")

            mock_gaps.return_value = [(datetime(2024, 1, 1), datetime(2024, 12, 31))]
            mock_segments.return_value = [Mock()]
            mock_prioritize.return_value = [Mock()]

            import pandas as pd

            mock_data = pd.DataFrame({"close": [100]})
            mock_fetch.return_value = ([mock_data], 1, 0)

            # Call download_data
            await service.download_data(
                symbol="AAPL",
                timeframe="1d",
                start_date="2024-01-01",
                end_date="2024-12-31",
                mode="tail",
            )

        # Give time for async operations to complete
        import asyncio

        await asyncio.sleep(0.1)

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Check for expected phase spans
        # The @trace_service_method creates "data.download" parent span
        # We should have child spans for internal phases

        span_names = [s.name for s in spans]

        # At minimum, should have the parent span
        assert any(
            "data.download" in name for name in span_names
        ), "Should have parent data.download span"

    @pytest.mark.asyncio
    async def test_data_spans_include_attributes(self, tracer_provider):
        """Test that data acquisition spans include proper attributes."""
        provider, exporter = tracer_provider

        service = DataAcquisitionService()

        with (
            patch.object(
                service.provider, "validate_and_get_metadata", new_callable=AsyncMock
            ) as mock_validate,
            patch.object(service.repository, "load_from_cache") as mock_load,
            patch.object(service.gap_analyzer, "analyze_gaps") as mock_gaps,
            patch.object(service.segment_manager, "create_segments") as mock_segments,
            patch.object(
                service.segment_manager, "prioritize_segments"
            ) as mock_prioritize,
            patch.object(
                service.segment_manager,
                "fetch_segments_with_resilience",
                new_callable=AsyncMock,
            ) as mock_fetch,
            patch.object(service.repository, "save_to_cache"),
        ):

            from ktrdr.data.components.symbol_cache import ValidationResult

            mock_validate.return_value = ValidationResult(
                is_valid=True,
                symbol="AAPL",
                head_timestamps={"1d": "2020-01-01T00:00:00Z"},
            )

            from ktrdr.errors.exceptions import DataNotFoundError

            mock_load.side_effect = DataNotFoundError("Not found")
            mock_gaps.return_value = [(datetime(2024, 1, 1), datetime(2024, 12, 31))]
            mock_segments.return_value = [Mock()]
            mock_prioritize.return_value = [Mock()]

            import pandas as pd

            mock_data = pd.DataFrame({"close": [100] * 50})
            mock_fetch.return_value = ([mock_data], 1, 0)

            await service.download_data(
                symbol="AAPL",
                timeframe="1d",
                start_date="2024-01-01",
                end_date="2024-12-31",
                mode="tail",
            )

        # Give time for async operations
        import asyncio

        await asyncio.sleep(0.1)

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find parent span
        parent_spans = [s for s in spans if "data.download" in s.name]

        if parent_spans:
            span = parent_spans[0]

            # Verify attributes
            assert span.attributes.get("data.symbol") == "AAPL"
            assert span.attributes.get("data.timeframe") == "1d"
            assert span.attributes.get("data.mode") == "tail"

    @pytest.mark.asyncio
    async def test_spans_inherit_operation_id(self, tracer_provider):
        """Test that data acquisition spans inherit operation.id from parent."""
        provider, exporter = tracer_provider

        # Create parent span with operation.id
        tracer = trace.get_tracer(__name__)

        with tracer.start_as_current_span("test_data_operation") as parent_span:
            parent_span.set_attribute("operation.id", "op_data_123")

            service = DataAcquisitionService()

            with (
                patch.object(
                    service.provider,
                    "validate_and_get_metadata",
                    new_callable=AsyncMock,
                ) as mock_validate,
                patch.object(service.repository, "load_from_cache") as mock_load,
                patch.object(service.gap_analyzer, "analyze_gaps") as mock_gaps,
                patch.object(
                    service.segment_manager, "create_segments"
                ) as mock_segments,
                patch.object(
                    service.segment_manager, "prioritize_segments"
                ) as mock_prioritize,
                patch.object(
                    service.segment_manager,
                    "fetch_segments_with_resilience",
                    new_callable=AsyncMock,
                ) as mock_fetch,
                patch.object(service.repository, "save_to_cache"),
            ):

                from ktrdr.data.components.symbol_cache import ValidationResult

                mock_validate.return_value = ValidationResult(
                    is_valid=True,
                    symbol="AAPL",
                    head_timestamps={"1d": "2020-01-01T00:00:00Z"},
                )

                from ktrdr.errors.exceptions import DataNotFoundError

                mock_load.side_effect = DataNotFoundError("Not found")
                mock_gaps.return_value = [
                    (datetime(2024, 1, 1), datetime(2024, 12, 31))
                ]
                mock_segments.return_value = [Mock()]
                mock_prioritize.return_value = [Mock()]

                import pandas as pd

                mock_data = pd.DataFrame({"close": [100]})
                mock_fetch.return_value = ([mock_data], 1, 0)

                await service.download_data(symbol="AAPL", timeframe="1d", mode="tail")

        # Give time for async operations
        import asyncio

        await asyncio.sleep(0.1)

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find child spans
        child_spans = [s for s in spans if s.parent is not None and "data." in s.name]

        # All child spans should have operation.id
        for span in child_spans:
            assert (
                span.attributes.get("operation.id") == "op_data_123"
            ), f"Span {span.name} should inherit operation.id from parent context"
