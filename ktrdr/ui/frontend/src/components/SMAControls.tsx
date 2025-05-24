import { FC, useState } from 'react';

interface SMAControlsProps {
  onAddSMA: (period: number) => void;
  isLoading?: boolean;
}

const SMAControls: FC<SMAControlsProps> = ({ onAddSMA, isLoading = false }) => {
  const [period, setPeriod] = useState(20);

  const handleAddSMA = () => {
    if (period >= 2 && period <= 500) {
      onAddSMA(period);
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      alignItems: 'center', 
      gap: '0.5rem',
      padding: '0.5rem',
      backgroundColor: '#f5f5f5',
      borderRadius: '4px',
      border: '1px solid #ddd'
    }}>
      <label style={{ fontSize: '0.9rem', fontWeight: 'bold' }}>
        SMA Period:
      </label>
      <input
        type="number"
        min="2"
        max="500"
        value={period}
        onChange={(e) => setPeriod(parseInt(e.target.value) || 20)}
        style={{
          width: '60px',
          padding: '0.25rem',
          border: '1px solid #ccc',
          borderRadius: '3px',
          textAlign: 'center'
        }}
        disabled={isLoading}
      />
      <button
        onClick={handleAddSMA}
        disabled={isLoading || period < 2 || period > 500}
        style={{
          padding: '0.25rem 0.75rem',
          backgroundColor: isLoading ? '#ccc' : '#1976d2',
          color: 'white',
          border: 'none',
          borderRadius: '3px',
          cursor: isLoading ? 'not-allowed' : 'pointer',
          fontSize: '0.85rem'
        }}
      >
        {isLoading ? 'Adding...' : 'Add SMA'}
      </button>
    </div>
  );
};

export default SMAControls;