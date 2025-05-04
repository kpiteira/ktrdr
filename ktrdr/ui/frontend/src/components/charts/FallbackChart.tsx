import React, { useEffect, useRef, useState } from 'react';

/**
 * FallbackChart - A simple canvas-based chart implementation
 * that doesn't rely on external libraries
 */
const FallbackChart: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // Track the last known width to prevent resize loops
  const [lastWidth, setLastWidth] = useState<number>(0);

  // Sample data
  const data = [
    { date: '2023-01-01', value: 50 },
    { date: '2023-01-02', value: 55 },
    { date: '2023-01-03', value: 48 },
    { date: '2023-01-04', value: 52 },
    { date: '2023-01-05', value: 58 },
    { date: '2023-01-06', value: 62 },
    { date: '2023-01-07', value: 60 },
    { date: '2023-01-08', value: 65 },
    { date: '2023-01-09', value: 63 },
    { date: '2023-01-10', value: 70 },
    { date: '2023-01-11', value: 75 },
    { date: '2023-01-12', value: 72 },
    { date: '2023-01-13', value: 78 },
    { date: '2023-01-14', value: 80 },
    { date: '2023-01-15', value: 82 },
  ];

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set initial canvas size based on container
    const containerWidth = container.clientWidth;
    setLastWidth(containerWidth);
    
    // Apply size constraints directly to the container to prevent infinite growth
    container.style.maxWidth = '100%';
    container.style.boxSizing = 'border-box';
    
    // Set canvas size with a maximum width constraint
    canvas.width = Math.min(containerWidth, window.innerWidth);
    canvas.height = canvas.clientHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw chart
    drawLineChart(ctx, data, canvas.width, canvas.height);

    // Handle resize with ResizeObserver if available, with fallback to window resize events
    let resizeTimeout: NodeJS.Timeout | null = null;
    
    const handleResize = () => {
      if (resizeTimeout) {
        clearTimeout(resizeTimeout);
      }
      
      resizeTimeout = setTimeout(() => {
        if (canvas && container && ctx) {
          const newWidth = container.clientWidth;
          
          // Define safe boundaries
          const originalWidth = lastWidth || containerWidth;
          const minWidth = Math.max(100, originalWidth * 0.5); // At least 50% of original or 100px
          const maxWidth = Math.min(window.innerWidth * 0.95, 3000); // At most 95% of window or 3000px
          
          const safeWidth = Math.max(minWidth, Math.min(newWidth, maxWidth));
          
          // Only redraw if width changed significantly and is within reasonable bounds
          if (Math.abs(safeWidth - lastWidth) > 5) {
            console.log(`[FallbackChart] Resizing canvas: ${lastWidth}px -> ${safeWidth}px`);
            
            canvas.width = safeWidth;
            canvas.height = canvas.clientHeight;
            setLastWidth(safeWidth);
            
            // Redraw with new dimensions
            drawLineChart(ctx, data, canvas.width, canvas.height);
          }
        }
      }, 250);
    };

    // Use ResizeObserver if available for more reliable resize detection
    let resizeObserver: ResizeObserver | null = null;
    
    try {
      resizeObserver = new ResizeObserver(() => {
        handleResize();
      });
      
      if (container.parentElement) {
        resizeObserver.observe(container.parentElement);
      }
    } catch (error) {
      console.warn('ResizeObserver not supported, falling back to window resize events');
      // Fallback to window resize events
      window.addEventListener('resize', handleResize);
    }
    
    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      } else {
        window.removeEventListener('resize', handleResize);
      }
      
      if (resizeTimeout) {
        clearTimeout(resizeTimeout);
      }
    };
  }, [lastWidth]);

  const drawLineChart = (
    ctx: CanvasRenderingContext2D,
    data: { date: string; value: number }[],
    width: number,
    height: number
  ) => {
    // Extract values
    const values = data.map(item => item.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = maxValue - minValue;

    // Padding
    const padding = { left: 40, right: 20, top: 20, bottom: 30 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;

    // Background
    ctx.fillStyle = '#f5f5f5';
    ctx.fillRect(0, 0, width, height);

    // Draw axes
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    ctx.beginPath();
    
    // Y-axis
    ctx.moveTo(padding.left, padding.top);
    ctx.lineTo(padding.left, height - padding.bottom);
    
    // X-axis
    ctx.moveTo(padding.left, height - padding.bottom);
    ctx.lineTo(width - padding.right, height - padding.bottom);
    ctx.stroke();

    // Draw grid lines and labels
    ctx.strokeStyle = '#ddd';
    ctx.fillStyle = '#333';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ctx.font = '10px Arial';

    // Y-axis grid lines and labels
    const yGridCount = 5;
    for (let i = 0; i <= yGridCount; i++) {
      const y = padding.top + (chartHeight * i) / yGridCount;
      const value = maxValue - (range * i) / yGridCount;
      
      // Grid line
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      
      // Label
      ctx.fillText(value.toFixed(0), padding.left - 5, y);
    }

    // X-axis labels (every 3rd point)
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    for (let i = 0; i < data.length; i += 3) {
      const x = padding.left + (chartWidth * i) / (data.length - 1);
      const date = new Date(data[i].date);
      const label = `${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getDate().toString().padStart(2, '0')}`;
      
      ctx.fillText(label, x, height - padding.bottom + 5);
    }

    // Draw line
    ctx.strokeStyle = '#2196F3';
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let i = 0; i < data.length; i++) {
      const x = padding.left + (chartWidth * i) / (data.length - 1);
      const y = padding.top + chartHeight - ((data[i].value - minValue) / range) * chartHeight;
      
      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Draw points
    ctx.fillStyle = '#2196F3';
    for (let i = 0; i < data.length; i++) {
      const x = padding.left + (chartWidth * i) / (data.length - 1);
      const y = padding.top + chartHeight - ((data[i].value - minValue) / range) * chartHeight;
      
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    // Chart title
    ctx.fillStyle = '#333';
    ctx.font = 'bold 14px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText('Line Chart (Canvas Fallback)', width / 2, 5);
  };

  return (
    <div 
      ref={containerRef}
      className="fallback-chart"
      style={{ 
        width: '100%', 
        maxWidth: '100%',
        overflow: 'hidden',
        boxSizing: 'border-box',
        contain: 'paint layout'
      }}
    >
      <canvas 
        ref={canvasRef} 
        style={{ 
          width: '100%', 
          height: '300px',
          display: 'block',
          boxSizing: 'border-box',
          border: '1px solid #ddd',
          borderRadius: '4px',
          maxWidth: '100%' 
        }} 
      />
    </div>
  );
};

export default FallbackChart;