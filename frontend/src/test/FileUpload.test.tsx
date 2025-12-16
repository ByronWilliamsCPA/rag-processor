import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FileUpload } from '@/components/FileUpload';
import { useUploadStore } from '@/store/uploadStore';
import { useUpload } from '@/hooks/useUpload';

// Mock react-dropzone
vi.mock('react-dropzone', () => ({
  useDropzone: vi.fn(() => ({
    getRootProps: vi.fn(() => ({ 'data-testid': 'dropzone' })),
    getInputProps: vi.fn(() => ({ 'data-testid': 'file-input' })),
    isDragActive: false,
    isDragReject: false,
  })),
}));

// Mock the upload store
vi.mock('@/store/uploadStore');

// Mock the useUpload hook
vi.mock('@/hooks/useUpload');

describe('FileUpload', () => {
  const mockAddFiles = vi.fn();
  const mockRemoveFile = vi.fn();
  const mockClearFiles = vi.fn();
  const mockSetError = vi.fn();
  const mockUpload = vi.fn();

  const defaultStoreState = {
    files: [] as File[],
    isUploading: false,
    uploadProgress: 0,
    error: null as string | null,
    response: null,
    addFiles: mockAddFiles,
    removeFile: mockRemoveFile,
    clearFiles: mockClearFiles,
    setError: mockSetError,
  };

  const defaultUploadHookState = {
    upload: mockUpload,
    isUploading: false,
    uploadProgress: 0,
    error: null as string | null,
    response: null,
    canUpload: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useUploadStore).mockReturnValue(defaultStoreState);
    vi.mocked(useUpload).mockReturnValue(defaultUploadHookState);
  });

  it('renders the dropzone with instructions', () => {
    render(<FileUpload />);
    expect(screen.getByText(/Drag and drop files here/i)).toBeInTheDocument();
  });

  it('displays file size and type hints', () => {
    render(<FileUpload />);
    expect(screen.getByText(/Max.*MB per file/i)).toBeInTheDocument();
    expect(screen.getByText(/Supported: PDF, images, audio, video, documents/i)).toBeInTheDocument();
  });

  it('shows error message when there is an error', () => {
    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      error: 'File too large',
    });

    render(<FileUpload />);
    expect(screen.getByText('File too large')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('allows dismissing error message', () => {
    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      error: 'File too large',
    });

    render(<FileUpload />);
    const dismissButton = screen.getByLabelText('Dismiss error');
    fireEvent.click(dismissButton);
    expect(mockSetError).toHaveBeenCalledWith(null);
  });

  it('displays list of selected files', () => {
    const mockFiles = [
      { name: 'test.pdf', type: 'application/pdf', size: 1024 },
      { name: 'image.png', type: 'image/png', size: 2048 },
    ] as File[];

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      files: mockFiles,
    });

    render(<FileUpload />);
    expect(screen.getByText('test.pdf')).toBeInTheDocument();
    expect(screen.getByText('image.png')).toBeInTheDocument();
    expect(screen.getByText('Selected Files (2)')).toBeInTheDocument();
  });

  it('allows removing individual files', () => {
    const mockFiles = [{ name: 'test.pdf', type: 'application/pdf', size: 1024 }] as File[];

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      files: mockFiles,
    });

    render(<FileUpload />);
    const removeButton = screen.getByLabelText('Remove test.pdf');
    fireEvent.click(removeButton);
    expect(mockRemoveFile).toHaveBeenCalledWith('test.pdf');
  });

  it('allows clearing all files', () => {
    const mockFiles = [
      { name: 'test.pdf', type: 'application/pdf', size: 1024 },
      { name: 'image.png', type: 'image/png', size: 2048 },
    ] as File[];

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      files: mockFiles,
    });

    render(<FileUpload />);
    const clearButton = screen.getByText('Clear All');
    fireEvent.click(clearButton);
    expect(mockClearFiles).toHaveBeenCalled();
  });

  it('shows upload progress when uploading', () => {
    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      isUploading: true,
      uploadProgress: 50,
    });

    render(<FileUpload />);
    expect(screen.getByText('Uploading... 50%')).toBeInTheDocument();
  });

  it('shows success message with batch details after upload', () => {
    const mockResponse = {
      message: 'Upload successful',
      batch_id: 'batch-123',
      jobs: [
        { job_id: 'job-1', filename: 'test.pdf', status: 'queued' },
        { job_id: 'job-2', filename: 'image.png', status: 'queued' },
      ],
    };

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      response: mockResponse,
    });

    render(<FileUpload />);
    expect(screen.getByText('Upload successful')).toBeInTheDocument();
    expect(screen.getByText(/Batch ID: batch-123/)).toBeInTheDocument();
    expect(screen.getByText(/test.pdf - queued/)).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('disables clear button during upload', () => {
    const mockFiles = [{ name: 'test.pdf', type: 'application/pdf', size: 1024 }] as File[];

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      files: mockFiles,
      isUploading: true,
    });

    render(<FileUpload />);
    const clearButton = screen.getByText('Clear All');
    expect(clearButton).toBeDisabled();
  });

  it('disables remove buttons during upload', () => {
    const mockFiles = [{ name: 'test.pdf', type: 'application/pdf', size: 1024 }] as File[];

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      files: mockFiles,
      isUploading: true,
    });

    render(<FileUpload />);
    const removeButton = screen.getByLabelText('Remove test.pdf');
    expect(removeButton).toBeDisabled();
  });

  it('displays total file size', () => {
    const mockFiles = [
      { name: 'test.pdf', type: 'application/pdf', size: 1024 },
      { name: 'image.png', type: 'image/png', size: 1024 },
    ] as File[];

    vi.mocked(useUploadStore).mockReturnValue({
      ...defaultStoreState,
      files: mockFiles,
    });

    render(<FileUpload />);
    expect(screen.getByText(/Total: 2 KB/)).toBeInTheDocument();
  });

  describe('Retry functionality', () => {
    it('shows retry button when there is an error and files are present', () => {
      const mockFiles = [{ name: 'test.pdf', type: 'application/pdf', size: 1024 }] as File[];

      vi.mocked(useUploadStore).mockReturnValue({
        ...defaultStoreState,
        files: mockFiles,
        error: 'Upload failed',
      });

      render(<FileUpload />);
      expect(screen.getByLabelText('Retry upload')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });

    it('does not show retry button when error exists but no files', () => {
      vi.mocked(useUploadStore).mockReturnValue({
        ...defaultStoreState,
        files: [],
        error: 'Upload failed',
      });

      render(<FileUpload />);
      expect(screen.queryByLabelText('Retry upload')).not.toBeInTheDocument();
    });

    it('calls upload when retry button is clicked', () => {
      const mockFiles = [{ name: 'test.pdf', type: 'application/pdf', size: 1024 }] as File[];

      vi.mocked(useUploadStore).mockReturnValue({
        ...defaultStoreState,
        files: mockFiles,
        error: 'Upload failed',
      });

      render(<FileUpload />);
      const retryButton = screen.getByLabelText('Retry upload');
      fireEvent.click(retryButton);

      expect(mockSetError).toHaveBeenCalledWith(null);
      expect(mockUpload).toHaveBeenCalled();
    });

    it('clears error before retrying upload', () => {
      const mockFiles = [{ name: 'test.pdf', type: 'application/pdf', size: 1024 }] as File[];

      vi.mocked(useUploadStore).mockReturnValue({
        ...defaultStoreState,
        files: mockFiles,
        error: 'Network error',
      });

      render(<FileUpload />);
      const retryButton = screen.getByLabelText('Retry upload');
      fireEvent.click(retryButton);

      // Verify setError is called before upload
      expect(mockSetError).toHaveBeenCalledWith(null);
      expect(mockUpload).toHaveBeenCalledTimes(1);
    });
  });
});
