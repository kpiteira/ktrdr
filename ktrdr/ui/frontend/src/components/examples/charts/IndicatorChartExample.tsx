// filepath: /Users/karl/Documents/dev/ktrdr2/ktrdr/ui/frontend/src/components/examples/charts/IndicatorChartExample.tsx
import React, { useState, useEffect, useCallback } from 'react';
import { 
  IndicatorChart, 
  IndicatorConfig, 
  IndicatorMetadata,
  IndicatorData,
  IndicatorType,
  IndicatorDisplay
} from '../../charts';
import { useTheme } from '../../layouts/ThemeProvider';
import { 
  INDICATORS, 
  SimpleMovingAverage, 
  ExponentialMovingAverage,
  BollingerBands,
  RelativeStrengthIndex,
  MACD,
  createDefaultConfig
} from '../../../utils/indicators/registry';
import * as calculations from '../../../utils/indicators/calculations';
import demoData from '../../../data/demo-data';
import './IndicatorChartExample.css';

// Mock OHLCV data
const mockData = demoData;

interface IndicatorOption {
  id: string;
  label: string;
  metadata: IndicatorMetadata;
}

/**
 * IndicatorChartExample component
 * 
 * Example component demonstrating the indicator visualization components
 * with user-configurable indicator selection and parameters.
 */
const IndicatorChartExample: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  const isDarkTheme = theme === 'dark';
  
  // State
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([]);
  const [indicatorConfigs, setIndicatorConfigs] = useState<IndicatorConfig[]>([]);
  const [indicatorData, setIndicatorData] = useState<IndicatorData[]>([]);
  const [availableIndicators, setAvailableIndicators] = useState<IndicatorOption[]>([]);
  
  // Initialize available indicators
  useEffect(() => {
    const options = INDICATORS.map(indicator => ({
      id: indicator.id,
      label: indicator.name,
      metadata: indicator
    }));
    
    setAvailableIndicators(options);
  }, []);
  
  // Initialize with some default indicators
  useEffect(() => {
    // Create default indicator configurations
    const smaConfig = createDefaultConfig(SimpleMovingAverage, 'sma-20');
    const emaConfig = createDefaultConfig(ExponentialMovingAverage, 'ema-50');
    const bbandsConfig = createDefaultConfig(BollingerBands, 'bbands-20');
    const rsiConfig = createDefaultConfig(RelativeStrengthIndex, 'rsi-14');
    const macdConfig = createDefaultConfig(MACD, 'macd-default');
    
    // Custom parameters
    smaConfig.parameters.period = 20;
    emaConfig.parameters.period = 50;
    emaConfig.colors = ['#FFA726'];
    rsiConfig.parameters.period = 14;
    
    setIndicatorConfigs([smaConfig, emaConfig, bbandsConfig, rsiConfig, macdConfig]);
    setSelectedIndicators([smaConfig.id, emaConfig.id, bbandsConfig.id, rsiConfig.id, macdConfig.id]);
  }, []);
  
  // Calculate indicator data when configurations change
  useEffect(() => {
    if (mockData) {
      const newIndicatorData = indicatorConfigs.map(config => {
        const metadata = INDICATORS.find(ind => ind.id === config.indicatorId);
        
        if (!metadata) {
          throw new Error(`Indicator metadata not found for ID: ${config.indicatorId}`);
        }
        
        // Calculate indicator data
        const data = calculations.createIndicatorData(mockData, config.indicatorId, config.parameters);
        
        // Ensure the indicator ID matches the config ID
        return {
          ...data,
          indicatorId: config.id
        };
      });
      
      setIndicatorData(newIndicatorData);
    }
  }, [indicatorConfigs, mockData]);
  
  // Handle adding an indicator
  const handleAddIndicator = (indicatorId: string) => {
    const metadata = INDICATORS.find(ind => ind.id === indicatorId);
    
    if (!metadata) {
      console.error(`Indicator metadata not found for ID: ${indicatorId}`);
      return;
    }
    
    // Generate a unique ID for the config
    const uniqueId = `${indicatorId}-${Date.now()}`;
    
    // Create default configuration
    const newConfig = createDefaultConfig(metadata, uniqueId);
    
    // Add to configs and selected indicators
    setIndicatorConfigs(prevConfigs => [...prevConfigs, newConfig]);
    setSelectedIndicators(prevSelected => [...prevSelected, uniqueId]);
  };
  
  // Handle removing an indicator
  const handleRemoveIndicator = (configId: string) => {
    setIndicatorConfigs(prevConfigs => prevConfigs.filter(config => config.id !== configId));
    setSelectedIndicators(prevSelected => prevSelected.filter(id => id !== configId));
  };
  
  // Handle indicator configuration changes
  const handleConfigChange = (updatedConfigs: IndicatorConfig[]) => {
    setIndicatorConfigs(updatedConfigs);
  };
  
  return (
    <div className={`indicator-chart-example ${isDarkTheme ? 'dark-theme' : 'light-theme'}`}>
      <div className="example-header">
        <h2>Technical Indicators Visualization</h2>
        
        <div className="example-controls">
          <button 
            className="theme-toggle"
            onClick={toggleTheme}
          >
            Toggle Theme ({theme})
          </button>
          
          <div className="add-indicator-control">
            <label htmlFor="indicator-select">Add Indicator:</label>
            <select 
              id="indicator-select"
              onChange={(e) => {
                if (e.target.value) {
                  handleAddIndicator(e.target.value);
                  e.target.value = '';
                }
              }}
              value=""
            >
              <option value="">Select an indicator...</option>
              {availableIndicators.map(indicator => (
                <option key={indicator.id} value={indicator.id}>
                  {indicator.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
      
      <div className="indicator-chart-wrapper">
        <IndicatorChart
          data={mockData}
          indicators={indicatorData}
          indicatorConfigs={indicatorConfigs}
          indicatorMetadata={INDICATORS}
          height={800}
          title="AAPL Daily Chart with Indicators"
          showVolume={true}
          fitContent={true}
          autoResize={true}
          showControls={true}
          showTooltips={true}
          onIndicatorConfigChange={handleConfigChange}
        />
      </div>
      
      <div className="example-info">
        <div className="features-list">
          <h3>Features Implemented:</h3>
          <ul>
            <li>Support for multiple indicator types (line, multi-line, histogram)</li>
            <li>Overlay indicators on price chart (moving averages, Bollinger Bands)</li>
            <li>Separate panel indicators (RSI, MACD)</li>
            <li>Interactive controls for indicator parameters and styling</li>
            <li>Tooltips showing indicator values at crosshair position</li>
            <li>Synchronized panels that move with the main chart</li>
            <li>Theme synchronization with the application theme</li>
          </ul>
        </div>
        
        <div className="implementation-details">
          <h3>Implementation Details:</h3>
          <p>
            This example demonstrates the indicator visualization components implemented in Task 8.4. 
            The components are designed to be reusable and composable, with a clear separation between 
            data and visualization. The implementation leverages TradingView's Lightweight Charts library
            for consistent rendering and performance.
          </p>
          <p>
            The indicator data calculation is done in utility functions that could be replaced with API calls
            in a production environment. The visualization components are agnostic to the data source.
          </p>
        </div>
      </div>
    </div>
  );
};

export default IndicatorChartExample;