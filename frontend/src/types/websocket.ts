/**
 * Types for WebSocket communication.
 *
 * These types match the backend event structure defined in
 * src/rag_processor/websocket/events.py
 */

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

/** Job update from WebSocket event */
export interface JobUpdate {
  jobId: string;
  status: string;
  message?: string;
  progress?: number;
  error?: string;
  retryCount?: number;
}

/** Batch update from WebSocket event */
export interface BatchUpdate {
  batchId: string;
  status: string;
  completedJobs: number;
  totalJobs: number;
  failedJobs: number;
}
