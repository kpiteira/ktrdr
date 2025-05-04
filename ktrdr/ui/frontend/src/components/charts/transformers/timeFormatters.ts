/**
 * Utilities for formatting time and dates for charts
 */

/**
 * Converts a date to ISO string for chart time scale
 * 
 * @param date Date to format (string, number, or Date object)
 * @returns ISO date string in YYYY-MM-DD format
 */
export const formatDateToISOString = (date: string | number | Date): string => {
  const dateObj = typeof date === 'string' ? new Date(date) : 
                  typeof date === 'number' ? new Date(date) : date;
  
  return dateObj.toISOString().split('T')[0];
};

/**
 * Formats time with different levels of precision based on timeframe
 * 
 * @param date Date to format
 * @param timeframe Chart timeframe (e.g. '1m', '1h', '1d')
 * @returns Formatted time string
 */
export const formatTimeForDisplay = (date: string | number | Date, timeframe: string): string => {
  const dateObj = typeof date === 'string' ? new Date(date) : 
                  typeof date === 'number' ? new Date(date) : date;
  
  // Determine precision based on timeframe
  if (timeframe.toLowerCase().includes('m')) {
    // Minute timeframe - show date and time with minutes
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(dateObj);
  } else if (timeframe.toLowerCase().includes('h')) {
    // Hour timeframe - show date and hour
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit'
    }).format(dateObj);
  } else {
    // Daily or larger timeframe - show just the date
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    }).format(dateObj);
  }
};

/**
 * Formats time range for chart description
 * 
 * @param startDate Start date
 * @param endDate End date
 * @param timeframe Chart timeframe
 * @returns Formatted time range string
 */
export const formatTimeRange = (
  startDate: string | number | Date, 
  endDate: string | number | Date, 
  timeframe: string
): string => {
  return `${formatTimeForDisplay(startDate, timeframe)} to ${formatTimeForDisplay(endDate, timeframe)}`;
};

/**
 * Formats timeframe string for display
 * 
 * @param timeframe Timeframe code (e.g., '1d', '4h', '15m')
 * @returns Formatted timeframe string
 */
export const formatTimeframeForDisplay = (timeframe: string): string => {
  if (!timeframe) return 'Unknown';
  
  const match = timeframe.match(/(\d+)([mhdwMy])/i);
  if (!match) return timeframe.toUpperCase();
  
  const [_, value, unit] = match;
  
  switch (unit.toLowerCase()) {
    case 'm': return `${value} Minute${value !== '1' ? 's' : ''}`;
    case 'h': return `${value} Hour${value !== '1' ? 's' : ''}`;
    case 'd': return `${value} Day${value !== '1' ? 's' : ''}`;
    case 'w': return `${value} Week${value !== '1' ? 's' : ''}`;
    case 'M': return `${value} Month${value !== '1' ? 's' : ''}`;
    case 'y': return `${value} Year${value !== '1' ? 's' : ''}`;
    default: return timeframe.toUpperCase();
  }
};

/**
 * Gets appropriate tick marks based on timeframe for chart time scale
 * 
 * @param timeframe Chart timeframe
 * @returns Time scale configuration
 */
export const getTimeScaleConfiguration = (timeframe: string): any => {
  if (timeframe.toLowerCase().includes('m')) {
    // For minute timeframes
    return {
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter: (time: number) => {
        const date = new Date(time * 1000);
        return date.getMinutes() === 0 ? 
          date.getHours() + ':00' : 
          date.getMinutes() + '';
      }
    };
  } else if (timeframe.toLowerCase().includes('h')) {
    // For hour timeframes
    return {
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter: (time: number) => {
        const date = new Date(time * 1000);
        return date.getHours() + ':00';
      }
    };
  } else if (timeframe.toLowerCase().includes('d')) {
    // For daily timeframes
    return {
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter: (time: number) => {
        const date = new Date(time * 1000);
        return `${date.getMonth() + 1}/${date.getDate()}`;
      }
    };
  } else {
    // For weekly or larger timeframes
    return {
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter: (time: number) => {
        const date = new Date(time * 1000);
        return `${date.getMonth() + 1}/${date.getDate()}/${date.getFullYear()}`;
      }
    };
  }
};