import React, { useState, useEffect } from 'react';
import { Button, Select } from '../../common';
import CandlestickChart from '../../charts/core/CandlestickChart';
import IndicatorPanel from '../../charts/indicators/IndicatorPanel';
import { 
  OHLCVData, 
  IndicatorData, 
  IndicatorConfig,
  IndicatorType
} from '../../../types/data';
// Import calculations from shared utility
import {
  calculateSMA,
  calculateRSI,
  calculateBollingerBands
} from '../../../utils/indicators/calculations';
import { validateIndicatorData } from '../../charts/transformers/indicatorAdapters';
import './ChartExampleWithData.css';

/**
 * ChartExampleWithData component
 * 
 * Demonstrates the CandlestickChart component with sample data and indicators
 */
const ChartExampleWithData: React.FC = () => {
  const [data, setData] = useState<OHLCVData | null>(null);
  const [timeframe, setTimeframe] = useState<string>('1D');
  const [numPoints, setNumPoints] = useState<number>(100);
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(['sma']);
  const [chartInstance, setChartInstance] = useState<any>(null);

  // Available indicators for dropdown
  const availableIndicators = [
    { value: 'sma', label: 'Simple Moving Average' },
    { value: 'rsi', label: 'Relative Strength Index' },
    { value: 'bbands', label: 'Bollinger Bands' }
  ];

  // Generate sample data on mount and when parameters change
  useEffect(() => {
    setData(generateSampleData(numPoints, timeframe));
  }, [numPoints, timeframe]);

  // Function to generate sample OHLCV data
  const generateSampleData = (days: number, timeframe: string): OHLCVData => {
    const dates: string[] = [];
    const ohlcv: number[][] = [];
    
    let price = 100;
    const today = new Date();
    
    // Adjust the time increment based on timeframe
    const timeIncrement = timeframe === '1h' ? 60 * 60 * 1000 : 
                         timeframe === '4h' ? 4 * 60 * 60 * 1000 :
                         24 * 60 * 60 * 1000; // Default to daily
    
    for (let i = 0; i < days; i++) {
      // Calculate date
      const date = new Date(today.getTime() - (days - i) * timeIncrement);
      dates.push(date.toISOString());
      
      // Generate realistic OHLCV data with some randomness
      const change = (Math.random() - 0.5) * 2;
      const volatility = Math.random() * 2;
      
      price = price * (1 + change / 100);
      
      const open = price;
      const close = price * (1 + (Math.random() - 0.5) / 50);
      const high = Math.max(open, close) * (1 + volatility / 100);
      const low = Math.min(open, close) * (1 - volatility / 100);
      const volume = Math.floor(Math.random() * 1000) + 100;
      
      ohlcv.push([open, high, low, close, volume]);
    }
    
    return {
      dates,
      ohlcv,
      metadata: {
        symbol: 'SAMPLE',
        timeframe,
        start: dates[0],
        end: dates[dates.length - 1],
        points: days,
      },
    };
  };

  // Calculate indicator data
  const calculateIndicatorData = (indicatorId: string, data: OHLCVData): IndicatorData => {
    if (!data) return {
      indicatorId,
      values: [[]],
      dates: []
    };

    const { dates, ohlcv } = data;
    const prices = ohlcv.map(candle => candle[3]); // Close prices
    const timestamps = dates;
    
    let values: any[] = [];
    let metadata: any = {};
    
    switch (indicatorId) {
      case 'sma': {
        // Use imported SMA calculation
        const period = 20;
        const smaValues = calculateSMA(prices, period);
        
        values = [smaValues];
        metadata = {
          name: 'Simple Moving Average',
          displayFormat: '.2f'
        };
        break;
      }
      
      case 'rsi': {
        // Use imported RSI calculation
        const period = 14;
        const rsiValues = calculateRSI(prices, period);
        
        values = [rsiValues];
        metadata = {
          name: 'Relative Strength Index',
          displayFormat: '.2f',
          valueRange: {
            min: 0,
            max: 100,
            markers: [
              { value: 70, label: 'Overbought' },
              { value: 30, label: 'Oversold' }
            ]
          }
        };
        break;
      }
      
      case 'bbands': {
        // Use imported Bollinger Bands calculation
        const period = 20;
        const stdDev = 2;
        const bbands = calculateBollingerBands(prices, period, stdDev);
        
        // Debug Bollinger Bands calculation
        console.log('Bollinger Bands calculation result:', bbands);
        
        // bbands contains upper, middle, lower bands
        values = [bbands.upper, bbands.middle, bbands.lower];
        metadata = {
          name: 'Bollinger Bands',
          displayFormat: '.2f',
          names: ['Upper Band', 'Middle Band', 'Lower Band']
        };
        break;
      }
      
      default:
        values = [];
        metadata = { name: 'Unknown Indicator' };
    }
    
    const result = {
      indicatorId,
      values,
      dates: timestamps,
      metadata
    };
    
    // Validate and debug
    const validation = validateIndicatorData(result);
    console.log(`Indicator ${indicatorId} data valid:`, validation.valid);
    if (!validation.valid) {
      console.warn(`Indicator ${indicatorId} validation errors:`, validation.errors);
    }
    
    return result;
  };

  // Get indicator configuration
  const getIndicatorConfig = (indicatorId: string): IndicatorConfig => {
    switch (indicatorId) {
      case 'sma':
        return {
          id: 'sma-20',
          indicatorId: 'sma',
          parameters: { period: 20, source: 'close' },
          colors: ['#2196F3'],
          visible: true
        };
      case 'rsi':
        return {
          id: 'rsi-14',
          indicatorId: 'rsi',
          parameters: { period: 14, source: 'close' },
          colors: ['#FF9800'],
          visible: true
        };
      case 'bbands':
        return {
          id: 'bbands-20',
          indicatorId: 'bbands',
          parameters: { period: 20, stdDev: 2, source: 'close' },
          colors: ['#4CAF50', '#9C27B0', '#4CAF50'],
          visible: true
        };
      default:
        throw new Error(`Unknown indicator: ${indicatorId}`);
    }
  };

  // Get indicator type
  const getIndicatorType = (indicatorId: string): IndicatorType => {
    switch (indicatorId) {
      case 'sma':
        return IndicatorType.LINE;
      case 'rsi':
        return IndicatorType.LINE;
      case 'bbands':
        return IndicatorType.MULTI_LINE;
      default:
        return IndicatorType.LINE;
    }
  };

  // Handle changing the number of data points
  const handlePointsChange = (points: number) => {
    setNumPoints(points);
  };

  // Handle changing the timeframe
  const handleTimeframeChange = (tf: string) => {
    setTimeframe(tf);
  };

  // Handle adding an indicator
  const handleAddIndicator = (value: string) => {
    if (!selectedIndicators.includes(value)) {
      setSelectedIndicators([...selectedIndicators, value]);
    }
  };

  // Handle removing an indicator
  const handleRemoveIndicator = (indicatorId: string) => {
    setSelectedIndicators(selectedIndicators.filter(id => id !== indicatorId));
  };

  // Create indicator panel title based on indicator type
  const getIndicatorTitle = (indicatorId: string): string => {
    switch (indicatorId) {
      case 'sma':
        return 'Simple Moving Average (20)';
      case 'rsi':
        return 'Relative Strength Index (14)';
      case 'bbands':
        return 'Bollinger Bands (20, 2)';
      default:
        return indicatorId;
    }
  };

  // Set chart instance when chart is created
  const setChartInstanceHandler = (chart: any) => {
    setChartInstance(chart);
  };

  return (
    <div className="chart-example-with-data">
      <div className="chart-controls">
        <div className="control-group">
          <span>Timeframe: </span>
          <Button 
            variant={timeframe === '1h' ? 'primary' : 'outline'} 
            size="small" 
            onClick={() => handleTimeframeChange('1h')}
          >
            1h
          </Button>
          <Button 
            variant={timeframe === '4h' ? 'primary' : 'outline'} 
            size="small" 
            onClick={() => handleTimeframeChange('4h')}
          >
            4h
          </Button>
          <Button 
            variant={timeframe === '1D' ? 'primary' : 'outline'} 
            size="small" 
            onClick={() => handleTimeframeChange('1D')}
          >
            1D
          </Button>
        </div>
        
        <div className="control-group">
          <span>Data points: </span>
          <Button 
            variant={numPoints === 30 ? 'primary' : 'outline'} 
            size="small" 
            onClick={() => handlePointsChange(30)}
          >
            30
          </Button>
          <Button 
            variant={numPoints === 100 ? 'primary' : 'outline'} 
            size="small" 
            onClick={() => handlePointsChange(100)}
          >
            100
          </Button>
          <Button 
            variant={numPoints === 500 ? 'primary' : 'outline'} 
            size="small" 
            onClick={() => handlePointsChange(500)}
          >
            500
          </Button>
        </div>
        
        <div className="control-group">
          <span>Add indicator: </span>
          <Select
            options={availableIndicators.filter(ind => !selectedIndicators.includes(ind.value))}
            onChange={handleAddIndicator}
            placeholder="Select indicator..."
            value=""
          />
        </div>

        <div className="control-group">
          <span>Current indicators: </span>
          {selectedIndicators.map(ind => (
            <Button 
              key={ind}
              variant="secondary" 
              size="small"
              onClick={() => handleRemoveIndicator(ind)}
            >
              {ind} ✕
            </Button>
          ))}
        </div>
      </div>
      
      {data && (
        <div className="chart-container">
          <CandlestickChart
            data={data}
            height={400}
            title="Sample OHLCV Data"
            showVolume={true}
            fitContent={true}
            autoResize={true}
            onChartInit={setChartInstanceHandler}
          />
          
          {chartInstance && selectedIndicators.map((indicatorId) => {
            const indicatorData = calculateIndicatorData(indicatorId, data);
            const indicatorConfig = getIndicatorConfig(indicatorId);
            const indicatorType = getIndicatorType(indicatorId);
            const title = getIndicatorTitle(indicatorId);
            
            console.log(`Rendering ${indicatorId} indicator:`, { 
              data: indicatorData, 
              type: indicatorType,
              config: indicatorConfig
            });
            
            return (
              <IndicatorPanel
                key={indicatorId}
                mainChart={chartInstance}
                data={indicatorData}
                config={indicatorConfig}
                type={indicatorType}
                height={150}
                title={title}
                visible={true}
                onRemove={() => handleRemoveIndicator(indicatorId)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default ChartExampleWithData;