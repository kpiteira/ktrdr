import React, { useRef, useEffect } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';
import { useTheme } from '../../../app/ThemeProvider';
import '../ChartContainer.css';

interface ChartContainerProps {
  children?: React.ReactNode;
  className?: string;
  width?: number;
  height?: number;
}

/**
 * Base chart container component that provides common chart functionality
 */
const ChartContainer: React.FC<ChartContainerProps> = ({
  children,
  className = '',
  width,
  height = 400,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!containerRef.current) return;
    
    // Initialize chart instance
    const chart = createChart(containerRef.current, {
      width: width || containerRef.current.clientWidth,
      height: height,
      layout: {
        background: { color: theme === 'dark' ? '#151924' : '#ffffff' },
        textColor: theme === 'dark' ? '#d1d4dc' : '#333333',
      },
    });
    
    chartRef.current = chart;
    
    return () => {
      chart.remove();
    };
  }, [width, height, theme]);

  return (
    <div className={`chart-container ${className}`}>
      <div 
        ref={containerRef} 
        className="chart-container-inner"
        style={{ width: '100%', height: `${height}px` }} 
      />
      {children}
    </div>
  );
};

export default ChartContainer;