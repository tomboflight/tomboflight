import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
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
  packageCode: string;
  packageName: string;
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

function firstString(...values: unknown[]): string {
  for (const value of values) {
    const normalized = asString(value);
    if (normalized) {
      return normalized;
    }
  }

  return '';
}

function firstStringArray(...values: unknown[]): string[] {
  for (const value of values) {
    const normalized = asStringArray(value);
    if (normalized.length > 0) {
      return normalized;
    }
  }

  return [];
}

function firstRecord(...values: unknown[]): Record<string, unknown> {
  for (const value of values) {
    const normalized = asRecord(value);
    if (Object.keys(normalized).length > 0) {
      return normalized;
    }
  }

  return {};
}

function inferExperienceMode(packageLane: string, packageCode: string, rawMode: string): string {
  if (rawMode) {
    return rawMode;
  }

  const normalizedLane = packageLane.toLowerCase();
  const normalizedCode = packageCode.toLowerCase();

  if (normalizedLane === 'household') {
    return 'household';
  }

  if (
    normalizedCode === 'legacy_plus' ||
    normalizedCode === 'household_foundation' ||
    normalizedCode === 'heirloom_legacy_tree' ||
    normalizedCode === 'family_estate_concierge'
  ) {
    return 'household';
  }

  return '';
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

function toAccessContextSummary(
  payload: Record<string, unknown>,
  memberships: WorkspaceMembership[] = []
): AccessContextSummary {
  const user = firstRecord(
    payload.user,
    payload.account,
    payload.profile,
    payload.identity,
    payload.current_user,
    payload.authenticated_user
  );

  const accessContext = firstRecord(
    payload.access_context,
    payload.context,
    payload.workspace_context,
    payload.current_access_context
  );

  const project = firstRecord(
    payload.project,
    payload.active_project,
    payload.current_project
  );

  const packageRecord = firstRecord(
    payload.package,
    payload.package_record,
    payload.package_details,
    accessContext.package,
    project.package,
    project.package_record,
    project.package_details
  );

  const family = firstRecord(
    payload.family,
    payload.active_family,
    payload.current_family
  );

  const legal = firstRecord(
    payload.legal_acceptance,
    payload.policy_acceptance,
    user.legal_acceptance,
    user.policy_acceptance
  );

  const primaryMembership = memberships[0] || ({} as WorkspaceMembership);

  const packageLane = firstString(
    payload.package_lane,
    payload.packageLane,
    accessContext.package_lane,
    accessContext.packageLane,
    project.package_lane,
    project.packageLane,
    packageRecord.package_lane,
    packageRecord.packageLane,
    primaryMembership.package_lane
  );

  const packageCode = firstString(
    payload.package_code,
    payload.packageCode,
    payload.package_slug,
    payload.packageSlug,
    accessContext.package_code,
    accessContext.packageCode,
    accessContext.package_slug,
    project.package_code,
    project.packageCode,
    project.package_slug,
    packageRecord.code,
    packageRecord.slug,
    packageRecord.package_code,
    packageRecord.package_slug
  );

  const packageName = firstString(
    payload.package_name,
    payload.packageName,
    accessContext.package_name,
    accessContext.packageName,
    project.package_name,
    project.packageName,
    packageRecord.name,
    packageRecord.label,
    packageRecord.package_name
  );

  const rawExperienceMode = firstString(
    payload.experience_mode,
    payload.experienceMode,
    payload.mode,
    accessContext.experience_mode,
    accessContext.experienceMode,
    accessContext.mode,
    project.experience_mode,
    project.experienceMode,
    project.mode
  );

  return {
    userId: firstString(
      payload.user_id,
      payload.userId,
      accessContext.user_id,
      accessContext.userId,
      user.id,
      user.user_id,
      user.userId,
      primaryMembership.user_id
    ),
    email: firstString(
      payload.email,
      accessContext.email,
      user.email,
      primaryMembership.email
    ),
    role: firstString(
      payload.role,
      payload.user_role,
      payload.userRole,
      accessContext.role,
      accessContext.user_role,
      accessContext.userRole,
      user.role,
      user.user_role,
      user.userRole,
      primaryMembership.member_role
    ),
    status: firstString(
      payload.status,
      accessContext.status,
      user.status,
      primaryMembership.status,
      'active'
    ),
    packageLane,
    packageCode,
    packageName,
    experienceMode: inferExperienceMode(packageLane, packageCode, rawExperienceMode),
    activeProjectId: firstString(
      payload.active_project_id,
      payload.activeProjectId,
      payload.project_id,
      payload.projectId,
      accessContext.active_project_id,
      accessContext.activeProjectId,
      accessContext.project_id,
      project.id,
      project.project_id,
      project.projectId,
      primaryMembership.project_id
    ),
    activeFamilyId: firstString(
      payload.active_family_id,
      payload.activeFamilyId,
      payload.family_id,
      payload.familyId,
      accessContext.active_family_id,
      accessContext.activeFamilyId,
      accessContext.family_id,
      family.id,
      family.family_id,
      family.familyId,
      primaryMembership.family_id
    ),
    modules: firstStringArray(
      payload.allowed_experience_modules,
      payload.allowedExperienceModules,
      payload.allowed_modules,
      payload.allowedModules,
      payload.modules,
      payload.unlocked_modules,
      accessContext.allowed_experience_modules,
      accessContext.allowed_modules,
      project.allowed_experience_modules
    ),
    entitlements: firstStringArray(
      payload.active_entitlements,
      payload.activeEntitlements,
      payload.entitlements,
      payload.enabled_entitlements,
      payload.enabledEntitlements,
      accessContext.active_entitlements,
      accessContext.entitlements,
      project.active_entitlements
    ),
    projectPermissions: firstStringArray(
      payload.project_permissions,
      payload.projectPermissions,
      payload.permissions,
      accessContext.project_permissions,
      accessContext.permissions,
      project.permissions
    ),
    legalAcceptance: {
      policyVersion: firstString(
        legal.policy_version,
        legal.policyVersion,
        payload.policy_version,
        user.policy_version
      ),
      termsAcceptedAt: firstString(
        legal.terms_accepted_at,
        legal.termsAcceptedAt,
        payload.terms_accepted_at,
        user.terms_accepted_at
      ),
      privacyAcceptedAt: firstString(
        legal.privacy_accepted_at,
        legal.privacyAcceptedAt,
        payload.privacy_accepted_at,
        user.privacy_accepted_at
      ),
      eligibilityAttestedAt: firstString(
        legal.eligibility_attested_at,
        legal.eligibilityAttestedAt,
        payload.eligibility_attested_at,
        user.eligibility_attested_at
      )
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
      const membershipItems = Array.isArray(membershipsPayload.items) ? membershipsPayload.items : [];

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setAccessContext(toAccessContextSummary(asRecord(contextPayload), membershipItems));
      setMemberships(membershipItems);
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

  const packageDisplay = accessContext
    ? accessContext.packageName || accessContext.packageCode || accessContext.packageLane
    : '';

  const heroContextLine = accessContext
    ? `${toHumanLabel(packageDisplay || 'unknown')} • ${toHumanLabel(accessContext.packageLane || 'unknown')} lane • ${toHumanLabel(accessContext.experienceMode || 'unknown')} mode`
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
                <Text style={styles.metricLabel}>Package</Text>
                <Text style={styles.metricValue}>{toHumanLabel(packageDisplay || 'unknown')}</Text>
              </View>
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

          <SectionCard title="Next Actions" subtitle="Jump to the most used mobile workflows.">
            <View style={styles.actionGrid}>
              <Link href="/(app)/project" asChild>
                <Pressable style={styles.actionButton} accessibilityRole="button" accessibilityLabel="Open project">
                  <Text style={styles.actionButtonText}>Project</Text>
                </Pressable>
              </Link>
              <Link href="/(app)/family" asChild>
                <Pressable style={styles.actionButton} accessibilityRole="button" accessibilityLabel="Open family">
                  <Text style={styles.actionButtonText}>Family</Text>
                </Pressable>
              </Link>
              <Link href="/(app)/uploads" asChild>
                <Pressable style={styles.actionButton} accessibilityRole="button" accessibilityLabel="Open uploads">
                  <Text style={styles.actionButtonText}>Uploads</Text>
                </Pressable>
              </Link>
              <Link href="/(app)/billing" asChild>
                <Pressable style={styles.actionButton} accessibilityRole="button" accessibilityLabel="Open billing">
                  <Text style={styles.actionButtonText}>Billing</Text>
                </Pressable>
              </Link>
              <Link href="/(app)/support" asChild>
                <Pressable style={styles.actionButtonWide} accessibilityRole="button" accessibilityLabel="Open support">
                  <Text style={styles.actionButtonText}>Support</Text>
                </Pressable>
              </Link>
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
  actionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.sm
  },
  actionButton: {
    minWidth: '31%',
    flexGrow: 1,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F6F9FE',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 10,
    paddingHorizontal: 12
  },
  actionButtonWide: {
    minWidth: '48%',
    flexGrow: 1,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F6F9FE',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 10,
    paddingHorizontal: 12
  },
  actionButtonText: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
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