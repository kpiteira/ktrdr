# Frontend Testing Setup

This document provides an overview of the testing infrastructure set up for the KTRDR frontend application.

## Testing Framework

We use the following tools for testing:

- **Vitest**: Main testing framework, compatible with Vite
- **React Testing Library**: For testing React components
- **Jest DOM**: For DOM-specific assertions
- **User Event**: For simulating user interactions
- **axe-core**: For accessibility testing

## Test Structure

The tests are organized into the following directories:

- `src/tests/components/`: Unit tests for UI components
- `src/tests/containers/`: Tests for container components (with Redux)
- `src/tests/store/`: Tests for Redux state management
- `src/tests/docs/`: Documentation and examples for testing

## Types of Tests

1. **Component Tests**: Test individual UI components in isolation
2. **Redux Tests**: Test Redux slices, actions, and reducers
3. **Snapshot Tests**: Detect unintended visual changes
4. **Accessibility Tests**: Ensure components meet accessibility guidelines

## Running Tests

```sh
# Run all tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run tests with UI visualization
npm run test:ui
```

## Test Utilities

We've created several utilities to make testing easier:

- `renderWithProviders`: Renders components with Redux and other providers
- `mockApiResponses`: Provides mock data for testing API-dependent components
- `checkAccessibility`: Utility for testing component accessibility

## Mocking Strategy

For testing components that depend on external services or complex state:

1. Use the mocking utilities in `src/tests/test-utils.tsx`
2. Mock Redux hooks with `vi.mock('@/store/hooks')`
3. Mock API endpoints with `vi.mock('@/api/endpoints/data')`

## Known Issues

1. Some accessibility tests are currently skipped due to configuration issues with axe-core.
2. The error message test for DataSelectionContainer is skipped due to mocking issues.

These will be addressed in future updates.

## Best Practices

1. Test behavior, not implementation details
2. Use semantic queries (getByRole, getByLabelText, etc.)
3. Test loading, success, and error states
4. Write focused tests that verify a single piece of functionality
5. Use descriptive test names to document component behavior

## Further Documentation

For more detailed information about testing patterns and examples, see the comprehensive testing guide in `src/tests/docs/testing-guide.md`.