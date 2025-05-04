import React, { useState } from 'react';
import { CandlestickChart } from './CandlestickChart';
import { Button } from '../common/Button';
import { OHLCVData } from '../../types/data';
import './ChartExample.css';

// Sample data for demonstration
const generateSampleData = (days: number): OHLCVData => {
  const dates: string[] = [];
  const ohlcv: number[][] = [];
  
  let price = 100;
  const today = new Date();
  
  for (let i = 0; i < days; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() - days + i);
    dates.push(date.toISOString().split('T')[0]);
    
    // Generate random price movement
    const change = (Math.random() - 0.5) * 2;
    const open = price;
    price = price + change;
    const high = Math.max(open, price) + Math.random();
    const low = Math.min(open, price) - Math.random();
    const close = price;
    const volume = Math.floor(Math.random() * 1000) + 100;
    
    ohlcv.push([open, high, low, close, volume]);
  }
  
  return {
    dates,
    ohlcv,
    metadata: {
      symbol: 'EXAMPLE',
      timeframe: '1d',
      start: dates[0],
      end: dates[dates.length - 1],
      points: days,
    },
  };
};

export interface ChartExampleProps {
  defaultDays?: number;
}

/**
 * ChartExample component
 * 
 * A demo component to showcase the chart functionality
 */
export const ChartExample: React.FC<ChartExampleProps> = ({
  defaultDays = 100,
}) => {
  const [data, setData] = useState<OHLCVData>(generateSampleData(defaultDays));
  const [showVolume, setShowVolume] = useState<boolean>(true);
  
  // Generate new data with different time spans
  const generateData = (days: number) => {
    setData(generateSampleData(days));
  };
  
  return (
    <div className="chart-example">
      <div className="chart-example-controls">
        <Button 
          variant="primary" 
          size="small" 
          onClick={() => generateData(30)}
        >
          1 Month
        </Button>
        <Button 
          variant="primary" 
          size="small" 
          onClick={() => generateData(90)}
        >
          3 Months
        </Button>
        <Button 
          variant="primary" 
          size="small" 
          onClick={() => generateData(365)}
        >
          1 Year
        </Button>
        <Button 
          variant="primary" 
          size="small" 
          onClick={() => generateData(1000)}
        >
          1000 Days
        </Button>
        <Button 
          variant="outline" 
          size="small" 
          onClick={() => setShowVolume(!showVolume)}
        >
          {showVolume ? 'Hide Volume' : 'Show Volume'}
        </Button>
      </div>
      
      <div className="chart-example-container">
        <CandlestickChart
          data={data}
          height={500}
          showVolume={showVolume}
          optimizePerformance={true}
          incrementalLoading={true}
        />
      </div>
      
      <div className="chart-example-info">
        <p>Symbol: {data.metadata.symbol} | Timeframe: {data.metadata.timeframe} | Points: {data.metadata.points}</p>
      </div>
    </div>
  );
};

export default ChartExample;