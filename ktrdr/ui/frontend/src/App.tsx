import React from 'react';
import { Provider } from 'react-redux';
import { store } from '@/store';
import { ThemeProvider, MainLayout } from '@/components/layouts';
import { NotificationProvider, NotificationContainer, DevModeIndicator } from '@/components/common';
import { Card, Button } from '@/components/common';
import { useNotification } from '@/components/common';
import { DataViewer } from '@/examples';
import { config } from '@/config';

function App() {
  const { addNotification } = useNotification();

  const showSampleNotification = () => {
    addNotification({
      message: 'This is a sample notification',
      type: 'info',
      duration: 5000
    });
  };

  return (
    <Provider store={store}>
      <ThemeProvider>
        <NotificationProvider>
          <MainLayout>
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
              </ul>
              <Button 
                onClick={showSampleNotification}
                variant="primary"
                style={{ marginTop: '16px', marginRight: '16px' }}
              >
                Show Sample Notification
              </Button>
            </Card>
            
            {/* API Integration Test Component */}
            <div style={{ marginTop: '32px' }}>
              <DataViewer />
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
