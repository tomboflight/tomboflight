import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  ApiError,
  fetchAccessContext,
  fetchIssuedCertificates,
  IssuedCertificateRecordPayload,
  mapWorkspaceDataError
} from '../../src/services/api';
import { appTheme } from '../../src/theme';
import { asRecord, asString, formatTimestamp, toHumanLabel } from '../../src/features/workspace/format';
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

type CertificateSummary = {
  id: string;
  certificateId: string;
  familyId: string;
  familyName: string;
  status: string;
  version: string;
  issuedAt: string;
  issuedBy: string;
  isLatest: boolean;
  integrityHash: string;
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

function normalizeCertificate(record: IssuedCertificateRecordPayload): CertificateSummary {
  const payload = asRecord(record.certificate_payload);
  const familyRecord = asRecord(payload.family);

  return {
    id: asString(record.id) || asString(record._id),
    certificateId: asString(record.certificate_id) || asString(payload.certificate_id),
    familyId: asString(record.family_id) || asString(familyRecord.id),
    familyName: asString(record.family_name) || asString(familyRecord.family_name) || 'Unknown family',
    status: asString(record.status) || asString(payload.status) || 'unknown',
    version: asString(record.version) || asString(payload.version) || '1',
    issuedAt: asString(record.issued_at) || asString(payload.issued_at),
    issuedBy: asString(record.issued_by) || 'system',
    isLatest: Boolean(record.is_latest),
    integrityHash: asString(record.integrity_hash) || asString(payload.integrity_hash)
  };
}

function toCountRows(items: CertificateSummary[], key: keyof CertificateSummary): CountRow[] {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const label = asString(item[key]).toLowerCase() || 'unknown';
    counts.set(label, (counts.get(label) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function isOptionalRouteError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

export default function CertificatesScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [certificates, setCertificates] = useState<CertificateSummary[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadCertificates = useCallback(async () => {
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

      const responseNotes: string[] = [];
      let list: CertificateSummary[] = [];

      try {
        const payload = await fetchIssuedCertificates({ limit: 100 });
        const rawRecords = Array.isArray(payload.issued_certificates) ? payload.issued_certificates : [];
        list = rawRecords.map((record) => normalizeCertificate(record));
      } catch (error) {
        if (isOptionalRouteError(error)) {
          responseNotes.push('Certificate records are not available for the current package scope.');
        } else {
          responseNotes.push(`Certificate records unavailable: ${mapWorkspaceDataError(error)}`);
        }
      }

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setCertificates(list);
      setNotes(responseNotes);
      setLastUpdatedAt(new Date().toISOString());
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setCertificates([]);
      setNotes([]);
      setLastUpdatedAt('');
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadCertificates();

    return () => {
      mountedRef.current = false;
    };
  }, [loadCertificates]);

  const statusRows = useMemo(() => toCountRows(certificates, 'status'), [certificates]);

  const latestCertificates = useMemo(() => {
    return [...certificates]
      .sort((left, right) => {
        const leftDate = Date.parse(left.issuedAt || '');
        const rightDate = Date.parse(right.issuedAt || '');

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
  }, [certificates]);

  const activeFamilyCertificates = useMemo(() => {
    if (!accessContext?.activeFamilyId) {
      return certificates;
    }

    const filtered = certificates.filter((item) => item.familyId === accessContext.activeFamilyId);
    return filtered.length > 0 ? filtered : certificates;
  }, [certificates, accessContext]);

  const latest = latestCertificates[0] || null;

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Certificates"
        description="Review issuance history, certificate state, and lineage proof readiness from your mobile workspace."
        contextLine={accessContext?.activeFamilyId ? `Family ${accessContext.activeFamilyId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadCertificates()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh certificates"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Certificate Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading certificate records"
          message="Fetching lineage certificate issuance history and current family certificate state."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load certificates"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadCertificates()}
        />
      ) : null}

      {!isLoading && !errorMessage && !accessContext ? (
        <DataStateCard
          kind="empty"
          title="No certificate context available"
          message="Account context is unavailable for certificate queries in this session."
          actionLabel="Refresh"
          onAction={() => void loadCertificates()}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Certificate Context" subtitle="Package and family scope linked to certificate visibility.">
            <View style={styles.rows}>
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Experience Mode" value={toHumanLabel(accessContext.experienceMode || 'unknown')} />
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Active Family ID" value={accessContext.activeFamilyId || 'Unavailable'} />
              <KeyValueRow label="Certificate Records" value={String(certificates.length)} />
              <KeyValueRow label="Last Updated" value={formatTimestamp(lastUpdatedAt, 'Unavailable')} />
            </View>
          </SectionCard>

          <SectionCard title="Current Proof Signal" subtitle="Most recent issuance record in the visible certificate list.">
            {latest ? (
              <View style={styles.rows}>
                <KeyValueRow label="Certificate ID" value={latest.certificateId || 'Unavailable'} />
                <KeyValueRow label="Family" value={latest.familyName} />
                <KeyValueRow label="Status" value={toHumanLabel(latest.status || 'unknown')} />
                <KeyValueRow label="Version" value={latest.version || '1'} />
                <KeyValueRow label="Issued" value={formatTimestamp(latest.issuedAt, 'Unavailable')} />
                <KeyValueRow label="Issued By" value={latest.issuedBy || 'system'} />
              </View>
            ) : (
              <DataStateCard
                kind="empty"
                title="No certificates issued yet"
                message="No certificate records were returned for this account and family context."
              />
            )}
          </SectionCard>

          <SectionCard title="Certificate Status Distribution" subtitle="Issuance status across visible records.">
            {statusRows.length > 0 ? (
              statusRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No status distribution is available yet.</Text>
            )}
          </SectionCard>

          <SectionCard
            title="Recent Certificate History"
            subtitle={`Showing ${activeFamilyCertificates.length} records in the current scope.`}
          >
            {latestCertificates.length > 0 ? (
              latestCertificates.map((item) => (
                <View key={item.id || item.certificateId} style={styles.certificateRow}>
                  <Text style={styles.certificateTitle}>{item.familyName}</Text>
                  <Text style={styles.certificateMeta}>Certificate: {item.certificateId || 'Unavailable'}</Text>
                  <Text style={styles.certificateMeta}>Status: {toHumanLabel(item.status || 'unknown')}</Text>
                  <Text style={styles.certificateMeta}>Version: {item.version || '1'}</Text>
                  <Text style={styles.certificateMeta}>Issued: {formatTimestamp(item.issuedAt, 'Unavailable')}</Text>
                  <View style={styles.chipRow}>
                    {item.isLatest ? (
                      <WorkspaceChip label="Latest Version" tone="success" />
                    ) : (
                      <WorkspaceChip label="Historical Version" tone="muted" />
                    )}
                    {item.integrityHash ? <WorkspaceChip label="Integrity Hash Present" tone="accent" /> : null}
                  </View>
                </View>
              ))
            ) : (
              <DataStateCard
                kind="empty"
                title="No certificate history"
                message="Certificate issuance history will appear here once records are issued."
              />
            )}
          </SectionCard>

          {notes.length > 0 ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking route limitations detected while loading certificates.">
              {notes.map((note) => (
                <Text key={note} style={styles.noteLine}>
                  - {note}
                </Text>
              ))}
            </SectionCard>
          ) : null}

          <View style={styles.actions}>
            <Link href="/(app)/billing" asChild>
              <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open billing">
                <Text style={styles.secondaryButtonText}>Open Billing</Text>
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
  inlineText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  inlineFallback: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body
  },
  certificateRow: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#FAFCFF',
    padding: appTheme.spacing.sm,
    gap: 2
  },
  certificateTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  certificateMeta: {
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
