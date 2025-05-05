import React from 'react';
import { Card } from '../components/common/Card';

/**
 * SymbolsPage displays available trading symbols.
 */
const SymbolsPage: React.FC = () => {
  return (
    <div className="symbols-page">
      <h1>Symbols</h1>
      
      <Card>
        <p>This is a placeholder for the Symbols page that will display a list of available trading symbols.</p>
      </Card>
    </div>
  );
};

export default SymbolsPage;