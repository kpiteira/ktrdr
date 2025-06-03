import { useEffect, useRef, FC } from 'react';
import { 
  createChart, 
  IChartApi, 
  ISeriesApi, 
  LineData,
  LineSeries,
  HistogramSeries
} from 'lightweight-charts';
import LoadingSpinner from '../../common/LoadingSpinner';
import ErrorDisplay from '../../common/ErrorDisplay';
import EmptyState from '../../common/EmptyState';
import FuzzyOverlay from './FuzzyOverlay';
import { ChartFuzzyData } from '../../../api/types/fuzzy';

/**
 * Generic presentation component for oscillator charts
 * 
 * This component can render any oscillator-type indicator (RSI, MACD, Stochastic, etc.)
 * in a separate chart panel. All data and state management is handled 
 * by the container component.
 */

export interface OscillatorData {
  indicators: OscillatorIndicatorSeries[];
}

export interface OscillatorIndicatorSeries {
  id: string;
  name: string;
  data: LineData[];
  color: string;
  visible: boolean;
  // Oscillator-specific properties
  type?: 'line' | 'histogram';
  yAxisConfig?: {
    min?: number;
    max?: number;
    referenceLines?: Array<{ value: number; color: string; style?: 'solid' | 'dashed' }>;
  };
}

interface OscillatorChartProps {
  // Chart configuration
  width?: number;
  height?: number;
  
  // Data props
  oscillatorData: OscillatorData | null;
  isLoading: boolean;
  error: string | null;
  
  // Fuzzy overlay props
  fuzzyData?: ChartFuzzyData[] | null;
  fuzzyVisible?: boolean;
  fuzzyOpacity?: number;
  fuzzyColorScheme?: string;
  
  // Chart synchronization
  onChartCreated?: (chart: IChartApi) => void;
  onChartDestroyed?: () => void;
  onCrosshairMove?: (params: any) => void;
  
  // Visual state
  showLoadingOverlay?: boolean;
  showErrorOverlay?: boolean;
  
  // Oscillator configuration
  oscillatorConfig?: {
    title?: string;
    yAxisRange?: { min: number; max: number };
    referenceLines?: Array<{ value: number; color: string; label?: string }>;
    backgroundColor?: string;
  };
  
  // Synchronization control
  preserveTimeScale?: boolean;
}

const OscillatorChart: FC<OscillatorChartProps> = ({
  width = 800,
  height = 200,
  oscillatorData,
  isLoading,
  error,
  fuzzyData,
  fuzzyVisible = false,
  fuzzyOpacity = 0.3,
  fuzzyColorScheme = 'default',
  onChartCreated,
  onChartDestroyed,
  onCrosshairMove,
  showLoadingOverlay = true,
  showErrorOverlay = true,
  oscillatorConfig = {},
  preserveTimeScale = false
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const indicatorSeriesRef = useRef<Map<string, ISeriesApi<'Line'> | ISeriesApi<'Histogram'>>>(new Map());


  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) {
      return;
    }
    
    // Don't create chart with invalid dimensions
    if (width <= 0 || height <= 0) {
      console.warn(`OscillatorChart: Invalid dimensions - width: ${width}, height: ${height}`);
      return;
    }

    // Clean up existing chart
    if (chartRef.current) {
      chartRef.current.remove();
      if (onChartDestroyed) {
        onChartDestroyed();
      }
    }

    // Default oscillator configuration
    const defaultReferenceLines = oscillatorConfig.referenceLines || [
      { value: 30, color: '#888888', label: 'Oversold' },
      { value: 70, color: '#888888', label: 'Overbought' }
    ];

    // Validate dimensions before creating chart
    const validWidth = Math.max(100, width);
    const validHeight = Math.max(100, height);
    
    // Create new chart
    const chart = createChart(chartContainerRef.current, {
      width: validWidth,
      height: validHeight,
      layout: {
        background: { color: oscillatorConfig.backgroundColor || '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: '#cccccc',
        scaleMargins: {
          top: 0.1,
          bottom: 0.1,
        },
        mode: 1,
        autoScale: false,
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: 6,
        minBarSpacing: 0.5,
        rightBarStaysOnScroll: true,
        shiftVisibleRangeOnNewBar: false,
      },
    });

    chartRef.current = chart;

    // Set price scale range if configured
    if (oscillatorConfig.yAxisRange) {
      chart.priceScale('right').applyOptions({
        scaleMargins: { top: 0.1, bottom: 0.1 },
      });
    }

    // Add reference lines (like RSI 30/70 levels)
    defaultReferenceLines.forEach(line => {
      const referenceSeries = chart.addSeries(LineSeries, {
        color: line.color,
        lineWidth: 1,
        lineStyle: 2, // Dashed line
        title: line.label || '',
        priceLineVisible: false,
        lastValueVisible: false,
      });
      
      // Add horizontal line at the reference value using proper UTC timestamps
      referenceSeries.setData([
        { time: (new Date('2020-01-01').getTime() / 1000) as any, value: line.value },
        { time: (new Date('2030-01-01').getTime() / 1000) as any, value: line.value }
      ]);
    });

    // Set up event listeners
    if (onCrosshairMove) {
      chart.subscribeCrosshairMove((param) => {
        onCrosshairMove(param);
      });
    }

    // Notify parent
    if (onChartCreated) {
      onChartCreated(chart);
    }

    // Cleanup function
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        indicatorSeriesRef.current.clear();
        if (onChartDestroyed) {
          onChartDestroyed();
        }
      }
    };
  }, [width, height]);

  // Update chart data when it changes
  useEffect(() => {
    if (!oscillatorData || !chartRef.current) {
      return;
    }

    // Track existing indicator count for chart jumping prevention
    const existingIndicatorCount = indicatorSeriesRef.current.size;

    // Update indicator series
    const currentIndicatorIds = new Set(indicatorSeriesRef.current.keys());
    const newIndicatorIds = new Set(oscillatorData.indicators.map(ind => ind.id));

    // Remove old indicators
    currentIndicatorIds.forEach(id => {
      if (!newIndicatorIds.has(id)) {
        const series = indicatorSeriesRef.current.get(id);
        if (series && chartRef.current) {
          chartRef.current.removeSeries(series);
          indicatorSeriesRef.current.delete(id);
        }
      }
    });

    // Add or update indicators
    oscillatorData.indicators.forEach(indicator => {
      let series = indicatorSeriesRef.current.get(indicator.id);
      
      if (!series && chartRef.current) {
        // Create appropriate series type based on indicator type
        if (indicator.type === 'histogram') {
          series = chartRef.current.addSeries(HistogramSeries, {
            color: indicator.color,
            title: indicator.name,
            // Make histogram less prominent
            priceFormat: {
              type: 'price',
              precision: 4,
              minMove: 0.0001,
            },
          });
        } else {
          // Default to line series with increased thickness for MACD lines
          const lineWidth = indicator.name.includes('MACD') ? 3 : 2;
          series = chartRef.current.addSeries(LineSeries, {
            color: indicator.color,
            lineWidth: lineWidth,
            title: indicator.name
          });
        }
        indicatorSeriesRef.current.set(indicator.id, series);
      }
      
      if (series) {
        if (indicator.data && indicator.data.length > 0) {
          series.setData(indicator.data);
        }
        
        // Apply options based on series type
        if (indicator.type === 'histogram') {
          series.applyOptions({
            color: indicator.color,
            title: indicator.name,
            visible: indicator.visible !== false
          });
        } else {
          // Line series options
          series.applyOptions({
            color: indicator.color,
            title: indicator.name,
            lineVisible: indicator.visible !== false,
            lastValueVisible: indicator.visible !== false,
            priceLineVisible: indicator.visible !== false
          });
        }
      }
    });

    // Fit content after data update (only if not preserving time scale for sync)
    if (!preserveTimeScale && chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }

    // ==================================================================================
    // CRITICAL FIX: Chart jumping bug when adding oscillator indicators - DO NOT REMOVE
    // ==================================================================================
    // 
    // ISSUE: TradingView Lightweight Charts v5 automatically adjusts the visible time 
    // range when oscillator indicators are added to synchronized charts, causing unwanted 
    // forward jumps in time that break the user experience.
    //
    // ROOT CAUSE: TradingView's internal auto-scaling logic conflicts with chart 
    // synchronization (preserveTimeScale=true), particularly when adding the first 
    // oscillator indicator to a chart or when fuzzy overlays are enabled/disabled.
    //
    // SOLUTION: Preventive visibility toggle (hide/show) of the first indicator 
    // immediately after it's added. This forces TradingView to recalculate the 
    // correct time range without the unwanted jump.
    //
    // TIMING: 1ms delays are critical - tested down from 300ms to find minimum 
    // effective timing that's imperceptible to users.
    //
    // TRIGGER: Only on first oscillator indicator addition to avoid unnecessary 
    // processing and maintain performance.
    //
    // TESTED: Confirmed working with TradingView Lightweight Charts v5.0.7
    // DATE: May 28, 2025 (ported from BasicChart.tsx to OscillatorChart.tsx)
    // SEVERITY: CRITICAL - Removing this fix will cause chart jumping regression
    // ==================================================================================
    
    const indicatorCountChanged = oscillatorData.indicators.length !== existingIndicatorCount;
    
    // Apply preventive fix only when adding the first oscillator indicator to synchronized charts
    if (indicatorCountChanged && preserveTimeScale && chartRef.current) {
      // Check if this is the first oscillator indicator being added
      const isFirstOscillatorIndicator = oscillatorData.indicators.length === 1 && existingIndicatorCount === 0;
      
      // console.log(`🔧 [OscillatorChart] Chart jumping check:`, {
      //   indicatorCountChanged,
      //   preserveTimeScale,
      //   isFirstOscillatorIndicator,
      //   currentIndicators: oscillatorData.indicators.length,
      //   existingCount: existingIndicatorCount
      // });
      
      if (isFirstOscillatorIndicator) {
        // console.log(`🚨 [OscillatorChart] Applying chart jumping prevention for first oscillator indicator`);
        
        // CRITICAL: Apply the visibility fix preventively - DO NOT MODIFY TIMING
        setTimeout(() => {
          const eyeButtons = document.querySelectorAll('button[title="Hide"], button[title="Show"]');
          // console.log(`👁️ [OscillatorChart] Found ${eyeButtons.length} eye buttons:`, Array.from(eyeButtons).map(btn => btn.title));
          
          if (eyeButtons.length > 0) {
            // console.log(`🖱️ [OscillatorChart] Clicking first eye button: ${eyeButtons[0].title}`);
            (eyeButtons[0] as HTMLButtonElement).click();
            setTimeout(() => {
              const eyeButtonsAgain = document.querySelectorAll('button[title="Hide"], button[title="Show"]');
              if (eyeButtonsAgain.length > 0) {
                // console.log(`🖱️ [OscillatorChart] Clicking eye button again: ${eyeButtonsAgain[0].title}`);
                (eyeButtonsAgain[0] as HTMLButtonElement).click();
              }
            }, 1); // CRITICAL: 1ms timing - tested minimum effective delay
          } else {
            console.warn(`⚠️ [OscillatorChart] No eye buttons found for chart jumping prevention`);
          }
        }, 1); // CRITICAL: 1ms timing - tested minimum effective delay
      }
    }
    
    // ==================================================================================
    // END CRITICAL FIX - Chart jumping prevention for oscillator charts
    // ==================================================================================
    
  }, [oscillatorData, preserveTimeScale]);

  // Handle resize
  useEffect(() => {
    if (chartRef.current) {
      chartRef.current.applyOptions({ width, height });
    }
  }, [width, height]);

  return (
    <div style={{ position: 'relative', width, height }}>
      {/* Chart title */}
      {oscillatorConfig.title && (
        <div style={{
          position: 'absolute',
          top: '8px',
          left: '8px',
          fontSize: '0.875rem',
          fontWeight: 'bold',
          color: '#666',
          zIndex: 10,
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          padding: '0.25rem 0.5rem',
          borderRadius: '3px',
          border: '1px solid #e0e0e0'
        }}>
          {oscillatorConfig.title}
        </div>
      )}
      
      {/* Chart container */}
      <div 
        ref={chartContainerRef} 
        style={{ width: '100%', height: '100%' }}
      />
    
      {/* Loading overlay */}
      {isLoading && showLoadingOverlay && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <LoadingSpinner 
            size="large" 
            message="Loading oscillator data..." 
          />
        </div>
      )}
      
      {/* Error overlay */}
      {error && showErrorOverlay && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem'
        }}>
          <ErrorDisplay 
            error={error}
            title="Oscillator Chart Error"
            compact={true}
          />
        </div>
      )}
      
      {/* Empty state */}
      {!isLoading && !error && (!oscillatorData || oscillatorData.indicators.length === 0) && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <EmptyState 
            title="No oscillator indicators to display"
            description="Add an oscillator indicator from the sidebar"
            compact={true}
          />
        </div>
      )}
      
      {/* Fuzzy Overlay */}
      <FuzzyOverlay
        chartInstance={chartRef.current}
        fuzzyData={fuzzyData || null}
        visible={fuzzyVisible}
        opacity={fuzzyOpacity}
        colorScheme={fuzzyColorScheme}
        indicatorId="oscillator-chart"
        preserveTimeScale={preserveTimeScale}
      />
    </div>
  );
};

export default OscillatorChart;