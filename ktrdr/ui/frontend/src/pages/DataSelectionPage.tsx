import React from 'react';
import DataSelectionContainer from '../features/symbols/DataSelectionContainer';
import { Card } from '../components/common';

/**
 * DataSelectionPage serves as the main page for data selection in the KTRDR application.
 * It demonstrates the implementation of Task 7.6: Create Data Selection Components.
 */
const DataSelectionPage: React.FC = () => {
  return (
    <div className="data-selection-page">
      <h1>Data Selection Components (Task 7.6)</h1>
      
      <div className="page-description">
        <Card>
          <h2>Implementation of Data Selection Components</h2>
          <p>
            This page demonstrates the data selection components implemented for Task 7.6.
            These components provide a clean, intuitive interface for selecting market data
            and handle loading states and errors appropriately.
          </p>
          
          <h3>Key Components Implemented:</h3>
          <ul>
            <li><strong>SymbolSelector</strong> - For selecting trading symbols</li>
            <li><strong>TimeframeSelector</strong> - For selecting timeframes (1m, 5m, 1h, etc.)</li>
            <li><strong>DateRangePicker</strong> - For selecting historical data date ranges</li>
            <li><strong>DataLoadButton</strong> - For triggering data loading with loading state feedback</li>
            <li><strong>DataPreview</strong> - For displaying loaded data with metadata and sample rows</li>
            <li><strong>DataSelectionPanel</strong> - A container that combines all selection controls</li>
          </ul>
        </Card>
      </div>
      
      <div className="data-selection-demo" style={{ marginTop: '24px' }}>
        <DataSelectionContainer />
      </div>
    </div>
  );
};

export default DataSelectionPage;