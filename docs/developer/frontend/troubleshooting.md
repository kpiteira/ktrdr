# Frontend Troubleshooting Guide

This document provides solutions for common issues you may encounter when developing or working with the KTRDR frontend application.

## Table of Contents

- [Startup and Build Issues](#startup-and-build-issues)
- [State Management Issues](#state-management-issues)
- [API Integration Issues](#api-integration-issues)
- [UI and Component Issues](#ui-and-component-issues)
- [Performance Issues](#performance-issues)
- [Testing Issues](#testing-issues)
- [TypeScript Issues](#typescript-issues)
- [Development Environment Issues](#development-environment-issues)

## Startup and Build Issues

### Application Doesn't Start

**Symptoms**: `npm run dev` or `yarn dev` command fails to start the development server.

**Possible Causes and Solutions**:

1. **Port Conflict**:
   - **Cause**: Port 3000 is already in use by another application.
   - **Solution**: Either stop the other application or change the port in `vite.config.ts`:
     ```typescript
     export default defineConfig({
       server: {
         port: 3001, // Change to an available port
       },
       // other config
     });
     ```

2. **Dependencies Not Installed**:
   - **Cause**: Missing node modules.
   - **Solution**: Run `npm install` or `yarn install` to install dependencies.

3. **Environment Variables**:
   - **Cause**: Missing or incorrectly formatted environment variables.
   - **Solution**: Verify `.env.local` file exists and is properly formatted.

### Build Fails

**Symptoms**: `npm run build` or `yarn build` command fails with errors.

**Possible Causes and Solutions**:

1. **TypeScript Errors**:
   - **Cause**: Type errors in the codebase.
   - **Solution**: Run `npm run typecheck` or `yarn typecheck` to identify errors and fix them.

2. **Missing Dependencies**:
   - **Cause**: Required dependencies are missing or outdated.
   - **Solution**: Check for missing dependencies in error messages and install them.

3. **Incompatible Dependency Versions**:
   - **Cause**: Conflicts between dependencies.
   - **Solution**: Check package.json for version conflicts and resolve them.

## State Management Issues

### Redux State Not Updating

**Symptoms**: UI doesn't reflect changes to Redux state.

**Possible Causes and Solutions**:

1. **Selector Issues**:
   - **Cause**: Incorrect selector implementation.
   - **Solution**: Verify selectors are correctly accessing state:
     ```typescript
     // Incorrect
     const data = useSelector(state.data.items);
     
     // Correct
     const data = useSelector(state => state.data.items);
     ```

2. **Action Dispatching**:
   - **Cause**: Action not dispatched or incorrect payload.
   - **Solution**: Use Redux DevTools to verify actions are being dispatched with correct payload.

3. **Reducer Logic**:
   - **Cause**: Reducer not handling action correctly.
   - **Solution**: Verify reducer logic correctly updates state based on action.

### Redux DevTools Not Working

**Symptoms**: Redux DevTools extension shows no state or actions.

**Possible Causes and Solutions**:

1. **Extension Not Installed**:
   - **Cause**: Redux DevTools browser extension not installed.
   - **Solution**: Install the extension from browser store.

2. **Store Configuration**:
   - **Cause**: Store not configured to work with DevTools.
   - **Solution**: Verify store configuration includes DevTools setup:
     ```typescript
     const store = configureStore({
       reducer: rootReducer,
       middleware: (getDefaultMiddleware) => getDefaultMiddleware(),
       devTools: process.env.NODE_ENV !== 'production',
     });
     ```

## API Integration Issues

### API Requests Failing

**Symptoms**: API requests fail with errors or timeouts.

**Possible Causes and Solutions**:

1. **API Server Not Running**:
   - **Cause**: Backend API server is not running.
   - **Solution**: Start the backend API server.

2. **Incorrect API URL**:
   - **Cause**: API base URL is incorrect.
   - **Solution**: Check the `VITE_API_BASE_URL` environment variable.

3. **CORS Issues**:
   - **Cause**: Backend server doesn't allow requests from frontend.
   - **Solution**: Configure CORS on the backend server:
     ```javascript
     // Backend CORS setup example
     app.use(cors({
       origin: 'http://localhost:3000',
       credentials: true,
     }));
     ```

4. **Authentication Issues**:
   - **Cause**: Missing or invalid authentication token.
   - **Solution**: Check if token is being sent in requests and is valid.

### API Error Handling

**Symptoms**: Application crashes or shows generic errors when API requests fail.

**Possible Causes and Solutions**:

1. **Missing Error Handling**:
   - **Cause**: No error handling for API requests.
   - **Solution**: Implement proper error handling in API hooks:
     ```typescript
     const { data, error, isLoading } = useGetDataQuery();
     
     if (isLoading) return <LoadingSpinner />;
     if (error) return <ErrorMessage message={error.message} />;
     ```

2. **Inconsistent Error Format**:
   - **Cause**: Backend returns inconsistent error formats.
   - **Solution**: Normalize error responses in API client interceptors.

## UI and Component Issues

### Components Not Rendering

**Symptoms**: Components are not visible or render incorrectly.

**Possible Causes and Solutions**:

1. **Conditional Rendering Issues**:
   - **Cause**: Incorrect conditional logic.
   - **Solution**: Verify conditional rendering expressions:
     ```tsx
     // Incorrect (common mistake)
     {isLoading && <LoadingSpinner />}
     {error && <ErrorMessage />}
     {data && <DataDisplay />}
     
     // Better approach
     {isLoading ? (
       <LoadingSpinner />
     ) : error ? (
       <ErrorMessage />
     ) : data ? (
       <DataDisplay data={data} />
     ) : (
       <EmptyState />
     )}
     ```

2. **Missing Key Prop**:
   - **Cause**: Missing key prop in list rendering.
   - **Solution**: Add unique key to list items:
     ```tsx
     {items.map(item => (
       <ListItem key={item.id} data={item} />
     ))}
     ```

3. **CSS Issues**:
   - **Cause**: CSS conflicts or missing styles.
   - **Solution**: Check CSS rules and component styling.

### Layout and Responsive Design Issues

**Symptoms**: Layout breaks on different screen sizes or elements overlap.

**Possible Causes and Solutions**:

1. **Missing Responsive Design**:
   - **Cause**: No media queries or responsive units.
   - **Solution**: Implement responsive design with media queries and relative units:
     ```css
     .container {
       width: 100%;
       max-width: 1200px;
     }
     
     @media (max-width: 768px) {
       .container {
         padding: 0 1rem;
       }
     }
     ```

2. **Flexbox/Grid Issues**:
   - **Cause**: Incorrect flex or grid properties.
   - **Solution**: Verify flex/grid container and item properties.

3. **Z-index Stacking**:
   - **Cause**: Incorrect z-index causing elements to overlap.
   - **Solution**: Audit z-index values and establish a z-index system.

## Performance Issues

### Slow Initial Load

**Symptoms**: Application takes a long time to load initially.

**Possible Causes and Solutions**:

1. **Large Bundle Size**:
   - **Cause**: Too many dependencies or inefficient code splitting.
   - **Solution**: Implement code splitting for routes and large components:
     ```typescript
     // Lazy loading components
     const LazyComponent = React.lazy(() => import('./LazyComponent'));
     
     // Usage with Suspense
     <Suspense fallback={<LoadingSpinner />}>
       <LazyComponent />
     </Suspense>
     ```

2. **Large Assets**:
   - **Cause**: Unoptimized images or assets.
   - **Solution**: Optimize assets and implement lazy loading for images.

3. **Too Many Initial API Requests**:
   - **Cause**: Multiple API requests on initial load.
   - **Solution**: Combine requests or prioritize critical data loading.

### Component Re-rendering Issues

**Symptoms**: UI feels sluggish or performs poorly when interacting.

**Possible Causes and Solutions**:

1. **Excessive Re-renders**:
   - **Cause**: Components re-render too frequently.
   - **Solution**: Use React.memo, useMemo, and useCallback to prevent unnecessary re-renders:
     ```typescript
     // Memoize expensive component
     const MemoizedComponent = React.memo(MyComponent);
     
     // Memoize expensive calculations
     const memoizedValue = useMemo(() => computeExpensiveValue(a, b), [a, b]);
     
     // Memoize callbacks
     const memoizedCallback = useCallback(() => {
       doSomething(a, b);
     }, [a, b]);
     ```

2. **Large Lists/Tables**:
   - **Cause**: Rendering large data sets without virtualization.
   - **Solution**: Implement virtualization for large lists:
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

## Testing Issues

### Tests Failing

**Symptoms**: Unit or integration tests fail when running.

**Possible Causes and Solutions**:

1. **Testing Environment Issues**:
   - **Cause**: Incorrect testing environment setup.
   - **Solution**: Verify testing environment configuration in `vitest.config.ts`.

2. **Component Dependency Issues**:
   - **Cause**: Tests failing due to missing provider components.
   - **Solution**: Use proper test wrappers for tested components:
     ```typescript
     const renderWithProviders = (ui, options = {}) => {
       return render(
         <Provider store={setupStore()}>
           <ThemeProvider theme={theme}>{ui}</ThemeProvider>
         </Provider>,
         options
       );
     };
     ```

3. **Outdated Snapshots**:
   - **Cause**: Component changed but snapshots weren't updated.
   - **Solution**: Update snapshots with `npm run test -- -u` or `yarn test -u`.

### Mocking Issues

**Symptoms**: Tests fail due to external dependencies or API calls.

**Possible Causes and Solutions**:

1. **API Calls in Tests**:
   - **Cause**: Real API calls in tests.
   - **Solution**: Mock API calls:
     ```typescript
     vi.mock('../api/dataApi', () => ({
       useGetDataQuery: () => ({
         data: mockData,
         isLoading: false,
         error: null,
       }),
     }));
     ```

2. **Browser API Mocking**:
   - **Cause**: Tests using unavailable browser APIs.
   - **Solution**: Mock browser APIs:
     ```typescript
     // Mock localStorage
     beforeEach(() => {
       Object.defineProperty(window, 'localStorage', {
         value: {
           getItem: vi.fn(),
           setItem: vi.fn(),
         },
         writable: true,
       });
     });
     ```

## TypeScript Issues

### Type Errors

**Symptoms**: TypeScript errors when building or type checking.

**Possible Causes and Solutions**:

1. **Incorrect Type Definitions**:
   - **Cause**: Types don't match implementation.
   - **Solution**: Fix type definitions to match implementation.

2. **Missing Type Declarations**:
   - **Cause**: Types not defined for variables or functions.
   - **Solution**: Add proper type declarations:
     ```typescript
     // Incorrect
     const getData = (param) => {
       return api.get(`/data/${param}`);
     };
     
     // Correct
     const getData = (param: string): Promise<DataResponse> => {
       return api.get<DataResponse>(`/data/${param}`);
     };
     ```

3. **Library Type Issues**:
   - **Cause**: Missing type definitions for libraries.
   - **Solution**: Install @types packages for the libraries:
     ```bash
     npm install --save-dev @types/library-name
     ```

### Third-Party Library Type Issues

**Symptoms**: TypeScript errors related to third-party libraries.

**Possible Causes and Solutions**:

1. **Missing Type Definitions**:
   - **Cause**: Library doesn't include or have available type definitions.
   - **Solution**: Create custom type declarations in a `.d.ts` file:
     ```typescript
     // src/types/library-name.d.ts
     declare module 'library-name' {
       export function someFunction(): void;
       export interface SomeInterface {
         prop: string;
       }
     }
     ```

## Development Environment Issues

### Hot Module Replacement Not Working

**Symptoms**: Changes to code don't automatically update in the browser.

**Possible Causes and Solutions**:

1. **Vite Configuration**:
   - **Cause**: HMR not properly configured.
   - **Solution**: Verify Vite HMR configuration:
     ```typescript
     // vite.config.ts
     export default defineConfig({
       server: {
         hmr: true,
       },
       // other config
     });
     ```

2. **React Component Issues**:
   - **Cause**: Component structure not compatible with HMR.
   - **Solution**: Use proper component export patterns and React.memo.

### Environment Variables Not Working

**Symptoms**: Environment variables are undefined in the application.

**Possible Causes and Solutions**:

1. **Naming Convention**:
   - **Cause**: Environment variables not prefixed with `VITE_`.
   - **Solution**: Rename environment variables to start with `VITE_`:
     ```
     // Incorrect
     API_URL=http://localhost:5000
     
     // Correct
     VITE_API_URL=http://localhost:5000
     ```

2. **Environment File Loading**:
   - **Cause**: Environment file not being loaded.
   - **Solution**: Verify file naming and placement (.env.local at project root).

3. **Cache Issues**:
   - **Cause**: Changes to environment variables not reflected due to caching.
   - **Solution**: Restart the development server after changing environment variables.