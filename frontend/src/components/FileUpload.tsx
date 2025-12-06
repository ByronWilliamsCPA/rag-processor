/**
 * FileUpload component with drag-and-drop support.
 */

import { useCallback, useMemo } from 'react';
import { useDropzone } from 'react-dropzone';
import { useUploadStore } from '@/store/uploadStore';
import {
  ALLOWED_MIME_TYPES,
  MAX_FILE_SIZE_BYTES,
  MAX_FILE_SIZE_MB,
  type FileWithPreview,
} from '@/types/upload';
import './FileUpload.css';

/**
 * Format file size to human-readable string.
 */
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';

  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Get file type icon based on MIME type.
 */
function getFileIcon(mimeType: string): string {
  if (mimeType.startsWith('image/')) return '🖼️';
  if (mimeType.startsWith('audio/')) return '🎵';
  if (mimeType.startsWith('video/')) return '🎬';
  if (mimeType === 'application/pdf') return '📄';
  if (mimeType.includes('word') || mimeType.includes('document')) return '📝';
  if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return '📊';
  if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return '📽️';
  if (mimeType.startsWith('text/')) return '📃';
  return '📁';
}

export function FileUpload() {
  const {
    files,
    isUploading,
    uploadProgress,
    error,
    response,
    addFiles,
    removeFile,
    clearFiles,
    setError,
  } = useUploadStore();

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: { file: File; errors: { message: string }[] }[]) => {
      // Handle rejected files
      if (rejectedFiles.length > 0) {
        const errors = rejectedFiles.map((r) => `${r.file.name}: ${r.errors[0]?.message || 'Invalid file'}`);
        setError(errors.join('; '));
        return;
      }

      // Add previews for images
      const filesWithPreview: FileWithPreview[] = acceptedFiles.map((file) =>
        Object.assign(file, {
          preview: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
        }),
      );

      addFiles(filesWithPreview);
    },
    [addFiles, setError],
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ALLOWED_MIME_TYPES.reduce(
      (acc, type) => ({ ...acc, [type]: [] }),
      {} as Record<string, string[]>,
    ),
    maxSize: MAX_FILE_SIZE_BYTES,
    disabled: isUploading,
  });

  const totalSize = useMemo(() => files.reduce((acc, f) => acc + f.size, 0), [files]);

  const dropzoneClassName = useMemo(() => {
    const classes = ['dropzone'];
    if (isDragActive) classes.push('dropzone--active');
    if (isDragReject) classes.push('dropzone--reject');
    if (isUploading) classes.push('dropzone--disabled');
    return classes.join(' ');
  }, [isDragActive, isDragReject, isUploading]);

  return (
    <div className="file-upload">
      <div {...getRootProps()} className={dropzoneClassName}>
        <input {...getInputProps()} />
        <div className="dropzone-content">
          <div className="dropzone-icon">📁</div>
          {isDragActive ? (
            <p>Drop the files here...</p>
          ) : (
            <>
              <p>Drag and drop files here, or click to select files</p>
              <span className="dropzone-hint">
                Max {MAX_FILE_SIZE_MB}MB per file. Supported: PDF, images, audio, video, documents
              </span>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="upload-error" role="alert">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
          <button
            type="button"
            className="error-dismiss"
            onClick={() => setError(null)}
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {files.length > 0 && (
        <div className="file-list">
          <div className="file-list-header">
            <h4>Selected Files ({files.length})</h4>
            <span className="file-list-size">Total: {formatFileSize(totalSize)}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={clearFiles}
              disabled={isUploading}
            >
              Clear All
            </button>
          </div>

          <ul className="file-items">
            {files.map((file) => (
              <li key={file.name} className="file-item">
                <span className="file-icon">{getFileIcon(file.type)}</span>
                <div className="file-info">
                  <span className="file-name" title={file.name}>
                    {file.name}
                  </span>
                  <span className="file-meta">
                    {file.type || 'Unknown type'} • {formatFileSize(file.size)}
                  </span>
                </div>
                <button
                  type="button"
                  className="file-remove"
                  onClick={() => removeFile(file.name)}
                  disabled={isUploading}
                  aria-label={`Remove ${file.name}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isUploading && (
        <div className="upload-progress">
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${uploadProgress}%` }} />
          </div>
          <span className="progress-text">Uploading... {uploadProgress}%</span>
        </div>
      )}

      {response && (
        <div className="upload-success" role="status">
          <span className="success-icon">✓</span>
          <div className="success-content">
            <strong>{response.message}</strong>
            <p>Batch ID: {response.batch_id}</p>
            <ul className="job-list">
              {response.jobs.map((job) => (
                <li key={job.job_id}>
                  {job.filename} - {job.status}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
