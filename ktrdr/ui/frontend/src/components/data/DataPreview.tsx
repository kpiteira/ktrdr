import React from 'react';
import { Table, LoadingSpinner, Card } from '../common';
import { useOhlcvData } from '../../hooks';

interface DataPreviewProps {
  className?: string;
  maxPreviewRows?: number;
}

export const DataPreview: React.FC<DataPreviewProps> = ({
  className = '',
  maxPreviewRows = 3
}) => {
  const { ohlcvData, dataStatus } = useOhlcvData();
  
  // Check if data is loading
  const isLoading = dataStatus === 'loading';
  
  // If no data is loaded yet, display appropriate message
  if (!ohlcvData && !isLoading) {
    return (
      <div className={`data-preview ${className}`}>
        <Card title="Data Preview">
          <p>No data loaded. Use the data selection controls to load OHLCV data.</p>
          <p className="helper-text">Select a symbol and timeframe, then click "Load Data".</p>
        </Card>
      </div>
    );
  }
  
  // If data is loading, show loading indicator
  if (isLoading) {
    return (
      <div className={`data-preview ${className}`}>
        <Card title="Data Preview">
          <div className="loading-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
            <LoadingSpinner />
            <p style={{ marginLeft: '1rem' }}>Loading data...</p>
          </div>
        </Card>
      </div>
    );
  }
  
  // Render data preview table
  if (ohlcvData) {
    try {
      const { dates, ohlcv, metadata } = ohlcvData;
      const previewRows = Math.min(maxPreviewRows, dates.length);
      
      return (
        <div className={`data-preview ${className}`}>
          <Card title="Data Preview">
            <div className="data-summary">
              <div className="metadata-section">
                <h4>Dataset Information</h4>
                <div className="metadata-grid">
                  <div className="metadata-item">
                    <span className="label">Symbol:</span>
                    <span className="value">{metadata?.symbol || 'Unknown'}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Timeframe:</span>
                    <span className="value">{metadata?.timeframe || 'Unknown'}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Date Range:</span>
                    <span className="value">{metadata?.start || 'N/A'} to {metadata?.end || 'N/A'}</span>
                  </div>
                  <div className="metadata-item">
                    <span className="label">Total Points:</span>
                    <span className="value">{metadata?.points || dates?.length || 0}</span>
                  </div>
                </div>
              </div>
              
              {dates && dates.length > 0 && (
                <div className="data-table-section">
                  <h4>Sample Data {previewRows > 0 ? `(showing ${previewRows} of ${dates.length} points)` : ''}</h4>
                  <div className="data-table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Open</th>
                          <th>High</th>
                          <th>Low</th>
                          <th>Close</th>
                          <th>Volume</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dates.slice(0, previewRows).map((date, index) => (
                          <tr key={date}>
                            <td>{date}</td>
                            <td>{ohlcv[index][0].toFixed(2)}</td>
                            <td>{ohlcv[index][1].toFixed(2)}</td>
                            <td>{ohlcv[index][2].toFixed(2)}</td>
                            <td>{ohlcv[index][3].toFixed(2)}</td>
                            <td>{ohlcv[index][4].toFixed(0)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      );
    } catch (error) {
      console.error("Error rendering data preview:", error);
      return (
        <div className={`data-preview ${className}`}>
          <Card title="Data Preview">
            <p>Error displaying data. The data format may be incorrect.</p>
          </Card>
        </div>
      );
    }
  }
  
  return null;
};

export default DataPreview;