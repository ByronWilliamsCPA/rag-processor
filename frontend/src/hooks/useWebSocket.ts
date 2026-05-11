/**
 * WebSocket hook for real-time batch status updates.
 *
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Event replay on reconnect (sends last_event_id)
 * - Ping/pong keepalive handling
 * - Graceful connection management
 */

import { useCallback, useEffect, useRef, useState } from 'react';

/** Event types matching backend EventType enum */
export type EventType =
  | 'job_queued'
  | 'job_processing'
  | 'job_completed'
  | 'job_failed'
  | 'batch_created'
  | 'batch_completed'
  | 'batch_failed';

/** WebSocket event from backend */
export interface BatchEvent {
  event_id: string;
  event_type: EventType;
  batch_id: string;
  job_id: string | null;
  status: string;
  message: string;
  data: Record<string, unknown>;
  timestamp: string;
}

/** System messages from WebSocket */
export interface SystemMessage {
  type: 'connected' | 'ping' | 'pong' | 'error' | 'server_restarting';
  batch_id?: string;
  message?: string;
  timestamp?: number;
}

/** Combined message type */
export type WebSocketMessage = BatchEvent | SystemMessage;

/** Connection state */
export type ConnectionState =
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'reconnecting'
  | 'error';

/** Hook options */
export interface UseWebSocketOptions {
  /** Batch ID to subscribe to */
  batchId: string;
  /** Authentication token (Cloudflare Access JWT) */
  token?: string;
  /** Enable auto-reconnect (default: true) */
  autoReconnect?: boolean;
  /** Maximum reconnection attempts (default: 10) */
  maxReconnectAttempts?: number;
  /** Base delay for reconnect backoff in ms (default: 1000) */
  reconnectBaseDelay?: number;
  /** Maximum reconnect delay in ms (default: 30000) */
  maxReconnectDelay?: number;
  /** Callback when event received */
  onEvent?: (event: BatchEvent) => void;
  /** Callback when connection state changes */
  onStateChange?: (state: ConnectionState) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

/** Hook return value */
export interface UseWebSocketReturn {
  /** Current connection state */
  connectionState: ConnectionState;
  /** All received events (oldest first) */
  events: BatchEvent[];
  /** Most recent event */
  lastEvent: BatchEvent | null;
  /** Last error message */
  error: string | null;
  /** Manually connect */
  connect: () => void;
  /** Manually disconnect */
  disconnect: () => void;
  /** Clear all events */
  clearEvents: () => void;
  /** Current reconnect attempt count */
  reconnectAttempt: number;
}

/**
 * Check if a message is a BatchEvent (has event_id and event_type)
 */
function isBatchEvent(msg: WebSocketMessage): msg is BatchEvent {
  return 'event_id' in msg && 'event_type' in msg;
}

/**
 * Hook for WebSocket connection to batch status stream.
 *
 * @param options - Configuration options
 * @returns WebSocket state and controls
 *
 * @example
 * ```tsx
 * const { connectionState, events, lastEvent } = useWebSocket({
 *   batchId: 'abc-123',
 *   token: cfAccessToken,
 *   onEvent: (event) => console.log('New event:', event),
 * });
 * ```
 */
export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    batchId,
    token,
    autoReconnect = true,
    maxReconnectAttempts = 10,
    reconnectBaseDelay = 1000,
    maxReconnectDelay = 30000,
    onEvent,
    onStateChange,
    onError,
  } = options;

  // State
  const [connectionState, setConnectionState] =
    useState<ConnectionState>('disconnected');
  const [events, setEvents] = useState<BatchEvent[]>([]);
  const [lastEvent, setLastEvent] = useState<BatchEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  // Refs for values that shouldn't trigger re-renders
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastEventIdRef = useRef<string | null>(null);
  const isManualDisconnectRef = useRef(false);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Update connection state with callback
  const updateConnectionState = useCallback(
    (state: ConnectionState) => {
      setConnectionState(state);
      onStateChange?.(state);
    },
    [onStateChange]
  );

  // Calculate reconnect delay with exponential backoff
  const getReconnectDelay = useCallback(
    (attempt: number): number => {
      const delay = reconnectBaseDelay * Math.pow(2, attempt);
      // Add jitter (0-25% of delay)
      const jitter = delay * 0.25 * Math.random();
      return Math.min(delay + jitter, maxReconnectDelay);
    },
    [reconnectBaseDelay, maxReconnectDelay]
  );

  // Build WebSocket URL
  const buildWsUrl = useCallback((): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : window.location.host;

    let url = `${protocol}//${host}/ws/batch/${batchId}`;

    const params = new URLSearchParams();
    if (token) {
      params.set('token', token);
    }
    if (lastEventIdRef.current) {
      params.set('last_event_id', lastEventIdRef.current);
    }

    const queryString = params.toString();
    if (queryString) {
      url += `?${queryString}`;
    }

    return url;
  }, [batchId, token]);

  // Send ping to keep connection alive
  const sendPing = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'ping', timestamp: Date.now() })
      );
    }
  }, []);

  // Start ping interval
  const startPingInterval = useCallback(() => {
    // Clear existing interval
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    // Ping every 25 seconds (server expects activity within 30s)
    pingIntervalRef.current = setInterval(sendPing, 25000);
  }, [sendPing]);

  // Stop ping interval
  const stopPingInterval = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  // Handle incoming message
  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage;

        // Handle system messages
        if ('type' in data) {
          const sysMsg = data as SystemMessage;

          switch (sysMsg.type) {
            case 'connected':
              updateConnectionState('connected');
              setReconnectAttempt(0);
              break;
            case 'ping':
              // Respond to server ping with pong
              wsRef.current?.send(
                JSON.stringify({ type: 'pong', timestamp: Date.now() })
              );
              break;
            case 'pong':
              // Server responded to our ping - connection is alive
              break;
            case 'server_restarting':
              // Server is shutting down, prepare to reconnect
              updateConnectionState('reconnecting');
              break;
            case 'error':
              setError(sysMsg.message || 'Unknown error');
              onError?.(new Error(sysMsg.message || 'WebSocket error'));
              break;
          }
        }

        // Handle batch events
        if (isBatchEvent(data)) {
          // Update last event ID for replay on reconnect
          lastEventIdRef.current = data.event_id;

          // Add to events list
          setEvents((prev) => [...prev, data]);
          setLastEvent(data);

          // Call callback
          onEvent?.(data);
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    },
    [onEvent, onError, updateConnectionState]
  );

  // Schedule reconnection
  const scheduleReconnect = useCallback(() => {
    if (!autoReconnect || isManualDisconnectRef.current) {
      return;
    }

    if (reconnectAttempt >= maxReconnectAttempts) {
      setError(`Failed to reconnect after ${maxReconnectAttempts} attempts`);
      updateConnectionState('error');
      return;
    }

    const delay = getReconnectDelay(reconnectAttempt);
    updateConnectionState('reconnecting');

    reconnectTimeoutRef.current = setTimeout(() => {
      setReconnectAttempt((prev) => prev + 1);
      // Connect will be called by effect when reconnectAttempt changes
    }, delay);
  }, [
    autoReconnect,
    reconnectAttempt,
    maxReconnectAttempts,
    getReconnectDelay,
    updateConnectionState,
  ]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    isManualDisconnectRef.current = false;
    setError(null);
    updateConnectionState('connecting');

    try {
      const url = buildWsUrl();
      const ws = new WebSocket(url);

      ws.onopen = () => {
        startPingInterval();
      };

      ws.onmessage = handleMessage;

      ws.onerror = () => {
        setError('WebSocket connection error');
        onError?.(new Error('WebSocket connection error'));
      };

      ws.onclose = (event) => {
        stopPingInterval();

        if (!isManualDisconnectRef.current) {
          // Abnormal close - attempt reconnect
          if (event.code !== 1000 && event.code !== 1001) {
            scheduleReconnect();
          } else {
            updateConnectionState('disconnected');
          }
        } else {
          updateConnectionState('disconnected');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect');
      onError?.(err instanceof Error ? err : new Error('Failed to connect'));
      updateConnectionState('error');
    }
  }, [
    buildWsUrl,
    handleMessage,
    onError,
    scheduleReconnect,
    startPingInterval,
    stopPingInterval,
    updateConnectionState,
  ]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    isManualDisconnectRef.current = true;

    // Clear reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    stopPingInterval();

    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }

    updateConnectionState('disconnected');
    setReconnectAttempt(0);
  }, [stopPingInterval, updateConnectionState]);

  // Clear events
  const clearEvents = useCallback(() => {
    setEvents([]);
    setLastEvent(null);
    lastEventIdRef.current = null;
  }, []);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    connect();

    return () => {
      isManualDisconnectRef.current = true;
      stopPingInterval();

      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }

      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
      }
    };
    // Only run on mount/unmount and when batchId changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchId]);

  // Reconnect when attempt counter increases
  useEffect(() => {
    if (
      reconnectAttempt > 0 &&
      connectionState === 'reconnecting' &&
      !isManualDisconnectRef.current
    ) {
      connect();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reconnectAttempt]);

  return {
    connectionState,
    events,
    lastEvent,
    error,
    connect,
    disconnect,
    clearEvents,
    reconnectAttempt,
  };
}
