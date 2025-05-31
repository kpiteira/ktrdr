"""
Chart visualization models for the KTRDR API.

This module defines models related to chart visualization, including
request and response models for generating and configuring charts.
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

from ktrdr.api.models.base import ApiResponse
from ktrdr.api.models.indicators import IndicatorConfig


class ChartTheme(str, Enum):
    """Chart color themes."""

    LIGHT = "light"
    DARK = "dark"
    CUSTOM = "custom"


class ChartGridOptions(BaseModel):
    """
    Chart grid display options.

    Attributes:
        show_vertical (bool): Whether to show vertical grid lines
        show_horizontal (bool): Whether to show horizontal grid lines
        color (Optional[str]): Grid line color (hex code)
        opacity (float): Grid line opacity (0.0 to 1.0)
    """

    show_vertical: bool = Field(True, description="Whether to show vertical grid lines")
    show_horizontal: bool = Field(
        True, description="Whether to show horizontal grid lines"
    )
    color: Optional[str] = Field(None, description="Grid line color (hex code)")
    opacity: float = Field(0.2, description="Grid line opacity (0.0 to 1.0)")

    @field_validator("opacity")
    @classmethod
    def validate_opacity(cls, v: float) -> float:
        """Validate that opacity is between 0 and 1."""
        if v < 0.0 or v > 1.0:
            raise ValueError("Opacity must be between 0.0 and 1.0")
        return v

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        """Validate color hex code if provided."""
        if v is not None and not v.startswith("#"):
            raise ValueError("Color must be a hex code starting with #")
        return v


class ChartAxisOptions(BaseModel):
    """
    Chart axis display options.

    Attributes:
        show_labels (bool): Whether to show axis labels
        format (Optional[str]): Format string for axis values
        color (Optional[str]): Axis color (hex code)
        position (str): Axis position (left, right, top, bottom)
    """

    show_labels: bool = Field(True, description="Whether to show axis labels")
    format: Optional[str] = Field(None, description="Format string for axis values")
    color: Optional[str] = Field(None, description="Axis color (hex code)")
    position: str = Field(
        "right", description="Axis position (left, right, top, bottom)"
    )

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: str) -> str:
        """Validate axis position."""
        valid_positions = ["left", "right", "top", "bottom"]
        if v not in valid_positions:
            raise ValueError(f"Position must be one of {valid_positions}")
        return v


class ChartSeriesType(str, Enum):
    """Types of chart series."""

    CANDLESTICK = "candlestick"
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    HISTOGRAM = "histogram"
    SCATTER = "scatter"
    HEATMAP = "heatmap"


class ChartSeriesStyle(BaseModel):
    """
    Style options for a chart series.

    Attributes:
        color (Optional[str]): Series color (hex code)
        line_width (Optional[float]): Line width for line series
        opacity (Optional[float]): Fill opacity for area series
        up_color (Optional[str]): Up color for candlestick series
        down_color (Optional[str]): Down color for candlestick series
        point_size (Optional[float]): Point size for scatter series
    """

    color: Optional[str] = Field(None, description="Series color (hex code)")
    line_width: Optional[float] = Field(None, description="Line width for line series")
    opacity: Optional[float] = Field(None, description="Fill opacity for area series")
    up_color: Optional[str] = Field(None, description="Up color for candlestick series")
    down_color: Optional[str] = Field(
        None, description="Down color for candlestick series"
    )
    point_size: Optional[float] = Field(
        None, description="Point size for scatter series"
    )

    @field_validator("opacity")
    @classmethod
    def validate_opacity(cls, v: Optional[float]) -> Optional[float]:
        """Validate that opacity is between 0 and 1 if provided."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Opacity must be between 0.0 and 1.0")
        return v


class ChartSeries(BaseModel):
    """
    Definition of a chart series.

    Attributes:
        name (str): Name of the series
        type (ChartSeriesType): Type of series
        data_key (str): Data key for this series
        visible (bool): Whether this series is visible
        y_axis_id (Optional[str]): ID of the y-axis for this series
        style (Optional[ChartSeriesStyle]): Style options for this series
    """

    name: str = Field(..., description="Name of the series")
    type: ChartSeriesType = Field(..., description="Type of series")
    data_key: str = Field(..., description="Data key for this series")
    visible: bool = Field(True, description="Whether this series is visible")
    y_axis_id: Optional[str] = Field(
        None, description="ID of the y-axis for this series"
    )
    style: Optional[ChartSeriesStyle] = Field(
        None, description="Style options for this series"
    )


class ChartPanel(BaseModel):
    """
    Definition of a chart panel.

    Attributes:
        id (str): Unique identifier for the panel
        title (str): Panel title
        height (int): Panel height in pixels
        series (List[ChartSeries]): Series to display in this panel
        y_axis (Optional[ChartAxisOptions]): Y-axis options
        grid (Optional[ChartGridOptions]): Grid options
    """

    id: str = Field(..., description="Unique identifier for the panel")
    title: str = Field(..., description="Panel title")
    height: int = Field(300, description="Panel height in pixels")
    series: List[ChartSeries] = Field(
        ..., description="Series to display in this panel"
    )
    y_axis: Optional[ChartAxisOptions] = Field(None, description="Y-axis options")
    grid: Optional[ChartGridOptions] = Field(None, description="Grid options")

    @field_validator("height")
    @classmethod
    def validate_height(cls, v: int) -> int:
        """Validate panel height."""
        if v < 100:
            raise ValueError("Panel height must be at least 100 pixels")
        return v


class ChartOptions(BaseModel):
    """
    Options for chart rendering.

    Attributes:
        theme (ChartTheme): Chart color theme
        width (Optional[int]): Chart width in pixels (null for responsive)
        show_volume (bool): Whether to show volume panel
        show_toolbar (bool): Whether to show the chart toolbar
        show_legend (bool): Whether to show the legend
        crosshair (bool): Whether to show crosshair
        timezone (Optional[str]): Chart timezone
        x_axis (Optional[ChartAxisOptions]): X-axis options
        custom_css (Optional[str]): Custom CSS for advanced styling
    """

    theme: ChartTheme = Field(ChartTheme.LIGHT, description="Chart color theme")
    width: Optional[int] = Field(
        None, description="Chart width in pixels (null for responsive)"
    )
    show_volume: bool = Field(True, description="Whether to show volume panel")
    show_toolbar: bool = Field(True, description="Whether to show the chart toolbar")
    show_legend: bool = Field(True, description="Whether to show the legend")
    crosshair: bool = Field(True, description="Whether to show crosshair")
    timezone: Optional[str] = Field(None, description="Chart timezone")
    x_axis: Optional[ChartAxisOptions] = Field(None, description="X-axis options")
    custom_css: Optional[str] = Field(
        None, description="Custom CSS for advanced styling"
    )

    @field_validator("width")
    @classmethod
    def validate_width(cls, v: Optional[int]) -> Optional[int]:
        """Validate chart width if provided."""
        if v is not None and v < 200:
            raise ValueError("Chart width must be at least 200 pixels")
        return v


class ChartRenderRequest(BaseModel):
    """
    Request model for chart rendering.

    Attributes:
        symbol (str): Trading symbol
        timeframe (str): Data timeframe
        indicators (List[IndicatorConfig]): Indicators to include in the chart
        start_date (Optional[str]): Start date for data range (ISO format)
        end_date (Optional[str]): End date for data range (ISO format)
        panels (Optional[List[ChartPanel]]): Custom panel configuration
        options (Optional[ChartOptions]): Chart rendering options
        custom_layout (bool): Whether to use custom panel layout
    """

    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Data timeframe")
    indicators: List[IndicatorConfig] = Field(
        default_factory=list, description="Indicators to include in the chart"
    )
    start_date: Optional[str] = Field(
        None, description="Start date for data range (ISO format)"
    )
    end_date: Optional[str] = Field(
        None, description="End date for data range (ISO format)"
    )
    panels: Optional[List[ChartPanel]] = Field(
        None, description="Custom panel configuration"
    )
    options: Optional[ChartOptions] = Field(None, description="Chart rendering options")
    custom_layout: bool = Field(False, description="Whether to use custom panel layout")

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Validate timeframe format."""
        valid_timeframes = [
            "1m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "1d",
            "1w",
            "1M",
        ]
        if v not in valid_timeframes:
            raise ValueError(f"Timeframe must be one of {valid_timeframes}")
        return v


class ChartData(BaseModel):
    """
    Chart data structure.

    Attributes:
        config (Dict[str, Any]): Chart configuration object
        panels (List[Dict[str, Any]]): Panel configuration
        data (Dict[str, List[Any]]): Data series
        metadata (Dict[str, Any]): Chart metadata
    """

    config: Dict[str, Any] = Field(..., description="Chart configuration object")
    panels: List[Dict[str, Any]] = Field(..., description="Panel configuration")
    data: Dict[str, List[Any]] = Field(..., description="Data series")
    metadata: Dict[str, Any] = Field(..., description="Chart metadata")


class ChartRenderResponse(ApiResponse[ChartData]):
    """Response model for chart rendering."""

    pass


class ChartTemplateInfo(BaseModel):
    """
    Information about a chart template.

    Attributes:
        id (str): Template identifier
        name (str): Template name
        description (Optional[str]): Template description
        preview_url (Optional[str]): URL to template preview image
        tags (List[str]): Template tags for categorization
    """

    id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    preview_url: Optional[str] = Field(
        None, description="URL to template preview image"
    )
    tags: List[str] = Field(
        default_factory=list, description="Template tags for categorization"
    )


class ChartTemplatesResponse(ApiResponse[List[ChartTemplateInfo]]):
    """Response model for listing available chart templates."""

    pass


class ChartExportRequest(BaseModel):
    """
    Request model for exporting chart as image or HTML.

    Attributes:
        chart_id (str): ID of the rendered chart to export
        format (str): Export format (png, jpg, svg, html, json)
        width (Optional[int]): Width of the exported image
        height (Optional[int]): Height of the exported image
        scale (float): Scale factor for image export
        transparent (bool): Whether to use transparent background
    """

    chart_id: str = Field(..., description="ID of the rendered chart to export")
    format: str = Field(..., description="Export format (png, jpg, svg, html, json)")
    width: Optional[int] = Field(None, description="Width of the exported image")
    height: Optional[int] = Field(None, description="Height of the exported image")
    scale: float = Field(1.0, description="Scale factor for image export")
    transparent: bool = Field(
        False, description="Whether to use transparent background"
    )

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate export format."""
        valid_formats = ["png", "jpg", "svg", "html", "json"]
        if v not in valid_formats:
            raise ValueError(f"Format must be one of {valid_formats}")
        return v


class ChartExportResponse(BaseModel):
    """
    Response model for chart export.

    Attributes:
        success (bool): Whether the export was successful
        url (Optional[str]): URL to the exported file
        content (Optional[str]): Base64-encoded content for direct download
        mime_type (str): MIME type of the exported file
    """

    success: bool = Field(..., description="Whether the export was successful")
    url: Optional[str] = Field(None, description="URL to the exported file")
    content: Optional[str] = Field(
        None, description="Base64-encoded content for direct download"
    )
    mime_type: str = Field(..., description="MIME type of the exported file")
