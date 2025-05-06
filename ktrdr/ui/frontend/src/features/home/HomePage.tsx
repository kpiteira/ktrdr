import React from 'react';

export const HomePage: React.FC = () => {
  return (
    <div className="home-page">
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">Welcome to KTRDR</h1>
        
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4">Trading Research Platform</h2>
          <p className="mb-4">
            KTRDR is an advanced trading research and analysis platform designed to help you make data-driven trading decisions.
          </p>
          <p>
            Use the navigation menu to explore different features of the platform.
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-3">Symbols</h3>
            <p>Browse available trading symbols and access detailed chart data.</p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-3">Charts</h3>
            <p>Visualize price data with technical indicators and custom overlays.</p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-3">Data Transformation</h3>
            <p>Transform and compare different data processing techniques.</p>
          </div>
          
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold mb-3">Strategies</h3>
            <p>Explore trading strategies and their historical performance.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HomePage;