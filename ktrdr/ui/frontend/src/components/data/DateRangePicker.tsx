import React, { useState } from 'react';
import { Input } from '../common';

interface DateRangePickerProps {
  className?: string;
  disabled?: boolean;
  startDate?: string;
  endDate?: string;
  onDateRangeChange?: (range: { startDate: string; endDate: string }) => void;
}

export const DateRangePicker: React.FC<DateRangePickerProps> = ({
  className = '',
  disabled = false,
  startDate = '',
  endDate = '',
  onDateRangeChange
}) => {
  const [start, setStart] = useState(startDate);
  const [end, setEnd] = useState(endDate);

  // Handle start date change
  const handleStartChange = (value: string) => {
    setStart(value);
    if (onDateRangeChange) {
      onDateRangeChange({ startDate: value, endDate: end });
    }
  };

  // Handle end date change
  const handleEndChange = (value: string) => {
    setEnd(value);
    if (onDateRangeChange) {
      onDateRangeChange({ startDate: start, endDate: value });
    }
  };

  return (
    <div className={`date-range-picker ${className}`}>
      <div className="date-range-inputs">
        <Input
          id="start-date"
          label="Start Date"
          type="date"
          value={start}
          onChange={handleStartChange}
          disabled={disabled}
          placeholder="YYYY-MM-DD"
          helperText="Start of data range"
        />
        <Input
          id="end-date"
          label="End Date"
          type="date"
          value={end}
          onChange={handleEndChange}
          disabled={disabled}
          placeholder="YYYY-MM-DD"
          helperText="End of data range"
        />
      </div>
    </div>
  );
};

export default DateRangePicker;