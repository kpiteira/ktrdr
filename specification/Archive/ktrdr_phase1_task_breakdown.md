# KTRDR Detailed Task Breakdown

This document breaks down each task from the original task list into granular, AI-codable subtasks with specific implementation details.

## Project Setup and Configuration

# KTRDR UV Project Setup Tasks

## Updated Project Setup Tasks for UV Integration

### Task 1.1.1: Scaffold Python project structure with UV
- [ ] **Task 1.1.1.1**: Create project root directory with standard Python project structure
- [ ] **Task 1.1.1.2**: Set up pyproject.toml for package configuration with UV compatibility
- [ ] **Task 1.1.1.3**: Create module directory structure (data, indicators, fuzzy, neural, visualization, ui)
- [ ] **Task 1.1.1.4**: Set up __init__.py files with proper imports for each module
- [ ] **Task 1.1.1.5**: Create utils and config directories for supporting functionality
- [ ] **Task 1.1.1.6**: Set up logging configuration with different verbosity levels
- [ ] **Task 1.1.1.7**: Create .uv directory configuration for UV-based dependency management
- [ ] **Task 1.1.1.8**: Set up .gitignore for Python project with data directory and .uv exclusions
- [ ] **Task 1.1.1.9**: Set up UV-based virtual environment creation script

### Task 1.1.2: Define YAML configuration structure
- [ ] **Task 1.1.2.1**: Define general settings section (data_dir, log_level, default_assets)
- [ ] **Task 1.1.2.2**: Create schema for data sources configuration (IB, local, parameters)
- [ ] **Task 1.1.2.3**: Define schema for indicators section (name, parameters, dependencies)
- [ ] **Task 1.1.2.4**: Design fuzzy logic configuration section (sets, membership functions)
- [ ] **Task 1.1.2.5**: Create neural network configuration structure (layers, nodes, activation)
- [ ] **Task 1.1.2.6**: Define visualization settings schema (colors, default_indicators)
- [ ] **Task 1.1.2.7**: Create sample configuration YAML file with documented options
- [ ] **Task 1.1.2.8**: Add schema documentation comments for each configuration section

### Task 1.1.3: Implement configuration loader
- [ ] **Task 1.1.3.1**: Create ConfigLoader class to handle YAML file loading
- [ ] **Task 1.1.3.2**: Implement Pydantic models for configuration validation
- [ ] **Task 1.1.3.3**: Add environment variable overrides for key configuration options
- [ ] **Task 1.1.3.4**: Implement default configuration values for optional settings
- [ ] **Task 1.1.3.5**: Add configuration inheritance/override capabilities
- [ ] **Task 1.1.3.6**: Create configuration validation function with helpful error messages
- [ ] **Task 1.1.3.7**: Implement configuration reload functionality for live updates
- [ ] **Task 1.1.3.8**: Add unit tests for configuration loading and validation

## Historical Data Management

### Task 1.2.1: Implement IBDataLoader
- [ ] **Task 1.2.1.1**: Create IBDataLoader class with ib_insync dependency
- [ ] **Task 1.2.1.2**: Implement connection management (connect, disconnect, reconnect)
- [ ] **Task 1.2.1.3**: Add contract creation helper for different asset types (stock, futures, forex)
- [ ] **Task 1.2.1.4**: Implement historical data request method with proper parameters
- [ ] **Task 1.2.1.5**: Add error handling for common IB API issues (connection loss, timeouts)
- [ ] **Task 1.2.1.6**: Implement data transformation from IB format to pandas DataFrame
- [ ] **Task 1.2.1.7**: Add date range splitting for large historical requests
- [ ] **Task 1.2.1.8**: Implement logging of all API interactions for debugging

### Task 1.2.2: Implement LocalDataLoader
- [ ] **Task 1.2.2.1**: Create LocalDataLoader class with configurable data directory
- [ ] **Task 1.2.2.2**: Implement standard CSV format and naming convention
- [ ] **Task 1.2.2.3**: Add data loading method with symbol, timeframe, date range parameters
- [ ] **Task 1.2.2.4**: Implement data saving method to write DataFrames to CSV
- [ ] **Task 1.2.2.5**: Add data format validation and error handling for corrupt files
- [ ] **Task 1.2.2.6**: Implement date filtering for partial data loads
- [ ] **Task 1.2.2.7**: Add data directory management (create if not exists, list available data)
- [ ] **Task 1.2.2.8**: Implement data integrity checks (missing values, duplicates)

### Task 1.2.3: Develop DataManager to orchestrate data loading
- [ ] **Task 1.2.3.1**: Create `DataManager` class with constructor accepting config parameters (data_dir, default_assets)
- [ ] **Task 1.2.3.2**: Implement `load()` method that accepts symbol, asset_type, interval, start_date, end_date parameters
- [ ] **Task 1.2.3.3**: Add logic to check for local data first using `LocalDataLoader`
- [ ] **Task 1.2.3.4**: Implement gap detection algorithm to identify missing date ranges in local data
- [ ] **Task 1.2.3.5**: Add fetching logic to fill gaps using `IBDataLoader` when local data is incomplete
- [ ] **Task 1.2.3.6**: Implement data merging logic to combine existing and newly fetched data
- [ ] **Task 1.2.3.7**: Add function to save merged data back to CSV storage
- [ ] **Task 1.2.3.8**: Add comprehensive logging of all actions (cache hits, fetches, etc.)

### Task 1.2.4: Implement rate-limit awareness
- [ ] **Task 1.2.4.1**: Create a `RateLimiter` class to track API request timing
- [ ] **Task 1.2.4.2**: Implement configurable request pacing (pause between requests)
- [ ] **Task 1.2.4.3**: Add adaptive backoff logic when approaching IB rate limits
- [ ] **Task 1.2.4.4**: Integrate rate limiter with `IBDataLoader` request methods
- [ ] **Task 1.2.4.5**: Add logging for rate limiting events and delays

### Task 1.2.5: Validate interruptible and resumable fetching logic
- [ ] **Task 1.2.5.1**: Implement batch processing for large date ranges (e.g., fetch 5 days at a time)
- [ ] **Task 1.2.5.2**: Create state tracking for batch progress (last successful date fetched)
- [ ] **Task 1.2.5.3**: Add checkpoint saving logic after each successful batch fetch
- [ ] **Task 1.2.5.4**: Implement resumption logic to continue from last checkpoint
- [ ] **Task 1.2.5.5**: Add clean interruption handling (e.g., keyboard interrupt, connection loss)

## Indicator Computation Engine

### Task 1.3.1: Define indicator interface and modular structure
- [ ] **Task 1.3.1.1**: Create `BaseIndicator` abstract class with required interface methods
- [ ] **Task 1.3.1.2**: Define standard `compute()` method signature (input: DataFrame, output: Series/DataFrame)
- [ ] **Task 1.3.1.3**: Implement parameter validation logic in base class
- [ ] **Task 1.3.1.4**: Define naming convention utility for indicator outputs
- [ ] **Task 1.3.1.5**: Create `IndicatorFactory` class to instantiate indicators from config

### Task 1.3.2: Implement RSI indicator
- [ ] **Task 1.3.2.1**: Create `RSIIndicator` class inheriting from `BaseIndicator`
- [ ] **Task 1.3.2.2**: Implement constructor accepting `period` and `source` parameters
- [ ] **Task 1.3.2.3**: Implement `compute()` method using pandas-ta or ta-lib
- [ ] **Task 1.3.2.4**: Add validation for boundary cases (insufficient data, invalid inputs)
- [ ] **Task 1.3.2.5**: Add unit tests comparing output to known reference values

### Task 1.3.3: Develop IndicatorEngine
- [ ] **Task 1.3.3.1**: Create `IndicatorEngine` class that accepts list of indicator configs
- [ ] **Task 1.3.3.2**: Implement `__init__` method to instantiate configured indicators using IndicatorFactory
- [ ] **Task 1.3.3.3**: Implement `apply()` method to process OHLCV DataFrame through all indicators
- [ ] **Task 1.3.3.4**: Add handling for indicator dependencies (if one indicator needs another's output)
- [ ] **Task 1.3.3.5**: Implement caching of indicator results to avoid recalculation
- [ ] **Task 1.3.3.6**: Add verbose logging of indicator computation process

### Task 1.3.4: Validate indicator outputs
- [ ] **Task 1.3.4.1**: Create reference dataset with pre-calculated indicator values
- [ ] **Task 1.3.4.2**: Implement validation function to compare engine outputs with reference data
- [ ] **Task 1.3.4.3**: Add tolerance parameter to handle floating-point differences
- [ ] **Task 1.3.4.4**: Create detailed validation report showing discrepancies
- [ ] **Task 1.3.4.5**: Implement as both unit test and standalone validation script

## Fuzzy Logic Engine

### Task 1.4.1: Define YAML-based fuzzy set configuration
- [ ] **Task 1.4.1.1**: Create Pydantic model for fuzzy set configuration validation
- [ ] **Task 1.4.1.2**: Define schema for triangular membership function parameters
- [ ] **Task 1.4.1.3**: Create sample fuzzy set configurations for common indicators (RSI, MACD)
- [ ] **Task 1.4.1.4**: Implement parsing logic to load fuzzy configurations from YAML
- [ ] **Task 1.4.1.5**: Add validation rules for parameter constraints (e.g., ordering of triangular points)

### Task 1.4.2: Implement triangular membership function
- [ ] **Task 1.4.2.1**: Create `MembershipFunction` abstract base class
- [ ] **Task 1.4.2.2**: Implement `TriangularMF` class with parameters a, b, c (start, peak, end)
- [ ] **Task 1.4.2.3**: Implement `evaluate()` method to calculate membership degree for input value
- [ ] **Task 1.4.2.4**: Add boundary condition handling (values outside triangle)
- [ ] **Task 1.4.2.5**: Create unit tests with various test cases (below, within, above triangle)
- [ ] **Task 1.4.2.6**: Add vectorized evaluation for pandas Series input

### Task 1.4.3: Develop FuzzyEngine
- [ ] **Task 1.4.3.1**: Create `FuzzyEngine` class that accepts fuzzy set configurations
- [ ] **Task 1.4.3.2**: Implement factory method to create membership functions from config
- [ ] **Task 1.4.3.3**: Implement `fuzzify()` method to process single indicator value
- [ ] **Task 1.4.3.4**: Implement `apply()` method to process entire DataFrame of indicators
- [ ] **Task 1.4.3.5**: Implement column naming convention for fuzzy outputs (e.g., `rsi_low`, `rsi_high`)
- [ ] **Task 1.4.3.6**: Add method to return flattened fuzzy vector for neural input

### Task 1.4.4: Validate fuzzy logic outputs
- [ ] **Task 1.4.4.1**: Create test cases with known indicator values and expected fuzzy memberships
- [ ] **Task 1.4.4.2**: Implement numerical validation function to compare actual vs. expected outputs
- [ ] **Task 1.4.4.3**: Create utility to generate matplotlib visualization of membership functions
- [ ] **Task 1.4.4.4**: Add function to plot indicator values alongside membership degrees
- [ ] **Task 1.4.4.5**: Create standalone validation script and integrate with test suite

## Visualization Subsystem

### Task 1.5.1: Implement basic candlestick chart
- [ ] **Task 1.5.1.1**: Create `Visualizer` class with modular plotting methods
- [ ] **Task 1.5.1.2**: Implement `plot_price()` method using Plotly's candlestick function
- [ ] **Task 1.5.1.3**: Add date range selection and zooming capabilities
- [ ] **Task 1.5.1.4**: Implement customizable chart styling options (colors, sizes)
- [ ] **Task 1.5.1.5**: Add hover information with OHLCV details

### Task 1.5.2: Overlay computed indicators
- [ ] **Task 1.5.2.1**: Implement `plot_indicator_overlay()` method for price-aligned indicators (e.g., EMA)
- [ ] **Task 1.5.2.2**: Implement `plot_indicator_subplot()` for separate indicators (e.g., RSI)
- [ ] **Task 1.5.2.3**: Create dynamic subplot layout based on indicator types
- [ ] **Task 1.5.2.4**: Add toggle controls for indicator visibility
- [ ] **Task 1.5.2.5**: Implement synchronized zooming/panning across all subplots

### Task 1.5.3: Visualize fuzzy membership bands
- [ ] **Task 1.5.3.1**: Implement `plot_fuzzy_bands()` method to show membership thresholds
- [ ] **Task 1.5.3.2**: Add colored shading for fuzzy regions on indicator plots
- [ ] **Task 1.5.3.3**: Implement hover text showing membership degree at each point
- [ ] **Task 1.5.3.4**: Add options to toggle fuzzy band visibility
- [ ] **Task 1.5.3.5**: Create heat map visualization for fuzzy membership intensity

### Task 1.5.4: Integrate visualization subsystem into Streamlit UI
- [ ] **Task 1.5.4.1**: Create base Streamlit app structure with sidebar controls
- [ ] **Task 1.5.4.2**: Add data loading options (symbol, timeframe, date range)
- [ ] **Task 1.5.4.3**: Implement indicator selection controls
- [ ] **Task 1.5.4.4**: Add fuzzy set visualization toggles
- [ ] **Task 1.5.4.5**: Implement figure caching for performance
- [ ] **Task 1.5.4.6**: Add UI feedback for data loading and processing steps

## UI Interface

### Task 1.6.1: Set up Streamlit-based UI scaffold
- [ ] **Task 1.6.1.1**: Create main.py Streamlit entry point with page structure
- [ ] **Task 1.6.1.2**: Implement sidebar with configuration controls
- [ ] **Task 1.6.1.3**: Set up tab-based navigation for different view modes
- [ ] **Task 1.6.1.4**: Add configuration YAML file loading capability
- [ ] **Task 1.6.1.5**: Implement session state management for persistent settings

### Task 1.6.2: Implement data loading controls
- [ ] **Task 1.6.2.1**: Create symbol selection dropdown with configurable options
- [ ] **Task 1.6.2.2**: Implement date range picker with presets (1m, 3m, 6m, 1y)
- [ ] **Task 1.6.2.3**: Add local/remote data source toggle
- [ ] **Task 1.6.2.4**: Implement data loading progress indicator
- [ ] **Task 1.6.2.5**: Add error handling and user feedback for data loading issues
- [ ] **Task 1.6.2.6**: Create data summary display (rows, date range, missing values)

### Tasks 1.6.3-1.6.4: Add indicator and fuzzy logic visualization controls
- [ ] **Task 1.6.3-4.1**: Create indicator selection multiselect control
- [ ] **Task 1.6.3-4.2**: Implement indicator parameter controls (e.g., RSI period)
- [ ] **Task 1.6.3-4.3**: Add fuzzy set visualization toggle for each indicator
- [ ] **Task 1.6.3-4.4**: Create interactive plot container with resizing capability
- [ ] **Task 1.6.3-4.5**: Implement plot download button for saving visualizations
- [ ] **Task 1.6.3-4.6**: Add numerical display of indicator and fuzzy values at cursor position

## Testing and CLI Entrypoints

### Task 1.7.1: Set up pytest-based unit testing framework
- [ ] **Task 1.7.1.1**: Set up pytest directory structure and configuration
- [ ] **Task 1.7.1.2**: Create fixtures for test data (OHLCV, indicators)
- [ ] **Task 1.7.1.3**: Implement mock classes for external dependencies (IB API)
- [ ] **Task 1.7.1.4**: Set up test coverage reporting
- [ ] **Task 1.7.1.5**: Create basic smoke tests for each module

### Task 1.7.2: Write unit tests for core engines
- [ ] **Task 1.7.2.1**: Create DataManager test suite (gap detection, merging, etc.)
- [ ] **Task 1.7.2.2**: Implement IndicatorEngine tests for each indicator type
- [ ] **Task 1.7.2.3**: Create FuzzyEngine tests for membership function evaluation
- [ ] **Task 1.7.2.4**: Add integration tests for the complete data-to-fuzzy pipeline
- [ ] **Task 1.7.2.5**: Implement edge case tests (empty data, missing values, etc.)

### Task 1.7.3: Implement CLI entrypoints
- [ ] **Task 1.7.3.1**: Set up Typer CLI framework with command groups
- [ ] **Task 1.7.3.2**: Implement `fetch` command for data retrieval
- [ ] **Task 1.7.3.3**: Add `plot-indicator` command for indicator visualization
- [ ] **Task 1.7.3.4**: Create `plot-fuzzy` command for fuzzy set visualization
- [ ] **Task 1.7.3.5**: Implement `visualize` command for full visualization
- [ ] **Task 1.7.3.6**: Add configuration loading and validation to CLI

### Task 1.7.4: Validate CLI commands
- [ ] **Task 1.7.4.1**: Create test script to execute each CLI command with sample inputs
- [ ] **Task 1.7.4.2**: Implement validation of command outputs (files created, exit codes)
- [ ] **Task 1.7.4.3**: Test parameter validation and error handling
- [ ] **Task 1.7.4.4**: Create documentation based on CLI test cases
- [ ] **Task.1.7.4.5**: Add smoke tests for all UI-related commands

## Neural Engine and Decision Interpreter

### Neural Config (Task 1.8.1)
- [ ] **Task 1.8.1.1**: Define Pydantic model for neural network configuration
- [ ] **Task 1.8.1.2**: Implement validation for model parameters (layers, sizes)
- [ ] **Task 1.8.1.3**: Create sample network configurations (small, medium, large)
- [ ] **Task 1.8.1.4**: Add support for activation function configuration
- [ ] **Task 1.8.1.5**: Implement loader to parse neural config from YAML

### Neural Training (Task 1.8.2)
- [ ] **Task 1.8.2.1**: Create `NeuralTrainer` class with configurable hyperparameters
- [ ] **Task 1.8.2.2**: Implement data preparation logic for fuzzy inputs
- [ ] **Task 1.8.2.3**: Create PyTorch model class with dynamic architecture
- [ ] **Task 1.8.2.4**: Implement training loop with early stopping
- [ ] **Task 1.8.2.5**: Add tensorboard logging for training metrics
- [ ] **Task 1.8.2.6**: Implement model checkpoint saving and resumption
- [ ] **Task 1.8.2.7**: Add cross-validation option for hyperparameter tuning

### Neural Inference (Task 1.8.3)
- [ ] **Task 1.8.3.1**: Create `NeuralInference` class to load trained models
- [ ] **Task 1.8.3.2**: Implement fuzzy input preprocessing for inference
- [ ] **Task 1.8.3.3**: Add batch prediction capability for historical data
- [ ] **Task 1.8.3.4**: Create real-time prediction logic for streaming data
- [ ] **Task 1.8.3.5**: Implement confidence calculation for predictions
- [ ] **Task 1.8.3.6**: Add model version tracking and validation

### Decision Interpreter (Task 1.8.4)
- [ ] **Task 1.8.4.1**: Create `DecisionInterpreter` class with configurable thresholds
- [ ] **Task 1.8.4.2**: Implement logic to convert neural outputs to action signals
- [ ] **Task 1.8.4.3**: Add position-aware decision logic (entry vs. exit rules)
- [ ] **Task 1.8.4.4**: Implement confidence filtering for weak signals
- [ ] **Task 1.8.4.5**: Create visualization of decision boundaries
- [ ] **Task 1.8.4.6**: Add logging of decision process for transparency

## Trade Lifecycle Management

### Trade Manager (Task 1.9.1)
- [ ] **Task 1.9.1.1**: Create `TradeManager` class with position state tracking
- [ ] **Task 1.9.1.2**: Implement `update()` method to process decision signals
- [ ] **Task 1.9.1.3**: Add position sizing logic based on configurable parameters
- [ ] **Task 1.9.1.4**: Implement trade execution simulation with slippage
- [ ] **Task 1.9.1.5**: Add P&L tracking for open and closed positions
- [ ] **Task 1.9.1.6**: Implement trade filtering logic (e.g., minimum holding period)

### Trade Logging (Task 1.9.2)
- [ ] **Task 1.9.2.1**: Define trade log data structure (entry/exit times, prices, etc.)
- [ ] **Task 1.9.2.2**: Implement CSV-based trade logging with timestamps
- [ ] **Task 1.9.2.3**: Add trade summary statistics calculation
- [ ] **Task 1.9.2.4**: Create trade performance metrics (win rate, avg profit)
- [ ] **Task 1.9.2.5**: Implement trade log export to various formats
- [ ] **Task 1.9.2.6**: Add trade journal capability with notes field

### Trade Visualization (Task 1.9.3)
- [ ] **Task 1.9.3.1**: Extend `Visualizer` to display trade entry/exit markers
- [ ] **Task 1.9.3.2**: Add P&L visualization as area chart
- [ ] **Task 1.9.3.3**: Implement trade annotation with key metrics
- [ ] **Task 1.9.3.4**: Create equity curve visualization
- [ ] **Task 1.9.3.5**: Add drawdown visualization capability
- [ ] **Task 1.9.3.6**: Implement comparative benchmark visualization