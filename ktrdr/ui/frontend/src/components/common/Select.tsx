import React, { useState, useRef, useEffect } from 'react';
import { SelectOption } from '@/types/ui';

interface SelectProps {
  id?: string;
  label?: string;
  value?: string;
  options: SelectOption[];
  placeholder?: string;
  error?: string;
  helperText?: string;
  disabled?: boolean;
  isFullWidth?: boolean;
  onChange?: (value: string) => void;
  className?: string;
}

export const Select: React.FC<SelectProps> = ({
  id,
  label,
  value,
  options,
  placeholder = 'Select an option',
  error,
  helperText,
  disabled = false,
  isFullWidth = false,
  onChange,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedValue, setSelectedValue] = useState(value || '');
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setSelectedValue(value || '');
  }, [value]);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleSelect = (option: SelectOption) => {
    setSelectedValue(option.value);
    setIsOpen(false);
    onChange?.(option.value);
  };

  const toggleDropdown = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  const selectedOption = options.find(option => option.value === selectedValue);
  
  const selectClasses = [
    'select-wrapper',
    isFullWidth ? 'select-full-width' : '',
    disabled ? 'select-disabled' : '',
    error ? 'select-error' : '',
    className
  ].filter(Boolean).join(' ');

  return (
    <div className={selectClasses} ref={dropdownRef}>
      {label && (
        <label className="select-label" id={`${id}-label`}>
          {label}
        </label>
      )}
      <div 
        className={`select-control ${isOpen ? 'open' : ''}`}
        onClick={toggleDropdown}
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-labelledby={label ? `${id}-label` : undefined}
        aria-disabled={disabled}
      >
        <div className="select-value">
          {selectedOption ? selectedOption.label : placeholder}
        </div>
        <div className="select-indicator">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7 10l5 5 5-5z" fill="currentColor" />
          </svg>
        </div>
      </div>
      {isOpen && (
        <ul 
          className="select-options" 
          role="listbox"
          aria-labelledby={label ? `${id}-label` : undefined}
        >
          {options.map((option) => (
            <li
              key={option.value}
              className={`select-option ${option.value === selectedValue ? 'selected' : ''}`}
              onClick={() => handleSelect(option)}
              role="option"
              aria-selected={option.value === selectedValue}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p className="select-error-text" id={`${id}-error`}>
          {error}
        </p>
      )}
      {!error && helperText && (
        <p className="select-helper-text" id={`${id}-helper`}>
          {helperText}
        </p>
      )}
    </div>
  );
};