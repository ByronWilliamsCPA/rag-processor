/**
 * Hook for uploading files to the ingest API.
 */

import { useCallback } from 'react';
import axios, { type AxiosProgressEvent } from 'axios';
import { useUploadStore } from '@/store/uploadStore';
import type { IngestResponse, Priority } from '@/types/upload';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface UploadOptions {
  priority?: Priority;
  targetVectorStore?: string | null;
}

interface UseUploadReturn {
  upload: (options?: UploadOptions) => Promise<IngestResponse | null>;
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  response: IngestResponse | null;
  canUpload: boolean;
}

export function useUpload(): UseUploadReturn {
  const {
    files,
    isUploading,
    uploadProgress,
    error,
    response,
    priority: defaultPriority,
    targetVectorStore: defaultTargetVectorStore,
    setUploading,
    setProgress,
    setError,
    setResponse,
    clearFiles,
  } = useUploadStore();

  const upload = useCallback(
    async (options?: UploadOptions): Promise<IngestResponse | null> => {
      if (files.length === 0) {
        setError('No files selected');
        return null;
      }

      setUploading(true);
      setProgress(0);

      try {
        const formData = new FormData();

        // Add files
        files.forEach((file) => {
          formData.append('files', file);
        });

        // Add priority
        const priority = options?.priority ?? defaultPriority;
        formData.append('priority', priority);

        // Add target vector store if specified
        const targetVectorStore = options?.targetVectorStore ?? defaultTargetVectorStore;
        if (targetVectorStore) {
          formData.append('target_vector_store', targetVectorStore);
        }

        const response = await axios.post<IngestResponse>(
          `${API_BASE_URL}/api/v1/ingest`,
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
            withCredentials: true, // Send cookies for Cloudflare Access auth
            timeout: 300000, // 5 minute timeout for large file uploads
            onUploadProgress: (progressEvent: AxiosProgressEvent) => {
              if (progressEvent.total) {
                const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
                setProgress(progress);
              }
            },
          },
        );

        setResponse(response.data);
        clearFiles();
        return response.data;
      } catch (err) {
        let errorMessage = 'Upload failed';

        if (axios.isAxiosError(err)) {
          if (err.response?.status === 401) {
            errorMessage = 'Authentication required. Please log in.';
          } else if (err.response?.status === 400) {
            const detail = err.response.data?.detail;
            if (typeof detail === 'string') {
              errorMessage = detail;
            } else if (detail?.message) {
              errorMessage = detail.message;
              if (detail.errors?.length) {
                errorMessage += ': ' + detail.errors.join('; ');
              }
            }
          } else if (err.response?.status === 413) {
            errorMessage = 'File(s) too large';
          } else if (err.message) {
            errorMessage = err.message;
          }
        }

        setError(errorMessage);
        return null;
      }
    },
    [
      files,
      defaultPriority,
      defaultTargetVectorStore,
      setUploading,
      setProgress,
      setError,
      setResponse,
      clearFiles,
    ],
  );

  return {
    upload,
    isUploading,
    uploadProgress,
    error,
    response,
    canUpload: files.length > 0 && !isUploading,
  };
}
