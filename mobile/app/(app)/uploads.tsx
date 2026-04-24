import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  ApiError,
  fetchAccessContext,
  fetchCinematicAssets,
  fetchFamilyUploads,
  mapWorkspaceDataError,
  UploadRecordPayload
} from '../../src/services/api';
import { appTheme } from '../../src/theme';
import {
  asRecord,
  asString,
  formatBytes,
  formatTimestamp,
  toHumanLabel
} from '../../src/features/workspace/format';
import {
  DataStateCard,
  KeyValueRow,
  SectionCard,
  WorkspaceChip,
  WorkspaceHero
} from '../../src/features/workspace/ui';

type AccessContextSnapshot = {
  activeProjectId: string;
  activeFamilyId: string;
  packageLane: string;
  experienceMode: string;
};

type CountRow = {
  label: string;
  count: number;
};

function summarizeContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    packageLane: asString(payload.package_lane),
    experienceMode: asString(payload.experience_mode)
  };
}

function toCountRows(items: UploadRecordPayload[], key: keyof UploadRecordPayload): CountRow[] {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const label = asString(item[key]).toLowerCase() || 'unknown';
    counts.set(label, (counts.get(label) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function normalizeUploadName(upload: UploadRecordPayload): string {
  return asString(upload.original_filename) || `${toHumanLabel(asString(upload.category) || 'upload')} Asset`;
}

function isOptionalRouteError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

export default function UploadsScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [uploads, setUploads] = useState<UploadRecordPayload[]>([]);
  const [cinematicAssets, setCinematicAssets] = useState<UploadRecordPayload[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');
  const [notes, setNotes] = useState<string[]>([]);

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadUploads = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');
    setNotes([]);

    try {
      const contextPayload = await fetchAccessContext();

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const context = summarizeContext(asRecord(contextPayload));
      setAccessContext(context);

      if (!context.activeFamilyId) {
        setUploads([]);
        setCinematicAssets([]);
        setLastUpdatedAt(new Date().toISOString());
        setNotes([
          'No active family id is currently resolved in access context, so family upload queues cannot be queried yet.'
        ]);
        return;
      }

      const [uploadsResult, cinematicResult] = await Promise.allSettled([
        fetchFamilyUploads(context.activeFamilyId),
        fetchCinematicAssets(context.activeFamilyId)
      ]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const responseNotes: string[] = [];

      if (uploadsResult.status === 'fulfilled') {
        const familyUploads = Array.isArray(uploadsResult.value.uploads) ? uploadsResult.value.uploads : [];
        setUploads(familyUploads);
      } else {
        setUploads([]);
        if (isOptionalRouteError(uploadsResult.reason)) {
          responseNotes.push('Upload queue route is not available for the current package scope.');
        } else {
          responseNotes.push(`Upload queue unavailable: ${mapWorkspaceDataError(uploadsResult.reason)}`);
        }
      }

      if (cinematicResult.status === 'fulfilled') {
        const items = Array.isArray(cinematicResult.value.items) ? cinematicResult.value.items : [];
        setCinematicAssets(items);
      } else {
        setCinematicAssets([]);
        if (isOptionalRouteError(cinematicResult.reason)) {
          responseNotes.push('Cinematic asset readiness route is not available for the current package scope.');
        } else {
          responseNotes.push(`Cinematic readiness unavailable: ${mapWorkspaceDataError(cinematicResult.reason)}`);
        }
      }

      setLastUpdatedAt(new Date().toISOString());
      setNotes(responseNotes);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setUploads([]);
      setCinematicAssets([]);
      setLastUpdatedAt('');
      setNotes([]);
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadUploads();

    return () => {
      mountedRef.current = false;
    };
  }, [loadUploads]);

  const categoryRows = useMemo(() => toCountRows(uploads, 'category'), [uploads]);
  const verificationRows = useMemo(() => toCountRows(uploads, 'verification_status'), [uploads]);
  const scanRows = useMemo(() => toCountRows(uploads, 'scan_status'), [uploads]);

  const recentUploads = useMemo(() => {
    return [...uploads]
      .sort((left, right) => {
        const leftDate = Date.parse(asString(left.created_at) || '');
        const rightDate = Date.parse(asString(right.created_at) || '');

        if (!Number.isNaN(leftDate) && !Number.isNaN(rightDate)) {
          return rightDate - leftDate;
        }

        if (!Number.isNaN(rightDate)) {
          return 1;
        }

        if (!Number.isNaN(leftDate)) {
          return -1;
        }

        return 0;
      })
      .slice(0, 8);
  }, [uploads]);

  const visibleToCustomer = uploads.filter((upload) => Boolean(upload.customer_visible)).length;
  const quarantinedCount = uploads.filter((upload) => Boolean(upload.quarantined)).length;

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Uploads"
        description="Track family upload intake, verification progress, and cinematic readiness from your active workspace context."
        contextLine={accessContext?.activeFamilyId ? `Family ${accessContext.activeFamilyId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadUploads()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh uploads"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Upload Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading uploads"
          message="Checking family upload queue, verification state, and cinematic asset readiness."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load uploads"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadUploads()}
        />
      ) : null}

      {!isLoading && !errorMessage && !accessContext ? (
        <DataStateCard
          kind="empty"
          title="No upload context available"
          message="Sign in again or refresh once active family context is provisioned for this account."
          actionLabel="Refresh"
          onAction={() => void loadUploads()}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Upload Context" subtitle="Current package and family scope for upload operations.">
            <View style={styles.rows}>
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Experience Mode" value={toHumanLabel(accessContext.experienceMode || 'unknown')} />
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Active Family ID" value={accessContext.activeFamilyId || 'Unavailable'} />
              <KeyValueRow label="Queue Records" value={String(uploads.length)} />
              <KeyValueRow label="Last Updated" value={formatTimestamp(lastUpdatedAt, 'Unavailable')} />
            </View>
          </SectionCard>

          <SectionCard title="Queue Summary" subtitle="Verification and scan progress across the current family uploads.">
            <View style={styles.summaryTiles}>
              <View style={styles.tile}>
                <Text style={styles.tileLabel}>Customer Visible</Text>
                <Text style={styles.tileValue}>{visibleToCustomer}</Text>
              </View>
              <View style={styles.tile}>
                <Text style={styles.tileLabel}>Quarantined</Text>
                <Text style={styles.tileValue}>{quarantinedCount}</Text>
              </View>
              <View style={styles.tile}>
                <Text style={styles.tileLabel}>Cinematic Ready</Text>
                <Text style={styles.tileValue}>{cinematicAssets.length}</Text>
              </View>
            </View>

            <Text style={styles.sectionLabel}>By Category</Text>
            {categoryRows.length > 0 ? (
              categoryRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No upload categories returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Verification Status</Text>
            {verificationRows.length > 0 ? (
              verificationRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No verification statuses returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Scan Status</Text>
            {scanRows.length > 0 ? (
              scanRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No scan statuses returned.</Text>
            )}
          </SectionCard>

          <SectionCard title="Recent Uploads" subtitle="Most recent upload records visible in the active family queue.">
            {recentUploads.length > 0 ? (
              recentUploads.map((upload) => (
                <View key={asString(upload.id) || normalizeUploadName(upload)} style={styles.uploadRow}>
                  <Text style={styles.uploadTitle}>{normalizeUploadName(upload)}</Text>
                  <Text style={styles.uploadMeta}>Category: {toHumanLabel(asString(upload.category) || 'unknown')}</Text>
                  <Text style={styles.uploadMeta}>
                    Verification: {toHumanLabel(asString(upload.verification_status) || 'pending')}
                  </Text>
                  <Text style={styles.uploadMeta}>Size: {formatBytes(upload.size_bytes)}</Text>
                  <Text style={styles.uploadMeta}>Created: {formatTimestamp(upload.created_at, 'Unavailable')}</Text>
                  <View style={styles.chipRow}>
                    <WorkspaceChip
                      label={upload.customer_visible ? 'Customer Visible' : 'Internal Only'}
                      tone={upload.customer_visible ? 'success' : 'muted'}
                    />
                    {upload.approved_for_cinematic ? (
                      <WorkspaceChip label="Cinematic Approved" tone="accent" />
                    ) : (
                      <WorkspaceChip label="Awaiting Cinematic Review" tone="muted" />
                    )}
                  </View>
                </View>
              ))
            ) : (
              <DataStateCard
                kind="empty"
                title="No uploads yet"
                message="No upload records are currently visible for this family context."
              />
            )}
          </SectionCard>

          {notes.length > 0 ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking route limitations detected while loading uploads.">
              {notes.map((note) => (
                <Text key={note} style={styles.noteLine}>
                  - {note}
                </Text>
              ))}
            </SectionCard>
          ) : null}

          <View style={styles.actions}>
            <Link href="/(app)/project" asChild>
              <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Return to project">
                <Text style={styles.secondaryButtonText}>Return To Project</Text>
              </Pressable>
            </Link>
            <Link href="/(app)/support" asChild>
              <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open support">
                <Text style={styles.primaryButtonText}>Open Support</Text>
              </Pressable>
            </Link>
          </View>
        </>
      ) : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  refreshButton: {
    alignSelf: 'flex-start',
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    minHeight: 44,
    justifyContent: 'center',
    paddingVertical: 10,
    paddingHorizontal: 16
  },
  refreshButtonDisabled: {
    opacity: 0.72
  },
  refreshText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  rows: {
    gap: appTheme.spacing.sm
  },
  summaryTiles: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.sm
  },
  tile: {
    minWidth: '31%',
    flexGrow: 1,
    borderWidth: 1,
    borderColor: '#C5D9F7',
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F5F9FF',
    padding: appTheme.spacing.sm,
    gap: 2
  },
  tileLabel: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  tileValue: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.heading,
    fontWeight: '700'
  },
  sectionLabel: {
    marginTop: 2,
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  inlineText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  inlineFallback: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body
  },
  uploadRow: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#FAFCFF',
    padding: appTheme.spacing.sm,
    gap: 2
  },
  uploadTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  uploadMeta: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 18
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.xs,
    marginTop: 4
  },
  noteLine: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  actions: {
    gap: appTheme.spacing.sm
  },
  primaryButton: {
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 12
  },
  primaryButtonText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  secondaryButton: {
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 12
  },
  secondaryButtonText: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  }
});
