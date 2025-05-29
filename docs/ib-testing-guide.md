# IB Integration Testing Guide

This guide explains how to test the Interactive Brokers (IB) integration to verify it works with real IB connections.

## Prerequisites

### 1. IB Gateway/TWS Setup
- Install and start IB Gateway or Trader Workstation (TWS)
- Log in with your IB credentials
- Configure API settings:
  1. Go to Configure → API → Settings
  2. Check "Enable ActiveX and Socket Clients"
  3. Set API port (7497 for paper trading, 7496 for live)
  4. Optional: Add trusted IP addresses
  5. Click "OK" and restart if prompted

### 2. Environment Configuration
Copy the environment template and configure IB settings:

```bash
# Copy template
cp .env.template .env

# Edit .env file with your IB settings
IB_HOST=127.0.0.1
IB_PORT=7497  # 7497 for paper, 7496 for live
IB_CLIENT_ID=1
IB_TIMEOUT=10
IB_READONLY=false
```

## Testing Methods

### Method 1: CLI Test Command (Recommended)

The easiest way to test IB integration:

```bash
# Quick test (just configuration and connection)
python ktrdr_cli.py test-ib --quick

# Full test with verbose output
python ktrdr_cli.py test-ib --verbose

# Test with specific symbol
python ktrdr_cli.py test-ib --symbol MSFT --verbose
```

### Method 2: Standalone Test Script

Run the comprehensive test script:

```bash
python scripts/test_ib_integration.py
```

### Method 3: Manual Testing via CLI

Test data loading through the CLI (this uses DataManager with IB integration):

```bash
# Show data - this will try IB first, then fallback to local CSV
python ktrdr_cli.py show-data AAPL --timeframe 1h --rows 5

# Plot data with IB fetching
python ktrdr_cli.py plot AAPL --timeframe 1h --indicator SMA --period 20
```

## Test Coverage

The tests verify:

1. **Configuration Loading**
   - Environment variables parsed correctly
   - IB settings validated
   - Default values applied

2. **IB Connection**
   - Connection establishment
   - Authentication
   - Health checks

3. **Data Fetching**
   - Historical data requests
   - Multiple timeframes (1h, 1d)
   - Different asset types (stocks, forex)
   - Rate limiting functionality
   - Data format validation

4. **DataManager Integration**
   - IB-first strategy
   - Fallback to local CSV
   - Data merging and gap filling
   - Automatic CSV caching

5. **Error Handling**
   - Connection failures
   - Symbol not found
   - Market closed scenarios
   - Rate limit exceeded

## Expected Results

### Successful Test Output

```
🚀 Testing IB Integration
Time: 2024-01-15 10:30:45

📋 Testing Configuration...
✅ Configuration loaded
   Host: 127.0.0.1:7497, Client ID: 1

🔌 Testing Connection...
✅ IB connection
   Connected successfully

📈 Testing Data Fetcher...
✅ Data fetching
   Fetched 48 bars for AAPL
   Columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']
   Date range: 2024-01-13 09:30:00+00:00 to 2024-01-15 16:00:00+00:00

🔄 Testing DataManager...
✅ DataManager IB integration
   IB components initialized

⚖️ Testing Fallback Logic...
✅ Fallback logic
   Loaded 48 bars

🔌 Disconnected from IB

📊 Test Results: 5/5 passed
🎉 All tests passed! IB integration is working.
```

## Troubleshooting

### Common Issues

#### 1. Configuration Errors
```
❌ Configuration loaded
   Error: IB config error

💡 Troubleshooting:
   1. Copy .env.template to .env
   2. Configure IB_HOST, IB_PORT, IB_CLIENT_ID
```

**Solution**: Ensure `.env` file exists with correct IB settings.

#### 2. Connection Failures
```
❌ IB connection
   Error: Connection refused

💡 Troubleshooting:
   1. Start IB Gateway/TWS and login
   2. Enable API in settings
   3. Check port (7497 paper, 7496 live)
```

**Solutions**:
- Verify IB Gateway/TWS is running and logged in
- Check API settings are enabled
- Verify port numbers match
- Ensure client ID is not already in use
- Check firewall settings

#### 3. Data Fetching Issues
```
❌ Data fetching
   Error: No security definition found
```

**Solutions**:
- Use valid symbols (AAPL, MSFT, EUR.USD)
- Check market hours for data availability
- Verify IB data permissions for the symbol

#### 4. No Data During Market Hours
```
❌ Data fetching
   Error: No data returned
```

**Solutions**:
- Some symbols may not have recent data during off-hours
- Try major symbols like AAPL, MSFT, or EUR.USD
- Check if IB data subscription covers the symbol

### Debug Mode

For detailed debugging, run with Python logging:

```bash
# Set debug logging
export KTRDR_LOGGING_LEVEL=DEBUG

# Run test with debug output
python ktrdr_cli.py test-ib --verbose
```

## Integration with Existing Workflows

Once IB integration is working:

1. **Automatic Data Updates**: DataManager will automatically try IB first for any data requests
2. **Fallback Safety**: If IB fails, it falls back to local CSV files
3. **Caching**: IB data is automatically saved to CSV for future use
4. **CLI Commands**: All existing commands (`show-data`, `plot`, etc.) now support IB data

## Next Steps

After successful testing:

1. **Production Setup**: Switch to live port (7496) for real data
2. **Data Permissions**: Ensure IB subscription covers needed symbols
3. **Monitoring**: Consider implementing health checks for production use
4. **Rate Limits**: Monitor IB API usage to stay within limits

## Support

If tests continue to fail:

1. Check IB API logs in TWS/Gateway
2. Verify network connectivity
3. Review IB account permissions
4. Contact IB support for API access issues