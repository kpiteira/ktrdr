import React from 'react';
import { MainLayout } from '../components/layouts';
import { Card } from '../components/common';
import { ChartExampleWithData } from '../components/examples';
import './ChartExamplePage.css';

/**
 * ChartExample Page
 * 
 * Displays the chart example in a page layout with indicator components
 */
const ChartExamplePage: React.FC = () => {
  return (
    <MainLayout>
      <div className="chart-example-page">
        <h1>Chart Example</h1>
        <p>This example demonstrates the TradingView chart integration with OHLCV data and technical indicators.</p>
        
        <Card className="chart-card">
          <h2>Interactive TradingView Chart</h2>
          <p>Fully interactive chart with sample data generation, indicators, and controls</p>
          <ChartExampleWithData />
        </Card>
        
        <Card className="feature-info-card">
          <h3>Features Implemented</h3>
          <ul>
            <li>Candlestick chart with volume display</li>
            <li>Technical indicators with configurable parameters</li>
            <li>Separate indicator panels synchronized with main chart</li>
            <li>Multiple timeframe support</li>
            <li>Theme integration (light/dark)</li>
            <li>Interactive crosshair and tooltips</li>
          </ul>
        </Card>
      </div>
    </MainLayout>
  );
};

export default ChartExamplePage;