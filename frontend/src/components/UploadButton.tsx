/**
 * Upload button component that triggers file upload.
 */

import { useUpload } from '@/hooks/useUpload';
import { useUploadStore } from '@/store/uploadStore';
import './UploadButton.css';

export function UploadButton() {
  const { upload, canUpload, isUploading } = useUpload();
  const { priority, setPriority } = useUploadStore();

  const handleUpload = async () => {
    await upload();
  };

  return (
    <div className="upload-controls">
      <div className="priority-select">
        <label htmlFor="priority">Priority:</label>
        <select
          id="priority"
          value={priority}
          onChange={(e) => setPriority(e.target.value as 'high' | 'normal' | 'low')}
          disabled={isUploading}
        >
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>
      </div>

      <button
        type="button"
        className="btn btn-primary btn-upload"
        onClick={handleUpload}
        disabled={!canUpload}
      >
        {isUploading ? 'Uploading...' : 'Upload Files'}
      </button>
    </div>
  );
}
