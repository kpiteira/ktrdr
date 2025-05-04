/**
 * Test file to verify that the chart utilities can be imported correctly
 */
import { 
  formatCandlestickData, 
  formatLineData, 
  formatHistogramData,
  formatVolumeData,
  createChartOptions
} from './utils/charts';

// Just import the functions to check if there are any conflicts
console.log('✅ Imports are working properly!');
console.log('formatCandlestickData:', typeof formatCandlestickData);
console.log('formatLineData:', typeof formatLineData);
console.log('formatVolumeData:', typeof formatVolumeData);
console.log('createChartOptions:', typeof createChartOptions);