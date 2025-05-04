import React, { useState } from 'react';
import { Card, Select, Button } from '@/components/common';
import DataTransformationExample from '@/components/examples/charts/DataTransformationExample';

// Example configuration options
const dataPoints = [
  { value: '50', label: '50 Points' },
  { value: '100', label: '100 Points' },
  { value: '250', label: '250 Points' },
  { value: '500', label: '500 Points' },
];

const timeframes = [
  { value: '1m', label: '1 Minute' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '1d', label: '1 Day' },
];

const symbols = [
  { value: 'EXAMPLE', label: 'EXAMPLE' },
  { value: 'AAPL', label: 'Apple Inc.' },
  { value: 'MSFT', label: 'Microsoft' },
  { value: 'GOOG', label: 'Google' },
  { value: 'AMZN', label: 'Amazon' },
  { value: 'TSLA', label: 'Tesla' },
];

/**
 * Page for demonstrating data transformation utilities
 */
const DataTransformationPage: React.FC = () => {
  const [points, setPoints] = useState('100');
  const [timeframe, setTimeframe] = useState('1d');
  const [symbol, setSymbol] = useState('EXAMPLE');
  const [errors, setErrors] = useState(false);
  
  return (
    <div className="data-transformation-page">
      <Card title="Chart Data Transformation">
        <p>
          This page demonstrates the chart data transformation utilities from Task 8.2.
          You can configure the sample data and see how different transformation methods
          affect the chart display.
        </p>
        
        <div className="config-controls" style={{ 
          display: 'flex', 
          gap: '1rem', 
          marginBottom: '1rem',
          flexWrap: 'wrap'
        }}>
          <div style={{ width: '150px' }}>
            <label>Data Points:</label>
            <Select
              value={points}
              options={dataPoints}
              onChange={setPoints}
            />
          </div>
          
          <div style={{ width: '150px' }}>
            <label>Timeframe:</label>
            <Select
              value={timeframe}
              options={timeframes}
              onChange={setTimeframe}
            />
          </div>
          
          <div style={{ width: '150px' }}>
            <label>Symbol:</label>
            <Select
              value={symbol}
              options={symbols}
              onChange={setSymbol}
            />
          </div>
          
          <div style={{ 
            display: 'flex', 
            alignItems: 'flex-end', 
            paddingBottom: '0.25rem' 
          }}>
            <Button
              onClick={() => setErrors(!errors)}
              variant={errors ? 'danger' : 'outline'}
            >
              {errors ? 'Using Data with Errors' : 'Use Clean Data'}
            </Button>
          </div>
        </div>
      </Card>
      
      <div style={{ marginTop: '1rem' }}>
        <DataTransformationExample
          initialPoints={parseInt(points, 10)}
          timeframe={timeframe}
          symbol={symbol}
          introduceErrors={errors}
          width={800}
          height={500}
        />
      </div>
      
      <Card title="Available Features" style={{ marginTop: '1rem' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem' }}>
          <div>
            <h4>Data Transformation</h4>
            <ul>
              <li>OHLCV to Candlestick format conversion</li>
              <li>OHLCV to Volume histogram format</li>
              <li>Time scale formatting for different timeframes</li>
              <li>Data preprocessing for missing values</li>
            </ul>
          </div>
          
          <div>
            <h4>Data Validation</h4>
            <ul>
              <li>Validation for data integrity</li>
              <li>Detailed error reporting</li>
              <li>Automatic data repair</li>
              <li>Validation for different chart data types</li>
            </ul>
          </div>
          
          <div>
            <h4>Streaming Updates</h4>
            <ul>
              <li>Efficient update methods</li>
              <li>Different update modes</li>
              <li>Optimized for performance</li>
              <li>Debug utilities with performance metrics</li>
            </ul>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default DataTransformationPage;