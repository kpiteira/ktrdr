# KTRDR Frontend Testing Guide

This guide provides best practices and examples for testing the KTRDR frontend application.

## Table of Contents

1. [Test Types](#test-types)
2. [Testing Components](#testing-components)
3. [Testing Redux](#testing-redux)
4. [Accessibility Testing](#accessibility-testing)
5. [Visual Regression Testing](#visual-regression-testing)
6. [Mocking](#mocking)
7. [Best Practices](#best-practices)

## Test Types

Our testing strategy includes several types of tests:

- **Unit Tests**: For testing individual components, functions, and hooks
- **Integration Tests**: For testing interactions between components and with Redux
- **Accessibility Tests**: For ensuring our UI is accessible to all users
- **Visual Regression Tests**: For detecting unintended visual changes
- **End-to-End Tests**: For validating complete user workflows (to be implemented)

## Testing Components

### Basic Component Tests

Use React Testing Library to test components by focusing on how users interact with them, not on implementation details.

```tsx
// Example: Testing a Button component
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Button } from '@/components/common/Button';

test('button executes callback when clicked', async () => {
  const handleClick = vi.fn();
  const user = userEvent.setup();
  
  render(<Button onClick={handleClick}>Click Me</Button>);
  const button = screen.getByRole('button', { name: /click me/i });
  
  await user.click(button);
  expect(handleClick).toHaveBeenCalledTimes(1);
});
```

### Testing Components with Redux

Use the `renderWithProviders` utility to test components that interact with Redux.

```tsx
// Example: Testing a component that uses Redux
import { renderWithProviders } from '../test-utils';
import { SymbolSelector } from '@/components/data/SymbolSelector';

test('SymbolSelector shows available symbols', () => {
  const { getByText } = renderWithProviders(<SymbolSelector />);
  expect(getByText('AAPL')).toBeInTheDocument();
});
```

## Testing Redux

### Testing Reducers

Test reducers by dispatching actions and checking the resulting state.

```tsx
import { configureStore } from '@reduxjs/toolkit';
import dataReducer, { setCurrentSymbol } from '@/store/slices/dataSlice';

test('setCurrentSymbol updates the symbol in state', () => {
  const store = configureStore({ reducer: { data: dataReducer } });
  store.dispatch(setCurrentSymbol('AAPL'));
  expect(store.getState().data.currentSymbol).toBe('AAPL');
});
```

### Testing Async Thunks

Test async thunks by mocking API calls and verifying state transitions.

```tsx
import { configureStore } from '@reduxjs/toolkit';
import dataReducer, { fetchData } from '@/store/slices/dataSlice';
import { loadData } from '@/api/endpoints/data';

// Mock API call
vi.mock('@/api/endpoints/data', () => ({
  loadData: vi.fn().mockResolvedValue({ /* mock data */ }),
}));

test('fetchData updates state correctly', async () => {
  const store = configureStore({ reducer: { data: dataReducer } });
  await store.dispatch(fetchData({ symbol: 'AAPL', timeframe: '1d' }));
  
  // Check loading states
  expect(store.getState().data.dataStatus).toBe('succeeded');
  expect(store.getState().data.error).toBeNull();
});
```

## Accessibility Testing

Use axe-core to test components for accessibility violations.

```tsx
import { checkAccessibility } from '../a11y-utils';
import { Button } from '@/components/common/Button';

test('Button has no accessibility violations', async () => {
  const results = await checkAccessibility(<Button>Click Me</Button>);
  expect(results).toHaveNoViolations();
});
```

## Visual Regression Testing

Use snapshot testing to detect unintended visual changes.

```tsx
import { render } from '@testing-library/react';
import { Card } from '@/components/common/Card';

test('Card renders correctly', () => {
  const { container } = render(
    <Card title="Test Card">
      <p>Card content</p>
    </Card>
  );
  expect(container).toMatchSnapshot();
});
```

## Mocking

### Mocking API Calls

```tsx
// Mock fetch or axios
global.fetch = vi.fn().mockImplementation(() => 
  Promise.resolve({
    ok: true,
    json: () => Promise.resolve(mockData),
  })
);

// Or use MSW for more complex API mocking
```

### Mocking Redux Hooks

```tsx
// Mock Redux hooks
vi.mock('@/store/hooks', () => ({
  useAppSelector: vi.fn().mockImplementation((selector) => 
    selector({ data: { symbols: ['AAPL', 'MSFT'] } })
  ),
  useAppDispatch: vi.fn().mockReturnValue(vi.fn()),
}));
```

## Best Practices

1. **Focus on user behavior**: Test what the user sees and does, not implementation details
2. **Use semantic queries**: Prefer `getByRole`, `getByLabelText`, etc. over `getByTestId`
3. **Test loading and error states**: Ensure your components handle all states gracefully
4. **Isolate tests**: Each test should be independent of others
5. **Test asynchronous behavior**: Use async/await with `waitFor` or `findBy*` queries
6. **Mock dependencies**: Isolate the component under test by mocking external dependencies
7. **Use RTL debugging**: When tests fail, use `screen.debug()` to see what's rendered

## Running Tests

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui
```

## Additional Resources

- [React Testing Library Docs](https://testing-library.com/docs/react-testing-library/intro/)
- [Vitest Docs](https://vitest.dev/)
- [Redux Testing Docs](https://redux.js.org/usage/writing-tests)
- [Axe-core Docs](https://github.com/dequelabs/axe-core)