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
  } 
  
  // For other timeframes
  return {
    timeVisible: true,
    secondsVisible: false,
    tickMarkFormatter: (time: number) => {
      const date = new Date(time * 1000);
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    }
  };
};