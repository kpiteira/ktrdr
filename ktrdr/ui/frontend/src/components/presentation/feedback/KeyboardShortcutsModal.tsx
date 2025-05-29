import { FC } from 'react';
import { KeyboardShortcut, formatShortcut } from '../../../hooks/useKeyboardShortcuts';

/**
 * Keyboard shortcuts help modal
 * 
 * Displays all available keyboard shortcuts organized by category
 * to help users learn and use the application more efficiently.
 */

interface KeyboardShortcutsModalProps {
  shortcuts: KeyboardShortcut[];
  isOpen: boolean;
  onClose: () => void;
}

const KeyboardShortcutsModal: FC<KeyboardShortcutsModalProps> = ({
  shortcuts,
  isOpen,
  onClose
}) => {
  if (!isOpen) return null;

  // Group shortcuts by category
  const groupedShortcuts = shortcuts.reduce((acc, shortcut) => {
    const category = shortcut.category || 'General';
    if (!acc[category]) {
      acc[category] = [];
    }
    acc[category].push(shortcut);
    return acc;
  }, {} as Record<string, KeyboardShortcut[]>);

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        zIndex: 2000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem'
      }}
      onClick={handleOverlayClick}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: '12px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          maxWidth: '600px',
          maxHeight: '80vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '1.5rem',
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '600', color: '#333' }}>
              ⌨️ Keyboard Shortcuts
            </h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: '#666' }}>
              Use these shortcuts to navigate faster
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '1.5rem',
              cursor: 'pointer',
              color: '#666',
              padding: '0.25rem',
              borderRadius: '4px'
            }}
            title="Close"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div style={{
          padding: '1.5rem',
          overflow: 'auto',
          flex: 1
        }}>
          {Object.entries(groupedShortcuts).map(([category, categoryShortcuts]) => (
            <div key={category} style={{ marginBottom: '2rem' }}>
              <h3 style={{
                margin: '0 0 1rem 0',
                fontSize: '1rem',
                fontWeight: '600',
                color: '#1976d2',
                borderBottom: '2px solid #e3f2fd',
                paddingBottom: '0.5rem'
              }}>
                {category}
              </h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {categoryShortcuts.map((shortcut, index) => (
                  <div
                    key={index}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '0.75rem 1rem',
                      backgroundColor: '#f8f9fa',
                      borderRadius: '6px',
                      border: '1px solid #e0e0e0'
                    }}
                  >
                    <span style={{
                      fontSize: '0.9rem',
                      color: '#333',
                      flex: 1
                    }}>
                      {shortcut.description}
                    </span>
                    
                    <div style={{
                      display: 'flex',
                      gap: '0.25rem'
                    }}>
                      {formatShortcut(shortcut).split(' + ').map((key, keyIndex) => (
                        <span key={keyIndex}>
                          <kbd style={{
                            padding: '0.25rem 0.5rem',
                            backgroundColor: '#fff',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                            fontSize: '0.8rem',
                            fontFamily: 'monospace',
                            color: '#333',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                          }}>
                            {key}
                          </kbd>
                          {keyIndex < formatShortcut(shortcut).split(' + ').length - 1 && (
                            <span style={{ margin: '0 0.25rem', color: '#666' }}>+</span>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
          
          {Object.keys(groupedShortcuts).length === 0 && (
            <div style={{
              textAlign: 'center',
              padding: '2rem',
              color: '#666'
            }}>
              No keyboard shortcuts are currently available.
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid #e0e0e0',
          backgroundColor: '#f8f9fa',
          fontSize: '0.85rem',
          color: '#666',
          textAlign: 'center'
        }}>
          💡 <strong>Tip:</strong> Shortcuts don't work when typing in input fields
        </div>
      </div>
    </div>
  );
};

export default KeyboardShortcutsModal;