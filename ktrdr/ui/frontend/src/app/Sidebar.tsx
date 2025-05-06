import React from 'react';
import { useTheme } from './ThemeProvider';
import { useUIStore } from './hooks/useUIStore';
import { Link, useLocation } from 'react-router-dom';
import { routes } from './routes';

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
  const { sidebarOpen: isOpen, toggleSidebar } = useUIStore();
  const location = useLocation();
  
  const handleClose = () => {
    toggleSidebar();
    if (onClose) onClose();
  };
  
  // Convert routes to menu items
  const menuItems: MenuItem[] = routes;

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