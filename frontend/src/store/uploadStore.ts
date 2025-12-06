/**
 * Zustand store for file upload state management.
 */

import { create } from 'zustand';
import type { FileWithPreview, IngestResponse } from '@/types/upload';

interface UploadStore {
  // State
  files: FileWithPreview[];
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  response: IngestResponse | null;
  priority: 'high' | 'normal' | 'low';
  targetVectorStore: string | null;

  // Actions
  addFiles: (files: FileWithPreview[]) => void;
  removeFile: (filename: string) => void;
  clearFiles: () => void;
  setUploading: (uploading: boolean) => void;
  setProgress: (progress: number) => void;
  setError: (error: string | null) => void;
  setResponse: (response: IngestResponse | null) => void;
  setPriority: (priority: 'high' | 'normal' | 'low') => void;
  setTargetVectorStore: (store: string | null) => void;
  reset: () => void;
}

const initialState = {
  files: [],
  isUploading: false,
  uploadProgress: 0,
  error: null,
  response: null,
  priority: 'normal' as const,
  targetVectorStore: null,
};

export const useUploadStore = create<UploadStore>((set) => ({
  ...initialState,

  addFiles: (newFiles) =>
    set((state) => ({
      files: [...state.files, ...newFiles],
      error: null,
    })),

  removeFile: (filename) =>
    set((state) => ({
      files: state.files.filter((f) => f.name !== filename),
    })),

  clearFiles: () =>
    set({
      files: [],
      error: null,
      response: null,
    }),

  setUploading: (uploading) =>
    set({
      isUploading: uploading,
      error: uploading ? null : undefined,
    }),

  setProgress: (progress) =>
    set({
      uploadProgress: progress,
    }),

  setError: (error) =>
    set({
      error,
      isUploading: false,
    }),

  setResponse: (response) =>
    set({
      response,
      isUploading: false,
      uploadProgress: 100,
    }),

  setPriority: (priority) =>
    set({
      priority,
    }),

  setTargetVectorStore: (store) =>
    set({
      targetVectorStore: store,
    }),

  reset: () => set(initialState),
}));
