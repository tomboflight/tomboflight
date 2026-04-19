import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  AccessContextPayload,
  fetchAccessContext,
  fetchMyMemberships,
  mapWorkspaceAccessError,
  WorkspaceMembership
} from '../../src/services/api';
import { appTheme } from '../../src/theme';

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

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => asString(item))
    .filter((item) => item.length > 0);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : {};
}

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

function toAccessContextSummary(payload: AccessContextPayload): AccessContextSummary {
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
  const name = asString(membership.full_name);
  const email = asString(membership.email);
  return name || email || 'Unnamed member';
}

function summarizeMembershipScope(membership: WorkspaceMembership): string {
  const relationshipScope = asString(membership.relationship_scope);
  const privacyScope = asString(membership.privacy_scope);

  if (relationshipScope && privacyScope) {
    return `${relationshipScope} / ${privacyScope}`;
  }

  return relationshipScope || privacyScope || 'scope unavailable';
}

export default function DashboardScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const [accessContext, setAccessContext] = useState<AccessContextSummary | null>(null);
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);

  const loadDashboard = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage('');

    try {
      const [contextPayload, membershipsPayload] = await Promise.all([
        fetchAccessContext(),
        fetchMyMemberships()
      ]);

      setAccessContext(toAccessContextSummary(contextPayload));
      setMemberships(membershipsPayload.items);
    } catch (error) {
      setErrorMessage(mapWorkspaceAccessError(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
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
      .slice(0, 5);
  }, [memberships]);

  return (
    <ScreenContainer>
      <View style={styles.hero}>
        <Text style={styles.badge}>Tomb of Light Mobile</Text>
        <Text style={styles.title}>Dashboard</Text>
        <Text style={styles.description}>
          Customer workspace role, package lane, access context, and membership visibility.
        </Text>
      </View>

      <Pressable style={styles.refreshButton} onPress={() => void loadDashboard()}>
        <Text style={styles.refreshText}>Refresh Workspace Data</Text>
      </Pressable>

      {isLoading ? (
        <View style={styles.loadingCard}>
          <ActivityIndicator size="large" color={appTheme.colors.primary} />
          <Text style={styles.loadingText}>Loading dashboard...</Text>
        </View>
      ) : null}

      {!isLoading && errorMessage ? (
        <View style={styles.errorCard}>
          <Text style={styles.errorTitle}>Unable to load dashboard</Text>
          <Text style={styles.errorMessage}>{errorMessage}</Text>
          <Text style={styles.errorHint}>Sign in again if the current session has expired.</Text>
        </View>
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Access Snapshot</Text>
            <Text style={styles.cardLine}>User ID: {accessContext.userId || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Email: {accessContext.email || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Role: {accessContext.role || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Status: {accessContext.status || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Package Lane: {accessContext.packageLane || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Experience Mode: {accessContext.experienceMode || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>
              Active Project: {accessContext.activeProjectId || 'No active project'}
            </Text>
            <Text style={styles.cardLine}>
              Active Family: {accessContext.activeFamilyId || 'No active family'}
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Entitlements And Modules</Text>

            <Text style={styles.cardLabel}>Entitlements</Text>
            <View style={styles.tagWrap}>
              {accessContext.entitlements.length > 0 ? (
                accessContext.entitlements.map((entry) => (
                  <Text key={entry} style={styles.tag}>
                    {entry}
                  </Text>
                ))
              ) : (
                <Text style={styles.cardLine}>No entitlements returned.</Text>
              )}
            </View>

            <Text style={styles.cardLabel}>Allowed Modules</Text>
            <View style={styles.tagWrap}>
              {accessContext.modules.length > 0 ? (
                accessContext.modules.map((entry) => (
                  <Text key={entry} style={styles.tag}>
                    {entry}
                  </Text>
                ))
              ) : (
                <Text style={styles.cardLine}>No modules returned.</Text>
              )}
            </View>

            <Text style={styles.cardLabel}>Project Permissions</Text>
            <View style={styles.tagWrap}>
              {accessContext.projectPermissions.length > 0 ? (
                accessContext.projectPermissions.map((entry) => (
                  <Text key={entry} style={styles.tagMuted}>
                    {entry}
                  </Text>
                ))
              ) : (
                <Text style={styles.cardLine}>No explicit project permissions returned.</Text>
              )}
            </View>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Workspace Memberships</Text>
            <Text style={styles.cardLine}>Total memberships: {memberships.length}</Text>

            <Text style={styles.cardLabel}>Role Distribution</Text>
            {roleRows.length > 0 ? (
              roleRows.map((row) => (
                <Text key={row.label} style={styles.cardLine}>
                  {row.label}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.cardLine}>No memberships available.</Text>
            )}

            <Text style={styles.cardLabel}>Status Distribution</Text>
            {statusRows.length > 0 ? (
              statusRows.map((row) => (
                <Text key={row.label} style={styles.cardLine}>
                  {row.label}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.cardLine}>No membership statuses available.</Text>
            )}
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Recent Membership Context</Text>
            {recentMemberships.length > 0 ? (
              recentMemberships.map((membership) => (
                <View key={membership.id || `${membership.project_id || 'project'}-${membership.email || 'member'}`} style={styles.memberRow}>
                  <Text style={styles.memberName}>{summarizeMembershipTarget(membership)}</Text>
                  <Text style={styles.memberMeta}>Role: {asString(membership.member_role) || 'unknown'}</Text>
                  <Text style={styles.memberMeta}>Scope: {summarizeMembershipScope(membership)}</Text>
                  <Text style={styles.memberMeta}>Project: {asString(membership.project_id) || 'unknown'}</Text>
                </View>
              ))
            ) : (
              <Text style={styles.cardLine}>No membership records found for this account.</Text>
            )}
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Legal Acceptance</Text>
            <Text style={styles.cardLine}>
              Policy Version: {accessContext.legalAcceptance.policyVersion || 'Unavailable'}
            </Text>
            <Text style={styles.cardLine}>
              Terms Accepted: {accessContext.legalAcceptance.termsAcceptedAt || 'Not yet recorded'}
            </Text>
            <Text style={styles.cardLine}>
              Privacy Accepted: {accessContext.legalAcceptance.privacyAcceptedAt || 'Not yet recorded'}
            </Text>
            <Text style={styles.cardLine}>
              Eligibility Attested: {accessContext.legalAcceptance.eligibilityAttestedAt || 'Not yet recorded'}
            </Text>
          </View>
        </>
      ) : null}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  hero: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.lg,
    padding: appTheme.spacing.lg,
    borderWidth: 1,
    borderColor: '#CFE0FA',
    gap: appTheme.spacing.sm
  },
  badge: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6
  },
  title: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.title,
    fontWeight: '700'
  },
  description: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 24
  },
  refreshButton: {
    alignSelf: 'flex-start',
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    paddingVertical: 10,
    paddingHorizontal: 16
  },
  refreshText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  loadingCard: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    padding: appTheme.spacing.lg,
    alignItems: 'center',
    gap: appTheme.spacing.sm,
    borderWidth: 1,
    borderColor: appTheme.colors.border
  },
  loadingText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body
  },
  errorCard: {
    backgroundColor: '#FFF5F5',
    borderColor: '#F5B2B2',
    borderWidth: 1,
    borderRadius: appTheme.radius.md,
    padding: appTheme.spacing.md,
    gap: appTheme.spacing.xs
  },
  errorTitle: {
    color: appTheme.colors.error,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  errorMessage: {
    color: appTheme.colors.error,
    fontSize: appTheme.typography.caption
  },
  errorHint: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption
  },
  card: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    padding: appTheme.spacing.md,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    gap: appTheme.spacing.xs
  },
  cardTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.heading,
    fontWeight: '700'
  },
  cardLabel: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    marginTop: 4
  },
  cardLine: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  tagWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.xs,
    marginBottom: 6
  },
  tag: {
    borderWidth: 1,
    borderColor: '#BFD7FF',
    borderRadius: appTheme.radius.md,
    backgroundColor: '#EFF5FF',
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    paddingHorizontal: 10,
    paddingVertical: 4,
    overflow: 'hidden'
  },
  tagMuted: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F7F9FC',
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    paddingHorizontal: 10,
    paddingVertical: 4,
    overflow: 'hidden'
  },
  memberRow: {
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
    fontSize: appTheme.typography.caption
  }
});
