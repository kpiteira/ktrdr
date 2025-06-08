/**
 * Trading Hours Filter Panel
 * Provides controls for filtering data to trading hours only
 */

import React from 'react';
import type { SymbolInfo } from '../../../api/types';

interface TradingHoursFilterPanelProps {
  symbol?: SymbolInfo;
  tradingHoursOnly: boolean;
  includeExtended: boolean;
  onToggleTradingHoursOnly: () => void;
  onToggleIncludeExtended: () => void;
  currentTime?: Date;
}

export const TradingHoursFilterPanel: React.FC<TradingHoursFilterPanelProps> = ({
  symbol,
  tradingHoursOnly,
  includeExtended,
  onToggleTradingHoursOnly,
  onToggleIncludeExtended,
  currentTime = new Date(),
}) => {
  const tradingHours = symbol?.trading_hours;

  // Get current market status
  const getMarketStatus = () => {
    if (!tradingHours) return 'Unknown';
    
    const day = currentTime.getUTCDay();
    if (!tradingHours.trading_days.includes(day)) {
      return 'Closed (Weekend)';
    }
    
    // Simple market hours check (this could be enhanced with proper timezone conversion)
    const hour = currentTime.getUTCHours();
    
    // Convert regular hours to check
    const [startHour] = tradingHours.regular_hours.start.split(':').map(Number);
    const [endHour] = tradingHours.regular_hours.end.split(':').map(Number);
    
    if (hour >= startHour && hour <= endHour) {
      return 'Open';
    }
    
    return 'Closed';
  };

  const marketStatus = getMarketStatus();

  return (
    <div className="trading-hours-filter-panel bg-gray-50 dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-900 dark:text-gray-100">
          Trading Hours Filter
        </h3>
        {symbol && (
          <div className="flex items-center space-x-2">
            <div
              className={`w-2 h-2 rounded-full ${
                marketStatus === 'Open'
                  ? 'bg-green-500'
                  : marketStatus.includes('Closed')
                  ? 'bg-red-500'
                  : 'bg-yellow-500'
              }`}
            />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              {marketStatus}
            </span>
          </div>
        )}
      </div>

      <div className="space-y-3">
        {/* Trading Hours Only Toggle */}
        <div className="flex items-center justify-between">
          <label className="flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={tradingHoursOnly}
              onChange={onToggleTradingHoursOnly}
              className="mr-2 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Trading hours only
            </span>
          </label>
        </div>

        {/* Extended Hours Toggle - only show if trading hours filter is enabled */}
        {tradingHoursOnly && (
          <div className="flex items-center justify-between ml-6">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={includeExtended}
                onChange={onToggleIncludeExtended}
                className="mr-2 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                Include extended hours
              </span>
            </label>
          </div>
        )}

        {/* Trading Hours Info */}
        {symbol?.trading_hours && (
          <div className="mt-4 p-3 bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-600">
            <div className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
              {symbol.exchange} Trading Hours ({tradingHours.timezone})
            </div>
            
            {/* Regular Hours */}
            <div className="text-xs text-gray-600 dark:text-gray-400 mb-1">
              <span className="font-medium">Regular:</span>{' '}
              {tradingHours.regular_hours.start} - {tradingHours.regular_hours.end}
            </div>
            
            {/* Extended Hours */}
            {tradingHours.extended_hours.length > 0 && (
              <div className="text-xs text-gray-600 dark:text-gray-400">
                <span className="font-medium">Extended:</span>
                <div className="ml-2">
                  {tradingHours.extended_hours.map((session, index) => (
                    <div key={index}>
                      {session.name}: {session.start} - {session.end}
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            {/* Trading Days */}
            <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              <span className="font-medium">Days:</span>{' '}
              {tradingHours.trading_days
                .map(day => ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][day])
                .join(', ')}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};