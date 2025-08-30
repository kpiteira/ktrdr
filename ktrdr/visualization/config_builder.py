"""
Configuration builder for visualization.

This module contains the ConfigBuilder class that provides methods to create
chart configuration objects for the visualization module.
"""

from typing import Any, Optional


class ConfigBuilder:
    """
    Builder for chart configuration objects.

    This class provides static methods to create standardized configuration
    dictionaries for various chart types and components.
    """

    @staticmethod
    def create_chart_options(
        theme: str = "dark",
        height: int = 400,
        visible_time_scale: bool = True,
        handle_scale: bool = True,
        handle_scroll: bool = True,
        time_scale_options: Optional[dict[str, Any]] = None,
        right_price_scale_options: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Create basic chart options.

        Args:
            theme: The chart theme. Either 'dark' or 'light'.
            height: The height of the chart in pixels.
            visible_time_scale: Whether to show the time scale.
            handle_scale: Whether to handle scaling events.
            handle_scroll: Whether to handle scroll events.
            time_scale_options: Additional options for the time scale.
            right_price_scale_options: Additional options for the right price scale.

        Returns:
            A dictionary of chart options.
        """
        # Set default colors based on theme
        if theme == "dark":
            background_color = "#151924"
            text_color = "#d1d4dc"
            grid_color = "#2A2E39"
        else:  # light
            background_color = "#FFFFFF"
            text_color = "#333333"
            grid_color = "#E0E0E0"

        # Base options
        options = {
            "height": height,
            "layout": {
                "background": {"color": background_color},
                "textColor": text_color,
            },
            "grid": {
                "vertLines": {"color": grid_color},
                "horzLines": {"color": grid_color},
            },
            "handleScale": handle_scale,
            "handleScroll": handle_scroll,
            "rightPriceScale": {"borderColor": grid_color, "visible": True},
            "timeScale": {
                "borderColor": grid_color,
                "visible": visible_time_scale,
                "timeVisible": True,
                "secondsVisible": False,
                "fixLeftEdge": True,
                "fixRightEdge": True,
                "lockVisibleTimeRangeOnResize": True,
            },
            "crosshair": {
                "mode": 0,  # Normal crosshair mode
                "vertLine": {
                    "style": 0,  # Solid line
                    "width": 1,
                    "color": "#9598A1",
                    "labelBackgroundColor": "#9598A1",
                },
                "horzLine": {
                    "style": 0,  # Solid line
                    "width": 1,
                    "color": "#9598A1",
                    "labelBackgroundColor": "#9598A1",
                },
            },
        }

        # Add additional time scale options if provided
        if time_scale_options:
            for key, value in time_scale_options.items():
                options["timeScale"][key] = value

        # Add additional right price scale options if provided
        if right_price_scale_options:
            for key, value in right_price_scale_options.items():
                options["rightPriceScale"][key] = value

        return options

    @staticmethod
    def create_price_chart_options(
        theme: str = "dark", height: int = 400, show_volume: bool = False, **kwargs
    ) -> dict[str, Any]:
        """
        Create options specifically for price charts.

        Args:
            theme: The chart theme. Either 'dark' or 'light'.
            height: The height of the chart in pixels.
            show_volume: Whether to show volume by default.
            **kwargs: Additional arguments to pass to create_chart_options.

        Returns:
            A dictionary of price chart options.
        """
        # Get base options
        options = ConfigBuilder.create_chart_options(
            theme=theme, height=height, **kwargs
        )

        # Enable auto scaling for price chart
        options["rightPriceScale"]["autoScale"] = True

        # Configure time scale
        options["timeScale"]["barSpacing"] = 6
        options["timeScale"]["tickMarkFormatter"] = None  # Use default formatter

        return options

    @staticmethod
    def create_indicator_chart_options(
        theme: str = "dark",
        height: int = 150,
        visible_time_scale: bool = False,
        handle_scale: bool = True,
        handle_scroll: bool = True,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create options specifically for indicator charts.

        Args:
            theme: The chart theme. Either 'dark' or 'light'.
            height: The height of the chart in pixels.
            visible_time_scale: Whether to show the time scale.
            handle_scale: Whether to handle scaling events.
            handle_scroll: Whether to handle scroll events.
            **kwargs: Additional arguments to pass to create_chart_options.

        Returns:
            A dictionary of indicator chart options.
        """
        # Get base options with smaller height
        options = ConfigBuilder.create_chart_options(
            theme=theme,
            height=height,
            visible_time_scale=visible_time_scale,
            handle_scale=handle_scale,
            handle_scroll=handle_scroll,
            **kwargs,
        )

        return options

    @staticmethod
    def create_range_slider_options(
        theme: str = "dark", height: int = 60, **kwargs
    ) -> dict[str, Any]:
        """
        Create options specifically for range sliders.

        Args:
            theme: The chart theme. Either 'dark' or 'light'.
            height: The height of the chart in pixels.
            **kwargs: Additional arguments to pass to create_chart_options.

        Returns:
            A dictionary of range slider chart options.
        """
        # Get base options with smaller height and visible time scale
        options = ConfigBuilder.create_chart_options(
            theme=theme, height=height, visible_time_scale=True, **kwargs
        )

        # Configure time scale for range slider
        options["timeScale"]["barSpacing"] = 4  # Smaller bar spacing for range slider
        options["timeScale"]["tickMarkFormatter"] = None  # Use default formatter

        # Add overlay mode for range slider
        options["overlay"] = True

        return options

    @staticmethod
    def create_series_options(
        series_type: str = "line",
        color: str = "#2962FF",
        line_width: float = 1.5,
        title: str = "",
        price_format: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create options for a chart series.

        Args:
            series_type: The type of series. One of 'line', 'candlestick', 'histogram', 'area'.
            color: The color of the series.
            line_width: The width of the line for line and area series.
            title: The title of the series.
            price_format: Custom price format settings.
            **kwargs: Additional options for specific series types.

        Returns:
            A dictionary of series options.
        """
        # Base options for all series types
        options = {
            "title": title,
            "priceFormat": price_format or {"type": "price", "precision": 2},
        }

        # Add options specific to the series type
        if series_type == "candlestick":
            options.update(
                {
                    "upColor": kwargs.get("up_color", "#26a69a"),
                    "downColor": kwargs.get("down_color", "#ef5350"),
                    "borderVisible": kwargs.get("border_visible", False),
                    "wickUpColor": kwargs.get("wick_up_color", "#26a69a"),
                    "wickDownColor": kwargs.get("wick_down_color", "#ef5350"),
                }
            )
        elif series_type == "line":
            options.update(
                {
                    "color": color,
                    "lineWidth": line_width,
                    "lineStyle": kwargs.get(
                        "line_style", 0
                    ),  # 0 = solid, 1 = dotted, 2 = dashed
                    "crosshairMarkerVisible": kwargs.get(
                        "crosshair_marker_visible", True
                    ),
                    "crosshairMarkerRadius": kwargs.get("crosshair_marker_radius", 4),
                }
            )
        elif series_type == "area":
            options.update(
                {
                    "topColor": kwargs.get(
                        "top_color", color + "80"
                    ),  # Add alpha for transparency
                    "bottomColor": kwargs.get("bottom_color", color + "10"),
                    "lineColor": kwargs.get("line_color", color),
                    "lineWidth": line_width,
                    "lineStyle": kwargs.get("line_style", 0),
                    "crosshairMarkerVisible": kwargs.get(
                        "crosshair_marker_visible", True
                    ),
                    "crosshairMarkerRadius": kwargs.get("crosshair_marker_radius", 4),
                }
            )
        elif series_type == "histogram":
            options.update({"color": color, "base": kwargs.get("base", 0)})

        return options

    @staticmethod
    def create_overlay_series_config(
        id: str,
        series_type: str = "line",
        color: str = "#2962FF",
        line_width: float = 1.5,
        title: str = "",
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create configuration for an overlay series.

        Args:
            id: The ID of the overlay series.
            series_type: The type of series. Usually 'line' for overlays.
            color: The color of the series.
            line_width: The width of the line.
            title: The title of the series.
            **kwargs: Additional options for specific series types.

        Returns:
            A dictionary containing the overlay series configuration.
        """
        # Create series options
        options = ConfigBuilder.create_series_options(
            series_type=series_type,
            color=color,
            line_width=line_width,
            title=title,
            **kwargs,
        )

        # Create overlay configuration
        return {"id": id, "type": series_type, "options": options}

    @staticmethod
    def create_multi_panel_config(
        title: str = "Multi-Panel Chart",
        theme: str = "dark",
        panels: Optional[list[dict[str, Any]]] = None,
        has_range_slider: bool = False,
    ) -> dict[str, Any]:
        """
        Create configuration for a multi-panel chart.

        Args:
            title: The title of the chart.
            theme: The theme. Either 'dark' or 'light'.
            panels: List of panel configurations.
            has_range_slider: Whether to include a range slider.

        Returns:
            A dictionary containing the full multi-panel configuration.
        """
        if panels is None:
            panels = []

        # Create main configuration object
        config = {
            "title": title,
            "theme": theme,
            "chart_configs": panels,
            "has_range_slider": has_range_slider,
        }

        return config

    @staticmethod
    def create_highlight_band(
        start_value: float,
        end_value: float,
        color: str = "rgba(76, 175, 80, 0.2)",  # Semi-transparent green
        axis_label_visible: bool = True,
        target_chart_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a configuration for a highlight band.

        Args:
            start_value: The start value of the band.
            end_value: The end value of the band.
            color: The color of the band.
            axis_label_visible: Whether to show the axis label.
            target_chart_id: The ID of the chart to add the band to.

        Returns:
            A dictionary containing the highlight band configuration.
        """
        return {
            "start_value": start_value,
            "end_value": end_value,
            "color": color,
            "axis_label_visible": axis_label_visible,
            "target_chart_id": target_chart_id,
        }
