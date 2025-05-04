import React, { useState, useEffect } from 'react';
import { TabItem } from '@/types/ui';

interface TabsProps {
  items?: TabItem[];
  tabs?: TabItem[];  // For backward compatibility
  activeTab?: string;
  defaultTab?: string;
  onChange?: (key: string) => void;
  className?: string;
}

export const Tabs: React.FC<TabsProps> = ({
  items,
  tabs,
  activeTab: controlledActiveTab,
  defaultTab,
  onChange,
  className = '',
}) => {
  // Determine which array of tabs to use (support both items and tabs props)
  const tabItems = items || tabs || [];
  
  const [internalActiveTab, setInternalActiveTab] = useState<string>(() => {
    // If activeTab is controlled from outside, use that
    if (controlledActiveTab) return controlledActiveTab;
    // Otherwise use defaultTab or first tab
    return defaultTab || (tabItems.length > 0 ? tabItems[0].key : '');
  });

  // Update internal active tab when controlled active tab changes
  useEffect(() => {
    if (controlledActiveTab !== undefined) {
      setInternalActiveTab(controlledActiveTab);
    }
  }, [controlledActiveTab]);

  // Update internal active tab when default tab changes and not controlled
  useEffect(() => {
    if (defaultTab && controlledActiveTab === undefined) {
      setInternalActiveTab(defaultTab);
    }
  }, [defaultTab, controlledActiveTab]);

  // Determine the current active tab (controlled or internal)
  const currentActiveTab = controlledActiveTab !== undefined 
    ? controlledActiveTab 
    : internalActiveTab;

  const handleTabClick = (key: string) => {
    if (controlledActiveTab === undefined) {
      // Only update internal state if not controlled
      setInternalActiveTab(key);
    }
    onChange?.(key);
  };

  const getActiveTabContent = () => {
    const tab = tabItems.find(tab => tab.key === currentActiveTab);
    return tab?.content || null;
  };

  const tabsClasses = [
    'tabs-container',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={tabsClasses}>
      <div className="tabs-header" role="tablist">
        {tabItems.map((tab) => (
          <button
            key={tab.key}
            className={`tab ${currentActiveTab === tab.key ? 'tab-active' : ''}`}
            onClick={() => handleTabClick(tab.key)}
            role="tab"
            aria-selected={currentActiveTab === tab.key}
            aria-controls={`panel-${tab.key}`}
            id={`tab-${tab.key}`}
            tabIndex={currentActiveTab === tab.key ? 0 : -1}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {getActiveTabContent() && (
        <div 
          className="tabs-content"
          role="tabpanel"
          id={`panel-${currentActiveTab}`}
          aria-labelledby={`tab-${currentActiveTab}`}
        >
          {getActiveTabContent()}
        </div>
      )}
    </div>
  );
};