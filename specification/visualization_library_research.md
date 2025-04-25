# KTRDR Visualization Library Research

## Current Challenges with Plotly

After attempting to implement visualization capabilities using Plotly, we encountered several significant challenges:

1. **Layout Control Issues**: Plotly's automatic layout handling proved inconsistent for multi-subplot charts, particularly with varying indicator counts.
2. **Subplot Overlapping**: Despite numerous attempts at adjusting spacing parameters, we continued to face issues with chart elements overlapping.
3. **Proportional Sizing**: Maintaining appropriate proportions between the main price chart and indicators was difficult, especially when adding multiple indicators.
4. **Range Slider Size**: The range slider component took up excessive space and was challenging to resize appropriately.
5. **Domain Value Precision**: We encountered technical issues with domain value calculations, including floating point precision errors.

These issues suggest that while Plotly is a powerful general-purpose visualization library, it may not be optimized for the specific requirements of financial charting with multiple indicators.

## Alternative Charting Libraries

### 1. TradingView's Lightweight-charts

**Overview**: A specialized JavaScript library created specifically for financial and trading charts.

**Key Strengths**:
- Purpose-built for financial time series visualization
- Optimized rendering performance for real-time data
- Designed with built-in support for multiple indicators
- Proper handling of price scales and time axes
- Native support for common trading chart features (candlesticks, bars, volume)
- Used by TradingView, a leading platform in the industry

**Potential Challenges**:
- JavaScript-based, requiring integration with Python backend
- May require additional work for interactive features

**Implementation Approach**:
- Use the library via PyScript or a simple web interface
- Create a Python wrapper class that generates appropriate configuration
- Implement data conversion utilities for our internal formats

### 2. ECharts

**Overview**: A comprehensive charting library with strong support for custom layouts and financial visualization.

**Key Strengths**:
- Explicit grid layout system for precise positioning
- Specialized stock chart components
- Excellent documentation and examples
- Strong performance with large datasets
- Support for both time-series and other visualization types

**Potential Challenges**:
- More general-purpose than trading-specific libraries
- Heavier than some alternatives
- May require more configuration for financial charts

### 3. D3FC / Financial Charts

**Overview**: Financial components built on D3.js with fine-grained control.

**Key Strengths**:
- Complete control over layout and drawing
- First-class financial charting components
- Can be tailored exactly to our requirements
- Support for advanced financial visualization techniques

**Potential Challenges**:
- Steeper learning curve
- Requires more custom code
- JavaScript-based, requiring integration with Python

### 4. Highcharts/Highstock

**Overview**: Premium charting solution with excellent financial charting capabilities.

**Key Strengths**:
- First-class stock charting components
- Commercial-grade reliability and performance
- Well-designed layouts for indicators and technical analysis
- Extensive documentation and examples

**Potential Challenges**:
- Commercial license required for most uses
- May be overkill for simpler applications

## Architectural Approaches

### Container-Based Architecture

Rather than relying on a plotting library to handle layout, we could implement a container-based approach:

1. Define explicit containers for each chart element with fixed proportions
2. Each chart renders within its own container boundaries
3. Use CSS Grid or Flexbox for explicit spacing control
4. Implement communication between charts for synchronized zooming/panning

This approach provides several advantages:
- Clear separation between charts prevents overlap by design
- Explicit proportion control for the price chart vs. indicators
- Greater control over individual chart elements
- More flexible layout options for different screen sizes

## Exploration Plan for TradingView's Lightweight-charts

### Phase 1: Proof of Concept (1-2 days)

1. **Setup and Integration**
   - Create a simple HTML/JS environment to test the library
   - Implement basic data conversion from our DataFrame format to lightweight-charts format
   - Create a simple price chart with candlesticks

2. **Implement Required Chart Components**
   - Create a comprehensive multi-chart layout with:
     - Price chart with overlay indicators:
       - SMA 20
       - EMA 10
     - Volume indicator panel
     - RSI indicator panel
     - MACD indicator panel with signal line and histogram
   - Implement a compact range slider for zooming and panning
   - Ensure all charts are synchronized when using the range slider
   - Verify proper spacing and no overlapping between chart components

3. **Evaluation**
   - Document the results of the proof of concept
   - Compare with our Plotly implementation
   - Make a go/no-go decision on proceeding with lightweight-charts

### Phase 2: Python Integration (2-3 days)

If the proof of concept is successful:

1. **Wrapper Development**
   - Create a Python wrapper class for lightweight-charts
   - Implement data transformation utilities
   - Create configuration generators for common chart types and indicator combinations:
     - Candlestick charts with moving average overlays
     - Volume indicator with coloring based on price movement
     - RSI with overbought/oversold lines
     - MACD with signal line and histogram

2. **Integration with KTRDR**
   - Create a Visualizer class that uses the lightweight-charts wrapper
   - Implement the standard interface for chart generation:
     ```python
     # Example API we want to support
     visualizer = Visualizer(theme="dark")
     
     # Create main chart with indicators
     fig = visualizer.plot_price(df, title="AAPL Price with Indicators")
     fig = visualizer.add_indicator_overlay(fig, df, "sma_20", color="#1f77b4")
     fig = visualizer.add_indicator_overlay(fig, df, "ema_10", color="#ff7f0e")
     
     # Add indicator subcharts
     fig = visualizer.add_volume(fig, df)
     fig = visualizer.add_rsi(fig, df, periods=14)
     fig = visualizer.add_macd(fig, df, fast=12, slow=26, signal=9)
     
     # Configure range slider
     fig = visualizer.configure_range_slider(fig, height=40, show=True)
     
     # Show or save the chart
     visualizer.show(fig)
     visualizer.save(fig, "my_chart.html")
     ```

3. **Testing and Refinement**
   - Test with various indicator combinations
   - Ensure all interactive features work properly
   - Verify proper proportional sizing of chart components
   - Test responsiveness and performance with different data sizes

### Phase 3: Documentation and Architecture Update (1 day)

1. **Update Architecture Documentation**
   - Document the chosen approach and rationale
   - Update component diagrams to reflect the new visualization implementation
   - Document the integration pattern between Python and JavaScript components

2. **Update Task Breakdown**
   - Revise the task breakdown to reflect the new implementation approach
   - Adjust time estimates based on our findings
   - Add any new tasks required for the chosen architecture

## Success Criteria

The exploration of TradingView's lightweight-charts will be considered successful if we can create an integrated visualization solution that includes:

1. **Price Chart Components**
   - Candlestick or OHLC price display
   - Support for multiple overlay indicators (SMA 20, EMA 10)
   - Proper handling of gaps in data

2. **Volume Panel**
   - Volume bars with coloring based on price movement
   - Proper scaling and alignment with the price chart

3. **Technical Indicators**
   - RSI panel with overbought/oversold reference lines
   - MACD panel with signal line and histogram
   - Easy extension to other indicators

4. **Navigation and Interactivity**
   - Compact range slider for zooming and panning
   - Synchronized movement across all chart components
   - Tooltips showing values on hover

5. **Layout and Design**
   - No overlapping between chart components
   - Price chart maintains appropriate proportional size (at least 50% of the vertical space)
   - Consistent styling with theme support
   - Responsive to different display sizes

6. **Integration**
   - Clean Python API that abstracts the JavaScript implementation details
   - Similar interface to what we attempted with Plotly for easy adoption
   - Good performance with typical data volumes (1000+ data points)

## Timeline

- Proof of Concept with All Required Components: 1-2 days
- Python Integration and API Development: 2-3 days
- Documentation and Architecture Updates: 1 day

Total estimated time: 4-6 days