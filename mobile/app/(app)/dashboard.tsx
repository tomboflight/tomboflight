import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { fetchAccessContext, fetchMyMemberships, mapWorkspaceAccessError, WorkspaceMembership } from '../../src/services/api';
import { appTheme } from '../../src/theme';
import { asRecord, asString, asStringArray, formatTimestamp, toHumanLabel } from '../../src/features/workspace/format';
import {
  DataStateCard,
  KeyValueRow,
  SectionCard,
  WorkspaceChip,
  WorkspaceHero
} from '../../src/features/workspace/ui';

type AccessContextSummary = {
  userId: string;
  email: string;
  role: string;
  status: string;
  packageLane: string;
  experienceMode: string;
  activeProjectId: string;
  activeFamilyId: string;
  modules: string[];
  entitlements: string[];
  projectPermissions: string[];
  legalAcceptance: {
    policyVersion: string;
    termsAcceptedAt: string;
    privacyAcceptedAt: string;
    eligibilityAttestedAt: string;
  };
};

type MetricRow = {
  label: string;
  count: number;
};

function toCountRows(items: WorkspaceMembership[], key: keyof WorkspaceMembership): MetricRow[] {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const normalized = asString(item[key]).toLowerCase() || 'unknown';
    counts.set(normalized, (counts.get(normalized) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function toAccessContextSummary(payload: Record<string, unknown>): AccessContextSummary {
  const legal = asRecord(payload.legal_acceptance);

  return {
    userId: asString(payload.user_id),
    email: asString(payload.email),
    role: asString(payload.role),
    status: asString(payload.status),
    packageLane: asString(payload.package_lane),
    experienceMode: asString(payload.experience_mode),
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    modules: asStringArray(payload.allowed_experience_modules),
    entitlements: asStringArray(payload.active_entitlements),
    projectPermissions: asStringArray(payload.project_permissions),
    legalAcceptance: {
      policyVersion: asString(legal.policy_version),
      termsAcceptedAt: asString(legal.terms_accepted_at),
      privacyAcceptedAt: asString(legal.privacy_accepted_at),
      eligibilityAttestedAt: asString(legal.eligibility_attested_at)
    }
  };
}

function summarizeMembershipTarget(membership: WorkspaceMembership): string {
  return asString(membership.full_name) || asString(membership.email) || 'Unnamed member';
}

function summarizeMembershipScope(membership: WorkspaceMembership): string {
  const relationshipScope = asString(membership.relationship_scope);
  const privacyScope = asString(membership.privacy_scope);

  if (relationshipScope && privacyScope) {
    return `${toHumanLabel(relationshipScope)} / ${toHumanLabel(privacyScope)}`;
  }

  return toHumanLabel(relationshipScope || privacyScope || 'unknown');
}

function membershipKey(membership: WorkspaceMembership, index: number): string {
  return (
    asString(membership.id) ||
    `${asString(membership.project_id) || 'project'}-${asString(membership.user_id) || asString(membership.email) || 'member'}-${index}`
  );
}

export default function DashboardScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [accessContext, setAccessContext] = useState<AccessContextSummary | null>(null);
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);

  const requestSequence = useRef(0);
  const mountedRef = useRef(true);

  const loadDashboard = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');

    try {
      const [contextPayload, membershipsPayload] = await Promise.all([fetchAccessContext(), fetchMyMemberships()]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setAccessContext(toAccessContextSummary(asRecord(contextPayload)));
      setMemberships(Array.isArray(membershipsPayload.items) ? membershipsPayload.items : []);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceAccessError(error));
      setAccessContext(null);
      setMemberships([]);
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadDashboard();

    return () => {
      mountedRef.current = false;
    };
  }, [loadDashboard]);

  const roleRows = useMemo(() => toCountRows(memberships, 'member_role'), [memberships]);
  const statusRows = useMemo(() => toCountRows(memberships, 'status'), [memberships]);

  const recentMemberships = useMemo(() => {
    return [...memberships]
      .sort((left, right) => {
        const leftDate = Date.parse(asString(left.created_at) || asString(left.joined_at) || '');
        const rightDate = Date.parse(asString(right.created_at) || asString(right.joined_at) || '');

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
      .slice(0, 6);
  }, [memberships]);

  const heroContextLine = accessContext
    ? `${toHumanLabel(accessContext.packageLane || 'unknown')} lane • ${toHumanLabel(accessContext.experienceMode || 'unknown')} mode`
    : undefined;

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Dashboard"
        description="Your mobile workspace snapshot: identity, package access, household scope, and current project context."
        contextLine={heroContextLine}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadDashboard()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh dashboard"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Workspace Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading workspace dashboard"
          message="We are pulling account access context, household memberships, and entitlement visibility."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load dashboard"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadDashboard()}
        />
      ) : null}

      {!isLoading && !errorMessage && !accessContext ? (
        <DataStateCard
          kind="empty"
          title="No access context returned"
          message="Sign in again or refresh after your account context is provisioned."
          actionLabel="Refresh"
          onAction={() => void loadDashboard()}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Workspace At A Glance" subtitle="Most important context first for mobile decisions.">
            <View style={styles.metricGrid}>
              <View style={styles.metricTile}>
                <Text style={styles.metricLabel}>Package Lane</Text>
                <Text style={styles.metricValue}>{toHumanLabel(accessContext.packageLane || 'unknown')}</Text>
              </View>
              <View style={styles.metricTile}>
                <Text style={styles.metricLabel}>Experience Mode</Text>
                <Text style={styles.metricValue}>{toHumanLabel(accessContext.experienceMode || 'unknown')}</Text>
              </View>
              <View style={styles.metricTile}>
                <Text style={styles.metricLabel}>Active Project</Text>
                <Text style={styles.metricValueSmall}>{accessContext.activeProjectId || 'None'}</Text>
              </View>
              <View style={styles.metricTile}>
                <Text style={styles.metricLabel}>Active Family</Text>
                <Text style={styles.metricValueSmall}>{accessContext.activeFamilyId || 'None'}</Text>
              </View>
            </View>
          </SectionCard>

          <SectionCard title="Account Access Snapshot" subtitle="Authenticated identity and policy-bound status.">
            <View style={styles.rows}>
              <KeyValueRow label="Email" value={accessContext.email || 'Unavailable'} />
              <KeyValueRow label="User ID" value={accessContext.userId || 'Unavailable'} />
              <KeyValueRow label="Role" value={toHumanLabel(accessContext.role || 'unknown')} />
              <KeyValueRow label="Status" value={toHumanLabel(accessContext.status || 'unknown')} />
            </View>
          </SectionCard>

          <SectionCard
            title="Entitlements And Modules"
            subtitle="Directly reflects current backend capability flags and unlocked modules."
          >
            <Text style={styles.sectionLabel}>Enabled Entitlements</Text>
            <View style={styles.chipRow}>
              {accessContext.entitlements.length > 0 ? (
                accessContext.entitlements.map((entry) => <WorkspaceChip key={entry} label={entry} tone="accent" />)
              ) : (
                <WorkspaceChip label="No entitlement flags returned" tone="muted" />
              )}
            </View>

            <Text style={styles.sectionLabel}>Allowed Modules</Text>
            <View style={styles.chipRow}>
              {accessContext.modules.length > 0 ? (
                accessContext.modules.map((entry) => <WorkspaceChip key={entry} label={entry} />)
              ) : (
                <WorkspaceChip label="No modules returned" tone="muted" />
              )}
            </View>

            <Text style={styles.sectionLabel}>Project Permissions</Text>
            <View style={styles.chipRow}>
              {accessContext.projectPermissions.length > 0 ? (
                accessContext.projectPermissions.map((entry) => (
                  <WorkspaceChip key={entry} label={entry} tone="muted" />
                ))
              ) : (
                <WorkspaceChip label="No explicit project permissions" tone="muted" />
              )}
            </View>
          </SectionCard>

          <SectionCard title="Household Membership Signals" subtitle={`Total memberships in scope: ${memberships.length}`}>
            <Text style={styles.sectionLabel}>Role Distribution</Text>
            {roleRows.length > 0 ? (
              roleRows.map((row) => (
                <Text key={row.label} style={styles.inlineMetricText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallbackText}>No membership role data returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Status Distribution</Text>
            {statusRows.length > 0 ? (
              statusRows.map((row) => (
                <Text key={row.label} style={styles.inlineMetricText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallbackText}>No membership status data returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Recent Membership Context</Text>
            {recentMemberships.length > 0 ? (
              recentMemberships.map((membership, index) => (
                <View key={membershipKey(membership, index)} style={styles.memberCard}>
                  <Text style={styles.memberName}>{summarizeMembershipTarget(membership)}</Text>
                  <Text style={styles.memberMeta}>Role: {toHumanLabel(asString(membership.member_role) || 'unknown')}</Text>
                  <Text style={styles.memberMeta}>Scope: {summarizeMembershipScope(membership)}</Text>
                  <Text style={styles.memberMeta}>Project: {asString(membership.project_id) || 'unknown'}</Text>
                </View>
              ))
            ) : (
              <Text style={styles.inlineFallbackText}>No membership records found for this account.</Text>
            )}
          </SectionCard>

          <SectionCard title="Legal Acceptance" subtitle="Policy acceptance metadata from current account profile.">
            <View style={styles.rows}>
              <KeyValueRow label="Policy Version" value={accessContext.legalAcceptance.policyVersion || 'Unavailable'} />
              <KeyValueRow
                label="Terms Accepted"
                value={formatTimestamp(accessContext.legalAcceptance.termsAcceptedAt, 'Not yet recorded')}
              />
              <KeyValueRow
                label="Privacy Accepted"
                value={formatTimestamp(accessContext.legalAcceptance.privacyAcceptedAt, 'Not yet recorded')}
              />
              <KeyValueRow
                label="Eligibility Attested"
                value={formatTimestamp(accessContext.legalAcceptance.eligibilityAttestedAt, 'Not yet recorded')}
              />
            </View>
          </SectionCard>
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
  metricGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.sm
  },
  metricTile: {
    minWidth: '47%',
    flexGrow: 1,
    backgroundColor: '#F5F9FF',
    borderWidth: 1,
    borderColor: '#C7DAF8',
    borderRadius: appTheme.radius.md,
    padding: appTheme.spacing.sm,
    gap: 2
  },
  metricLabel: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  metricValue: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  metricValueSmall: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  rows: {
    gap: appTheme.spacing.sm
  },
  sectionLabel: {
    marginTop: 2,
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.xs
  },
  inlineMetricText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  inlineFallbackText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body
  },
  memberCard: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#FBFDFF',
    padding: appTheme.spacing.sm,
    gap: 2
  },
  memberName: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  memberMeta: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 19
  }
});
