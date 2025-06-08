/**
 * Custom hook for managing trading hours filtering state
 */

import { useState, useCallback, useMemo } from 'react';
import type { DataFilters, SymbolInfo } from '../api/types';

interface TradingHoursFilterState {
  tradingHoursOnly: boolean;
  includeExtended: boolean;
}

interface TradingHoursFilterHook {
  filters: TradingHoursFilterState;
  apiFilters: DataFilters | undefined;
  setTradingHoursOnly: (enabled: boolean) => void;
  setIncludeExtended: (enabled: boolean) => void;
  toggleTradingHoursOnly: () => void;
  toggleIncludeExtended: () => void;
  reset: () => void;
  isMarketOpen: (timestamp: Date, symbol?: SymbolInfo) => boolean;
  getMarketStatus: (timestamp: Date, symbol?: SymbolInfo) => string;
  formatInExchangeTime: (timestamp: Date, symbol?: SymbolInfo) => string;
}

/**
 * Hook for managing trading hours filtering and timezone utilities
 */
export const useTradingHoursFilter = (
  initialTradingHoursOnly: boolean = false,
  initialIncludeExtended: boolean = false
): TradingHoursFilterHook => {
  const [filters, setFilters] = useState<TradingHoursFilterState>({
    tradingHoursOnly: initialTradingHoursOnly,
    includeExtended: initialIncludeExtended,
  });

  // Convert to API format - only include if trading hours filtering is enabled
  const apiFilters = useMemo((): DataFilters | undefined => {
    if (!filters.tradingHoursOnly) {
      return undefined;
    }
    return {
      trading_hours_only: filters.tradingHoursOnly,
      include_extended: filters.includeExtended,
    };
  }, [filters.tradingHoursOnly, filters.includeExtended]);

  const setTradingHoursOnly = useCallback((enabled: boolean) => {
    setFilters(prev => ({
      ...prev,
      tradingHoursOnly: enabled,
    }));
  }, []);

  const setIncludeExtended = useCallback((enabled: boolean) => {
    setFilters(prev => ({
      ...prev,
      includeExtended: enabled,
    }));
  }, []);

  const toggleTradingHoursOnly = useCallback(() => {
    setFilters(prev => ({
      ...prev,
      tradingHoursOnly: !prev.tradingHoursOnly,
    }));
  }, []);

  const toggleIncludeExtended = useCallback(() => {
    setFilters(prev => ({
      ...prev,
      includeExtended: !prev.includeExtended,
    }));
  }, []);

  const reset = useCallback(() => {
    setFilters({
      tradingHoursOnly: false,
      includeExtended: false,
    });
  }, []);

  // Utility function to check if market is open at a given timestamp
  const isMarketOpen = useCallback((timestamp: Date, symbol?: SymbolInfo): boolean => {
    if (!symbol?.trading_hours) {
      // Default to US market hours if no trading hours available
      const hour = timestamp.getUTCHours();
      const day = timestamp.getUTCDay();
      
      // Convert UTC to EST (approximate)
      const estHour = (hour - 5 + 24) % 24;
      
      // Weekday and between 9:30 AM - 4:00 PM EST
      return day >= 1 && day <= 5 && estHour >= 9.5 && estHour <= 16;
    }

    const tradingHours = symbol.trading_hours;
    const day = timestamp.getUTCDay();
    
    // Check if it's a trading day
    if (!tradingHours.trading_days.includes(day)) {
      return false;
    }

    // Convert timestamp to exchange timezone
    const exchangeTime = formatInExchangeTime(timestamp, symbol);
    const timeStr = exchangeTime.split(' ')[1] || '';
    const [hourStr, minuteStr] = timeStr.split(':');
    const hour = parseInt(hourStr, 10);
    const minute = parseInt(minuteStr, 10);
    const totalMinutes = hour * 60 + minute;

    // Check regular hours
    const regularStart = tradingHours.regular_hours.start;
    const regularEnd = tradingHours.regular_hours.end;
    const [startHour, startMin] = regularStart.split(':').map(Number);
    const [endHour, endMin] = regularEnd.split(':').map(Number);
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = endHour * 60 + endMin;

    if (startMinutes <= endMinutes) {
      // Normal case (e.g., 9:30 - 16:00)
      return totalMinutes >= startMinutes && totalMinutes <= endMinutes;
    } else {
      // Crosses midnight (e.g., 22:00 - 21:59 for forex)
      return totalMinutes >= startMinutes || totalMinutes <= endMinutes;
    }
  }, []);

  // Get market status (Open, Closed, Pre-Market, After-Hours)
  const getMarketStatus = useCallback((timestamp: Date, symbol?: SymbolInfo): string => {
    if (!symbol?.trading_hours) {
      return isMarketOpen(timestamp, symbol) ? 'Open' : 'Closed';
    }

    const tradingHours = symbol.trading_hours;
    const day = timestamp.getUTCDay();
    
    // Check if it's a trading day
    if (!tradingHours.trading_days.includes(day)) {
      return 'Closed';
    }

    // Convert timestamp to exchange timezone
    const exchangeTime = formatInExchangeTime(timestamp, symbol);
    const timeStr = exchangeTime.split(' ')[1] || '';
    const [hourStr, minuteStr] = timeStr.split(':');
    const hour = parseInt(hourStr, 10);
    const minute = parseInt(minuteStr, 10);
    const totalMinutes = hour * 60 + minute;

    // Check regular hours first
    const regularStart = tradingHours.regular_hours.start;
    const regularEnd = tradingHours.regular_hours.end;
    const [startHour, startMin] = regularStart.split(':').map(Number);
    const [endHour, endMin] = regularEnd.split(':').map(Number);
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = endHour * 60 + endMin;

    if (startMinutes <= endMinutes) {
      if (totalMinutes >= startMinutes && totalMinutes <= endMinutes) {
        return 'Open';
      }
    } else {
      if (totalMinutes >= startMinutes || totalMinutes <= endMinutes) {
        return 'Open';
      }
    }

    // Check extended hours
    for (const extendedSession of tradingHours.extended_hours) {
      const [extStartHour, extStartMin] = extendedSession.start.split(':').map(Number);
      const [extEndHour, extEndMin] = extendedSession.end.split(':').map(Number);
      const extStartMinutes = extStartHour * 60 + extStartMin;
      const extEndMinutes = extEndHour * 60 + extEndMin;

      if (extStartMinutes <= extEndMinutes) {
        if (totalMinutes >= extStartMinutes && totalMinutes <= extEndMinutes) {
          return extendedSession.name;
        }
      } else {
        if (totalMinutes >= extStartMinutes || totalMinutes <= extEndMinutes) {
          return extendedSession.name;
        }
      }
    }

    return 'Closed';
  }, [isMarketOpen]);

  // Format timestamp in exchange timezone
  const formatInExchangeTime = useCallback((timestamp: Date, symbol?: SymbolInfo): string => {
    if (!symbol?.trading_hours?.timezone) {
      // Default to UTC if no timezone info
      return timestamp.toISOString().replace('T', ' ').replace('Z', ' UTC');
    }

    try {
      // Use Intl.DateTimeFormat for timezone conversion
      const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: symbol.trading_hours.timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      });

      return formatter.format(timestamp);
    } catch (error) {
      console.warn(`Failed to format timestamp for timezone ${symbol.trading_hours.timezone}:`, error);
      return timestamp.toISOString().replace('T', ' ').replace('Z', ' UTC');
    }
  }, []);

  return {
    filters,
    apiFilters,
    setTradingHoursOnly,
    setIncludeExtended,
    toggleTradingHoursOnly,
    toggleIncludeExtended,
    reset,
    isMarketOpen,
    getMarketStatus,
    formatInExchangeTime,
  };
};