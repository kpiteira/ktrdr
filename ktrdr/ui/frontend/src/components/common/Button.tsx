import React from 'react';
import { ButtonVariant, ButtonSize } from '@/types/ui';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  isLoading?: boolean;
  isFullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'medium',
  isLoading = false,
  isFullWidth = false,
  leftIcon,
  rightIcon,
  children,
  disabled,
  className = '',
  ...rest
}) => {
  const baseClass = 'btn';
  const variantClass = `btn-${variant}`;
  const sizeClass = `btn-${size}`;
  const widthClass = isFullWidth ? 'btn-full-width' : '';
  const loadingClass = isLoading ? 'btn-loading' : '';
  
  const buttonClasses = [
    baseClass,
    variantClass,
    sizeClass,
    widthClass,
    loadingClass,
    className
  ].filter(Boolean).join(' ');

  return (
    <button
      className={buttonClasses}
      disabled={disabled || isLoading}
      {...rest}
    >
      {isLoading && (
        <span className="btn-spinner" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="4" strokeDasharray="42" strokeDashoffset="14">
              <animateTransform 
                attributeName="transform" 
                type="rotate" 
                from="0 12 12" 
                to="360 12 12" 
                dur="1s" 
                repeatCount="indefinite" 
              />
            </circle>
          </svg>
        </span>
      )}
      {!isLoading && leftIcon && (
        <span className="btn-icon btn-icon-left">{leftIcon}</span>
      )}
      <span className="btn-text">{children}</span>
      {!isLoading && rightIcon && (
        <span className="btn-icon btn-icon-right">{rightIcon}</span>
      )}
    </button>
  );
};