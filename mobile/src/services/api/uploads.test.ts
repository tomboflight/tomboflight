import {
  canDownloadUpload,
  canPreviewUpload,
  getProtectedUploadUrl,
  uploadStatusLabel
} from './uploads';

describe('mobile upload contract helpers', () => {
  it('builds a protected route without exposing a storage URL', () => {
    expect(getProtectedUploadUrl('upload-123', 'preview', 'project-456')).toBe(
      'https://tomboflight-api.onrender.com/uploads/upload-123/preview?viewer_project_id=project-456'
    );
  });

  it('keeps protected actions driven by backend permissions', () => {
    const upload = {
      permissions: {
        can_preview: true,
        can_download: false
      }
    };

    expect(canPreviewUpload(upload)).toBe(true);
    expect(canDownloadUpload(upload)).toBe(false);
  });

  it('fails closed for quarantine and non-clean scans', () => {
    expect(uploadStatusLabel({ quarantined: true, scan_status: 'clean' })).toContain('Blocked');
    expect(uploadStatusLabel({ scan_status: 'pending' })).toBe('Security scan in progress');
    expect(uploadStatusLabel({ scan_status: 'error' })).toContain('Blocked');
  });

  it('reports clean approved uploads as approved', () => {
    expect(
      uploadStatusLabel({
        scan_status: 'clean',
        verification_status: 'approved',
        approved_for_cinematic: true
      })
    ).toBe('Approved');
  });
});
