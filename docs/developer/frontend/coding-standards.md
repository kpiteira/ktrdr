# Frontend Coding Standards and Patterns

This document outlines the coding standards, best practices, and recommended patterns for the KTRDR frontend application.

## Table of Contents

- [Code Style and Formatting](#code-style-and-formatting)
- [TypeScript Best Practices](#typescript-best-practices)
- [Component Patterns](#component-patterns)
- [State Management Patterns](#state-management-patterns)
- [File and Directory Structure](#file-and-directory-structure)
- [Naming Conventions](#naming-conventions)
- [Error Handling](#error-handling)
- [Logging](#logging)
- [Performance Considerations](#performance-considerations)
- [Security Best Practices](#security-best-practices)
- [Accessibility (A11y)](#accessibility-a11y)
- [Documentation Standards](#documentation-standards)

## Code Style and Formatting

We use ESLint and Prettier to enforce consistent code style across the codebase.

### ESLint Configuration

Our ESLint configuration extends from:
- `eslint:recommended`
- `plugin:react/recommended`
- `plugin:@typescript-eslint/recommended`
- `plugin:react-hooks/recommended`

Key rules include:
- No unused variables
- Consistent use of quotes (single)
- No console statements in production code
- Proper React Hooks usage

### Prettier Configuration

Our Prettier configuration includes:
```json
{
  "singleQuote": true,
  "printWidth": 100,
  "tabWidth": 2,
  "trailingComma": "es5",
  "semi": true,
  "arrowParens": "avoid"
}
```

### Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

Types include:
- `feat` - Features
- `fix` - Bug fixes
- `docs` - Documentation
- `style` - Formatting changes
- `refactor` - Code refactoring
- `test` - Adding/updating tests
- `chore` - Maintenance tasks

## TypeScript Best Practices

### Type Definitions

Define interfaces and types in dedicated files:

```typescript
// src/types/data.ts
export interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'guest';
}

export type UserRole = User['role'];

export interface UserState {
  currentUser: User | null;
  isLoading: boolean;
  error: string | null;
}
```

### Prop Types

Use TypeScript interfaces for component props:

```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'tertiary';
  size?: 'small' | 'medium' | 'large';
  isLoading?: boolean;
  disabled?: boolean;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'medium',
  isLoading = false,
  disabled = false,
  onClick,
  children,
}) => {
  // Implementation
};
```

### Type Guards

Use type guards for narrowing types:

```typescript
function isErrorResponse(response: unknown): response is ErrorResponse {
  return (
    typeof response === 'object' &&
    response !== null &&
    'error' in response &&
    'message' in response
  );
}

// Usage
if (isErrorResponse(response)) {
  // TypeScript now knows response has error and message properties
  console.error(response.message);
}
```

### Utility Types

Leverage TypeScript utility types:

```typescript
// Extract specific properties
type UserBasicInfo = Pick<User, 'id' | 'username'>;

// Make properties optional
type PartialUser = Partial<User>;

// Make properties required
type RequiredUser = Required<User>;

// Create a type with all properties except some
type UserWithoutEmail = Omit<User, 'email'>;

// Extract return type from function
type FetchUserResult = ReturnType<typeof fetchUser>;
```

## Component Patterns

### Functional Components

Use functional components with hooks:

```typescript
import React, { useState, useEffect } from 'react';

interface UserProfileProps {
  userId: string;
}

export const UserProfile: React.FC<UserProfileProps> = ({ userId }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [userData, setUserData] = useState<User | null>(null);
  
  useEffect(() => {
    const fetchUser = async () => {
      setIsLoading(true);
      try {
        const data = await api.getUser(userId);
        setUserData(data);
      } catch (error) {
        console.error('Failed to fetch user:', error);
      } finally {
        setIsLoading(false);
      }
    };
    
    fetchUser();
  }, [userId]);
  
  if (isLoading) return <LoadingSpinner />;
  if (!userData) return <ErrorMessage message="User not found" />;
  
  return (
    <div className="user-profile">
      <h2>{userData.username}</h2>
      <p>{userData.email}</p>
    </div>
  );
};
```

### Component Organization

Structure components in a logical hierarchy:

1. **Page Components**: Top-level components that correspond to routes
2. **Container Components**: Connect to state and pass data to presentational components
3. **Presentational Components**: Focus on UI and receive data via props
4. **Common Components**: Reusable across the application

### Component Composition

Favor composition over inheritance:

```typescript
// Base Card component
const Card: React.FC<CardProps> = ({ children, className, ...rest }) => (
  <div className={`card ${className || ''}`} {...rest}>
    {children}
  </div>
);

// Specialized cards using composition
const ErrorCard: React.FC<ErrorCardProps> = ({ message, onRetry }) => (
  <Card className="error-card">
    <AlertIcon />
    <p>{message}</p>
    {onRetry && <Button onClick={onRetry}>Retry</Button>}
  </Card>
);

const UserCard: React.FC<UserCardProps> = ({ user }) => (
  <Card className="user-card">
    <Avatar src={user.avatar} />
    <h3>{user.name}</h3>
    <p>{user.email}</p>
  </Card>
);
```

### Custom Hooks

Extract reusable logic into custom hooks:

```typescript
// src/hooks/useLocalStorage.ts
export function useLocalStorage<T>(key: string, initialValue: T) {
  const [storedValue, setStoredValue] = useState<T>(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(error);
      return initialValue;
    }
  });

  const setValue = (value: T | ((val: T) => T)) => {
    try {
      const valueToStore =
        value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(error);
    }
  };

  return [storedValue, setValue] as const;
}

// Usage
const [theme, setTheme] = useLocalStorage<'light' | 'dark'>('theme', 'light');
```

## State Management Patterns

### Local Component State

Use `useState` for component-specific state:

```typescript
const Counter: React.FC = () => {
  const [count, setCount] = useState(0);
  
  return (
    <div>
      <p>Count: {count}</p>
      <button onClick={() => setCount(count + 1)}>Increment</button>
      <button onClick={() => setCount(count - 1)}>Decrement</button>
    </div>
  );
};
```

### Context for Shared State

Use Context API for state shared between components:

```typescript
// src/contexts/ThemeContext.tsx
import React, { createContext, useContext, useState } from 'react';

type Theme = 'light' | 'dark';
interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setTheme] = useState<Theme>('light');
  
  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };
  
  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};
```

### Redux State Management

Follow Redux best practices:

1. **Organize by Slice**: Group related state, actions, and reducers
2. **Use Redux Toolkit**: Simplifies Redux code with createSlice
3. **Normalize State**: Use normalized state structure for collections
4. **Memoize Selectors**: Use createSelector for derived data

```typescript
// src/store/slices/userSlice.ts
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { User, UserState } from '../../types/user';
import { api } from '../../api';

const initialState: UserState = {
  currentUser: null,
  isLoading: false,
  error: null,
};

export const fetchCurrentUser = createAsyncThunk(
  'user/fetchCurrentUser',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.getCurrentUser();
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Failed to fetch user');
    }
  }
);

const userSlice = createSlice({
  name: 'user',
  initialState,
  reducers: {
    clearUser: (state) => {
      state.currentUser = null;
    },
    setUser: (state, action: PayloadAction<User>) => {
      state.currentUser = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCurrentUser.pending, (state) => {
        state.isLoading = true;
        state.error = null;
      })
      .addCase(fetchCurrentUser.fulfilled, (state, action) => {
        state.isLoading = false;
        state.currentUser = action.payload;
      })
      .addCase(fetchCurrentUser.rejected, (state, action) => {
        state.isLoading = false;
        state.error = action.payload as string;
      });
  },
});

export const { clearUser, setUser } = userSlice.actions;
export default userSlice.reducer;
```

## File and Directory Structure

### Project Structure

Organize files in a logical, modular structure:

```
src/
├── api/                # API integration
│   ├── client.ts       # Base API client
│   ├── endpoints/      # API endpoint definitions
│   └── hooks/          # API hooks
├── assets/             # Static assets
├── components/         # React components
│   ├── common/         # Shared components
│   ├── features/       # Feature-specific components
│   └── layout/         # Layout components
├── config/             # Configuration
├── contexts/           # React Context providers
├── hooks/              # Custom hooks
├── pages/              # Page components
├── routes/             # Routing configuration
├── store/              # Redux store configuration
│   ├── slices/         # Redux slices
│   └── index.ts        # Store setup
├── styles/             # Global styles
├── types/              # TypeScript types
└── utils/              # Utility functions
```

### Module Pattern

Group related files together:

```
src/features/auth/
├── components/         # Auth-specific components
│   ├── LoginForm.tsx
│   ├── RegisterForm.tsx
│   └── PasswordReset.tsx
├── hooks/              # Auth-specific hooks
│   └── useAuth.ts
├── store/              # Auth-specific store
│   └── authSlice.ts
├── types/              # Auth-specific types
│   └── auth.ts
└── utils/              # Auth-specific utilities
    └── validators.ts
```

## Naming Conventions

### Files and Directories

- **Components**: PascalCase with `.tsx` extension
  - `Button.tsx`, `UserProfile.tsx`
- **Hooks**: camelCase with `use` prefix and `.ts` extension
  - `useAuth.ts`, `useLocalStorage.ts`
- **Utils**: camelCase with `.ts` extension
  - `formatDate.ts`, `validators.ts`
- **Types**: PascalCase with `.ts` extension
  - `User.ts`, `ApiResponses.ts`
- **Styles**: Match component name with `.module.css` or `.module.scss` extension
  - `Button.module.css`, `UserProfile.module.scss`

### Variables and Functions

- **Variables**: camelCase
  - `userName`, `isLoading`, `apiResponse`
- **Constants**: UPPER_SNAKE_CASE
  - `API_URL`, `MAX_RETRY_ATTEMPTS`
- **Functions**: camelCase with verb
  - `getUserData()`, `formatCurrency()`, `handleSubmit()`
- **React Components**: PascalCase
  - `LoginForm`, `UserProfile`, `Button`
- **Type Names**: PascalCase
  - `User`, `ApiResponse`, `ButtonProps`
- **Interfaces**: PascalCase, typically without 'I' prefix
  - `UserProps`, `ApiConfig`, `Theme`
- **Enum Names**: PascalCase
  - `ButtonVariant`, `UserRole`, `FetchStatus`

## Error Handling

### API Error Handling

Implement consistent error handling for API requests:

```typescript
const fetchData = async () => {
  try {
    setIsLoading(true);
    const data = await api.getData();
    return data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      // Handle Axios errors
      const status = error.response?.status;
      
      if (status === 401) {
        // Handle unauthorized
        logoutUser();
        toast.error('Your session has expired, please log in again.');
      } else if (status === 404) {
        // Handle not found
        toast.error('The requested resource was not found.');
      } else {
        // Handle other errors
        toast.error(
          error.response?.data?.message || 
          'An error occurred while fetching data.'
        );
      }
    } else {
      // Handle unexpected errors
      toast.error('An unexpected error occurred.');
      console.error('Unexpected error:', error);
    }
    throw error;
  } finally {
    setIsLoading(false);
  }
};
```

### Error Boundaries

Use Error Boundaries to catch and handle rendering errors:

```typescript
// src/components/common/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  fallback?: ReactNode;
  children: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
    console.error('Error caught by ErrorBoundary:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="error-boundary">
          <h2>Something went wrong.</h2>
          <p>{this.state.error?.message || 'Unknown error'}</p>
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

// Usage
<ErrorBoundary fallback={<ErrorPage />}>
  <MyComponent />
</ErrorBoundary>
```

## Logging

### Client-Side Logging

Implement a structured logging system:

```typescript
// src/utils/logger.ts
type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  data?: any;
}

class Logger {
  private context: string;
  
  constructor(context: string) {
    this.context = context;
  }

  private createLogEntry(level: LogLevel, message: string, data?: any): LogEntry {
    return {
      timestamp: new Date().toISOString(),
      level,
      message: `[${this.context}] ${message}`,
      data,
    };
  }

  public debug(message: string, data?: any): void {
    const entry = this.createLogEntry('debug', message, data);
    console.debug(entry.message, entry.data || '');
    
    // In development, store logs in localStorage for debugging
    if (process.env.NODE_ENV === 'development') {
      this.storeLog(entry);
    }
  }

  public info(message: string, data?: any): void {
    const entry = this.createLogEntry('info', message, data);
    console.info(entry.message, entry.data || '');
    this.storeLog(entry);
  }

  public warn(message: string, data?: any): void {
    const entry = this.createLogEntry('warn', message, data);
    console.warn(entry.message, entry.data || '');
    this.storeLog(entry);
    
    // Optionally send to monitoring service
    if (process.env.NODE_ENV === 'production') {
      this.sendToMonitoring(entry);
    }
  }

  public error(message: string, error?: any): void {
    const entry = this.createLogEntry('error', message, error);
    console.error(entry.message, error || '');
    this.storeLog(entry);
    
    // Send to monitoring service in production
    if (process.env.NODE_ENV === 'production') {
      this.sendToMonitoring(entry);
    }
  }

  private storeLog(entry: LogEntry): void {
    try {
      const logs = JSON.parse(localStorage.getItem('app_logs') || '[]');
      logs.push(entry);
      
      // Limit to last 1000 logs to prevent localStorage from growing too large
      const trimmedLogs = logs.slice(-1000);
      localStorage.setItem('app_logs', JSON.stringify(trimmedLogs));
    } catch (error) {
      console.error('Failed to store log in localStorage', error);
    }
  }

  private sendToMonitoring(entry: LogEntry): void {
    // Integration with monitoring service like Sentry
    try {
      // Example Sentry integration
      if (typeof window.Sentry !== 'undefined') {
        window.Sentry.captureMessage(entry.message, {
          level: entry.level,
          extra: entry.data,
        });
      }
    } catch (error) {
      console.error('Failed to send log to monitoring service', error);
    }
  }
}

export const createLogger = (context: string): Logger => {
  return new Logger(context);
};

// Usage
const logger = createLogger('AuthService');
logger.info('User logged in', { userId: '123' });
logger.error('Authentication failed', new Error('Invalid credentials'));
```

## Performance Considerations

### Rendering Optimization

Implement performance optimizations:

1. **Memoization**: Use React.memo, useMemo, and useCallback
   ```typescript
   // Memoize expensive component
   const ExpensiveComponent = React.memo(({ data }) => {
     return <div>{/* render using data */}</div>;
   });
   
   // Memoize expensive calculation
   const memoizedValue = useMemo(() => {
     return computeExpensiveValue(a, b);
   }, [a, b]);
   
   // Memoize callback
   const memoizedCallback = useCallback(() => {
     doSomething(a, b);
   }, [a, b]);
   ```

2. **List Virtualization**: Use virtualization for long lists
   ```typescript
   import { FixedSizeList } from 'react-window';
   
   const VirtualizedList = ({ items }) => (
     <FixedSizeList
       height={500}
       width="100%"
       itemCount={items.length}
       itemSize={35}
     >
       {({ index, style }) => (
         <div style={style}>{items[index].name}</div>
       )}
     </FixedSizeList>
   );
   ```

3. **Code Splitting**: Lazy load components
   ```typescript
   import React, { Suspense, lazy } from 'react';
   
   const LazyComponent = lazy(() => import('./LazyComponent'));
   
   const App = () => (
     <Suspense fallback={<LoadingSpinner />}>
       <LazyComponent />
     </Suspense>
   );
   ```

## Security Best Practices

### Input Validation

Validate all user inputs:

```typescript
// Validate form input
const validateEmail = (email: string): boolean => {
  const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  return regex.test(email);
};

// Usage in component
const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  
  if (!validateEmail(email)) {
    setError('Please enter a valid email address');
    return;
  }
  
  // Proceed with form submission
};
```

### XSS Prevention

Prevent Cross-Site Scripting attacks:

1. **React's Built-in Protection**: React escapes values by default
2. **Sanitize HTML**: When rendering HTML content
   ```typescript
   import DOMPurify from 'dompurify';
   
   const SanitizedHTML: React.FC<{ html: string }> = ({ html }) => {
     const sanitizedHTML = DOMPurify.sanitize(html);
     return <div dangerouslySetInnerHTML={{ __html: sanitizedHTML }} />;
   };
   ```

### Authentication Best Practices

Secure authentication implementation:

1. **Token Storage**: Store tokens in HttpOnly cookies or securely in localStorage
2. **Auto Logout**: Implement session timeout
3. **CSRF Protection**: Use CSRF tokens for form submissions

## Accessibility (A11y)

### A11y Patterns

Implement accessible patterns:

1. **Semantic HTML**: Use appropriate HTML elements
   ```tsx
   // Bad
   <div onClick={handleClick}>Click me</div>
   
   // Good
   <button onClick={handleClick}>Click me</button>
   ```

2. **ARIA Attributes**: Use ARIA when needed
   ```tsx
   <button
     aria-pressed={isPressed}
     aria-expanded={isExpanded}
     aria-controls="panel-id"
   >
     Toggle Panel
   </button>
   
   <div id="panel-id" aria-hidden={!isExpanded}>
     Panel content
   </div>
   ```

3. **Keyboard Navigation**: Ensure keyboard accessibility
   ```tsx
   const KeyboardNavigable = () => {
     const handleKeyDown = (e: React.KeyboardEvent) => {
       if (e.key === 'Enter' || e.key === ' ') {
         // Activate on Enter or Space
         activate();
       }
     };
     
     return (
       <div
         tabIndex={0}
         role="button"
         onKeyDown={handleKeyDown}
         onClick={activate}
       >
         Activate
       </div>
     );
   };
   ```

4. **Focus Management**: Manage focus appropriately
   ```tsx
   const Modal = ({ isOpen, onClose }) => {
     const modalRef = useRef<HTMLDivElement>(null);
     
     useEffect(() => {
       if (isOpen && modalRef.current) {
         modalRef.current.focus();
       }
     }, [isOpen]);
     
     if (!isOpen) return null;
     
     return (
       <div
         ref={modalRef}
         tabIndex={-1}
         role="dialog"
         aria-modal="true"
       >
         <button onClick={onClose}>Close</button>
         {/* Modal content */}
       </div>
     );
   };
   ```

## Documentation Standards

### Code Documentation

Document code with JSDoc comments:

```typescript
/**
 * Formats a date according to the specified format.
 * 
 * @param date - The date to format
 * @param format - The format string (default: 'YYYY-MM-DD')
 * @returns The formatted date string
 * 
 * @example
 * ```
 * formatDate(new Date(), 'MM/DD/YYYY') // '01/31/2023'
 * ```
 */
export function formatDate(date: Date, format: string = 'YYYY-MM-DD'): string {
  // Implementation
}
```

### Component Documentation

Document components with JSDoc and include examples:

```typescript
/**
 * Button component for user interactions.
 * 
 * @component
 * @example
 * ```tsx
 * <Button variant="primary" onClick={() => console.log('Clicked')}>
 *   Click Me
 * </Button>
 * ```
 */
export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'medium',
  isLoading = false,
  disabled = false,
  onClick,
  children,
}) => {
  // Implementation
};
```

### README Files

Include README files in important directories:

```markdown
# API Module

This directory contains the API integration layer for the application.

## Structure

- `client.ts` - Base API client with Axios
- `endpoints/` - API endpoint definitions
- `hooks/` - React Query hooks for API data

## Usage

```typescript
import { useGetUserQuery } from './hooks/useUser';

const UserProfile = ({ userId }) => {
  const { data, isLoading, error } = useGetUserQuery(userId);
  
  // Component implementation
};
```
```