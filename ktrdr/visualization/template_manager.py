"""
Template Manager for visualization module.

This module contains the TemplateManager class for handling HTML and JavaScript
templates used in the visualization module.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union

from ktrdr.errors import ConfigurationError

# Setup logging
import logging
logger = logging.getLogger(__name__)


class TemplateManager:
    """
    Manager for HTML and JavaScript templates used in chart visualization.
    
    This class handles the loading, manipulation, and rendering of HTML and JavaScript
    templates used for chart visualization. It provides methods for generating chart
    HTML and JavaScript code based on configurations.
    """

    @staticmethod
    def get_base_template() -> str:
        """
        Get the base HTML template for chart visualization.
        
        Returns:
            The base HTML template as a string.
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
            margin: 0;
            padding: 0;
            background-color: {background_color};
            color: {text_color};
        }}
        .chart-container {{
            margin: 20px auto;
            width: 95%;
        }}
        .chart-inner {{
            margin-bottom: 15px;
            border: 1px solid {border_color};
            border-radius: 4px;
            overflow: hidden;
        }}
        .chart-title {{
            padding: 10px;
            margin: 0;
            font-size: 16px;
            border-bottom: 1px solid {border_color};
            background-color: {panel_color};
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .chart-title h2 {{
            margin: 0;
            font-size: 18px;
        }}
        .chart-title .legend {{
            display: flex;
            gap: 15px;
            font-size: 12px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-color {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}
        .chart-wrapper {{
            position: relative;
            height: {chart_height}px;
        }}
        .controls {{
            margin: 20px auto;
            width: 95%;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .theme-switch {{
            display: flex;
            gap: 10px;
        }}
        button {{
            padding: 8px 16px;
            background-color: {button_bg};
            color: {button_text};
            border: 1px solid {border_color};
            border-radius: 4px;
            cursor: pointer;
        }}
        button:hover {{
            background-color: {button_hover};
        }}
        button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        h1 {{
            text-align: center;
            margin: 20px 0;
            font-size: 24px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        @media (max-width: 768px) {{
            .chart-container {{
                width: 100%;
            }}
            .controls {{
                width: 100%;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="controls">
            <div class="theme-switch">
                <button id="darkTheme" {dark_disabled}>Dark Theme</button>
                <button id="lightTheme" {light_disabled}>Light Theme</button>
            </div>
            <div class="actions">
                <button id="zoomFit">Fit All Data</button>
            </div>
        </div>
        <div id="charts-container">
            {chart_containers}
        </div>
    </div>

    <script>
        // Ensure the library is loaded before proceeding
        document.addEventListener('DOMContentLoaded', function() {{
            // Make sure LightweightCharts is defined
            if (typeof LightweightCharts === 'undefined') {{
                console.error('LightweightCharts library not loaded!');
                alert('Unable to load chart library. Please check your internet connection and try again.');
                return;
            }}
            
            // Get elements
            const darkThemeBtn = document.getElementById('darkTheme');
            const lightThemeBtn = document.getElementById('lightTheme');
            const zoomFitBtn = document.getElementById('zoomFit');
            
            // Create all charts and keep references for theme switching
            const charts = [];
            
            {chart_scripts}
            
            // Theme switch functionality
            darkThemeBtn.addEventListener('click', () => {{
                // Apply dark theme styling
                document.body.style.backgroundColor = '#151924';
                document.body.style.color = '#d1d4dc';
                document.querySelectorAll('.chart-inner').forEach(el => el.style.borderColor = '#2a2e39');
                document.querySelectorAll('.chart-title').forEach(el => {{
                    el.style.borderColor = '#2a2e39';
                    el.style.backgroundColor = '#1e222d';
                }});
                document.querySelectorAll('button').forEach(el => {{
                    el.style.backgroundColor = '#2a2e39';
                    el.style.color = '#d1d4dc';
                    el.style.borderColor = '#2a2e39';
                }});
                
                // Update disabled state of theme buttons
                darkThemeBtn.disabled = true;
                lightThemeBtn.disabled = false;
                
                // Apply theme to all charts
                charts.forEach(chart => {{
                    chart.applyOptions({{
                        layout: {{ background: {{ color: '#151924' }}, textColor: '#d1d4dc' }},
                        grid: {{ vertLines: {{ color: '#2a2e39' }}, horzLines: {{ color: '#2a2e39' }} }},
                        rightPriceScale: {{ borderColor: '#2a2e39' }},
                        timeScale: {{ borderColor: '#2a2e39' }}
                    }});
                }});
            }});
            
            lightThemeBtn.addEventListener('click', () => {{
                // Apply light theme styling
                document.body.style.backgroundColor = '#ffffff';
                document.body.style.color = '#333333';
                document.querySelectorAll('.chart-inner').forEach(el => el.style.borderColor = '#e6e6e6');
                document.querySelectorAll('.chart-title').forEach(el => {{
                    el.style.borderColor = '#e6e6e6';
                    el.style.backgroundColor = '#f9f9f9';
                }});
                document.querySelectorAll('button').forEach(el => {{
                    el.style.backgroundColor = '#f0f0f0';
                    el.style.color = '#333333';
                    el.style.borderColor = '#e6e6e6';
                }});
                
                // Update disabled state of theme buttons
                darkThemeBtn.disabled = false;
                lightThemeBtn.disabled = true;
                
                // Apply theme to all charts
                charts.forEach(chart => {{
                    chart.applyOptions({{
                        layout: {{ background: {{ color: '#ffffff' }}, textColor: '#333333' }},
                        grid: {{ vertLines: {{ color: '#e6e6e6' }}, horzLines: {{ color: '#e6e6e6' }} }},
                        rightPriceScale: {{ borderColor: '#e6e6e6' }},
                        timeScale: {{ borderColor: '#e6e6e6' }}
                    }});
                }});
            }});
            
            // Handle window resize
            window.addEventListener('resize', () => {{
                {resize_handlers}
            }});
            
            // Handle zoom fit button
            zoomFitBtn.addEventListener('click', () => {{
                {zoom_fit_handlers}
            }});
            
            {sync_scripts}
            
            // Create overlay series
            {overlay_scripts}
        }});
    </script>
</body>
</html>
"""

    @staticmethod
    def render_chart_html(
        title: str = "KTRDR Chart",
        chart_configs: List[Dict] = None,
        chart_data: Dict = None,
        theme: str = "dark", 
        has_range_slider: bool = False
    ) -> str:
        """
        Render chart HTML based on the template.
        
        Args:
            title: The title of the chart.
            chart_configs: List of chart configurations.
            chart_data: Dictionary of chart data.
            theme: The theme to use. Either 'dark' or 'light'.
            has_range_slider: Whether to include a range slider.
            
        Returns:
            The rendered HTML as a string.
        
        Raises:
            ConfigurationError: If an invalid theme is provided.
        """
        if chart_configs is None:
            chart_configs = []
        
        if chart_data is None:
            chart_data = {}

        # Set theme-specific styles
        if theme == "dark":
            background_color = "#151924"
            text_color = "#d1d4dc"
            border_color = "#2a2e39"
            panel_color = "#1e222d"
            button_bg = "#2a2e39"
            button_text = "#d1d4dc"
            button_hover = "#3a3e49"
            dark_disabled = "disabled"
            light_disabled = ""
        elif theme == "light":
            background_color = "#ffffff"
            text_color = "#333333"
            border_color = "#e6e6e6"
            panel_color = "#f9f9f9"
            button_bg = "#f0f0f0"
            button_text = "#333333"
            button_hover = "#e0e0e0"
            dark_disabled = ""
            light_disabled = "disabled"
        else:
            raise ConfigurationError(
                f"Invalid theme: {theme}. Use 'dark' or 'light'.",
                "CONFIG-InvalidTheme",
                {"theme": theme}
            )
        
        # Create chart containers
        chart_containers = ""
        chart_scripts = ""
        resize_handlers = ""
        zoom_fit_handlers = ""
        sync_scripts = ""
        overlay_scripts = ""
        
        # Maps to track charts for synchronization
        chart_ids = []
        charts_to_sync = {}
        
        # Process chart configurations
        for config in chart_configs:
            chart_id = config.get("id", f"chart_{len(chart_ids)}")
            chart_ids.append(chart_id)
            
            chart_type = config.get("type", "price")
            chart_title = config.get("title", f"{chart_type.capitalize()} Chart")
            chart_height = config.get("height", 400)
            
            # Create chart container div with the correct height
            chart_containers += f"""
        <div class="chart-container">
            <div class="chart-inner">
                <div class="chart-title">
                    <h2>{chart_title}</h2>
                    <div class="legend" id="{chart_id}_legend"></div>
                </div>
                <div class="chart-wrapper" id="{chart_id}" style="height: {chart_height}px;"></div>
            </div>
        </div>
"""
            
            # Track charts that need to be synchronized
            if "sync" in config:
                target_chart_id = config["sync"].get("target")
                sync_mode = config["sync"].get("mode", "default")
                
                if target_chart_id:
                    if target_chart_id not in charts_to_sync:
                        charts_to_sync[target_chart_id] = []
                    charts_to_sync[target_chart_id].append({
                        "chart_id": chart_id,
                        "mode": sync_mode
                    })
            
            # Generate chart data
            chart_data_obj = chart_data.get(chart_id, [])
            
            # Generate chart script
            chart_scripts += TemplateManager._generate_chart_script(
                chart_id=chart_id,
                chart_type=chart_type,
                chart_config=config,
                data=chart_data_obj,
                is_range_slider=config.get("is_range_slider", False)
            )
            
            # Add resize handler
            resize_handlers += f"if ({chart_id}) {chart_id}.resize({chart_height}, {chart_id}.clientWidth);\n            "
            
            # Add zoom fit handler
            zoom_fit_handlers += f"if ({chart_id}) {chart_id}.timeScale().fitContent();\n            "
            
            # Process overlay series if present
            if "overlay_series" in config and chart_data:
                for overlay in config.get("overlay_series", []):
                    overlay_id = overlay.get("id")
                    overlay_type = overlay.get("type", "line")
                    overlay_options = overlay.get("options", {})
                    
                    # Skip if no data is available for this overlay
                    if overlay_id not in chart_data:
                        continue
                    
                    overlay_data = chart_data.get(overlay_id, [])
                    
                    # Generate script for adding overlay series
                    color = overlay_options.get("color", "#2962FF")
                    line_width = overlay_options.get("lineWidth", 1.5)
                    title = overlay_options.get("title", "")
                    
                    # Generate method name with proper case (addLineSeries, addAreaSeries, etc.)
                    overlay_method_name = f"add{overlay_type[0].upper()}{overlay_type[1:]}Series"
                    
                    overlay_scripts += f"""
        // Add {overlay_type} overlay to {chart_id}
        const {overlay_id} = {chart_id}.{overlay_method_name}({{
            color: '{color}',
            lineWidth: {line_width},
            title: '{title}'
        }});
        {overlay_id}.setData({json.dumps(overlay_data)});
        
        // Add to legend
        const {overlay_id}_legend = document.createElement('div');
        {overlay_id}_legend.className = 'legend-item';
        const {overlay_id}_color = document.createElement('div');
        {overlay_id}_color.className = 'legend-color';
        {overlay_id}_color.style.backgroundColor = '{color}';
        const {overlay_id}_label = document.createElement('span');
        {overlay_id}_label.textContent = '{title}';
        {overlay_id}_legend.appendChild({overlay_id}_color);
        {overlay_id}_legend.appendChild({overlay_id}_label);
        document.getElementById('{chart_id}_legend').appendChild({overlay_id}_legend);
"""
        
        # Generate synchronization scripts
        for target_chart_id, source_charts in charts_to_sync.items():
            sync_scripts += f"""
        // Sync {target_chart_id} with its dependent charts
        if ({target_chart_id}) {{
            {target_chart_id}.timeScale().subscribeVisibleLogicalRangeChange((timeRange) => {{
                if (timeRange) {{
"""
            
            for source in source_charts:
                source_chart_id = source["chart_id"]
                sync_scripts += f"""                    if ({source_chart_id}) {{
                        {source_chart_id}.timeScale().setVisibleLogicalRange(timeRange);
                    }}
"""
            
            sync_scripts += """                }
            });
"""
            
            # Add bidirectional synchronization
            for source in source_charts:
                source_chart_id = source["chart_id"]
                sync_scripts += f"""
            // Bidirectional sync: When {source_chart_id} changes, update {target_chart_id} and other dependent charts
            if ({source_chart_id}) {{
                {source_chart_id}.timeScale().subscribeVisibleLogicalRangeChange((timeRange) => {{
                    if (timeRange) {{
                        {target_chart_id}.timeScale().setVisibleLogicalRange(timeRange);
"""
                
                # Sync other dependent charts too
                for other_source in source_charts:
                    other_chart_id = other_source["chart_id"]
                    if other_chart_id != source_chart_id:
                        sync_scripts += f"""                        if ({other_chart_id}) {{
                            {other_chart_id}.timeScale().setVisibleLogicalRange(timeRange);
                        }}
"""
                
                sync_scripts += """                    }
                });
            }
"""
            
            sync_scripts += "        }\n"

        # Handle range slider if needed
        if has_range_slider:
            slider_id = next((c["id"] for c in chart_configs if c.get("is_range_slider", False)), "range_slider")
            main_chart_id = next((c["sync"]["target"] for c in chart_configs if c.get("id") == slider_id), chart_ids[0])
            
            sync_scripts += f"""
        // Special handling for range slider
        if ({slider_id} && {main_chart_id}) {{
            // Set initial visible range from range slider to main chart
            const initialRange = {slider_id}.timeScale().getVisibleLogicalRange();
            if (initialRange) {{
                {main_chart_id}.timeScale().setVisibleLogicalRange(initialRange);
            }}
        }}
"""
        
        # Render the template with all components
        return TemplateManager.get_base_template().format(
            title=title,
            background_color=background_color,
            text_color=text_color,
            border_color=border_color,
            panel_color=panel_color,
            button_bg=button_bg,
            button_text=button_text,
            button_hover=button_hover,
            dark_disabled=dark_disabled,
            light_disabled=light_disabled,
            chart_height=400,  # This is overridden by individual chart heights in the container divs
            chart_containers=chart_containers,
            chart_scripts=chart_scripts,
            resize_handlers=resize_handlers,
            zoom_fit_handlers=zoom_fit_handlers,
            sync_scripts=sync_scripts,
            overlay_scripts=overlay_scripts
        )

    @staticmethod
    def _generate_chart_script(chart_id: str, chart_type: str, chart_config: Dict, 
                            data: List[Dict], is_range_slider: bool = False) -> str:
        """
        Generate JavaScript code to create a chart with the given configuration.
        
        Args:
            chart_id: The ID of the chart.
            chart_type: The type of chart.
            chart_config: The chart configuration.
            data: The data for the chart.
            is_range_slider: Whether the chart is a range slider.
            
        Returns:
            The generated JavaScript code.
        """
        # Set up variables
        chart_options = chart_config.get("options", {})
        series_options = chart_config.get("series_options", {})
        height = chart_config.get("height", 400)
        
        # Series type based on chart type
        series_type = "candlestick" if chart_type == "price" else \
                     "histogram" if chart_type == "histogram" else \
                     "area" if chart_type == "range" else "line"
        
        # Generate method name with proper case (addCandlestickSeries, addHistogramSeries, etc.)
        method_name = f"add{series_type[0].upper()}{series_type[1:]}Series"
        
        # Set up the chart creation script with explicit sizing to ensure rendering
        script = f"""
        // Create {chart_id} container with explicit size
        const {chart_id}_container = document.getElementById('{chart_id}');
        {chart_id}_container.style.height = '{height}px';
        
        // Create chart with explicit options
        const {chart_id} = LightweightCharts.createChart({chart_id}_container, {{
            layout: {{
                background: {{ color: '{chart_options.get("layout", {}).get("background", {}).get("color", "#151924")}' }},
                textColor: '{chart_options.get("layout", {}).get("textColor", "#d1d4dc")}'
            }},
            grid: {{
                vertLines: {{ color: '{chart_options.get("grid", {}).get("vertLines", {}).get("color", "#2A2E39")}' }},
                horzLines: {{ color: '{chart_options.get("grid", {}).get("horzLines", {}).get("color", "#2A2E39")}' }}
            }},
            rightPriceScale: {{
                borderColor: '{chart_options.get("rightPriceScale", {}).get("borderColor", "#2A2E39")}',
                visible: {str(chart_options.get("rightPriceScale", {}).get("visible", True)).lower()}
            }},
            timeScale: {{
                borderColor: '{chart_options.get("timeScale", {}).get("borderColor", "#2A2E39")}',
                timeVisible: {str(chart_options.get("timeScale", {}).get("timeVisible", True)).lower()},
                secondsVisible: {str(chart_options.get("timeScale", {}).get("secondsVisible", False)).lower()},
                fixLeftEdge: {str(chart_options.get("timeScale", {}).get("fixLeftEdge", True)).lower()},
                fixRightEdge: {str(chart_options.get("timeScale", {}).get("fixRightEdge", True)).lower()}
            }},
            handleScroll: {str(chart_options.get("handleScroll", True)).lower()},
            handleScale: {str(chart_options.get("handleScale", True)).lower()}
        }});
        
        // Add chart to the charts array for theme switching
        charts.push({chart_id});
        
        // Make sure chart is properly sized
        {chart_id}.resize(
            {chart_id}_container.clientWidth,
            {chart_id}_container.clientHeight
        );
        
        // Create series with explicit options
        const {chart_id}_series = {chart_id}.{method_name}({{
            {', '.join([f'{k}: "{v}"' if isinstance(v, str) else f'{k}: {str(v).lower()}' if isinstance(v, bool) else f'{k}: {v}' for k, v in series_options.items()])}
        }});
        
        // Set data for {chart_id}
        {chart_id}_series.setData({json.dumps(data)});
        
        // Fit content to ensure chart displays properly
        {chart_id}.timeScale().fitContent();
"""
        
        # Add special handling for range slider if needed
        if is_range_slider:
            script += f"""
        // Configure range slider behavior
        const handle{chart_id}TimeRangeChange = (timeRange) => {{
            if (typeof window.onRangeChange === 'function') {{
                window.onRangeChange(timeRange);
            }}
        }};
        
        {chart_id}.timeScale().subscribeVisibleLogicalRangeChange(handle{chart_id}TimeRangeChange);
"""
        
        return script