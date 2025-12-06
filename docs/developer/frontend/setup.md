# Frontend Developer Setup Guide

This guide will walk you through setting up the KTRDR frontend development environment and getting started with development.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Development Environment](#development-environment)
- [Running the Application](#running-the-application)
- [Development Workflow](#development-workflow)
- [Environment Configuration](#environment-configuration)
- [Debugging](#debugging)
- [Common Issues](#common-issues)

## Prerequisites

Before you begin, ensure you have the following installed:

- **Node.js** (v16.x or higher)
- **npm** (v8.x or higher) or **yarn** (v1.22.x or higher)
- **Git** for version control
- A code editor (we recommend **Visual Studio Code**)

## Installation

Follow these steps to set up the frontend application:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/ktrdr.git
   cd ktrdr
   ```

2. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

3. **Install dependencies**:
   ```bash
   # Using npm
   npm install

   # Using yarn
   yarn install
   ```

## Development Environment

### Recommended VS Code Extensions

We recommend installing the following VS Code extensions for an optimal development experience:

- **ESLint** - For JavaScript/TypeScript linting
- **Prettier** - For code formatting
- **vscode-styled-components** - For styled-components syntax highlighting
- **Redux DevTools** - For Redux state debugging
- **TypeScript Error Translator** - For more readable TypeScript errors

### Editor Configuration

Create a `.vscode/settings.json` file in the frontend directory with the following content:

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "editor.codeActionsOnSave": {
    "source.fixAll.eslint": true
  },
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.enablePromptUseWorkspaceTsdk": true,
  "eslint.validate": [
    "javascript",
    "javascriptreact",
    "typescript",
    "typescriptreact"
  ]
}
```

## Running the Application

### Development Mode

To start the development server:

```bash
# Using npm
npm run dev

# Using yarn
yarn dev
```

This will start the development server on `http://localhost:3000` (or another port if 3000 is already in use).

### Production Build

To create a production build:

```bash
# Using npm
npm run build

# Using yarn
yarn build
```

To preview the production build locally:

```bash
# Using npm
npm run preview

# Using yarn
yarn preview
```

### Running with Docker

We provide a Docker setup for consistent development environments:

```bash
# Build and start the development container
docker compose up -d

# Stop the container
docker compose down
```

## Development Workflow

### Branch Management

Follow these guidelines for branch management:

1. **Create a feature branch** from the `main` branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and commit them with clear messages:
   ```bash
   git add .
   git commit -m "feat: add new feature"
   ```

3. **Push your branch** to the remote repository:
   ```bash
   git push -u origin feature/your-feature-name
   ```

4. **Create a Pull Request** for review.

### Commit Message Format

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification for commit messages:

- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `style:` for formatting changes
- `refactor:` for code refactoring
- `test:` for adding or fixing tests
- `chore:` for maintenance tasks

### Code Style

Our codebase follows a consistent code style enforced by ESLint and Prettier. Run the linter to ensure your code conforms to our standards:

```bash
# Using npm
npm run lint

# Using yarn
yarn lint
```

To automatically fix linting issues:

```bash
# Using npm
npm run lint:fix

# Using yarn
yarn lint:fix
```

### Type Checking

Run TypeScript type checking:

```bash
# Using npm
npm run typecheck

# Using yarn
yarn typecheck
```

## Environment Configuration

The frontend application uses environment variables for configuration. Create a `.env.local` file in the frontend directory with the following variables:

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:5000/api

# Feature Flags
VITE_ENABLE_BETA_FEATURES=false

# Application Settings
VITE_APP_NAME="KTRDR"
VITE_DEFAULT_THEME=dark
```

For different environments, you can use:
- `.env.development` - Development environment settings
- `.env.production` - Production environment settings
- `.env.test` - Test environment settings

### Available Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| VITE_API_BASE_URL | Base URL for API requests | http://localhost:5000/api |
| VITE_ENABLE_BETA_FEATURES | Enable beta features | false |
| VITE_DEFAULT_THEME | Default application theme | dark |
| VITE_LOG_LEVEL | Application log level | info |

## Debugging

### Browser DevTools

The application is configured to work with Redux DevTools for state debugging:

1. Install the [Redux DevTools Extension](https://github.com/reduxjs/redux-devtools) for your browser
2. Open DevTools in your browser and navigate to the Redux tab
3. You can now inspect state, actions, and state changes

### Debugging API Calls

For API debugging:

1. Open DevTools in your browser and navigate to the Network tab
2. Filter by "Fetch/XHR" to see only API calls
3. Click on a request to see details, including request/response headers and body

### Vite Debug Mode

For Vite-specific issues, you can enable debug mode:

```bash
# Using npm
DEBUG=vite:* npm run dev

# Using yarn
DEBUG=vite:* yarn dev
```

## Common Issues

### "Module not found" Errors

If you encounter "Module not found" errors:

1. Make sure all dependencies are installed: `npm install` or `yarn install`
2. Check for path typos in import statements
3. Verify the module exists in `node_modules`
4. Try clearing the Vite cache: `npm run clean` or `yarn clean`

### API Connection Issues

If you cannot connect to the API:

1. Verify the API server is running
2. Check the `VITE_API_BASE_URL` environment variable is set correctly
3. Look for CORS issues in the browser console
4. Ensure the API endpoint exists and is properly implemented

### Build Errors

For build errors:

1. Check TypeScript errors: `npm run typecheck` or `yarn typecheck`
2. Fix linting issues: `npm run lint:fix` or `yarn lint:fix`
3. Make sure all dependencies are updated: `npm update` or `yarn upgrade`
4. Clear the cache and node_modules: 
   ```bash
   rm -rf node_modules
   rm -rf .vite
   npm install
   ```

### Hot Module Replacement Issues

If changes aren't reflected immediately:

1. Check for console errors
2. Ensure your components are properly set up for HMR
3. Try restarting the development server
4. Clear browser cache and reload

### Content Security Policy Issues

If you encounter CSP errors in the console:

1. Check the Content Security Policy in your `index.html`
2. Ensure the policy allows connections to all required resources
3. During development, you may need to disable CSP in your browser for local testing