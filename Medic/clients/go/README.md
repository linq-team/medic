# Medic Go Client

`import "github.com/linq-team/medic/Medic/clients/go"`

## Overview

The Medic package allows you to easily integrate an already registered service for posting heartbeats.

## Installation

```bash
go get github.com/linq-team/medic/Medic/clients/go
```

## Configuration

Set the `MEDIC_BASE_URL` environment variable to point to your Medic instance:

```bash
export MEDIC_BASE_URL=https://your-medic-host.com
```

## Usage

### Simple Usage

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

    err := medic.SendHeartbeat(h)
    if err != nil {
        // Handle error
    }
}
```

### Using a Custom Client

```go
package main

import (
    medic "github.com/linq-team/medic/Medic/clients/go"
)

func main() {
    // Create a client with a custom base URL
    client := medic.NewClient("https://custom-medic.example.com")

    h := medic.Heartbeat{
        HeartbeatName: "my-service-heartbeat",
        Service:       "my-service",
        Status:        "UP",
    }

    err := client.SendHeartbeat(h)
    if err != nil {
        // Handle error
    }
}
```

## API Reference

### Types

#### Heartbeat

```go
type Heartbeat struct {
    HeartbeatName string `validate:"required" json:"heartbeat_name"`
    Service       string `json:"service_name"`
    Status        string `json:"status"`
}
```

#### Client

```go
type Client struct {
    BaseURL    string
    HTTPClient *http.Client
}
```

### Functions

#### NewClient

```go
func NewClient(baseURL string) *Client
```

Creates a new Medic client. If baseURL is empty, uses the `MEDIC_BASE_URL` environment variable or the default URL.

#### SendHeartbeat

```go
func SendHeartbeat(h Heartbeat) error
```

Sends a heartbeat using the default client configuration.

#### (c *Client) SendHeartbeat

```go
func (c *Client) SendHeartbeat(h Heartbeat) error
```

Sends a heartbeat using the specified client configuration.
