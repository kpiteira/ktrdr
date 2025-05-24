# Trading UI Requirements Document

## Project Overview
Automated trading application with neuro-fuzzy network backend and web-based research/analysis frontend. The system uses technical indicators as fuzzy inputs to generate trading decisions.

## MVP Scope: Research Phase
Primary goal is to visualize instrument data, indicators, and fuzzy sets to facilitate strategy development.

## Functional Requirements

### 1. Instrument Data Management
- **FR-1.1**: Select instrument from available list via API
- **FR-1.2**: Display instrument metadata (symbol, timeframe, data range)
- **FR-1.3**: Load historical candlestick data for selected instrument
- **FR-1.4**: Handle data loading states (loading, error, success)

### 2. Main Chart Visualization
- **FR-2.1**: Display candlestick chart using TradingView Lightweight Charts
- **FR-2.2**: Support pan/zoom interactions
- **FR-2.3**: Show OHLC values on hover/crosshair
- **FR-2.4**: Display volume bars (if available in data)
- **FR-2.5**: Time-axis synchronization with indicator charts

### 3. Technical Indicators
- **FR-3.1**: Fetch available indicators for selected instrument via API
- **FR-3.2**: Add/remove indicators dynamically
- **FR-3.3**: Display overlay indicators (SMA, EMA) on main price chart
- **FR-3.4**: Display oscillator indicators (RSI, MACD) in separate synchronized panels
- **FR-3.5**: Configure indicator parameters (periods, etc.)

### 4. Fuzzy Set Visualization
- **FR-4.1**: Fetch fuzzy set data for each indicator via API
- **FR-4.2**: Display fuzzy membership as colored shading/overlay on indicator charts
- **FR-4.3**: Show fuzzy set activation levels with visual emphasis
- **FR-4.4**: Legend/key for fuzzy set colors and meanings
- **FR-4.5**: Toggle fuzzy set visibility on/off

### 5. Chart Layout & Synchronization
- **FR-5.1**: Master chart (price) with multiple indicator sub-charts
- **FR-5.2**: Time-axis synchronization across all charts
- **FR-5.3**: Crosshair synchronization showing values across all charts
- **FR-5.4**: Resizable chart panels
- **FR-5.5**: Collapsible indicator panels

### 6. User Interface Controls
- **FR-6.1**: Instrument selector dropdown
- **FR-6.2**: Indicator management panel (add/remove/configure)
- **FR-6.3**: Chart controls (zoom, reset, timeframe selection)
- **FR-6.4**: Mode selector (Research/Train/Run) - Research only for MVP
- **FR-6.5**: Settings panel for display preferences

## Non-Functional Requirements

### Performance
- **NFR-1.1**: Initial chart load < 2 seconds for 12k candles
- **NFR-1.2**: Smooth pan/zoom interactions (>30fps)
- **NFR-1.3**: Indicator calculations handled entirely by backend
- **NFR-1.4**: Efficient data transfer (only visible range if possible)

### Usability
- **NFR-2.1**: Intuitive chart interactions following TradingView conventions
- **NFR-2.2**: Clear visual hierarchy and information density
- **NFR-2.3**: Responsive design for different screen sizes
- **NFR-2.4**: Keyboard shortcuts for common actions

### Reliability
- **NFR-3.1**: Graceful error handling for API failures
- **NFR-3.2**: Loading states for all async operations
- **NFR-3.3**: Data validation and sanitization

### Maintainability
- **NFR-4.1**: Modular component architecture
- **NFR-4.2**: Clear separation between chart logic and business logic
- **NFR-4.3**: Consistent coding patterns and documentation

## API Requirements (Backend Dependencies)

### Existing Endpoints to Leverage
- `GET /instruments` - List available instruments
- `GET /instruments/{symbol}/data` - Get OHLC data
- `GET /instruments/{symbol}/indicators` - Get calculated indicators
- `GET /instruments/{symbol}/fuzzy` - Get fuzzy set data

### Required API Enhancements
- Add fuzzy set data to indicator endpoints
- Include metadata (timeframe, data range) in responses
- Support for date range filtering
- Indicator parameter configuration endpoints

## Future Considerations (Out of MVP Scope)

### Train Phase
- Neural network training interface
- Training progress visualization
- Model performance metrics
- Parameter optimization controls

### Run Phase
- Paper trading simulation
- Real account integration
- Position management
- Performance tracking
- Risk management controls

### Advanced Research Features
- Strategy backtesting
- Multi-timeframe analysis
- Drawing tools and annotations
- Data export capabilities
- Custom indicator development

## Technical Constraints

### Frontend Technology Stack
- React with TypeScript
- TradingView Lightweight Charts library
- Modern CSS (Grid/Flexbox)
- Fetch API for backend communication

### Browser Support
- Modern browsers (Chrome 90+, Firefox 88+, Safari 14+)
- No IE support required
- Progressive enhancement approach

### Data Limitations
- Maximum 50k candlesticks per request
- Fuzzy set data synchronized with indicator data
- Real-time updates not required for MVP

## Success Criteria

### MVP Success Metrics
1. Successfully load and display candlestick data for available instruments
2. Add/remove at least 2 indicator types (overlay + oscillator)
3. Visualize fuzzy sets with clear visual distinction
4. Smooth chart interactions with time-axis synchronization
5. Intuitive workflow for exploring different instruments and indicators

### User Acceptance Criteria
- User can load EURUSD 1H data and see candlestick chart
- User can add SMA(20) overlay and see it on price chart
- User can add RSI(14) in separate panel below main chart
- User can see fuzzy set shading on RSI indicating buy/sell zones
- Charts stay synchronized when panning/zooming
- Loading states clearly indicate when data is being fetched