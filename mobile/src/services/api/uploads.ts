import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';

import { API_CONFIG, API_ENDPOINTS } from '../../config';
import { getAccessToken } from '../auth/auth-state';
import { ApiError, apiRequest } from './client';
import { UploadRecordPayload } from './workspace';

export type MobileFileAsset = {
  uri: string;
  name: string;
  mimeType?: string | null;
  size?: number | null;
};

export type UploadStatusPayload = {
  state?: string;
  message?: string;
  [key: string]: unknown;
};

export type UploadMutationPayload = {
  message?: string;
  upload?: UploadRecordPayload;
  replacement?: UploadRecordPayload;
  upload_status?: UploadStatusPayload | string;
  idempotency_replayed?: boolean;
  [key: string]: unknown;
};

function withAuthToken(token?: string): string | undefined {
  return token || getAccessToken() || undefined;
}

function assertFile(file: MobileFileAsset): void {
  if (!file.uri || !file.name) {
    throw new Error('Choose a file before uploading.');
  }
}

function appendField(body: FormData, key: string, value: string | undefined): void {
  if (value !== undefined && value !== '') {
    body.append(key, value);
  }
}

function appendFile(body: FormData, file: MobileFileAsset): void {
  body.append(
    'file',
    {
      uri: file.uri,
      name: file.name,
      type: file.mimeType || 'application/octet-stream'
    } as unknown as Blob
  );
}

function createIdempotencyKey(prefix: string): string {
  const random = Math.random().toString(36).slice(2, 12);
  return `mobile-${prefix}-${Date.now().toString(36)}-${random}`;
}

async function postMultipart(
  path: string,
  fields: Record<string, string | undefined>,
  file: MobileFileAsset,
  prefix: string,
  token?: string
): Promise<UploadMutationPayload> {
  assertFile(file);
  const body = new FormData();

  Object.entries(fields).forEach(([key, value]) => appendField(body, key, value));
  appendFile(body, file);

  return apiRequest<UploadMutationPayload>(path, {
    method: 'POST',
    token: withAuthToken(token),
    headers: {
      'Idempotency-Key': createIdempotencyKey(prefix)
    },
    body
  });
}

export async function uploadMemberPhoto(args: {
  familyId: string;
  memberId: string;
  file: MobileFileAsset;
  token?: string;
}): Promise<UploadMutationPayload> {
  const familyId = String(args.familyId || '').trim();
  const memberId = String(args.memberId || '').trim();
  if (!familyId || !memberId) {
    throw new Error('Choose a family member before uploading a portrait.');
  }

  return postMultipart(
    API_ENDPOINTS.uploads.memberPhoto,
    {
      family_id: familyId,
      member_id: memberId,
      consent_attested: 'true',
      authority_attested: 'true'
    },
    args.file,
    'portrait-upload',
    args.token
  );
}

export async function uploadVerificationEvidence(args: {
  familyId: string;
  memberId: string;
  verificationType: string;
  evidenceKind?: string;
  file: MobileFileAsset;
  token?: string;
}): Promise<UploadMutationPayload> {
  const familyId = String(args.familyId || '').trim();
  const memberId = String(args.memberId || '').trim();
  const verificationType = String(args.verificationType || '').trim();
  if (!familyId || !memberId || !verificationType) {
    throw new Error('Choose a family member and verification record type before uploading.');
  }

  return postMultipart(
    API_ENDPOINTS.uploads.verificationEvidence,
    {
      family_id: familyId,
      member_id: memberId,
      verification_type: verificationType,
      evidence_kind: String(args.evidenceKind || verificationType).trim()
    },
    args.file,
    'verification-evidence',
    args.token
  );
}

export async function uploadVaultFile(args: {
  projectId: string;
  familyId?: string;
  memberId?: string;
  assetType: 'vault_photo' | 'vault_document' | 'private_voice_message' | 'private_video_message';
  privacyScope?: 'private_to_owner' | 'private_to_owner_and_co_owner' | 'household_private' | 'linked_family_shared';
  vaultScope?: string;
  releaseState?: 'released' | 'scheduled';
  revealAt?: string;
  file: MobileFileAsset;
  token?: string;
}): Promise<UploadMutationPayload> {
  const projectId = String(args.projectId || '').trim();
  if (!projectId) {
    throw new Error('An active project is required before uploading to Vault.');
  }

  return postMultipart(
    API_ENDPOINTS.uploads.privateMedia,
    {
      project_id: projectId,
      family_id: String(args.familyId || '').trim() || undefined,
      member_id: String(args.memberId || '').trim() || undefined,
      asset_type: args.assetType,
      privacy_scope: args.privacyScope || 'private_to_owner',
      vault_scope: String(args.vaultScope || '').trim() || undefined,
      release_state: args.releaseState || 'released',
      reveal_at: args.revealAt || undefined,
      consent_attested: 'true',
      authority_attested: 'true'
    },
    args.file,
    'vault-upload',
    args.token
  );
}

export function getProtectedUploadUrl(
  uploadId: string,
  operation: 'preview' | 'download',
  viewerProjectId?: string
): string {
  const normalizedId = String(uploadId || '').trim();
  if (!normalizedId) {
    throw new Error('Upload id is required.');
  }

  const params = new URLSearchParams();
  const projectId = String(viewerProjectId || '').trim();
  if (projectId) {
    params.set('viewer_project_id', projectId);
  }

  const query = params.toString();
  const path = API_ENDPOINTS.uploads.protected(normalizedId, operation);
  return `${API_CONFIG.baseUrl}${path}${query ? `?${query}` : ''}`;
}

function safeCacheName(uploadId: string, operation: string): string {
  return `tol-${operation}-${String(uploadId).replace(/[^a-zA-Z0-9_-]/g, '')}`;
}

export async function cacheProtectedUpload(args: {
  uploadId: string;
  operation?: 'preview' | 'download';
  viewerProjectId?: string;
  token?: string;
}): Promise<string> {
  const operation = args.operation || 'preview';
  const cacheDirectory = FileSystem.cacheDirectory;
  if (!cacheDirectory) {
    throw new Error('Secure device storage is unavailable for this file.');
  }

  const destination = `${cacheDirectory}${safeCacheName(args.uploadId, operation)}`;
  try {
    await FileSystem.deleteAsync(destination, { idempotent: true });
  } catch {
    // A missing cache entry is expected on first use.
  }

  const result = await FileSystem.downloadAsync(
    getProtectedUploadUrl(args.uploadId, operation, args.viewerProjectId),
    destination,
    {
      headers: withAuthToken(args.token)
        ? { Authorization: `Bearer ${withAuthToken(args.token)}` }
        : undefined
    }
  );

  if (result.status < 200 || result.status >= 300) {
    throw new ApiError(result.status, 'The protected file could not be opened.');
  }

  return result.uri;
}

export async function shareProtectedUpload(args: {
  uploadId: string;
  viewerProjectId?: string;
  fileName?: string;
  token?: string;
}): Promise<string> {
  const localUri = await cacheProtectedUpload({
    uploadId: args.uploadId,
    operation: 'download',
    viewerProjectId: args.viewerProjectId,
    token: args.token
  });

  if (!(await Sharing.isAvailableAsync())) {
    throw new Error('Secure file sharing is not available on this device.');
  }

  await Sharing.shareAsync(localUri, {
    dialogTitle: args.fileName ? `Open ${args.fileName}` : 'Open protected Tomb of Light file'
  });
  return localUri;
}

export function uploadStatusLabel(upload: UploadRecordPayload | null | undefined): string {
  if (!upload) {
    return 'Unknown';
  }
  if (upload.quarantined) {
    return 'Blocked — security review required';
  }

  const scanStatus = String(upload.scan_status || '').trim().toLowerCase();
  if (!scanStatus || scanStatus === 'pending') {
    return 'Security scan in progress';
  }
  if (scanStatus !== 'clean') {
    return 'Blocked — security review required';
  }

  const verificationStatus = String(upload.verification_status || '').trim().toLowerCase();
  if (verificationStatus === 'rejected') {
    return 'Rejected';
  }
  if (verificationStatus === 'needs_correction') {
    return 'Needs correction';
  }
  if (upload.approved_for_cinematic || verificationStatus === 'approved') {
    return 'Approved';
  }
  return 'Uploaded';
}

export function canPreviewUpload(upload: UploadRecordPayload): boolean {
  const permissions = upload.permissions;
  return Boolean(permissions && typeof permissions === 'object' && (permissions as Record<string, unknown>).can_preview === true);
}

export function canDownloadUpload(upload: UploadRecordPayload): boolean {
  const permissions = upload.permissions;
  return Boolean(permissions && typeof permissions === 'object' && (permissions as Record<string, unknown>).can_download === true);
}
