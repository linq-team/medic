# Medic TypeScript Client

A type-safe TypeScript client for the Medic heartbeat monitoring service.

## Installation

```bash
npm install @linq-team/medic
```

## Configuration

Set the `MEDIC_BASE_URL` environment variable to point to your Medic instance:

```bash
export MEDIC_BASE_URL=https://your-medic-host.com
```

## Usage

### Simple Usage

```typescript
import { sendHeartbeat } from '@linq-team/medic';

// Uses MEDIC_BASE_URL environment variable
await sendHeartbeat({
  heartbeatName: 'my-service-heartbeat',
  serviceName: 'my-service',
  status: 'UP'
});
```

### Using a Custom Client

```typescript
import { MedicClient } from '@linq-team/medic';

const client = new MedicClient({
  baseUrl: 'https://your-medic-host.com',
  timeout: 5000, // Optional: 5 second timeout
});

await client.sendHeartbeat({
  heartbeatName: 'my-service-heartbeat',
  serviceName: 'my-service',
  status: 'UP'
});
```

### Registering a Service

```typescript
import { MedicClient } from '@linq-team/medic';

const client = new MedicClient({
  baseUrl: 'https://your-medic-host.com'
});

await client.registerService({
  heartbeatName: 'my-service-heartbeat',
  serviceName: 'my-service',
  alertInterval: 5, // minutes
  environment: 'production',
  threshold: 1,
  team: 'platform',
  priority: 'p2',
  runbook: 'https://docs.example.com/runbook'
});
```

### Querying Heartbeats

```typescript
import { MedicClient } from '@linq-team/medic';

const client = new MedicClient({
  baseUrl: 'https://your-medic-host.com'
});

const response = await client.getHeartbeats({
  heartbeatName: 'my-service-heartbeat',
  maxCount: 100
});

console.log(response.results);
```

### Error Handling

```typescript
import { sendHeartbeat, MedicError } from '@linq-team/medic';

try {
  await sendHeartbeat({
    heartbeatName: 'my-service-heartbeat',
    status: 'UP'
  });
} catch (error) {
  if (error instanceof MedicError) {
    console.error(`Medic API error: ${error.message}`);
    console.error(`Status code: ${error.statusCode}`);
  }
}
```

## API Reference

### Types

#### Heartbeat

```typescript
interface Heartbeat {
  heartbeatName: string;
  serviceName?: string;
  status: 'UP' | 'DOWN' | 'DEGRADED' | string;
}
```

#### MedicClientOptions

```typescript
interface MedicClientOptions {
  baseUrl?: string;
  timeout?: number;
  headers?: Record<string, string>;
}
```

### Classes

#### MedicClient

```typescript
class MedicClient {
  constructor(options?: MedicClientOptions);
  sendHeartbeat(heartbeat: Heartbeat): Promise<MedicResponse>;
  getHeartbeats(options?: GetHeartbeatsOptions): Promise<MedicResponse<Heartbeat[]>>;
  registerService(service: ServiceRegistration): Promise<MedicResponse>;
}
```

#### MedicError

```typescript
class MedicError extends Error {
  statusCode: number;
  response?: MedicResponse;
}
```

### Functions

#### sendHeartbeat

```typescript
function sendHeartbeat(heartbeat: Heartbeat): Promise<MedicResponse>;
```

Sends a heartbeat using the default client configuration.

#### configure

```typescript
function configure(options: MedicClientOptions): void;
```

Configures the default client with custom options.

## License

MIT
