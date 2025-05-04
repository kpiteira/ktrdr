import React, { useRef, useEffect, useState } from 'react';
import { useTheme } from '../../layouts/ThemeProvider';
import { Button } from '../../common/Button';
import { Card } from '../../common/Card';
import { Select } from '../../common/Select';

// Import chart utilities
import {
  createTestData,
  preprocessData,
  formatCandlestickData,
  formatHistogramData,
  formatTimeForDisplay,
  getTimeFormatForTimeframe,
  validateData,
  chartDebugger,
  ChartUpdater,
  UpdateMode
} from '../../../utils/charts';

// Import validation utilities
import {
  validateOHLCVData,
  fixOHLCVData
} from '../../../utils/charts/dataValidation';

// Import common types or interfaces
import { OHLCVData } from '../../../types/data';

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
  const resizeTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const dimensionsRef = useRef<{
    width: number;
    height: number;
  }>({
    width: 0,
    height: 0
  });
  const [chartInstance, setChartInstance] = useState<any>(null);
  const [series, setSeries] = useState<any>({
    candlestick: null,
    volume: null
  });
  const [data, setData] = useState<OHLCVData | null>(null);
  const [transformedData, setTransformedData] = useState<any[]>([]);
  const [volumeData, setVolumeData] = useState<any[]>([]);
  const [preprocessMethod, setPreprocessMethod] = useState<string>('none');
  const [updateMode, setUpdateMode] = useState<UpdateMode>(UpdateMode.REPLACE);
  const [validation, setValidation] = useState<{valid: boolean, issues: any[]}|null>(null);
  const [showVolume, setShowVolume] = useState<boolean>(true);
  const [showDebug, setShowDebug] = useState<boolean>(false);
  const [isLibraryLoaded, setIsLibraryLoaded] = useState<boolean>(false);
  const updaterRef = useRef<ChartUpdater | null>(null);
  const scriptRef = useRef<HTMLScriptElement | null>(null);

  // Generate initial test data
  useEffect(() => {
    generateData();
  }, [initialPoints, symbol, timeframe, introduceErrors]);

  // Load the library if it's not already loaded
  useEffect(() => {
    // Skip if library is already loaded or if we already started loading it
    if (typeof window.LightweightCharts !== 'undefined') {
      setIsLibraryLoaded(true);
      return;
    }
    
    if (scriptRef.current) {
      return; // Script is already being loaded
    }
    
    console.log('Loading Lightweight Charts library...');
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js';
    script.async = true;
    script.onload = () => {
      console.log('Lightweight Charts library loaded!');
      setIsLibraryLoaded(true);
    };
    scriptRef.current = script;
    document.head.appendChild(script);
    
    // Cleanup on unmount
    return () => {
      if (scriptRef.current && scriptRef.current.parentNode) {
        scriptRef.current.parentNode.removeChild(scriptRef.current);
      }
    };
  }, []);

  // Initialize chart
  useEffect(() => {
    // Skip if library is not loaded or container doesn't exist
    if (!isLibraryLoaded || !containerRef.current) {
      return;
    }
    
    // Skip re-initialization if nothing important changed
    if (chartInstance && 
        chartInstance._options && 
        chartInstance._options.width === width && 
        chartInstance._options.height === height) {
      return;
    }
    
    console.log('Initializing chart with dimensions:', width, 'x', height);
    
    // Clean up previous chart
    if (chartInstance) {
      try {
        chartInstance.remove();
        // Also reset series references to prevent stale data updates
        setSeries({ candlestick: null, volume: null });
      } catch (e) {
        console.error('Error removing chart:', e);
      }
    }
    
    // Store any cleanup function that initializeChart might return
    let cleanupFunction: (() => void) | void;
    
    try {
      cleanupFunction = initializeChart();
    } catch (e) {
      console.error('Error during chart initialization:', e);
    }
    
    // Return cleanup function that handles both the chart instance and any internal cleanup
    return () => {
      // First call any internal cleanup from initializeChart
      if (typeof cleanupFunction === 'function') {
        try {
          cleanupFunction();
        } catch (e) {
          console.error('Error in cleanup function:', e);
        }
      }
      
      // Then remove the chart
      if (chartInstance) {
        try {
          chartInstance.remove();
          setSeries({ candlestick: null, volume: null });
        } catch (e) {
          console.error('Error removing chart:', e);
        }
      }
    };
  }, [isLibraryLoaded, theme, width, height, showVolume]);

  // Update data when it changes or preprocessing method changes
  useEffect(() => {
    if (!data || !chartInstance) return;
    updateChartData();
  }, [data, preprocessMethod, chartInstance]);

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

  // Toggle debug mode
  const toggleDebug = () => {
    setShowDebug(!showDebug);
    if (chartDebugger) {
      chartDebugger.setEnabled(!showDebug);
      if (!showDebug && data) {
        console.info('Debug data inspection:', chartDebugger.inspectData(data, 'Current Data'));
      }
    }
  };

  // Initialize chart
  const initializeChart = () => {
    if (!containerRef.current || !window.LightweightCharts) return;

    try {
      console.log('Initializing chart with LightweightCharts v4.1.1');

      // Clear previous chart if any
      if (chartInstance) {
        chartInstance.remove();
      }
      containerRef.current.innerHTML = '';

      // Set up colors based on theme
      const colors = theme === 'dark' 
        ? {
            background: '#151924',
            text: '#d1d4dc',
            grid: '#2a2e39',
          }
        : {
            background: '#ffffff',
            text: '#333333',
            grid: '#e6e6e6',
          };

      // Create chart with version 4 API
      const chart = window.LightweightCharts.createChart(containerRef.current, {
        width: width,
        height: height,
        layout: {
          background: { color: colors.background },
          textColor: colors.text
        },
        grid: {
          vertLines: { color: colors.grid },
          horzLines: { color: colors.grid }
        },
        rightPriceScale: {
          borderColor: colors.grid,
        },
        timeScale: {
          borderColor: colors.grid,
          timeVisible: true,
        },
      });

      // Add candlestick series
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#26a69a',
        downColor: '#ef5350',
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
        borderVisible: false,
      });

      // Store series reference
      setSeries(prev => ({ ...prev, candlestick: candlestickSeries }));

      // Add volume series if needed
      if (showVolume) {
        const volumeSeries = chart.addHistogramSeries({
          color: '#26a69a',
          priceFormat: {
            type: 'volume',
          },
          priceScaleId: 'volume',
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
        });

        // Configure the price scale
        chart.priceScale('volume').applyOptions({
          scaleMargins: {
            top: 0.8,
            bottom: 0,
          },
          borderVisible: false,
        });

        // Store volume series reference
        setSeries(prev => ({ ...prev, volume: volumeSeries }));
      }

      // Store chart instance
      setChartInstance(chart);

      // Try to create the updater - ensure we use the locally scoped variables
      try {
        const updater = new ChartUpdater(chart, {
          maxPoints: 1000,
          defaultUpdateMode: updateMode
        });

        // Create a local variable for tracking what series we added
        let seriesAdded = false;

        // If candlestick series exists, add it to the updater
        if (typeof candlestickSeries !== 'undefined' && candlestickSeries !== null) {
          try {
            updater.addSeries('candlestick', candlestickSeries, 'Candlestick');
            seriesAdded = true;
          } catch (e) {
            console.warn('Failed to add candlestick series to updater:', e);
          }
        }
        
        // If volume series exists and volume is enabled, add it to the updater
        if (showVolume && typeof volumeSeries !== 'undefined' && volumeSeries !== null) {
          try {
            updater.addSeries('histogram', volumeSeries, 'Volume');
            seriesAdded = true;
          } catch (e) {
            console.warn('Failed to add volume series to updater:', e);
          }
        }
        
        // Only save the updater if at least one series was added successfully
        if (seriesAdded) {
          updaterRef.current = updater;
        } else {
          // Dispose the updater if no series were added
          updater.dispose();
        }
      } catch (error) {
        console.error('Error initializing chart updater:', error);
      }

      // Fit content
      chart.timeScale().fitContent();

      // Store initial dimensions
      dimensionsRef.current = { width: width, height: height };
      
      // Add resize handler with debounce
      const handleResize = () => {
        // Cancel any pending resize operations
        if (resizeTimeoutRef.current) {
          clearTimeout(resizeTimeoutRef.current);
        }
        
        // Debounce the resize to prevent rapid consecutive calls
        resizeTimeoutRef.current = setTimeout(() => {
          if (containerRef.current) {
            const containerWidth = containerRef.current.clientWidth;
            
            // Only resize if there's a meaningful change in width
            if (Math.abs(containerWidth - dimensionsRef.current.width) > 1) {
              console.log('Resizing chart from', dimensionsRef.current.width, 'to', containerWidth);
              
              try {
                // Update the chart size
                chart.resize(containerWidth, height);
                
                // Update the last known dimensions
                dimensionsRef.current.width = containerWidth;
              } catch (e) {
                console.error('Error during chart resize:', e);
              }
            }
          }
        }, 150); // Wait 150ms after last resize event
      };

      window.addEventListener('resize', handleResize);
      
      console.log('Chart created successfully');
      
      // Return cleanup function
      return () => {
        window.removeEventListener('resize', handleResize);
        if (resizeTimeoutRef.current) {
          clearTimeout(resizeTimeoutRef.current);
          resizeTimeoutRef.current = null;
        }
      };
    } catch (error) {
      console.error('Error initializing chart:', error);
    }
  };

  // Update chart data
  const updateChartData = () => {
    if (!data || !chartInstance || !series.candlestick) return;

    try {
      // Preprocess data if needed
      let processedData = data;
      if (preprocessMethod !== 'none') {
        processedData = preprocessData(
          data, 
          preprocessMethod as 'previous' | 'linear' | 'zero' | 'none'
        );
      }
      
      // Validate data
      try {
        const validationResult = validateData(processedData);
        setValidation({ 
          valid: validationResult.valid, 
          issues: validationResult.issues 
        });
        
        // Fix data if validation failed
        if (!validationResult.valid) {
          console.log('Fixing invalid data before display');
          processedData = fixOHLCVData(processedData);
        }
      } catch (error) {
        console.error('Error validating data:', error);
        setValidation({
          valid: false,
          issues: ['Error validating data']
        });
      }
      
      // Format data for chart
      const candlestickData = formatCandlestickData(processedData);
      setTransformedData(candlestickData);

      // Set candlestick data
      if (series.candlestick) {
        series.candlestick.setData(candlestickData);
      }

      // Set volume data if needed
      if (showVolume && series.volume) {
        const volumeData = formatHistogramData(processedData);
        setVolumeData(volumeData);
        series.volume.setData(volumeData);
      }

      // Fit chart to content
      chartInstance.timeScale().fitContent();
    } catch (error) {
      console.error('Error updating chart data:', error);
    }
  };

  // Show summary of transformed data
  const renderDataSummary = () => {
    if (!transformedData || transformedData.length === 0) return null;

    // Select a few samples to display
    const samples = transformedData.slice(0, 3);
    
    return (
      <div className="data-sample" style={{ 
        marginTop: '1rem',
        fontSize: '0.85rem',
        overflow: 'auto',
        maxHeight: '150px'
      }}>
        <h4>Data Sample (first 3 points):</h4>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #ccc' }}>
              <th style={{ textAlign: 'left', padding: '4px' }}>Time</th>
              <th style={{ textAlign: 'right', padding: '4px' }}>Open</th>
              <th style={{ textAlign: 'right', padding: '4px' }}>High</th>
              <th style={{ textAlign: 'right', padding: '4px' }}>Low</th>
              <th style={{ textAlign: 'right', padding: '4px' }}>Close</th>
              {showVolume && <th style={{ textAlign: 'right', padding: '4px' }}>Volume</th>}
            </tr>
          </thead>
          <tbody>
            {samples.map((item, index) => (
              <tr key={index} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '4px' }}>
                  {formatTimeForDisplay(
                    item.time,
                    timeframe,
                    getTimeFormatForTimeframe(timeframe)
                  )}
                </td>
                <td style={{ textAlign: 'right', padding: '4px' }}>{item.open.toFixed(2)}</td>
                <td style={{ textAlign: 'right', padding: '4px' }}>{item.high.toFixed(2)}</td>
                <td style={{ textAlign: 'right', padding: '4px' }}>{item.low.toFixed(2)}</td>
                <td style={{ textAlign: 'right', padding: '4px' }}>{item.close.toFixed(2)}</td>
                {showVolume && <td style={{ textAlign: 'right', padding: '4px' }}>
                  {volumeData[index]?.value.toLocaleString()}
                </td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="data-transformation-example">
      <Card title="Chart Data Transformation Example">
        {/* Add a small info about version */}
        <p style={{ fontSize: '0.8rem', color: '#666', marginBottom: '0.5rem' }}>
          Using lightweight-charts v4.1.1
        </p>
        
        <div className="controls" style={{ marginBottom: '1rem' }}>
          <div className="control-row" style={{ display: 'flex', gap: '1rem', marginBottom: '0.5rem' }}>
            <Button onClick={generateData}>
              Regenerate Data
            </Button>
            
            <Button onClick={addMoreData} variant="secondary">
              Add More Data
            </Button>
            
            <Button 
              onClick={() => {
                setShowVolume(!showVolume);
                // This will trigger chart re-initialization
              }} 
              variant="outline"
            >
              {showVolume ? 'Hide Volume' : 'Show Volume'}
            </Button>
            
            <Button
              onClick={toggleDebug}
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
        
        <div 
          className="chart-container" 
          ref={containerRef} 
          style={{ 
            height, 
            width: '100%',
            position: 'relative'
          }}
        />
        
        {validation && !validation.valid && (
          <div className="validation-errors" style={{ 
            marginTop: '1rem', 
            padding: '0.5rem', 
            backgroundColor: 'rgba(255, 0, 0, 0.1)',
            borderRadius: '4px'
          }}>
            <h4>Validation Errors:</h4>
            <ul>
              {Array.isArray(validation.issues) && validation.issues.slice(0, 5).map((issue: any, index: number) => (
                <li key={index}>
                  {typeof issue === 'string' 
                    ? issue 
                    : (issue.message || JSON.stringify(issue))}
                  {issue?.index !== undefined && ` (at index ${issue.index})`}
                </li>
              ))}
              {Array.isArray(validation.issues) && validation.issues.length > 5 && (
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
          
          {/* Render data sample */}
          {transformedData.length > 0 && renderDataSummary()}
        </div>
      </Card>
    </div>
  );
};

export default DataTransformationExample;

// Add the LightweightCharts type to the Window interface
declare global {
  interface Window {
    LightweightCharts: any;
  }
}