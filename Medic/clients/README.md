# Medic Clients

* [Overview](#Overview)
* [Configuration](#Configuration)
* [Clients](#Clients)
    * [Go](#golang)
    * [Python](#python)
    * [Ruby](#ruby)
    * [TypeScript](#typescript)

## Overview

Below are sample and importable clients for various languages to make integrating your service into Medic easier.

API Docs for Medic are available at your deployed instance (e.g., `https://your-medic-host/docs`).

## Configuration

All clients support the `MEDIC_BASE_URL` environment variable to configure the Medic API endpoint:

```bash
export MEDIC_BASE_URL=https://your-medic-host.com
```

## Clients

Select the client that is best for your project to get started.

## Go

You can import the Go package via the following URL in your code:

```go
import medic "github.com/linq-team/medic/Medic/clients/go"
```

Example code:

```go
package main

import (
    medic "github.com/linq-team/medic/Medic/clients/go"
)

func main() {
    h := medic.Heartbeat{
        HeartbeatName: "my-service-heartbeat",
        Service:       "my-service",
        Status:        "UP",
    }

    // Uses MEDIC_BASE_URL env var or default
    err := medic.SendHeartbeat(h)
    if err != nil {
        // Handle error
    }

    // Or use a custom client with explicit URL
    client := medic.NewClient("https://custom-medic.example.com")
    err = client.SendHeartbeat(h)
}
```

## Python

Example Code:

```python
import os
from medic import SendHeartbeat

# Set the environment variable
os.environ["MEDIC_BASE_URL"] = "https://your-medic-host.com"

# Send a heartbeat
success = SendHeartbeat(
    heartbeat_name="my-service-heartbeat",
    service_name="my-service",
    status="UP"
)

# Or pass the URL directly
success = SendHeartbeat(
    heartbeat_name="my-service-heartbeat",
    service_name="my-service",
    status="UP",
    base_url="https://custom-medic.example.com"
)
```

## Ruby

Example Code:

```ruby
require_relative 'medic'

# Set the environment variable
ENV['MEDIC_BASE_URL'] = 'https://your-medic-host.com'

# Send a heartbeat
response = sendHeartbeat('my-service-heartbeat', 'my-service', 'UP')

# Or pass the URL directly
response = sendHeartbeat(
  'my-service-heartbeat',
  'my-service',
  'UP',
  base_url: 'https://custom-medic.example.com'
)
```

## TypeScript

Example Code:

```typescript
import { MedicClient, sendHeartbeat } from '@linq-team/medic';

// Using environment variable (MEDIC_BASE_URL)
await sendHeartbeat({
  heartbeatName: 'my-service-heartbeat',
  serviceName: 'my-service',
  status: 'UP'
});

// Or create a client with explicit configuration
const client = new MedicClient({
  baseUrl: 'https://your-medic-host.com'
});

await client.sendHeartbeat({
  heartbeatName: 'my-service-heartbeat',
  serviceName: 'my-service',
  status: 'UP'
});
```
