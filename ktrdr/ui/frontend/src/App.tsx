import { FC } from 'react';
import BasicChart from './components/BasicChart';
import ErrorBoundary from './components/ErrorBoundary';
import './App.css';


const App: FC = () => {
  return (
    <ErrorBoundary>
      <div className="App">
        <header className="App-header">
          <h1>KTRDR Trading Research - MVP Slice 1</h1>
        </header>
        <main className="App-main">
          <ErrorBoundary>
            <BasicChart />
          </ErrorBoundary>
        </main>
      </div>
    </ErrorBoundary>
  );
};

export default App;