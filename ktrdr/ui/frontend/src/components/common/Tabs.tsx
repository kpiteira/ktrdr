import React, { useState, useEffect } from 'react';
import { TabItem } from '@/types/ui';

interface TabsProps {
  tabs: TabItem[];
  defaultTab?: string;
  onChange?: (key: string) => void;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  tabs,
  defaultTab,
  onChange,
  className = '',
}) => {
  const [activeTab, setActiveTab] = useState<string>(() => {
    return defaultTab || (tabs.length > 0 ? tabs[0].key : '');
  });

  useEffect(() => {
    if (defaultTab) {
      setActiveTab(defaultTab);
    }
  }, [defaultTab]);

  const handleTabClick = (key: string) => {
    setActiveTab(key);
    onChange?.(key);
  };

  const getActiveTabContent = () => {
    const tab = tabs.find(tab => tab.key === activeTab);
    return tab ? tab.content : null;
  };

  const tabsClasses = [
    'tabs-container',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={tabsClasses}>
      <div className="tabs-header" role="tablist">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${activeTab === tab.key ? 'tab-active' : ''}`}
            onClick={() => handleTabClick(tab.key)}
            role="tab"
            aria-selected={activeTab === tab.key}
            aria-controls={`panel-${tab.key}`}
            id={`tab-${tab.key}`}
            tabIndex={activeTab === tab.key ? 0 : -1}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div 
        className="tabs-content"
        role="tabpanel"
        id={`panel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
      >
        {getActiveTabContent()}
      </div>
    </div>
  );
};