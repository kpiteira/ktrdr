import React, { useEffect, useState } from 'react';
import { useDataSelection } from '../../store/hooks';
import { LoadingSpinner, ErrorMessage, Select } from '../common';

interface TimeframeSelectorProps {
  className?: string;
  disabled?: boolean;
  onTimeframeChange?: (timeframe: string) => void;
}

// Define potential timeframe object structure
interface TimeframeObject {
  id?: string;
  value?: string;
  name?: string;
  label?: string;
  [key: string]: any; // Allow other properties
}

// Type for timeframe which can be string or object
type TimeframeType = string | TimeframeObject;

export const TimeframeSelector: React.FC<TimeframeSelectorProps> = ({
  className = '',
  disabled = false,
  onTimeframeChange
}) => {
  const {
    timeframes,
    currentTimeframe,
    selectTimeframe
  } = useDataSelection();

  const [isLoading, setIsLoading] = useState(true);

  // Monitor loading state
  useEffect(() => {
    // If timeframes is null for too long, assume API error
    const timer = setTimeout(() => {
      setIsLoading(false);
    }, 2000); // 2 second timeout

    // If timeframes load successfully, clear loading state
    if (timeframes) {
      setIsLoading(false);
      clearTimeout(timer);
    }

    return () => clearTimeout(timer);
  }, [timeframes]);

  // Handle timeframe selection
  const handleChange = (value: string) => {
    selectTimeframe(value);
    if (onTimeframeChange) {
      onTimeframeChange(value);
    }
  };

  // If still loading, show spinner
  if (isLoading) {
    return <LoadingSpinner size="small" />;
  }

  // If API error / no timeframes received
  if (!timeframes) {
    return (
      <ErrorMessage 
        message="Failed to load timeframes from API" 
        details="Please check your backend connection and reload the page." 
      />
    );
  }

  // Check if we have valid timeframes to display
  if (!Array.isArray(timeframes) || timeframes.length === 0) {
    return <ErrorMessage message="No timeframes available" />;
  }

  return (
    <div className={`timeframe-selector ${className}`}>
      <Select
        id="timeframe-select"
        label="Timeframe"
        value={currentTimeframe || ''}
        options={timeframes.map((t: TimeframeType) => {
          // Handle both string and object formats for timeframes
          if (typeof t === 'string') {
            return { value: t, label: t };
          } else if (typeof t === 'object' && t !== null) {
            const timeframeObj = t as TimeframeObject;
            const timeframeId = timeframeObj.id || timeframeObj.value || String(t);
            const timeframeLabel = timeframeObj.name || timeframeObj.label || String(t);
            return { value: timeframeId, label: timeframeLabel };
          }
          // Fallback for unexpected types
          return { value: String(t), label: String(t) };
        })}
        onChange={handleChange}
        placeholder="Select a timeframe"
        disabled={disabled}
      />
    </div>
  );
};

export default TimeframeSelector;