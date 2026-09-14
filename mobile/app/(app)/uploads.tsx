import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { Link } from 'expo-router';
import { Alert, Image, Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { asRecord, asString, formatBytes, formatTimestamp, toHumanLabel } from '../../src/features/workspace/format';
import {
  ApiError,
  FamilyTreePayload,
  fetchAccessContext,
  fetchCinematicAssets,
  fetchFamilyTree,
  fetchFamilyUploads,
  mapWorkspaceDataError,
  UploadRecordPayload,
  uploadMemberPhoto,
  uploadVerificationEvidence,
  uploadStatusLabel,
  uploadVaultFile,
  MobileFileAsset,
  cacheProtectedUpload,
  canDownloadUpload,
  canPreviewUpload,
  shareProtectedUpload
} from '../../src/services/api';
import { appTheme } from '../../src/theme';
import {
  DataStateCard,
  KeyValueRow,
  SectionCard,
  WorkspaceChip,
  WorkspaceHero
} from '../../src/features/workspace/ui';

type UploadMode = 'portrait' | 'verification' | 'vault';
type VaultAssetType = 'vault_photo' | 'vault_document' | 'private_voice_message' | 'private_video_message';

type AccessContextSnapshot = {
  activeProjectId: string;
  activeFamilyId: string;
  packageLane: string;
};

const VERIFICATION_TYPES = [
  'supporting_family_record',
  'birth_certificate',
  'marriage_certificate',
  'death_certificate',
  'obituary'
];

const VAULT_ASSET_TYPES: VaultAssetType[] = [
  'vault_photo',
  'vault_document',
  'private_voice_message',
  'private_video_message'
];

function summarizeContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    packageLane: asString(payload.package_lane)
  };
}

function fileNameFromUri(uri: string, fallback: string): string {
  const lastPart = uri.split('/').pop()?.split('?')[0];
  return lastPart || fallback;
}

function asImageAsset(asset: ImagePicker.ImagePickerAsset): MobileFileAsset {
  return {
    uri: asset.uri,
    name: asset.fileName || fileNameFromUri(asset.uri, 'portrait.jpg'),
    mimeType: asset.mimeType || 'image/jpeg',
    size: asset.fileSize
  };
}

function isOptionalRouteError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

function fileTypeAllowed(mode: UploadMode, assetType: VaultAssetType, file: MobileFileAsset): boolean {
  const mime = String(file.mimeType || '').toLowerCase();
  const name = file.name.toLowerCase();
  const hasExtension = (extensions: string[]) => extensions.some((extension) => name.endsWith(extension));

  if (mode === 'portrait') {
    return ['image/jpeg', 'image/png', 'image/webp'].includes(mime) || hasExtension(['.jpg', '.jpeg', '.png', '.webp']);
  }
  if (mode === 'verification') {
    return ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'].includes(mime) || hasExtension(['.pdf', '.jpg', '.jpeg', '.png', '.webp']);
  }
  if (assetType === 'vault_photo') {
    return mime.startsWith('image/') || hasExtension(['.jpg', '.jpeg', '.png', '.webp']);
  }
  if (assetType === 'vault_document') {
    return mime === 'application/pdf' || mime.startsWith('image/') || hasExtension(['.pdf', '.jpg', '.jpeg', '.png', '.webp']);
  }
  if (assetType === 'private_voice_message') {
    return ['audio/mpeg', 'audio/mp4', 'audio/wav', 'audio/x-wav', 'audio/webm', 'audio/ogg'].includes(mime) || hasExtension(['.mp3', '.m4a', '.wav', '.webm', '.ogg']);
  }
  return ['video/mp4', 'video/webm', 'video/quicktime', 'video/ogg'].includes(mime) || hasExtension(['.mp4', '.webm', '.mov', '.ogv']);
}

function uploadMessage(payload: { message?: string; upload_status?: unknown }): string {
  const status = payload.upload_status;
  const state = typeof status === 'string' ? status : asString(asRecord(status).state);
  if (['blocked', 'quarantined', 'infected', 'error', 'unavailable'].includes(state.toLowerCase())) {
    return 'The file was received but remains blocked. It cannot be opened until security and private-storage checks pass.';
  }
  if (['available', 'ready', 'clean'].includes(state.toLowerCase())) {
    return 'File stored securely and available to permitted viewers.';
  }
  return payload.message || 'File received securely and is processing through security review.';
}

export default function UploadsScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [treePayload, setTreePayload] = useState<FamilyTreePayload | null>(null);
  const [uploads, setUploads] = useState<UploadRecordPayload[]>([]);
  const [cinematicAssets, setCinematicAssets] = useState<UploadRecordPayload[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [mode, setMode] = useState<UploadMode>('portrait');
  const [selectedFile, setSelectedFile] = useState<MobileFileAsset | null>(null);
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [verificationType, setVerificationType] = useState('supporting_family_record');
  const [vaultAssetType, setVaultAssetType] = useState<VaultAssetType>('vault_photo');
  const [consentAttested, setConsentAttested] = useState(false);
  const [authorityAttested, setAuthorityAttested] = useState(false);
  const [previewUris, setPreviewUris] = useState<Record<string, string>>({});
  const mountedRef = useRef(true);

  const members = useMemo(
    () => (Array.isArray(treePayload?.members) ? treePayload.members : []).filter(Boolean),
    [treePayload?.members]
  );

  const loadUploads = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');
    setNotes([]);

    try {
      const context = summarizeContext(asRecord(await fetchAccessContext()));
      const responseNotes: string[] = [];
      let tree: FamilyTreePayload | null = null;
      let familyUploads: UploadRecordPayload[] = [];
      let cinematic: UploadRecordPayload[] = [];

      if (context.activeFamilyId) {
        try {
          const payload = await fetchFamilyUploads(context.activeFamilyId);
          familyUploads = Array.isArray(payload.uploads) ? payload.uploads : [];
        } catch (error) {
          if (isOptionalRouteError(error)) responseNotes.push('Upload inventory is not enabled for this family context.');
          else responseNotes.push(`Upload inventory unavailable: ${mapWorkspaceDataError(error)}`);
        }

        try {
          const payload = await fetchCinematicAssets(context.activeFamilyId);
          cinematic = Array.isArray(payload.items) ? payload.items : [];
        } catch (error) {
          if (!isOptionalRouteError(error)) responseNotes.push(`Cinematic readiness unavailable: ${mapWorkspaceDataError(error)}`);
        }

        try {
          tree = await fetchFamilyTree(context.activeFamilyId);
        } catch (error) {
          if (!isOptionalRouteError(error)) responseNotes.push(`Family members unavailable: ${mapWorkspaceDataError(error)}`);
        }
      } else {
        responseNotes.push('No active family identifier is available for upload intake.');
      }

      if (!mountedRef.current) return;
      setAccessContext(context);
      setTreePayload(tree);
      setUploads(familyUploads);
      setCinematicAssets(cinematic);
      setNotes(responseNotes);
      if (!selectedMemberId && tree?.members?.length) {
        const firstId = asString(tree.members[0].id) || asString(tree.members[0].person_id);
        setSelectedMemberId(firstId);
      }
    } catch (error) {
      if (!mountedRef.current) return;
      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setTreePayload(null);
      setUploads([]);
      setCinematicAssets([]);
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  }, [selectedMemberId]);

  useEffect(() => {
    mountedRef.current = true;
    void loadUploads();
    return () => {
      mountedRef.current = false;
    };
  }, [loadUploads]);

  const pickFromLibrary = useCallback(async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      setStatusMessage('Photo-library access is needed to choose a portrait.');
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.9,
      allowsEditing: false
    });
    if (!result.canceled && result.assets[0]) {
      setSelectedFile(asImageAsset(result.assets[0]));
      setStatusMessage('Portrait selected. Confirm both attestations before upload.');
    }
  }, []);

  const takePhoto = useCallback(async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) {
      setStatusMessage('Camera access is needed to take a portrait.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.9,
      allowsEditing: false
    });
    if (!result.canceled && result.assets[0]) {
      setSelectedFile(asImageAsset(result.assets[0]));
      setStatusMessage('Portrait captured. Confirm both attestations before upload.');
    }
  }, []);

  const pickDocument = useCallback(async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: '*/*',
      copyToCacheDirectory: true,
      multiple: false
    });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      setSelectedFile({
        uri: asset.uri,
        name: asset.name || fileNameFromUri(asset.uri, 'tomb-of-light-upload'),
        mimeType: asset.mimeType,
        size: asset.size
      });
      setStatusMessage('File selected. Confirm both attestations before upload.');
    }
  }, []);

  const submitUpload = useCallback(async () => {
    if (!accessContext?.activeFamilyId || !selectedFile) {
      setStatusMessage('Choose a family member and a file first.');
      return;
    }
    if (!selectedMemberId) {
      setStatusMessage('Choose the named family member this upload belongs to.');
      return;
    }
    if (!consentAttested || !authorityAttested) {
      setStatusMessage('Both consent and upload-authority confirmations are required.');
      return;
    }
    if (!fileTypeAllowed(mode, vaultAssetType, selectedFile)) {
      setStatusMessage('That file type does not match the selected upload category.');
      return;
    }
    if (mode === 'vault' && !accessContext.activeProjectId) {
      setStatusMessage('An active project is required for Vault uploads.');
      return;
    }

    setIsUploading(true);
    setStatusMessage('Uploading through secure staging and security review…');
    try {
      let payload;
      if (mode === 'portrait') {
        payload = await uploadMemberPhoto({
          familyId: accessContext.activeFamilyId,
          memberId: selectedMemberId,
          file: selectedFile
        });
      } else if (mode === 'verification') {
        payload = await uploadVerificationEvidence({
          familyId: accessContext.activeFamilyId,
          memberId: selectedMemberId,
          verificationType,
          evidenceKind: verificationType,
          file: selectedFile
        });
      } else {
        payload = await uploadVaultFile({
          projectId: accessContext.activeProjectId,
          familyId: accessContext.activeFamilyId,
          memberId: selectedMemberId,
          assetType: vaultAssetType,
          privacyScope: 'private_to_owner',
          vaultScope: 'personal',
          file: selectedFile
        });
      }

      setStatusMessage(uploadMessage(payload));
      setSelectedFile(null);
      setConsentAttested(false);
      setAuthorityAttested(false);
      await loadUploads();
    } catch (error) {
      setStatusMessage(mapWorkspaceDataError(error));
    } finally {
      if (mountedRef.current) setIsUploading(false);
    }
  }, [accessContext, authorityAttested, consentAttested, loadUploads, mode, selectedFile, selectedMemberId, vaultAssetType, verificationType]);

  const previewUpload = useCallback(async (upload: UploadRecordPayload) => {
    const uploadId = asString(upload.id);
    if (!uploadId || !canPreviewUpload(upload)) return;
    try {
      const uri = await cacheProtectedUpload({ uploadId, operation: 'preview', viewerProjectId: accessContext?.activeProjectId });
      setPreviewUris((current) => ({ ...current, [uploadId]: uri }));
    } catch (error) {
      Alert.alert('Protected preview unavailable', mapWorkspaceDataError(error));
    }
  }, [accessContext?.activeProjectId]);

  const shareUpload = useCallback(async (upload: UploadRecordPayload) => {
    const uploadId = asString(upload.id);
    if (!uploadId || !canDownloadUpload(upload)) return;
    try {
      await shareProtectedUpload({
        uploadId,
        viewerProjectId: accessContext?.activeProjectId,
        fileName: asString(upload.original_filename) || 'Tomb of Light file'
      });
    } catch (error) {
      Alert.alert('Protected file unavailable', mapWorkspaceDataError(error));
    }
  }, [accessContext?.activeProjectId]);

  const memberName = (member: Record<string, unknown>): string =>
    asString(member.full_name) || `${asString(member.first_name)} ${asString(member.last_name)}`.trim() || 'Unnamed member';

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Secure Uploads"
        description="Send portraits, verification evidence, or permitted Vault files through the same customer authorization, idempotency, scanning, and private-storage path used by the web workspace."
        contextLine={accessContext?.activeFamilyId ? `Family ${accessContext.activeFamilyId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.buttonDisabled]}
        onPress={() => void loadUploads()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh secure uploads"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing…' : 'Refresh Uploads'}</Text>
      </Pressable>

      {isLoading ? <DataStateCard kind="loading" title="Loading upload workspace" message="Resolving your active family, members, entitlements, and authorized upload inventory." /> : null}
      {!isLoading && errorMessage ? <DataStateCard kind="error" title="Unable to load uploads" message={errorMessage} actionLabel="Retry" onAction={() => void loadUploads()} /> : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Upload Type" subtitle="Choose the customer action you need. Admin review controls remain on the web workspace.">
            <View style={styles.modeRow}>
              {(['portrait', 'verification', 'vault'] as UploadMode[]).map((item) => (
                <Pressable
                  key={item}
                  style={[styles.modeButton, mode === item && styles.modeButtonActive]}
                  onPress={() => { setMode(item); setSelectedFile(null); setStatusMessage(''); }}
                  accessibilityRole="button"
                  accessibilityState={{ selected: mode === item }}
                  accessibilityLabel={`Choose ${item} upload`}
                >
                  <Text style={[styles.modeText, mode === item && styles.modeTextActive]}>{toHumanLabel(item)}</Text>
                </Pressable>
              ))}
            </View>
          </SectionCard>

          <SectionCard title="Named Family Member" subtitle="Every customer upload must be tied to the exact family member it belongs to.">
            {members.length ? (
              <View style={styles.chipRow}>
                {members.map((member) => {
                  const id = asString(member.id) || asString(member.person_id);
                  const selected = id === selectedMemberId;
                  return (
                    <Pressable key={id} style={[styles.memberChip, selected && styles.memberChipActive]} onPress={() => setSelectedMemberId(id)} accessibilityRole="button" accessibilityState={{ selected }}>
                      <Text style={[styles.memberChipText, selected && styles.memberChipTextActive]}>{memberName(member)}</Text>
                    </Pressable>
                  );
                })}
              </View>
            ) : (
              <Text style={styles.helperText}>No member records are available yet. Add family records before sending a member-specific upload.</Text>
            )}
          </SectionCard>

          <SectionCard title="Choose File" subtitle={mode === 'portrait' ? 'JPG, PNG, or WEBP portraits are accepted.' : mode === 'verification' ? 'PDF, JPG, PNG, or WEBP evidence is accepted.' : 'Vault file types and package entitlements are enforced by the backend.'}>
            <View style={styles.actions}>
              {mode === 'portrait' ? (
                <>
                  <Pressable style={styles.primaryButton} onPress={() => void pickFromLibrary()} accessibilityRole="button" accessibilityLabel="Choose portrait from photo library"><Text style={styles.primaryButtonText}>Choose From Library</Text></Pressable>
                  <Pressable style={styles.secondaryButton} onPress={() => void takePhoto()} accessibilityRole="button" accessibilityLabel="Take a portrait photo"><Text style={styles.secondaryButtonText}>Take Portrait</Text></Pressable>
                </>
              ) : (
                <Pressable style={styles.primaryButton} onPress={() => void pickDocument()} accessibilityRole="button" accessibilityLabel="Choose upload file"><Text style={styles.primaryButtonText}>Choose File</Text></Pressable>
              )}
            </View>
            {selectedFile ? (
              <View style={styles.selectedFile}>
                <Text style={styles.selectedFileName}>{selectedFile.name}</Text>
                <Text style={styles.selectedFileMeta}>{selectedFile.mimeType || 'Unknown type'} • {formatBytes(selectedFile.size)}</Text>
              </View>
            ) : <Text style={styles.helperText}>No file selected.</Text>}

            {mode === 'verification' ? (
              <>
                <Text style={styles.fieldLabel}>Verification record type</Text>
                <View style={styles.chipRow}>
                  {VERIFICATION_TYPES.map((item) => (
                    <Pressable key={item} style={[styles.optionChip, verificationType === item && styles.optionChipActive]} onPress={() => setVerificationType(item)} accessibilityRole="button" accessibilityState={{ selected: verificationType === item }}>
                      <Text style={[styles.optionText, verificationType === item && styles.optionTextActive]}>{toHumanLabel(item)}</Text>
                    </Pressable>
                  ))}
                </View>
              </>
            ) : null}

            {mode === 'vault' ? (
              <>
                <Text style={styles.fieldLabel}>Vault file type</Text>
                <View style={styles.chipRow}>
                  {VAULT_ASSET_TYPES.map((item) => (
                    <Pressable key={item} style={[styles.optionChip, vaultAssetType === item && styles.optionChipActive]} onPress={() => setVaultAssetType(item)} accessibilityRole="button" accessibilityState={{ selected: vaultAssetType === item }}>
                      <Text style={[styles.optionText, vaultAssetType === item && styles.optionTextActive]}>{toHumanLabel(item)}</Text>
                    </Pressable>
                  ))}
                </View>
                <Text style={styles.helperText}>This mobile flow starts with personal, owner-only Vault scope. Wider sharing remains governed by the web review and privacy controls.</Text>
              </>
            ) : null}
          </SectionCard>

          <SectionCard title="Required Confirmations" subtitle="These are sent to the existing backend attestation fields and cannot be skipped.">
            <View style={styles.switchRow}>
              <Switch value={consentAttested} onValueChange={setConsentAttested} trackColor={{ false: appTheme.colors.border, true: '#8AB6FF' }} thumbColor={consentAttested ? appTheme.colors.primary : '#FFFFFF'} accessibilityLabel="Confirm upload consent" />
              <Text style={styles.switchText}>I have the right to submit this file and understand the consent record.</Text>
            </View>
            <View style={styles.switchRow}>
              <Switch value={authorityAttested} onValueChange={setAuthorityAttested} trackColor={{ false: appTheme.colors.border, true: '#8AB6FF' }} thumbColor={authorityAttested ? appTheme.colors.primary : '#FFFFFF'} accessibilityLabel="Confirm upload authority" />
              <Text style={styles.switchText}>I confirm this upload is authorized for the selected family member and workspace.</Text>
            </View>
            <Pressable style={[styles.primaryButton, isUploading && styles.buttonDisabled]} onPress={() => void submitUpload()} disabled={isUploading} accessibilityRole="button" accessibilityLabel="Submit secure upload">
              <Text style={styles.primaryButtonText}>{isUploading ? 'Uploading Securely…' : 'Submit Secure Upload'}</Text>
            </Pressable>
            {statusMessage ? <Text style={styles.statusText}>{statusMessage}</Text> : null}
          </SectionCard>

          <SectionCard title="Upload Inventory" subtitle={`${uploads.length} family upload${uploads.length === 1 ? '' : 's'} • ${cinematicAssets.length} approved cinematic asset${cinematicAssets.length === 1 ? '' : 's'}`}>
            {uploads.length ? uploads.slice(0, 20).map((upload) => {
              const uploadId = asString(upload.id);
              const previewUri = previewUris[uploadId];
              return (
                <View key={uploadId || `${upload.original_filename}-${upload.created_at}`} style={styles.uploadCard}>
                  {previewUri ? <Image source={{ uri: previewUri }} style={styles.previewImage} accessibilityLabel={asString(upload.original_filename) || 'Protected upload preview'} /> : null}
                  <Text style={styles.uploadTitle}>{asString(upload.original_filename) || `${toHumanLabel(asString(upload.category) || 'upload')} asset`}</Text>
                  <Text style={styles.uploadMeta}>{toHumanLabel(asString(upload.category) || 'upload')} • {uploadStatusLabel(upload)}</Text>
                  <Text style={styles.uploadMeta}>{formatBytes(upload.size_bytes)} • {formatTimestamp(upload.created_at)}</Text>
                  <View style={styles.chipRow}>
                    {upload.customer_visible ? <WorkspaceChip label="Customer visible" tone="success" /> : null}
                    {upload.internal_only ? <WorkspaceChip label="Internal only" tone="muted" /> : null}
                    {upload.cinematic_approved || upload.approved_for_cinematic ? <WorkspaceChip label="Cinematic approved" tone="accent" /> : null}
                  </View>
                  <View style={styles.inlineActions}>
                    {canPreviewUpload(upload) ? <Pressable style={styles.smallButton} onPress={() => void previewUpload(upload)} accessibilityRole="button" accessibilityLabel={`Preview ${asString(upload.original_filename) || 'upload'}`}><Text style={styles.smallButtonText}>Preview</Text></Pressable> : null}
                    {canDownloadUpload(upload) ? <Pressable style={styles.smallButton} onPress={() => void shareUpload(upload)} accessibilityRole="button" accessibilityLabel={`Open ${asString(upload.original_filename) || 'upload'}`}><Text style={styles.smallButtonText}>Open Secure Copy</Text></Pressable> : null}
                  </View>
                </View>
              );
            }) : <Text style={styles.helperText}>No upload records are currently visible for this authorized family context.</Text>}
          </SectionCard>

          {notes.length ? <SectionCard title="Data Notes">{notes.map((note) => <Text key={note} style={styles.noteLine}>{note}</Text>)}</SectionCard> : null}

          <Link href="/(app)/support" asChild>
            <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Contact upload support"><Text style={styles.secondaryButtonText}>Need Help With an Upload?</Text></Pressable>
          </Link>
        </>
      ) : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  refreshButton: { alignSelf: 'flex-start', backgroundColor: appTheme.colors.primary, borderRadius: appTheme.radius.md, minHeight: 44, justifyContent: 'center', paddingVertical: 10, paddingHorizontal: 16 },
  refreshText: { color: appTheme.colors.surface, fontSize: appTheme.typography.caption, fontWeight: '700' },
  buttonDisabled: { opacity: 0.68 },
  modeRow: { flexDirection: 'row', flexWrap: 'wrap', gap: appTheme.spacing.xs },
  modeButton: { borderWidth: 1, borderColor: appTheme.colors.border, borderRadius: appTheme.radius.sm, paddingVertical: 10, paddingHorizontal: 12, backgroundColor: appTheme.colors.surface },
  modeButtonActive: { borderColor: appTheme.colors.primary, backgroundColor: '#EAF1FF' },
  modeText: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption, fontWeight: '600' },
  modeTextActive: { color: appTheme.colors.primary, fontWeight: '800' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: appTheme.spacing.xs },
  memberChip: { borderWidth: 1, borderColor: appTheme.colors.border, borderRadius: 18, paddingVertical: 8, paddingHorizontal: 12, backgroundColor: appTheme.colors.surface },
  memberChipActive: { backgroundColor: '#EAF1FF', borderColor: appTheme.colors.primary },
  memberChipText: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption, fontWeight: '600' },
  memberChipTextActive: { color: appTheme.colors.primary, fontWeight: '800' },
  actions: { gap: appTheme.spacing.sm },
  primaryButton: { backgroundColor: appTheme.colors.primary, borderRadius: appTheme.radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 46, paddingVertical: 12 },
  primaryButtonText: { color: appTheme.colors.surface, fontSize: appTheme.typography.body, fontWeight: '700' },
  secondaryButton: { backgroundColor: appTheme.colors.surface, borderWidth: 1, borderColor: appTheme.colors.border, borderRadius: appTheme.radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 46, paddingVertical: 12 },
  secondaryButtonText: { color: appTheme.colors.textPrimary, fontSize: appTheme.typography.body, fontWeight: '600' },
  selectedFile: { marginTop: appTheme.spacing.sm, padding: appTheme.spacing.sm, backgroundColor: '#F3F7FF', borderRadius: appTheme.radius.sm, gap: 2 },
  selectedFileName: { color: appTheme.colors.textPrimary, fontWeight: '700', fontSize: appTheme.typography.body },
  selectedFileMeta: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption },
  helperText: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption, lineHeight: 19 },
  fieldLabel: { color: appTheme.colors.textPrimary, fontSize: appTheme.typography.caption, fontWeight: '700', marginTop: appTheme.spacing.md, marginBottom: appTheme.spacing.xs },
  optionChip: { borderWidth: 1, borderColor: appTheme.colors.border, borderRadius: 18, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: appTheme.colors.surface },
  optionChipActive: { borderColor: appTheme.colors.primary, backgroundColor: '#EAF1FF' },
  optionText: { color: appTheme.colors.textSecondary, fontSize: 12, fontWeight: '600' },
  optionTextActive: { color: appTheme.colors.primary, fontWeight: '800' },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: appTheme.spacing.sm },
  switchText: { flex: 1, color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption, lineHeight: 19 },
  statusText: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption, lineHeight: 19 },
  uploadCard: { gap: 4, padding: appTheme.spacing.sm, borderRadius: appTheme.radius.md, borderWidth: 1, borderColor: appTheme.colors.border, backgroundColor: '#FAFCFF' },
  uploadTitle: { color: appTheme.colors.textPrimary, fontSize: appTheme.typography.body, fontWeight: '700' },
  uploadMeta: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.caption },
  previewImage: { width: '100%', height: 160, borderRadius: appTheme.radius.sm, backgroundColor: '#E7EEF9', marginBottom: appTheme.spacing.xs },
  inlineActions: { flexDirection: 'row', flexWrap: 'wrap', gap: appTheme.spacing.xs, marginTop: appTheme.spacing.xs },
  smallButton: { borderWidth: 1, borderColor: appTheme.colors.primary, borderRadius: appTheme.radius.sm, paddingVertical: 8, paddingHorizontal: 10 },
  smallButtonText: { color: appTheme.colors.primary, fontSize: appTheme.typography.caption, fontWeight: '700' },
  noteLine: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.body, lineHeight: 22 }
});
