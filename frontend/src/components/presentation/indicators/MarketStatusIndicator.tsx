/**
 * Market Status Indicator
 * Shows current market status with visual indicator
 */

import React from 'react';
import type { SymbolInfo } from '../../../api/types';

interface MarketStatusIndicatorProps {
  symbol?: SymbolInfo;
  currentTime?: Date;
  className?: string;
  showDetails?: boolean;
}

export const MarketStatusIndicator: React.FC<MarketStatusIndicatorProps> = ({
  symbol,
  currentTime = new Date(),
  className = '',
  showDetails = false,
}) => {
  if (!symbol?.trading_hours) {
    return (
      <div className={`flex items-center space-x-2 ${className}`}>
        <div className="w-2 h-2 bg-gray-400 rounded-full" />
        <span className="text-xs text-gray-500">Unknown</span>
      </div>
    );
  }

  const tradingHours = symbol.trading_hours;
  
  // Get market status
  const getMarketStatus = () => {
    const day = currentTime.getUTCDay();
    
    // Check if it's a trading day
    if (!tradingHours.trading_days.includes(day)) {
      return { status: 'Closed', reason: 'Weekend', color: 'red' };
    }

    // For now, use a simple UTC-based check
    // In a real implementation, you'd want proper timezone conversion
    const hour = currentTime.getUTCHours();
    const minute = currentTime.getUTCMinutes();
    const totalMinutes = hour * 60 + minute;

    // Parse regular hours
    const [startHour, startMin] = tradingHours.regular_hours.start.split(':').map(Number);
    const [endHour, endMin] = tradingHours.regular_hours.end.split(':').map(Number);
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = endHour * 60 + endMin;

    // Check if in regular hours
    if (startMinutes <= endMinutes) {
      // Normal case (e.g., 9:30 - 16:00)
      if (totalMinutes >= startMinutes && totalMinutes <= endMinutes) {
        return { status: 'Open', reason: 'Regular Hours', color: 'green' };
      }
    } else {
      // Crosses midnight (e.g., 22:00 - 21:59 for forex)
      if (totalMinutes >= startMinutes || totalMinutes <= endMinutes) {
        return { status: 'Open', reason: 'Regular Hours', color: 'green' };
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
          return { status: extendedSession.name, reason: 'Extended Hours', color: 'yellow' };
        }
      } else {
        if (totalMinutes >= extStartMinutes || totalMinutes <= extEndMinutes) {
          return { status: extendedSession.name, reason: 'Extended Hours', color: 'yellow' };
        }
      }
    }

    return { status: 'Closed', reason: 'Outside Hours', color: 'red' };
  };

  const { status, reason, color } = getMarketStatus();

  const colorClasses = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
    gray: 'bg-gray-400',
  };

  const textColorClasses = {
    green: 'text-green-700 dark:text-green-400',
    yellow: 'text-yellow-700 dark:text-yellow-400',
    red: 'text-red-700 dark:text-red-400',
    gray: 'text-gray-600 dark:text-gray-400',
  };

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      <div className={`w-2 h-2 rounded-full ${colorClasses[color]}`} />
      <div className="flex flex-col">
        <span className={`text-xs font-medium ${textColorClasses[color]}`}>
          {status}
        </span>
        {showDetails && (
          <span className="text-xs text-gray-500 dark:text-gray-400">
            {reason}
          </span>
        )}
      </div>
      {showDetails && symbol.exchange && (
        <span className="text-xs text-gray-500 dark:text-gray-400">
          ({symbol.exchange})
        </span>
      )}
    </div>
  );
};