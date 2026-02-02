/**
 * Medic TypeScript Client
 *
 * A type-safe client for the Medic heartbeat monitoring service.
 */

/** Status values for heartbeat */
export type HeartbeatStatus = 'UP' | 'DOWN' | 'DEGRADED' | string;

/** Heartbeat payload structure */
export interface Heartbeat {
  /** Name of the registered heartbeat */
  heartbeatName: string;
  /** Name of the associated service */
  serviceName?: string;
  /** Current status of the service */
  status: HeartbeatStatus;
}

/** API response structure */
export interface MedicResponse<T = unknown> {
  success: boolean;
  message: string;
  results: T;
}

/** Configuration options for the Medic client */
export interface MedicClientOptions {
  /** Base URL for the Medic API */
  baseUrl?: string;
  /** Request timeout in milliseconds */
  timeout?: number;
  /** Custom headers to include in requests */
  headers?: Record<string, string>;
}

/** Default base URL if none provided and no environment variable set */
const DEFAULT_BASE_URL = 'https://medic.example.com';

/** Default timeout in milliseconds */
const DEFAULT_TIMEOUT = 30000;

/**
 * Get the base URL from environment or default
 */
function getBaseUrl(): string {
  // Check for Node.js environment variable
  if (typeof process !== 'undefined' && process.env?.MEDIC_BASE_URL) {
    return process.env.MEDIC_BASE_URL;
  }
  return DEFAULT_BASE_URL;
}

/**
 * Medic API Client
 *
 * Provides methods for interacting with the Medic heartbeat monitoring service.
 *
 * @example
 * ```typescript
 * const client = new MedicClient({ baseUrl: 'https://medic.example.com' });
 * await client.sendHeartbeat({
 *   heartbeatName: 'my-service-heartbeat',
 *   serviceName: 'my-service',
 *   status: 'UP'
 * });
 * ```
 */
export class MedicClient {
  private readonly baseUrl: string;
  private readonly timeout: number;
  private readonly headers: Record<string, string>;

  constructor(options: MedicClientOptions = {}) {
    this.baseUrl = options.baseUrl || getBaseUrl();
    this.timeout = options.timeout || DEFAULT_TIMEOUT;
    this.headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };
  }

  /**
   * Send a heartbeat to the Medic service
   *
   * @param heartbeat - The heartbeat data to send
   * @returns Promise resolving to the API response
   * @throws Error if the request fails
   */
  async sendHeartbeat(heartbeat: Heartbeat): Promise<MedicResponse> {
    const url = `${this.baseUrl}/heartbeat`;
    const body = JSON.stringify({
      heartbeat_name: heartbeat.heartbeatName,
      service_name: heartbeat.serviceName,
      status: heartbeat.status,
    });

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: this.headers,
        body,
        signal: controller.signal,
      });

      const data = await response.json() as MedicResponse;

      if (!response.ok) {
        throw new MedicError(
          data.message || `HTTP ${response.status}`,
          response.status,
          data
        );
      }

      return data;
    } catch (error) {
      if (error instanceof MedicError) {
        throw error;
      }
      if (error instanceof Error && error.name === 'AbortError') {
        throw new MedicError('Request timeout', 408);
      }
      throw new MedicError(
        error instanceof Error ? error.message : 'Unknown error',
        0
      );
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Get heartbeat events
   *
   * @param options - Query options
   * @returns Promise resolving to the list of heartbeats
   */
  async getHeartbeats(options: {
    heartbeatName?: string;
    serviceName?: string;
    maxCount?: number;
  } = {}): Promise<MedicResponse<Heartbeat[]>> {
    const params = new URLSearchParams();
    if (options.heartbeatName) params.set('heartbeat_name', options.heartbeatName);
    if (options.serviceName) params.set('service_name', options.serviceName);
    if (options.maxCount) params.set('maxCount', options.maxCount.toString());

    const url = `${this.baseUrl}/heartbeat${params.toString() ? `?${params}` : ''}`;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: this.headers,
        signal: controller.signal,
      });

      const data = await response.json() as MedicResponse<Heartbeat[]>;

      if (!response.ok) {
        throw new MedicError(
          data.message || `HTTP ${response.status}`,
          response.status,
          data
        );
      }

      return data;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Register a new heartbeat service
   *
   * @param service - The service registration data
   * @returns Promise resolving to the API response
   */
  async registerService(service: {
    heartbeatName: string;
    serviceName: string;
    alertInterval: number;
    environment?: string;
    threshold?: number;
    team?: string;
    priority?: string;
    runbook?: string;
  }): Promise<MedicResponse> {
    const url = `${this.baseUrl}/service`;
    const body = JSON.stringify({
      heartbeat_name: service.heartbeatName,
      service_name: service.serviceName,
      alert_interval: service.alertInterval,
      environment: service.environment,
      threshold: service.threshold,
      team: service.team,
      priority: service.priority,
      runbook: service.runbook,
    });

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: this.headers,
        body,
        signal: controller.signal,
      });

      const data = await response.json() as MedicResponse;

      if (!response.ok) {
        throw new MedicError(
          data.message || `HTTP ${response.status}`,
          response.status,
          data
        );
      }

      return data;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}

/**
 * Custom error class for Medic API errors
 */
export class MedicError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly response?: MedicResponse
  ) {
    super(message);
    this.name = 'MedicError';
  }
}

// Default client instance
let defaultClient: MedicClient | null = null;

/**
 * Get or create the default client instance
 */
function getDefaultClient(): MedicClient {
  if (!defaultClient) {
    defaultClient = new MedicClient();
  }
  return defaultClient;
}

/**
 * Send a heartbeat using the default client
 *
 * @param heartbeat - The heartbeat data to send
 * @returns Promise resolving to the API response
 *
 * @example
 * ```typescript
 * await sendHeartbeat({
 *   heartbeatName: 'my-service-heartbeat',
 *   serviceName: 'my-service',
 *   status: 'UP'
 * });
 * ```
 */
export async function sendHeartbeat(heartbeat: Heartbeat): Promise<MedicResponse> {
  return getDefaultClient().sendHeartbeat(heartbeat);
}

/**
 * Configure the default client
 *
 * @param options - Client configuration options
 */
export function configure(options: MedicClientOptions): void {
  defaultClient = new MedicClient(options);
}

export default MedicClient;
