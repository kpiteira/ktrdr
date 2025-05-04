import React from 'react';
import { MainLayout } from '../components/layouts';
import { ChartExample } from '../components/charts';
import { Card } from '../components/common';
import './ChartExamplePage.css';
import WorkingChart from '../components/charts/WorkingChart';
import FallbackChart from '../components/charts/FallbackChart';
import ChartExampleWithData from '../components/charts/ChartExampleWithData';

/**
 * ChartExample Page
 * 
 * Displays the chart example in a page layout
 */
const ChartExamplePage: React.FC = () => {
  return (
    <MainLayout>
      <div className="chart-example-page">
        <h1>Chart Example</h1>
        <p>This example demonstrates the TradingView chart integration with OHLCV data.</p>
        
        <Card className="chart-card">
          <h2>Interactive TradingView Chart</h2>
          <p>Fully interactive chart with sample data generation and controls</p>
          <ChartExampleWithData />
        </Card>
        
        <Card className="chart-card" style={{ marginTop: '20px' }}>
          <h2>Basic TradingView Chart</h2>
          <p>Simple implementation using Lightweight Charts v4.1.1</p>
          <WorkingChart />
        </Card>
        
        <Card className="chart-card" style={{ marginTop: '20px' }}>
          <h2>Canvas Fallback Chart</h2>
          <p>Pure canvas implementation that doesn't rely on external libraries</p>
          <FallbackChart />
        </Card>
        
        {/* Temporarily commented out until fixed 
        <Card className="chart-card" style={{ marginTop: '20px' }}>
          <ChartExample defaultDays={100} />
        </Card>
        */}
      </div>
    </MainLayout>
  );
};

export default ChartExamplePage;