---
name: visualization
description: Use when working on chart generation, TradingView lightweight-charts, HTML chart rendering, indicator overlays, or chart configuration.
---

# Visualization

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL visualization loaded!`

Load this skill when working on:

- Chart generation (candlestick, line, area, histogram)
- Indicator overlays and panels
- HTML chart rendering and export
- Chart configuration and theming

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/visualization/visualizer.py` | High-level public API |
| `ktrdr/visualization/renderer.py` | HTML rendering engine |
| `ktrdr/visualization/data_adapter.py` | DataFrame → lightweight-charts JSON |
| `ktrdr/visualization/config_builder.py` | Chart configuration factory |
| `ktrdr/visualization/template_manager.py` | HTML template management |

---

## Architecture

```
DataFrame (OHLCV + indicators)
    │
    ▼ DataAdapter (static transforms)
JSON data (lightweight-charts format)
    │
    ▼ ConfigBuilder (chart options)
    │
    ▼ Renderer + TemplateManager
HTML output (self-contained, TradingView lightweight-charts v4.1.1)
```

**Framework:** TradingView's [lightweight-charts v4.1.1](https://github.com/nickvdyck/lightweight-charts) loaded via CDN.

---

## Visualizer API

```python
from ktrdr.visualization.visualizer import Visualizer

viz = Visualizer()

# Create base chart
chart = viz.create_chart(data=df, title="AAPL", chart_type="candlestick", height=400)

# Add indicator overlay (on main chart)
viz.add_indicator_overlay(chart, data=sma_series, label="SMA 20", color="blue")

# Add indicator panel (separate panel below)
viz.add_indicator_panel(chart, data=rsi_series, label="RSI 14", panel_height=150)

# Add range slider
viz.configure_range_slider(chart)

# Export
viz.save(chart, "chart.html")     # Save to file
html = viz.show(chart)            # Return HTML string
```

### Chart Types

- **Candlestick** — OHLC candlesticks
- **Line** — Single series line
- **Area** — Filled area chart
- **Bar** — OHLC bar chart
- **Histogram** — Volume or signal histogram

### DataAdapter

Static methods for DataFrame → JSON conversion:

```python
DataAdapter.transform_ohlc(df)        # OHLCV → candlestick data
DataAdapter.transform_line(series)    # Series → line data
DataAdapter.transform_histogram(series)  # Series → histogram data
```

---

## Gotchas

### Charts are self-contained HTML

Output HTML files include inline JavaScript and load lightweight-charts from CDN. They work standalone in any browser — no server needed.

### Dark/light theme support

ConfigBuilder supports both themes. Theme is set at chart creation time.
