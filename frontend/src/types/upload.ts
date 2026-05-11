/**
 * Types for file upload functionality.
 */

export type Priority = 'high' | 'normal' | 'low';

export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';

export type BatchStatus = 'queued' | 'processing' | 'completed' | 'partial' | 'failed';

export interface JobResponse {
  job_id: string;
  filename: string;
  file_type: string;
  file_size_bytes: number;
  status: JobStatus;
}

export interface IngestResponse {
  batch_id: string;
  status: BatchStatus;
  total_files: number;
  jobs: JobResponse[];
  message: string;
}

export interface FileWithPreview extends File {
  preview?: string;
}

export interface UploadState {
  files: FileWithPreview[];
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  response: IngestResponse | null;
}

export interface ValidationError {
  filename: string;
  error: string;
}

// Allowed MIME types matching backend configuration
export const ALLOWED_MIME_TYPES = [
  // PDF
  'application/pdf',
  // Images
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'image/tiff',
  // Audio
  'audio/mpeg',
  'audio/wav',
  'audio/mp4',
  'audio/ogg',
  'audio/flac',
  // Video
  'video/mp4',
  'video/webm',
  'video/quicktime',
  // Documents
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.ms-powerpoint',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  // Text
  'text/plain',
  'text/markdown',
  'text/csv',
];

export const MAX_FILE_SIZE_MB = 100;
export const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
