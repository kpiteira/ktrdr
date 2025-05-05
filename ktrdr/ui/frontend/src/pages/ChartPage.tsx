import React from 'react';
import { Card } from '../components/common';
import CandlestickChart from '../features/charting/CandlestickChart';
import { generateDemoData } from '../demo/legacy/demo-data';

/**
 * ChartPage displays trading charts with indicators
 */
const ChartPage: React.FC = () => {
  // This is a placeholder that will be replaced with actual data fetching
  const demoData = generateDemoData(100);
  
  return (
    <div className="chart-page">
      <h1>Chart</h1>
      
      <Card>
        <p>This is the Chart page that will display trading charts with indicators.</p>
        <div style={{ height: '400px', marginTop: '20px' }}>
          <CandlestickChart 
            data={demoData}
            height={400}
            showVolume={true}
            title="Sample Chart"
          />
        </div>
      </Card>
    </div>
  );
};

export default ChartPage;