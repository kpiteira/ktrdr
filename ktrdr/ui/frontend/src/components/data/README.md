# Data Selection Components

This directory contains reusable components for data selection and visualization in the KTRDR frontend application. These components implement Task 7.6 from the KTRDR Phase 1 Task Breakdown.

## Component Overview

### Individual Components

- **SymbolSelector**: Select trading symbol from available options
- **TimeframeSelector**: Select time interval (1m, 5m, 1h, 1d, etc.)
- **DateRangePicker**: Select date range for historical data
- **DataLoadButton**: Load data with status feedback
- **DataPreview**: Display loaded data summary and samples

### Combined Components

- **DataSelectionPanel**: Combines all data selection controls in a single panel

## Usage Examples

### Basic Usage

```tsx
import { 
  SymbolSelector, 
  TimeframeSelector, 
  DateRangePicker,
  DataLoadButton 
} from '../components/data';

const MyComponent = () => {
  return (
    <div>
      <SymbolSelector />
      <TimeframeSelector />
      <DateRangePicker 
        startDate="2023-01-01"
        endDate="2023-12-31"
      />
      <DataLoadButton />
    </div>
  );
};
```

### Using the Complete Panel

```tsx
import { DataSelectionPanel, DataPreview } from '../components/data';

const MyComponent = () => {
  const handleDataLoaded = () => {
    console.log('Data loaded successfully');
  };

  return (
    <div>
      <DataSelectionPanel
        autoLoadMetadata={true}
        onDataLoaded={handleDataLoaded}
      />
      <DataPreview maxPreviewRows={5} />
    </div>
  );
};
```

## Component Props

### SymbolSelector

| Prop | Type | Description |
|------|------|-------------|
| className | string | Additional CSS class names |
| disabled | boolean | Whether the selector is disabled |
| onSymbolChange | (symbol: string) => void | Callback when symbol changes |

### TimeframeSelector

| Prop | Type | Description |
|------|------|-------------|
| className | string | Additional CSS class names |
| disabled | boolean | Whether the selector is disabled |
| onTimeframeChange | (timeframe: string) => void | Callback when timeframe changes |

### DateRangePicker

| Prop | Type | Description |
|------|------|-------------|
| className | string | Additional CSS class names |
| disabled | boolean | Whether the inputs are disabled |
| startDate | string | Initial start date (YYYY-MM-DD) |
| endDate | string | Initial end date (YYYY-MM-DD) |
| onDateRangeChange | (range: { startDate: string; endDate: string }) => void | Callback when dates change |

### DataLoadButton

| Prop | Type | Description |
|------|------|-------------|
| className | string | Additional CSS class names |
| dateRange | { startDate: string; endDate: string } | Date range for data loading |
| onDataLoaded | () => void | Callback when data is loaded |
| variant | 'primary' \| 'secondary' \| 'outline' | Button variant |
| size | 'small' \| 'medium' \| 'large' | Button size |

### DataPreview

| Prop | Type | Description |
|------|------|-------------|
| className | string | Additional CSS class names |
| maxPreviewRows | number | Maximum number of data rows to show |

### DataSelectionPanel

| Prop | Type | Description |
|------|------|-------------|
| className | string | Additional CSS class names |
| onDataLoaded | () => void | Callback when data is loaded |
| autoLoadMetadata | boolean | Whether to automatically load symbols and timeframes |

## Redux Integration

These components integrate with Redux via custom hooks:

- `useDataSelection`: For working with symbols and timeframes
- `useOhlcvData`: For loading and accessing OHLCV data
- `useThemeControl`: For theme settings

## Styling

Component styles are defined in `App.css` and follow the application's theme system with support for both light and dark modes.