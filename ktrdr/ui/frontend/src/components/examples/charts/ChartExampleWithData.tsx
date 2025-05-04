import React, { useState, useEffect } from 'react';
import { Button } from '../../common/Button';
import { CandlestickTradingView } from '../../charts'; 
import { OHLCVData } from '../../../types/data';
import './ChartExampleWithData.css';

/**
 * ChartExampleWithData component
 * 
 * Demonstrates the CandlestickTradingView component with sample data
 */
const ChartExampleWithData: React.FC = () => {
  const [data, setData] = useState<OHLCVData | null>(null);
  const [timeframe, setTimeframe] = useState<string>('1D');
  const [numPoints, setNumPoints] = useState<number>(100);

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
                          timeframe === '1D' ? 24 * 60 * 60 * 1000 : 
                          24 * 60 * 60 * 1000;
    
    for (let i = 0; i < days; i++) {
      const date = new Date(today.getTime() - (days - i) * timeIncrement);
      dates.push(date.toISOString().split('T')[0]);
      
      // Generate random price movement
      const change = (Math.random() - 0.5) * 2;
      const open = price;
      price = price + price * change * 0.02; // 2% maximum change
      const high = Math.max(open, price) + Math.random() * price * 0.01;
      const low = Math.min(open, price) - Math.random() * price * 0.01;
      const close = price;
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

  // Handle changing the number of data points
  const handlePointsChange = (points: number) => {
    setNumPoints(points);
  };

  // Handle changing the timeframe
  const handleTimeframeChange = (tf: string) => {
    setTimeframe(tf);
  };

  return (
    <div className="chart-example-with-data">
      <div className="chart-controls">
        <div className="timeframe-selector">
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
        
        <div className="data-points-selector">
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
      </div>
      
      {data && (
        <div style={{
          width: '100%',
          height: '500px',
          position: 'relative',
          overflow: 'hidden',
          margin: '0 auto',
          border: '1px solid #ddd',
          borderRadius: '4px',
          boxSizing: 'border-box'
        }}>
          <CandlestickTradingView
            data={data}
            height={500}
            title="Sample OHLCV Data"
            showVolume={true}
            fitContent={true}
            autoResize={true}
          />
        </div>
      )}
    </div>
  );
};

export default ChartExampleWithData;