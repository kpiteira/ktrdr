import React from 'react';
import { useTheme } from './ThemeProvider';
import { useUI } from './hooks/useUI';
import { Link, useLocation } from 'react-router-dom';

interface MenuItem {
  id: string;
  label: string;
  icon?: React.ReactNode;
  path?: string;
  onClick?: () => void;
  items?: MenuItem[];
}

interface SidebarProps {
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ onClose }) => {
  const { theme } = useTheme();
  const { sidebarOpen: isOpen, toggleSidebar } = useUI();
  const location = useLocation();
  
  const handleClose = () => {
    toggleSidebar();
    if (onClose) onClose();
  };
  
  // Menu items for the sidebar
  const menuItems: MenuItem[] = [
    {
      id: 'symbols',
      label: 'Symbols',
      path: '/symbols',
      icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M9 5H7V7H5V9H7V11H9V9H11V7H9V5zM19 11h-2V9h-2v2h-2v2h2v2h2v-2h2v-2zM21 3H3C1.9 3 1 3.9 1 5v14c0 1.1 0.9 2 2 2h18c1.1 0 2-0.9 2-2V5c0-1.1-0.9-2-2-2zm0 16.01H3V4.99h18v14.02z" fill="currentColor" />
            </svg>,
    },
    {
      id: 'chart',
      label: 'Chart',
      path: '/chart',
      icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3.5 18.49L9.5 12.48L13.5 16.48L22 6.92001L20.59 5.51001L13.5 13.48L9.5 9.48001L2 16.99L3.5 18.49Z" fill="currentColor" />
            </svg>,
    },
    {
      id: 'data-transform',
      label: 'Data Transform',
      path: '/data-transform',
      icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3ZM9 17H7V10H9V17ZM13 17H11V7H13V17ZM17 17H15V13H17V17Z" fill="currentColor" />
            </svg>,
    },
    {
      id: 'strategies',
      label: 'Strategies',
      path: '/strategies',
      icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M15.9 18.45l6-6-6-6-1.4 1.4 3.6 3.6H2v2h16.1l-3.6 3.6 1.4 1.4zM20 6h2v12h-2z" fill="currentColor" />
            </svg>,
    },
    {
      id: 'data-selection',
      label: 'Data Selection',
      path: '/data-selection',
      icon: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z" fill="currentColor" />
            </svg>,
    },
  ];

  const renderMenuItem = (item: MenuItem, depth = 0) => {
    const hasSubMenu = item.items && item.items.length > 0;
    const isActive = item.path && location.pathname === item.path;
    
    const menuItemContent = (
      <div className={`menu-item-content ${isActive ? 'active' : ''}`}>
        {item.icon && <span className="menu-item-icon">{item.icon}</span>}
        <span className="menu-item-label">{item.label}</span>
      </div>
    );
    
    return (
      <li key={item.id} className={`menu-item depth-${depth} ${isActive ? 'active' : ''}`}>
        {item.path ? (
          <Link to={item.path} onClick={item.onClick}>
            {menuItemContent}
          </Link>
        ) : (
          <div onClick={item.onClick}>
            {menuItemContent}
          </div>
        )}
        {hasSubMenu && (
          <ul className="submenu">
            {item.items?.map(subItem => renderMenuItem(subItem, depth + 1))}
          </ul>
        )}
      </li>
    );
  };

  return (
    <div className={`sidebar ${isOpen ? 'open' : 'closed'} ${theme === 'dark' ? 'sidebar-dark' : 'sidebar-light'}`}>
      <div className="sidebar-header">
        <h2>KTRDR</h2>
        <button className="close-sidebar" onClick={handleClose} aria-label="Close sidebar">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M19 6.41L17.59 5L12 10.59L6.41 5L5 6.41L10.59 12L5 17.59L6.41 19L12 13.41L17.59 19L19 17.59L13.41 12L19 6.41Z" fill="currentColor" />
          </svg>
        </button>
      </div>
      <nav className="sidebar-nav">
        <ul className="menu">
          {menuItems.map(item => renderMenuItem(item))}
        </ul>
      </nav>
    </div>
  );
};