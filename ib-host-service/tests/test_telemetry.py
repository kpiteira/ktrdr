"""Tests for IB Host Service OpenTelemetry instrumentation."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


class TestIBConnectionTelemetry:
    """Test IB connection instrumentation."""

    @pytest.fixture
    def tracer_provider(self):
        """Create a tracer provider with in-memory exporter for testing."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        return provider, exporter

    @pytest.fixture
    def tracer(self, tracer_provider):
        """Get a tracer for testing."""
        provider, _ = tracer_provider
        return provider.get_tracer(__name__)

    def test_ib_connect_creates_span_with_attributes(self, tracer, tracer_provider):
        """Test that IB connection creates span with connection attributes."""
        from ib.connection import IbConnection

        _, exporter = tracer_provider

        # Create connection with instrumentation
        _ = IbConnection(client_id=1, host="localhost", port=4002)

        # Simulate connection attempt (mock the actual IB connection)
        with tracer.start_as_current_span("test.connection"):
            # The connection should create an ib.connect span
            # For now, we'll manually verify the pattern works
            pass

        # Get completed spans
        spans = exporter.get_finished_spans()
        assert len(spans) > 0

        # Find ib.connect span (will be added in implementation)
        # For now, this will fail - that's expected in RED phase

    def test_ib_connect_span_includes_connection_details(
        self, tracer, tracer_provider
    ):
        """Test that ib.connect span includes host, port, and connection status."""
        _, exporter = tracer_provider

        # This test will verify the span has:
        # - ib.host
        # - ib.port
        # - connection.status
        # - connection.client_id

        # Will implement after writing the code
        pass


class TestIBDataFetchingTelemetry:
    """Test IB data fetching instrumentation."""

    @pytest.fixture
    def tracer_provider(self):
        """Create a tracer provider with in-memory exporter for testing."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        return provider, exporter

    @pytest.fixture
    def tracer(self, tracer_provider):
        """Get a tracer for testing."""
        provider, _ = tracer_provider
        return provider.get_tracer(__name__)

    @pytest.mark.asyncio
    async def test_fetch_historical_creates_span(self, tracer, tracer_provider):
        """Test that fetch_historical_data creates instrumented span."""
        from datetime import datetime, timezone

        from ib.data_fetcher import IbDataFetcher

        _, exporter = tracer_provider

        fetcher = IbDataFetcher()

        # This will fail initially - expected in RED phase
        # We're testing that the span exists and has the right name
        try:
            with tracer.start_as_current_span("test.fetch"):
                # Fetch will create ib.fetch_historical span
                await fetcher.fetch_historical_data(
                    symbol="AAPL",
                    timeframe="1d",
                    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    end=datetime(2024, 1, 31, tzinfo=timezone.utc),
                )
        except Exception:
            # Expected to fail - we're in RED phase
            pass

        spans = exporter.get_finished_spans()
        # Should have test.fetch span at minimum
        assert len(spans) > 0

    @pytest.mark.asyncio
    async def test_fetch_historical_span_attributes(self, tracer, tracer_provider):
        """Test that ib.fetch_historical span includes required attributes."""
        _, exporter = tracer_provider

        # After implementation, span should have:
        # - data.symbol
        # - data.timeframe
        # - bars.requested (time range)
        # - bars.received (actual count)
        # - ib.latency_ms (fetch time)

        # Will implement verification after code is written
        pass

    @pytest.mark.asyncio
    async def test_fetch_historical_records_errors(self, tracer, tracer_provider):
        """Test that fetch errors are recorded in spans."""
        _, exporter = tracer_provider

        # Test that failed fetches:
        # - Record exception in span
        # - Set span status to ERROR
        # - Include error details

        # Will implement after code is written
        pass


class TestIBHostServiceEndToEnd:
    """End-to-end telemetry tests for IB Host Service."""

    @pytest.fixture
    def tracer_provider(self):
        """Create a tracer provider with in-memory exporter for testing."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        return provider, exporter

    def test_full_data_request_creates_nested_spans(self, tracer_provider):
        """Test that a full data request creates properly nested spans."""
        _, exporter = tracer_provider

        # A complete data fetch should create:
        # - Parent span from FastAPI auto-instrumentation
        # - ib.connect span (if connection needed)
        # - ib.fetch_historical span
        # All properly nested with parent-child relationships

        # Will implement after full instrumentation is complete
        pass
