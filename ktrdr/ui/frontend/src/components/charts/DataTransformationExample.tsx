import React, { useState, useEffect, useRef } from 'react';
import { useTheme } from '../layouts/ThemeProvider';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { Select } from '../common/Select';

// Import chart utilities
import {
  createTestData,
  preprocessData,
  formatCandlestickData,
  formatHistogramData,
  formatTimeForDisplay,
  getTimeFormatForTimeframe,
  validateOHLCVData,
  fixOHLCVData,
  chartDebugger,
  ChartUpdater,
  UpdateMode
} from '../../utils/charts';
import { OHLCVData } from '../../types/data';
import { IChartApi, createChart, ColorType } from 'lightweight-charts';

// Preprocessing methods for the dropdown
const preprocessingMethods = [
  { value: 'none', label: 'No Preprocessing' },
  { value: 'previous', label: 'Fill with Previous Values' },
  { value: 'zero', label: 'Fill with Zeros' },
  { value: 'linear', label: 'Linear Interpolation' }
];

// Update modes for the dropdown
const updateModes = [
  { value: UpdateMode.REPLACE, label: 'Replace All Data' },
  { value: UpdateMode.APPEND, label: 'Append New Data' },
  { value: UpdateMode.UPDATE_LAST_AND_APPEND, label: 'Update Last & Append' },
  { value: UpdateMode.VISIBLE_RANGE_ONLY, label: 'Visible Range Only' }
];

interface DataTransformationExampleProps {
  /** Initial number of data points */
  initialPoints?: number;
  /** Symbol for test data */
  symbol?: string;
  /** Timeframe for test data */
  timeframe?: string;
  /** Whether to introduce errors in test data */
  introduceErrors?: boolean;
  /** Chart width */
  width?: number;
  /** Chart height */
  height?: number;
}

/**
 * Component demonstrating chart data transformation utilities
 */
const DataTransformationExample: React.FC<DataTransformationExampleProps> = ({
  initialPoints = 100,
  symbol = 'EXAMPLE',
  timeframe = '1d',
  introduceErrors = false,
  width = 800,
  height = 400
}) => {
  const { theme } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const [chart, setChart] = useState<IChartApi | null>(null);
  const [candlestickSeries, setCandlestickSeries] = useState<any>(null);
  const [volumeSeries, setVolumeSeries] = useState<any>(null);
  const [data, setData] = useState<OHLCVData | null>(null);
  const [transformedData, setTransformedData] = useState<any[]>([]);
  const [volumeData, setVolumeData] = useState<any[]>([]);
  const [preprocessMethod, setPreprocessMethod] = useState<string>('none');
  const [updateMode, setUpdateMode] = useState<UpdateMode>(UpdateMode.REPLACE);
  const [validation, setValidation] = useState<any>(null);
  const [showVolume, setShowVolume] = useState<boolean>(true);
  const [showDebug, setShowDebug] = useState<boolean>(false);
  const updaterRef = useRef<ChartUpdater | null>(null);
  
  // Generate initial test data
  useEffect(() => {
    generateData();
  }, [initialPoints, symbol, timeframe, introduceErrors]);
  
  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Get container dimensions
    const container = containerRef.current;
    
    // Create chart
    const newChart = createChart(container, {
      width,
      height,
      layout: {
        background: { 
          type: 'solid', 
          color: theme === 'dark' ? '#1E1E1E' : '#FFFFFF' 
        },
        textColor: theme === 'dark' ? '#D9D9D9' : '#191919',
      },
      grid: {
        vertLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
        horzLines: { color: theme === 'dark' ? '#2B2B43' : '#E6E6E6' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: theme === 'dark' ? '#2B2B43' : '#E6E6E6',
      },
    });
    
    // Create candlestick series
    const newCandlestickSeries = newChart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      borderVisible: false,
    });
    
    // Create volume series if enabled
    let newVolumeSeries = null;
    if (showVolume) {
      newVolumeSeries = newChart.addHistogramSeries({
        color: 'rgba(38, 166, 154, 0.5)',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });
      
      // Configure volume price scale
      newChart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
        borderVisible: false,
      });
    }
    
    // Save references
    setChart(newChart);
    setCandlestickSeries(newCandlestickSeries);
    setVolumeSeries(newVolumeSeries);
    
    // Create chart updater
    const updater = new ChartUpdater(newChart, {
      maxPoints: 1000,
      defaultUpdateMode: updateMode
    });
    
    // Add series to updater
    updater.addSeries('candlestick', newCandlestickSeries, 'Candlestick');
    if (newVolumeSeries) {
      updater.addSeries('volume', newVolumeSeries, 'Histogram');
    }
    
    updaterRef.current = updater;
    
    // Create debug overlay if enabled
    if (showDebug) {
      chartDebugger.setEnabled(true);
      chartDebugger.createDebugOverlay(newChart, container, data || undefined);
    }
    
    // Clean up on unmount
    return () => {
      if (updaterRef.current) {
        updaterRef.current.dispose();
      }
      
      if (newChart) {
        newChart.remove();
      }
    };
  }, [theme, showVolume, showDebug]);
  
  // Update data when it changes
  useEffect(() => {
    if (!data) return;
    
    // Preprocess data if needed
    let processedData = data;
    if (preprocessMethod !== 'none') {
      processedData = preprocessData(
        data, 
        preprocessMethod as 'previous' | 'linear' | 'zero' | 'none'
      );
    }
    
    // Validate data
    const validationResult = validateOHLCVData(processedData);
    setValidation(validationResult);
    
    // Fix data if needed and validation failed
    if (!validationResult.valid) {
      const { data: fixedData } = fixOHLCVData(processedData, validationResult);
      processedData = fixedData;
    }
    
    // Format data for chart
    const candlestickData = formatCandlestickData(processedData);
    const volumeData = formatHistogramData(processedData);
    
    setTransformedData(candlestickData);
    setVolumeData(volumeData);
    
    // Update chart
    if (updaterRef.current) {
      updaterRef.current.updateSeries('candlestick', processedData, { 
        mode: updateMode,
        updateTimeScale: true
      });
      
      if (showVolume) {
        updaterRef.current.updateSeries('volume', processedData, { 
          mode: updateMode,
          updateTimeScale: false
        });
      }
    } else {
      // Fallback direct update if updater not available
      if (candlestickSeries) {
        candlestickSeries.setData(candlestickData);
      }
      
      if (volumeSeries && showVolume) {
        volumeSeries.setData(volumeData);
      }
      
      // Fit content
      if (chart) {
        chart.timeScale().fitContent();
      }
    }
    
    // Debug data
    if (showDebug) {
      chartDebugger.inspectData(processedData, 'example');
      
      if (chart && containerRef.current) {
        chartDebugger.createDebugOverlay(chart, containerRef.current, processedData);
      }
    }
  }, [data, preprocessMethod, updateMode, showVolume, candlestickSeries, volumeSeries, chart, showDebug]);
  
  // Update chart updater config when update mode changes
  useEffect(() => {
    if (updaterRef.current) {
      // Create new updater with new update mode
      const currentUpdater = updaterRef.current;
      const newUpdater = new ChartUpdater(chart, {
        maxPoints: 1000,
        defaultUpdateMode: updateMode
      });
      
      // Transfer series
      if (candlestickSeries) {
        newUpdater.addSeries('candlestick', candlestickSeries, 'Candlestick');
      }
      
      if (volumeSeries && showVolume) {
        newUpdater.addSeries('volume', volumeSeries, 'Histogram');
      }
      
      // Dispose old updater
      currentUpdater.dispose();
      updaterRef.current = newUpdater;
    }
  }, [updateMode, chart, candlestickSeries, volumeSeries, showVolume]);
  
  // Generate test data
  const generateData = () => {
    // Create initial test data
    let newData = createTestData(initialPoints, symbol, timeframe);
    
    // Introduce errors if enabled
    if (introduceErrors) {
      const dataWithErrors = { ...newData };
      const ohlcv = [...dataWithErrors.ohlcv];
      
      // Add a few errors
      for (let i = 0; i < Math.min(5, ohlcv.length); i++) {
        const errorIndex = Math.floor(Math.random() * ohlcv.length);
        const errorType = Math.floor(Math.random() * 3);
        
        switch (errorType) {
          case 0:
            // High/low inversion
            ohlcv[errorIndex] = [
              ohlcv[errorIndex][0],
              ohlcv[errorIndex][2], // Low as high
              ohlcv[errorIndex][1], // High as low
              ohlcv[errorIndex][3],
              ohlcv[errorIndex][4]
            ];
            break;
          case 1:
            // Non-numeric value
            ohlcv[errorIndex] = [
              ohlcv[errorIndex][0],
              NaN, // NaN high
              ohlcv[errorIndex][2],
              ohlcv[errorIndex][3],
              ohlcv[errorIndex][4]
            ];
            break;
          case 2:
            // Negative volume
            ohlcv[errorIndex] = [
              ohlcv[errorIndex][0],
              ohlcv[errorIndex][1],
              ohlcv[errorIndex][2],
              ohlcv[errorIndex][3],
              -1000 // Negative volume
            ];
            break;
        }
      }
      
      dataWithErrors.ohlcv = ohlcv;
      newData = dataWithErrors;
    }
    
    setData(newData);
  };
  
  // Add more data
  const addMoreData = () => {
    if (!data) return;
    
    // Get last date
    const lastDate = data.dates[data.dates.length - 1];
    const lastTimestamp = typeof lastDate === 'string' 
      ? new Date(lastDate).getTime()
      : (lastDate as number) * 1000;
    
    // Create continuation data starting after last point
    const additionalData = createTestData(
      20, 
      symbol, 
      timeframe, 
      new Date(lastTimestamp + 24 * 60 * 60 * 1000)
    );
    
    // Combine data
    const newData: OHLCVData = {
      dates: [...data.dates, ...additionalData.dates],
      ohlcv: [...data.ohlcv, ...additionalData.ohlcv],
      metadata: {
        ...data.metadata,
        end: additionalData.metadata.end,
        points: data.metadata.points + additionalData.metadata.points
      }
    };
    
    setData(newData);
  };
  
  return (
    <div className="data-transformation-example">
      <Card title="Chart Data Transformation Example">
        <div className="controls" style={{ marginBottom: '1rem' }}>
          <div className="control-row" style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
            <Button onClick={generateData}>
              Regenerate Data
            </Button>
            
            <Button onClick={addMoreData} variant="secondary">
              Add More Data
            </Button>
            
            <Button 
              onClick={() => setShowVolume(!showVolume)} 
              variant="outline"
            >
              {showVolume ? 'Hide Volume' : 'Show Volume'}
            </Button>
            
            <Button
              onClick={() => {
                setShowDebug(!showDebug);
                chartDebugger.setEnabled(!showDebug);
              }}
              variant="outline"
            >
              {showDebug ? 'Hide Debug' : 'Show Debug'}
            </Button>
          </div>
          
          <div className="control-row" style={{ display: 'flex', gap: '1rem' }}>
            <div style={{ width: '200px' }}>
              <label>Preprocessing Method:</label>
              <Select
                value={preprocessMethod}
                options={preprocessingMethods}
                onChange={(value) => setPreprocessMethod(value)}
              />
            </div>
            
            <div style={{ width: '200px' }}>
              <label>Update Mode:</label>
              <Select
                value={updateMode}
                options={updateModes}
                onChange={(value) => setUpdateMode(value as UpdateMode)}
              />
            </div>
          </div>
        </div>
        
        <div className="chart-container" ref={containerRef} style={{ height }}>
          {/* Chart will be rendered here */}
        </div>
        
        {validation && !validation.valid && (
          <div className="validation-errors" style={{ 
            marginTop: '1rem', 
            padding: '0.5rem', 
            backgroundColor: 'rgba(255, 0, 0, 0.1)',
            borderRadius: '4px'
          }}>
            <h4>Validation Errors ({validation.issues.length}):</h4>
            <ul>
              {validation.issues.slice(0, 5).map((issue: any, index: number) => (
                <li key={index}>
                  {issue.message} {issue.index !== undefined && `(at index ${issue.index})`}
                </li>
              ))}
              {validation.issues.length > 5 && (
                <li>...and {validation.issues.length - 5} more errors</li>
              )}
            </ul>
          </div>
        )}
        
        <div className="data-info" style={{ marginTop: '1rem' }}>
          <h4>Data Summary:</h4>
          <p>
            Symbol: {data?.metadata.symbol}, 
            Timeframe: {data?.metadata.timeframe}, 
            Points: {data?.dates.length || 0}
          </p>
          {data && data.dates.length > 0 && (
            <p>
              Date Range: {formatTimeForDisplay(
                new Date(data.dates[0]).getTime() / 1000, 
                data.metadata.timeframe,
                getTimeFormatForTimeframe(data.metadata.timeframe)
              )} to {formatTimeForDisplay(
                new Date(data.dates[data.dates.length - 1]).getTime() / 1000,
                data.metadata.timeframe,
                getTimeFormatForTimeframe(data.metadata.timeframe)
              )}
            </p>
          )}
        </div>
      </Card>
    </div>
  );
};

export default DataTransformationExample;