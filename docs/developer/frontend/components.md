# Component Usage Guide

This guide provides examples and best practices for using the KTRDR frontend component library.

## Table of Contents

- [Component Library Overview](#component-library-overview)
- [Basic UI Components](#basic-ui-components)
- [Layout Components](#layout-components)
- [Data Display Components](#data-display-components)
- [Form Components](#form-components)
- [Chart Components](#chart-components)
- [Feedback Components](#feedback-components)
- [Custom Component Development](#custom-component-development)
- [Theming and Styling](#theming-and-styling)
- [Accessibility Guidelines](#accessibility-guidelines)

## Component Library Overview

The KTRDR frontend uses a custom component library built with React and TypeScript. The components are designed to be:

- **Reusable**: Components can be used across the application
- **Composable**: Components can be combined to create complex UIs
- **Accessible**: Components follow WCAG accessibility guidelines
- **Themeable**: Components respect the application theme
- **Type-safe**: Components have TypeScript interfaces for props

### Component Organization

Components are organized into the following categories:

```
components/
├── common/            # Basic UI components
│   ├── Button/
│   ├── Card/
│   ├── Input/
│   ├── Select/
│   └── ...
├── layout/            # Layout components
│   ├── Header/
│   ├── Sidebar/
│   ├── MainLayout/
│   └── ...
├── data/              # Data display components
│   ├── DataTable/
│   ├── DataGrid/
│   └── ...
├── forms/             # Form components
│   ├── Form/
│   ├── TextField/
│   ├── Checkbox/
│   └── ...
├── charts/            # Chart components
│   ├── CandlestickChart/
│   ├── LineChart/
│   └── ...
└── feedback/          # Feedback components
    ├── Toast/
    ├── Modal/
    ├── Alert/
    └── ...
```

## Basic UI Components

### Button

The `Button` component is used for actions and navigation.

```tsx
import { Button } from 'components/common/Button';

// Primary button (default)
<Button onClick={handleClick}>Click Me</Button>

// Secondary button
<Button variant="secondary" onClick={handleClick}>Click Me</Button>

// Tertiary button
<Button variant="tertiary" onClick={handleClick}>Click Me</Button>

// Disabled button
<Button disabled>Click Me</Button>

// Loading button
<Button isLoading>Loading</Button>

// Button with icon
<Button icon={<IconComponent />}>With Icon</Button>

// Icon-only button with tooltip
<Button iconOnly aria-label="Settings">
  <IconComponent />
</Button>

// Full width button
<Button fullWidth>Full Width</Button>

// Button with different sizes
<Button size="small">Small</Button>
<Button size="medium">Medium</Button>
<Button size="large">Large</Button>
```

#### Button Props Interface

```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'tertiary';
  size?: 'small' | 'medium' | 'large';
  fullWidth?: boolean;
  isLoading?: boolean;
  disabled?: boolean;
  iconOnly?: boolean;
  icon?: React.ReactNode;
  type?: 'button' | 'submit' | 'reset';
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  children: React.ReactNode;
}
```

### Card

The `Card` component is used to group related content.

```tsx
import { Card } from 'components/common/Card';

// Basic card
<Card>
  <p>Card content goes here</p>
</Card>

// Card with header
<Card
  header={<h3>Card Title</h3>}
>
  <p>Card content goes here</p>
</Card>

// Card with header and footer
<Card
  header={<h3>Card Title</h3>}
  footer={<Button>Action</Button>}
>
  <p>Card content goes here</p>
</Card>

// Clickable card
<Card onClick={handleCardClick}>
  <p>Click this card</p>
</Card>

// Card with custom padding
<Card padding="large">
  <p>Card with large padding</p>
</Card>
```

#### Card Props Interface

```typescript
interface CardProps {
  header?: React.ReactNode;
  footer?: React.ReactNode;
  padding?: 'none' | 'small' | 'medium' | 'large';
  onClick?: () => void;
  children: React.ReactNode;
}
```

### Input

The `Input` component is used for text input.

```tsx
import { Input } from 'components/common/Input';

// Basic input
<Input
  name="username"
  value={username}
  onChange={handleChange}
  placeholder="Enter username"
/>

// Input with label
<Input
  label="Username"
  name="username"
  value={username}
  onChange={handleChange}
/>

// Input with error
<Input
  label="Email"
  name="email"
  value={email}
  onChange={handleChange}
  error="Please enter a valid email"
/>

// Input with helper text
<Input
  label="Password"
  name="password"
  type="password"
  value={password}
  onChange={handleChange}
  helperText="Password must be at least 8 characters"
/>

// Input with icon
<Input
  label="Search"
  name="search"
  value={search}
  onChange={handleChange}
  icon={<SearchIcon />}
/>

// Disabled input
<Input
  label="Username"
  name="username"
  value={username}
  disabled
/>

// Required input
<Input
  label="Email"
  name="email"
  value={email}
  onChange={handleChange}
  required
/>
```

#### Input Props Interface

```typescript
interface InputProps {
  name: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  label?: string;
  placeholder?: string;
  type?: 'text' | 'password' | 'email' | 'number' | 'tel';
  error?: string;
  helperText?: string;
  icon?: React.ReactNode;
  disabled?: boolean;
  required?: boolean;
  autoFocus?: boolean;
  autoComplete?: string;
}
```

### Select

The `Select` component is used for selecting from a list of options.

```tsx
import { Select } from 'components/common/Select';

// Basic select
<Select
  name="country"
  value={country}
  onChange={handleChange}
  options={[
    { value: 'us', label: 'United States' },
    { value: 'ca', label: 'Canada' },
    { value: 'mx', label: 'Mexico' },
  ]}
/>

// Select with label
<Select
  label="Country"
  name="country"
  value={country}
  onChange={handleChange}
  options={countryOptions}
/>

// Select with placeholder
<Select
  label="Country"
  name="country"
  value={country}
  onChange={handleChange}
  options={countryOptions}
  placeholder="Select a country"
/>

// Select with error
<Select
  label="Country"
  name="country"
  value={country}
  onChange={handleChange}
  options={countryOptions}
  error="Please select a country"
/>

// Disabled select
<Select
  label="Country"
  name="country"
  value={country}
  onChange={handleChange}
  options={countryOptions}
  disabled
/>

// Multi-select
<Select
  label="Countries"
  name="countries"
  value={countries}
  onChange={handleMultiChange}
  options={countryOptions}
  isMulti
/>
```

#### Select Props Interface

```typescript
interface SelectOption {
  value: string | number;
  label: string;
}

interface SelectProps {
  name: string;
  value: string | string[];
  onChange: (value: string | string[]) => void;
  options: SelectOption[];
  label?: string;
  placeholder?: string;
  error?: string;
  helperText?: string;
  disabled?: boolean;
  required?: boolean;
  isMulti?: boolean;
}
```

## Layout Components

### MainLayout

The `MainLayout` component provides the main application layout.

```tsx
import { MainLayout } from 'components/layout/MainLayout';

// Basic usage
<MainLayout>
  <p>Main content goes here</p>
</MainLayout>

// With custom sidebar content
<MainLayout sidebarContent={<CustomSidebar />}>
  <p>Main content goes here</p>
</MainLayout>

// With custom header content
<MainLayout headerContent={<CustomHeader />}>
  <p>Main content goes here</p>
</MainLayout>

// With sidebar collapsed
<MainLayout sidebarCollapsed={true}>
  <p>Main content goes here</p>
</MainLayout>
```

#### MainLayout Props Interface

```typescript
interface MainLayoutProps {
  sidebarContent?: React.ReactNode;
  headerContent?: React.ReactNode;
  sidebarCollapsed?: boolean;
  children: React.ReactNode;
}
```

### Header

The `Header` component is used at the top of the application.

```tsx
import { Header } from 'components/layout/Header';

// Basic header
<Header title="KTRDR" />

// Header with navigation
<Header 
  title="KTRDR"
  navigation={[
    { label: 'Dashboard', path: '/' },
    { label: 'Charts', path: '/charts' },
    { label: 'Settings', path: '/settings' },
  ]}
/>

// Header with user menu
<Header
  title="KTRDR"
  user={{
    name: 'John Doe',
    avatar: '/path/to/avatar.jpg',
  }}
  onLogout={handleLogout}
/>

// Header with theme toggle
<Header
  title="KTRDR"
  showThemeToggle
  currentTheme={theme}
  onThemeChange={handleThemeChange}
/>
```

#### Header Props Interface

```typescript
interface HeaderProps {
  title: string;
  navigation?: Array<{ label: string; path: string }>;
  user?: { name: string; avatar?: string };
  onLogout?: () => void;
  showThemeToggle?: boolean;
  currentTheme?: 'light' | 'dark';
  onThemeChange?: (theme: 'light' | 'dark') => void;
}
```

### Sidebar

The `Sidebar` component provides navigation and context.

```tsx
import { Sidebar } from 'components/layout/Sidebar';

// Basic sidebar
<Sidebar
  items={[
    { label: 'Dashboard', icon: <DashboardIcon />, path: '/' },
    { label: 'Charts', icon: <ChartIcon />, path: '/charts' },
    { label: 'Settings', icon: <SettingsIcon />, path: '/settings' },
  ]}
/>

// Sidebar with nested items
<Sidebar
  items={[
    {
      label: 'Data',
      icon: <DataIcon />,
      children: [
        { label: 'Symbols', path: '/data/symbols' },
        { label: 'Timeframes', path: '/data/timeframes' },
      ],
    },
    // Other items
  ]}
/>

// Sidebar with selected item
<Sidebar
  items={sidebarItems}
  selectedPath={currentPath}
/>

// Collapsible sidebar
<Sidebar
  items={sidebarItems}
  collapsible
  collapsed={isSidebarCollapsed}
  onToggleCollapse={handleToggleCollapse}
/>

// Sidebar with footer
<Sidebar
  items={sidebarItems}
  footer={<VersionInfo version="1.0.0" />}
/>
```

#### Sidebar Props Interface

```typescript
interface SidebarItem {
  label: string;
  icon?: React.ReactNode;
  path?: string;
  children?: Omit<SidebarItem, 'children' | 'icon'>[];
}

interface SidebarProps {
  items: SidebarItem[];
  selectedPath?: string;
  collapsible?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  footer?: React.ReactNode;
}
```

## Data Display Components

### DataTable

The `DataTable` component displays tabular data.

```tsx
import { DataTable } from 'components/data/DataTable';

// Basic data table
<DataTable
  columns={[
    { id: 'name', header: 'Name' },
    { id: 'symbol', header: 'Symbol' },
    { id: 'price', header: 'Price' },
  ]}
  data={[
    { id: '1', name: 'Apple Inc.', symbol: 'AAPL', price: 150.25 },
    { id: '2', name: 'Microsoft', symbol: 'MSFT', price: 280.75 },
    { id: '3', name: 'Google', symbol: 'GOOGL', price: 2500.50 },
  ]}
/>

// Data table with formatting
<DataTable
  columns={[
    { id: 'name', header: 'Name' },
    { id: 'symbol', header: 'Symbol' },
    { 
      id: 'price', 
      header: 'Price',
      format: (value) => `$${value.toFixed(2)}`,
    },
  ]}
  data={stockData}
/>

// Data table with sorting
<DataTable
  columns={columns}
  data={data}
  sortable
  defaultSortColumn="name"
  defaultSortDirection="asc"
  onSort={handleSort}
/>

// Data table with pagination
<DataTable
  columns={columns}
  data={data}
  pagination
  pageSize={10}
  totalItems={100}
  currentPage={1}
  onPageChange={handlePageChange}
/>

// Data table with row selection
<DataTable
  columns={columns}
  data={data}
  selectable
  selectedRows={selectedRows}
  onRowSelect={handleRowSelect}
/>

// Data table with loading state
<DataTable
  columns={columns}
  data={data}
  isLoading={isLoading}
  loadingText="Loading data..."
/>
```

#### DataTable Props Interface

```typescript
interface DataTableColumn {
  id: string;
  header: string;
  width?: string;
  format?: (value: any) => React.ReactNode;
}

interface DataTableProps {
  columns: DataTableColumn[];
  data: Array<Record<string, any>>;
  idField?: string;
  sortable?: boolean;
  defaultSortColumn?: string;
  defaultSortDirection?: 'asc' | 'desc';
  onSort?: (column: string, direction: 'asc' | 'desc') => void;
  pagination?: boolean;
  pageSize?: number;
  currentPage?: number;
  totalItems?: number;
  onPageChange?: (page: number) => void;
  selectable?: boolean;
  selectedRows?: string[];
  onRowSelect?: (ids: string[]) => void;
  isLoading?: boolean;
  loadingText?: string;
}
```

## Form Components

### Form

The `Form` component manages form state and validation.

```tsx
import { Form } from 'components/forms/Form';
import { TextField } from 'components/forms/TextField';
import { Button } from 'components/common/Button';

// Basic form
<Form onSubmit={handleSubmit}>
  {({ values, handleChange, handleSubmit }) => (
    <>
      <TextField
        name="email"
        label="Email"
        value={values.email}
        onChange={handleChange}
      />
      <TextField
        name="password"
        label="Password"
        type="password"
        value={values.password}
        onChange={handleChange}
      />
      <Button type="submit">Sign In</Button>
    </>
  )}
</Form>

// Form with validation
<Form
  initialValues={{ email: '', password: '' }}
  validationSchema={{
    email: {
      required: 'Email is required',
      pattern: {
        value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
        message: 'Invalid email address',
      },
    },
    password: {
      required: 'Password is required',
      minLength: {
        value: 8,
        message: 'Password must be at least 8 characters',
      },
    },
  }}
  onSubmit={handleSubmit}
>
  {({ values, errors, handleChange, handleSubmit }) => (
    <>
      <TextField
        name="email"
        label="Email"
        value={values.email}
        error={errors.email}
        onChange={handleChange}
      />
      <TextField
        name="password"
        label="Password"
        type="password"
        value={values.password}
        error={errors.password}
        onChange={handleChange}
      />
      <Button type="submit">Sign In</Button>
    </>
  )}
</Form>

// Form with dynamic fields
<Form
  initialValues={{ users: [{ name: '', email: '' }] }}
  onSubmit={handleSubmit}
>
  {({ values, handleChange, handleSubmit, addArrayField, removeArrayField }) => (
    <>
      {values.users.map((user, index) => (
        <div key={index}>
          <TextField
            name={`users[${index}].name`}
            label="Name"
            value={user.name}
            onChange={handleChange}
          />
          <TextField
            name={`users[${index}].email`}
            label="Email"
            value={user.email}
            onChange={handleChange}
          />
          <Button onClick={() => removeArrayField('users', index)}>
            Remove
          </Button>
        </div>
      ))}
      <Button onClick={() => addArrayField('users', { name: '', email: '' })}>
        Add User
      </Button>
      <Button type="submit">Submit</Button>
    </>
  )}
</Form>
```

#### Form Props Interface

```typescript
interface FormProps<T> {
  initialValues: T;
  validationSchema?: Record<keyof T, ValidationRule>;
  onSubmit: (values: T) => void;
  children: (formProps: {
    values: T;
    errors: Record<keyof T, string>;
    touched: Record<keyof T, boolean>;
    handleChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    handleBlur: (e: React.FocusEvent<HTMLInputElement>) => void;
    handleSubmit: (e: React.FormEvent) => void;
    addArrayField: (field: string, value: any) => void;
    removeArrayField: (field: string, index: number) => void;
  }) => React.ReactNode;
}
```

## Chart Components

### CandlestickChart

The `CandlestickChart` component displays OHLCV data.

```tsx
import { CandlestickChart } from 'components/charts/CandlestickChart';

// Basic candlestick chart
<CandlestickChart
  data={[
    { time: '2023-01-01', open: 150, high: 155, low: 145, close: 152 },
    { time: '2023-01-02', open: 152, high: 160, low: 150, close: 155 },
    // More data points...
  ]}
/>

// Candlestick chart with volume
<CandlestickChart
  data={ohlcvData}
  showVolume
/>

// Candlestick chart with indicators
<CandlestickChart
  data={ohlcvData}
  indicators={[
    { type: 'sma', params: { period: 20 } },
    { type: 'ema', params: { period: 50 } },
  ]}
/>

// Interactive candlestick chart
<CandlestickChart
  data={ohlcvData}
  interactive
  onCrosshairMove={handleCrosshairMove}
  onTimeRangeChange={handleTimeRangeChange}
/>

// Candlestick chart with custom options
<CandlestickChart
  data={ohlcvData}
  options={{
    layout: {
      backgroundColor: '#1E1E1E',
      textColor: '#D9D9D9',
    },
    grid: {
      vertLines: { color: '#2B2B43' },
      horzLines: { color: '#2B2B43' },
    },
  }}
/>
```

#### CandlestickChart Props Interface

```typescript
interface OHLCVData {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface ChartIndicator {
  type: 'sma' | 'ema' | 'bollinger' | 'macd' | 'rsi';
  params: Record<string, any>;
}

interface CandlestickChartProps {
  data: OHLCVData[];
  width?: number;
  height?: number;
  showVolume?: boolean;
  indicators?: ChartIndicator[];
  interactive?: boolean;
  options?: Record<string, any>;
  onCrosshairMove?: (param: any) => void;
  onTimeRangeChange?: (range: { from: number; to: number }) => void;
}
```

## Feedback Components

### Modal

The `Modal` component displays content in a dialog.

```tsx
import { Modal } from 'components/feedback/Modal';
import { Button } from 'components/common/Button';

// Basic modal
<Modal
  isOpen={isModalOpen}
  onClose={handleCloseModal}
  title="Confirmation"
>
  <p>Are you sure you want to continue?</p>
  <div className="modal-actions">
    <Button variant="secondary" onClick={handleCloseModal}>Cancel</Button>
    <Button onClick={handleConfirm}>Confirm</Button>
  </div>
</Modal>

// Modal with custom size
<Modal
  isOpen={isModalOpen}
  onClose={handleCloseModal}
  title="Large Modal"
  size="large"
>
  <p>This is a large modal with more content.</p>
</Modal>

// Modal with footer
<Modal
  isOpen={isModalOpen}
  onClose={handleCloseModal}
  title="Modal with Footer"
  footer={
    <>
      <Button variant="secondary" onClick={handleCloseModal}>Cancel</Button>
      <Button onClick={handleConfirm}>Confirm</Button>
    </>
  }
>
  <p>Modal content here.</p>
</Modal>

// Modal with close on backdrop click disabled
<Modal
  isOpen={isModalOpen}
  onClose={handleCloseModal}
  title="Important Modal"
  closeOnBackdropClick={false}
>
  <p>You must use the close button to dismiss this modal.</p>
</Modal>
```

#### Modal Props Interface

```typescript
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  size?: 'small' | 'medium' | 'large';
  footer?: React.ReactNode;
  closeOnBackdropClick?: boolean;
  children: React.ReactNode;
}
```

### Toast

The `Toast` component displays temporary notifications.

```tsx
import { Toast, useToast } from 'components/feedback/Toast';

// Using the Toast component directly
<Toast
  message="Settings saved successfully"
  type="success"
  isVisible={isToastVisible}
  onClose={handleCloseToast}
/>

// Using the useToast hook
const ToastExample = () => {
  const toast = useToast();
  
  const handleSave = () => {
    // Save logic...
    toast.success('Settings saved successfully');
  };
  
  const handleError = () => {
    toast.error('Failed to save settings. Please try again.');
  };
  
  const handleInfo = () => {
    toast.info('Your data is being processed.');
  };
  
  const handleWarning = () => {
    toast.warning('This action cannot be undone.');
  };
  
  return (
    <div>
      <Button onClick={handleSave}>Success Toast</Button>
      <Button onClick={handleError}>Error Toast</Button>
      <Button onClick={handleInfo}>Info Toast</Button>
      <Button onClick={handleWarning}>Warning Toast</Button>
    </div>
  );
};
```

#### Toast Props Interface

```typescript
interface ToastProps {
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  isVisible: boolean;
  onClose: () => void;
  duration?: number;
}

interface ToastHook {
  success: (message: string, duration?: number) => void;
  error: (message: string, duration?: number) => void;
  info: (message: string, duration?: number) => void;
  warning: (message: string, duration?: number) => void;
}
```

## Custom Component Development

### Creating New Components

Follow these steps to create a new component:

1. Create a new directory for your component:
   ```
   components/common/MyComponent/
   ```

2. Create the component files:
   ```
   components/common/MyComponent/
   ├── MyComponent.tsx      # Component implementation
   ├── MyComponent.module.css # Component styles
   ├── MyComponent.test.tsx # Component tests
   └── index.ts             # Re-export the component
   ```

3. Implement the component with TypeScript interfaces:
   ```tsx
   // MyComponent.tsx
   import React from 'react';
   import styles from './MyComponent.module.css';
   
   export interface MyComponentProps {
     // Define your props interface
     label: string;
     onClick?: () => void;
     className?: string;
   }
   
   export const MyComponent: React.FC<MyComponentProps> = ({
     label,
     onClick,
     className,
   }) => {
     return (
       <div 
         className={`${styles.container} ${className || ''}`}
         onClick={onClick}
       >
         {label}
       </div>
     );
   };
   ```

4. Create a named export in the index.ts file:
   ```typescript
   // index.ts
   export { MyComponent } from './MyComponent';
   export type { MyComponentProps } from './MyComponent';
   ```

5. Write tests for your component:
   ```tsx
   // MyComponent.test.tsx
   import React from 'react';
   import { render, screen, fireEvent } from '@testing-library/react';
   import { MyComponent } from './MyComponent';
   
   describe('MyComponent', () => {
     it('renders correctly with label', () => {
       render(<MyComponent label="Test Label" />);
       expect(screen.getByText('Test Label')).toBeInTheDocument();
     });
     
     it('calls onClick when clicked', () => {
       const handleClick = vi.fn();
       render(<MyComponent label="Clickable" onClick={handleClick} />);
       fireEvent.click(screen.getByText('Clickable'));
       expect(handleClick).toHaveBeenCalledTimes(1);
     });
   });
   ```

### Component Best Practices

1. **Props Interface**: Always define a props interface for your component.
2. **Default Props**: Provide default values for optional props.
3. **Component Composition**: Use composition over inheritance.
4. **Memoization**: Use React.memo for performance optimization when needed.
5. **Ref Forwarding**: Use forwardRef when creating components that need refs.
6. **Error Boundaries**: Implement error boundaries for component failure handling.
7. **Accessibility**: Ensure components are accessible with proper ARIA attributes.

## Theming and Styling

### Theme System

The application uses a theme system with light and dark modes:

```tsx
import { ThemeProvider, useTheme } from 'components/theme';

// Providing the theme
const App = () => {
  return (
    <ThemeProvider defaultTheme="dark">
      <MainLayout>
        <AppContent />
      </MainLayout>
    </ThemeProvider>
  );
};

// Using the theme
const ThemedComponent = () => {
  const { theme, toggleTheme } = useTheme();
  
  return (
    <div className={`themed-component ${theme}`}>
      <p>Current theme: {theme}</p>
      <Button onClick={toggleTheme}>
        Toggle to {theme === 'light' ? 'dark' : 'light'} theme
      </Button>
    </div>
  );
};
```

### CSS Module Pattern

Components use CSS Modules for scoped styling:

```css
/* MyComponent.module.css */
.container {
  display: flex;
  padding: 16px;
  border-radius: 4px;
}

.primary {
  background-color: var(--color-primary);
  color: var(--color-text-on-primary);
}

.secondary {
  background-color: var(--color-secondary);
  color: var(--color-text-on-secondary);
}
```

```tsx
// MyComponent.tsx
import styles from './MyComponent.module.css';

export const MyComponent: React.FC<MyComponentProps> = ({ variant = 'primary' }) => {
  return (
    <div className={`${styles.container} ${styles[variant]}`}>
      {/* Component content */}
    </div>
  );
};
```

### CSS Variables

The application uses CSS variables for theming:

```css
/* Base theme variables */
:root {
  --font-family: 'Inter', sans-serif;
  --font-size-base: 16px;
  --border-radius: 4px;
  
  /* Light theme colors (default) */
  --color-primary: #2563eb;
  --color-secondary: #6b7280;
  --color-background: #ffffff;
  --color-surface: #f3f4f6;
  --color-text: #111827;
  --color-text-secondary: #4b5563;
  --color-border: #d1d5db;
  --color-error: #dc2626;
  --color-success: #16a34a;
  --color-warning: #ca8a04;
  --color-info: #0891b2;
}

/* Dark theme colors */
[data-theme="dark"] {
  --color-primary: #3b82f6;
  --color-secondary: #9ca3af;
  --color-background: #111827;
  --color-surface: #1f2937;
  --color-text: #f9fafb;
  --color-text-secondary: #d1d5db;
  --color-border: #374151;
  --color-error: #ef4444;
  --color-success: #22c55e;
  --color-warning: #eab308;
  --color-info: #06b6d4;
}
```

## Accessibility Guidelines

### Keyboard Navigation

Ensure components are keyboard navigable:

```tsx
// Example of a keyboard-accessible button
const KeyboardButton = ({ onClick, children }) => {
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };
  
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className="keyboard-button"
    >
      {children}
    </div>
  );
};
```

### ARIA Attributes

Use ARIA attributes for better accessibility:

```tsx
// Example of a dropdown with ARIA attributes
const Dropdown = ({ label, isOpen, onToggle, children }) => {
  return (
    <div className="dropdown">
      <button
        aria-haspopup="true"
        aria-expanded={isOpen}
        onClick={onToggle}
      >
        {label}
      </button>
      <div
        className={`dropdown-menu ${isOpen ? 'open' : ''}`}
        role="menu"
        aria-hidden={!isOpen}
      >
        {children}
      </div>
    </div>
  );
};
```

### Focus Management

Manage focus for better user experience:

```tsx
// Example of focus management in a modal
const AccessibleModal = ({ isOpen, onClose, title, children }) => {
  const modalRef = useRef(null);
  
  useEffect(() => {
    if (isOpen && modalRef.current) {
      // Save previous focus
      const previousFocus = document.activeElement;
      
      // Focus the modal
      modalRef.current.focus();
      
      // Return focus on cleanup
      return () => {
        if (previousFocus) {
          (previousFocus as HTMLElement).focus();
        }
      };
    }
  }, [isOpen]);
  
  return isOpen ? (
    <div className="modal-overlay">
      <div
        className="modal"
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
      >
        <h2 id="modal-title">{title}</h2>
        <div className="modal-content">{children}</div>
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  ) : null;
};
```