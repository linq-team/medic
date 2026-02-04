# Medic UI

Web-based administrative dashboard for the Medic service monitoring platform. Built with React, TypeScript, and Vite.

## Features

- **Dashboard**: Overview of service health with summary cards (Total Services, Active, Down, Active Alerts)
- **Services**: List, search, filter, and sort monitored services with detailed views
- **Alerts**: View active and historical alerts with priority-based color coding
- **Playbooks**: Manage automated remediation playbooks
- **Audit Logs**: Track playbook execution history with filtering and pagination
- **Settings**: Configure theme preferences and auto-refresh intervals

## Tech Stack

- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite 7
- **Styling**: Tailwind CSS 4 with Linq brand colors
- **Components**: shadcn/ui (Radix UI primitives)
- **State Management**: React Query (TanStack Query) for server state
- **Routing**: React Router v6
- **Icons**: Lucide React
- **Font**: Geist (sans and mono)
- **Testing**: Vitest with React Testing Library

## Prerequisites

- Node.js 22+ (LTS recommended)
- npm 10+
- Access to a running Medic API instance

## Getting Started

### Local Development

1. **Install dependencies**:
   ```bash
   cd ui
   npm install
   ```

2. **Start the development server**:
   ```bash
   npm run dev
   ```
   The UI will be available at `http://localhost:5173`

3. **Configure API endpoint**:
   By default, the UI proxies API requests to `/api`. In development, you may need to configure the Vite proxy in `vite.config.ts` to point to your local Medic API instance.

### Docker Development

Run the full stack with Docker Compose from the repository root:

```bash
docker-compose up --build
```

This starts:
- PostgreSQL database on port 5432
- Medic API on port 5000
- Medic Worker (background monitor)
- Medic UI on port 80

The UI is served by nginx, which proxies `/api/*` requests to the Medic API.

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server with hot reload |
| `npm run build` | TypeScript compile + production build |
| `npm run preview` | Preview production build locally |
| `npm run test` | Run unit tests once |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage report |
| `npm run lint` | Run ESLint on all files |
| `npm run lint:fix` | Run ESLint and auto-fix issues |
| `npm run format` | Format code with Prettier |
| `npm run typecheck` | Run TypeScript type checking |

## Environment Variables

The UI uses runtime configuration rather than build-time environment variables. Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| API Base URL | Configured in `src/lib/api.ts` | `/api` |

### API Proxy Configuration

In development, API requests are proxied through Vite. In production (Docker), nginx handles the proxy:

- `/api/*` → Medic API (`http://medic-api:5000/`)
- `/ws` → WebSocket endpoint (for future real-time features)
- `/*` → Static React files

## Authentication

The UI uses API key authentication:

1. Navigate to the login page (`/login`)
2. Enter your Medic API key
3. The key is validated against the `/health` endpoint
4. On success, the key is stored in `sessionStorage` (cleared on browser close)

API keys are sent in the `Authorization` header as Bearer tokens.

## Project Structure

```
ui/
├── public/
│   ├── assets/          # Static assets (logo, images)
│   └── fonts/           # Geist font files
├── src/
│   ├── components/      # React components
│   │   ├── ui/          # shadcn/ui base components
│   │   ├── layout.tsx   # Main layout with sidebar
│   │   ├── header.tsx   # App header with logo
│   │   ├── sidebar.tsx  # Navigation sidebar
│   │   └── ...          # Feature components
│   ├── hooks/           # Custom React hooks
│   │   ├── use-services.ts
│   │   ├── use-alerts.ts
│   │   ├── use-playbooks.ts
│   │   └── use-audit-logs.ts
│   ├── lib/
│   │   ├── api.ts       # API client with TypeScript types
│   │   └── utils.ts     # Utility functions (cn, etc.)
│   ├── pages/           # Route page components
│   │   ├── Dashboard.tsx
│   │   ├── Services.tsx
│   │   ├── Alerts.tsx
│   │   └── ...
│   ├── test/            # Test setup and utilities
│   ├── App.tsx          # Route configuration
│   ├── main.tsx         # Application entry point
│   └── index.css        # Global styles and Tailwind
├── Dockerfile           # Multi-stage Docker build
├── nginx.conf           # Production nginx configuration
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## Styling

### Linq Brand Colors

The UI uses Linq brand colors configured in Tailwind:

| Color | Hex | Usage |
|-------|-----|-------|
| Black | `#141414` | Dark mode background |
| Cream | `#FCF9E9` | Light mode background |
| Sage | `#B0BFB7` | Secondary elements |
| Linq Blue | `#4F9FDF` | Primary actions, links |
| Navy | `#1B3D67` | Headers, emphasis |
| Linq Green | `#83B149` | Healthy status |
| Lime | `#E8DF6E` | Highlights |

### Status Colors

| Status | Light Mode | Dark Mode |
|--------|------------|-----------|
| Healthy | `#83B149` | `#83B149` |
| Warning | `#CA8A04` | `#EAB308` |
| Error | `#DC2626` | `#EF4444` |
| Critical | `#991B1B` | `#DC2626` |

### Theme Support

- Light mode (default)
- Dark mode
- System preference detection

Theme preference is persisted in `localStorage` under the key `medic-ui-theme`.

## Testing

Tests are located alongside their source files with the `.test.tsx` or `.test.ts` suffix.

```bash
# Run all tests
npm run test

# Run tests in watch mode during development
npm run test:watch

# Generate coverage report
npm run test:coverage
```

### Test Coverage

Core components have unit tests:
- `ThemeProvider` - Theme switching and persistence
- `AuthProvider` - Authentication state management
- `API client` - Request handling and error cases

## Building for Production

```bash
# Build production bundle
npm run build

# Preview production build
npm run preview
```

Production builds output to the `dist/` directory and are optimized for deployment.

## Docker Deployment

The `Dockerfile` uses a multi-stage build:

1. **Builder stage**: Node.js builds the React application
2. **Production stage**: nginx serves static files and proxies API requests

```bash
# Build the Docker image
docker build -t medic-ui ./ui

# Run the container
docker run -p 80:80 medic-ui
```

## Troubleshooting

### API Connection Issues

1. Verify the Medic API is running and accessible
2. Check browser console for CORS errors
3. Ensure the API key is valid

### Build Errors

1. Run `npm run typecheck` to identify TypeScript errors
2. Run `npm run lint` to check for linting issues
3. Ensure all dependencies are installed: `npm ci`

### Style Issues

1. Verify Tailwind is processing CSS: check for `@tailwind` directives in `index.css`
2. Clear browser cache if styles appear stale
3. Restart the dev server after config changes

## Contributing

1. Follow existing code patterns and conventions
2. Run `npm run lint` and `npm run typecheck` before committing
3. Write tests for new features
4. Use conventional commit messages

## License

See the main repository LICENSE file.
