import React, { useState } from 'react';
import { Provider } from 'react-redux';
import { store } from '@/store';
import { ThemeProvider, MainLayout } from '@/components/layouts';
import { NotificationProvider, NotificationContainer, DevModeIndicator } from '@/components/common';
import { Card, Button, Tabs } from '@/components/common';
import { useNotification } from '@/components/common';
import { DataSelectionPage, ChartExamplePage } from '@/pages';
import { config } from '@/config';

function App() {
  const { addNotification } = useNotification();
  const [activeTab, setActiveTab] = useState<string>('welcome');

  const showSampleNotification = () => {
    addNotification({
      message: 'This is a sample notification',
      type: 'info',
      duration: 5000
    });
  };
  
  const navigationTabs = [
    { key: 'welcome', label: 'Welcome' },
    { key: 'data', label: 'Data Selection' },
    { key: 'charts', label: 'Chart Example' },
  ];

  // Render the active page based on the selected tab
  const renderActivePage = () => {
    switch (activeTab) {
      case 'welcome':
        return (
          <Card 
            title="Welcome to KTRDR Trading Platform" 
            subtitle="Frontend infrastructure implementation"
          >
            <p>This is the initial setup of the KTRDR frontend application.</p>
            <p>The following components have been implemented:</p>
            <ul>
              <li>Theme system with dark/light mode</li>
              <li>Layout components (Header, Sidebar, MainLayout)</li>
              <li>Common UI components (Button, Input, Select, Card, Tabs)</li>
              <li>Error and loading state components</li>
              <li>Notification system</li>
              <li>Developer mode indicators</li>
              <li>API client and data access layer</li>
              <li>Redux state management</li>
              <li>Data selection components (Task 7.6)</li>
              <li>Chart visualization components (Task 8.1)</li>
            </ul>
            <Button 
              onClick={showSampleNotification}
              variant="primary"
              style={{ marginTop: '16px', marginRight: '16px' }}
            >
              Show Sample Notification
            </Button>
          </Card>
        );
      case 'data':
        return <DataSelectionPage />;
      case 'charts':
        return <ChartExamplePage />;
      default:
        return null;
    }
  };

  return (
    <Provider store={store}>
      <ThemeProvider>
        <NotificationProvider>
          <MainLayout>
            <Card className="navigation-tabs">
              <Tabs 
                items={navigationTabs.map(tab => ({
                  key: tab.key,
                  label: tab.label,
                  content: null
                }))}
                activeTab={activeTab}
                onChange={setActiveTab}
              />
            </Card>
            
            <div style={{ marginTop: '16px' }}>
              {renderActivePage()}
            </div>
          </MainLayout>
          <NotificationContainer />
          <DevModeIndicator position="bottom-right" />
        </NotificationProvider>
      </ThemeProvider>
    </Provider>
  );
}

export default App;
