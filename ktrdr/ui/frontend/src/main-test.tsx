/**
 * Test main file to verify chart utils imports
 */
import { 
  formatCandlestickData, 
  formatLineData, 
  formatHistogramData,
  formatVolumeData,
  createChartOptions
} from './utils/charts';

// Log to console to verify imports
console.log('✅ Chart utils imports are working properly!');
console.log('formatCandlestickData:', typeof formatCandlestickData);
console.log('formatLineData:', typeof formatLineData);
console.log('formatVolumeData:', typeof formatVolumeData);
console.log('createChartOptions:', typeof createChartOptions);

// Simple render function
function render() {
  const container = document.getElementById('app');
  if (container) {
    container.innerHTML = `
      <div>
        <h1>Chart Utils Import Test</h1>
        <div id="results">
          <p>✅ Imports successful! Check console for details.</p>
        </div>
      </div>
    `;
  }
}

// Run the test
render();