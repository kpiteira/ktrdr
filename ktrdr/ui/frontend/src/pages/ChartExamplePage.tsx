import React from 'react';
import { MainLayout } from '../components/layouts';
import { Card } from '../components/common';
import { ChartExampleWithData } from '../components/examples';
import './ChartExamplePage.css';

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
      </div>
    </MainLayout>
  );
};

export default ChartExamplePage;