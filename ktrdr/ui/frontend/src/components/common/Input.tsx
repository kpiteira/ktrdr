import React, { forwardRef } from 'react';
import { InputType } from '@/types/ui';

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'onChange'> {
  label?: string;
  type?: InputType;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  isFullWidth?: boolean;
  onChange?: (value: string) => void;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({
  label,
  type = 'text',
  error,
  helperText,
  leftIcon,
  rightIcon,
  isFullWidth = false,
  onChange,
  className = '',
  ...rest
}, ref) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange?.(e.target.value);
  };

  const inputClasses = [
    'input-field',
    error ? 'input-error' : '',
    leftIcon ? 'has-left-icon' : '',
    rightIcon ? 'has-right-icon' : '',
    isFullWidth ? 'input-full-width' : '',
    className
  ].filter(Boolean).join(' ');

  const wrapperClasses = [
    'input-wrapper',
    isFullWidth ? 'input-wrapper-full-width' : ''
  ].filter(Boolean).join(' ');

  return (
    <div className={wrapperClasses}>
      {label && (
        <label className="input-label" htmlFor={rest.id}>
          {label}
        </label>
      )}
      <div className="input-container">
        {leftIcon && (
          <span className="input-icon input-icon-left">
            {leftIcon}
          </span>
        )}
        <input
          ref={ref}
          type={type}
          className={inputClasses}
          onChange={handleChange}
          aria-invalid={!!error}
          aria-describedby={error ? `${rest.id}-error` : helperText ? `${rest.id}-helper` : undefined}
          {...rest}
        />
        {rightIcon && (
          <span className="input-icon input-icon-right">
            {rightIcon}
          </span>
        )}
      </div>
      {error && (
        <p className="input-error-text" id={`${rest.id}-error`}>
          {error}
        </p>
      )}
      {!error && helperText && (
        <p className="input-helper-text" id={`${rest.id}-helper`}>
          {helperText}
        </p>
      )}
    </div>
  );
});