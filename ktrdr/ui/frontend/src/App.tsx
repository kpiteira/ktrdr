import React from 'react';
import { ThemeProvider, MainLayout } from '@/components/layouts';
import { NotificationProvider, NotificationContainer, DevModeIndicator } from '@/components/common';
import { Card, Button } from '@/components/common';
import { useNotification } from '@/components/common';

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
            </ul>
            <Button 
              onClick={showSampleNotification}
              variant="primary"
              style={{ marginTop: '16px' }}
            >
              Show Sample Notification
            </Button>
          </Card>
        </MainLayout>
        <NotificationContainer />
        <DevModeIndicator position="bottom-right" />
      </NotificationProvider>
    </ThemeProvider>
  );
}

export default App;
