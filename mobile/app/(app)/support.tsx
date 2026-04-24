import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Alert, Linking, Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  fetchAccessContext,
  fetchMyMemberships,
  fetchMyProfile,
  mapWorkspaceDataError,
  UserProfilePayload,
  WorkspaceMembership
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
  userId: string;
  email: string;
  role: string;
  status: string;
  packageLane: string;
  experienceMode: string;
  activeProjectId: string;
  activeFamilyId: string;
};

type CountRow = {
  label: string;
  count: number;
};

const SUPPORT_EMAIL = String(process.env.EXPO_PUBLIC_SUPPORT_EMAIL || '').trim();

function summarizeAccessContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    userId: asString(payload.user_id),
    email: asString(payload.email),
    role: asString(payload.role),
    status: asString(payload.status),
    packageLane: asString(payload.package_lane),
    experienceMode: asString(payload.experience_mode),
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id)
  };
}

function profileDisplayName(profile: UserProfilePayload | null): string {
  if (!profile) {
    return '';
  }

  return asString(profile.full_name) || asString(profile.email);
}

function toCountRows(items: WorkspaceMembership[], key: keyof WorkspaceMembership): CountRow[] {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const label = asString(item[key]).toLowerCase() || 'unknown';
    counts.set(label, (counts.get(label) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function supportSubject(context: AccessContextSnapshot | null): string {
  if (!context) {
    return 'Tomb of Light mobile support request';
  }

  const project = context.activeProjectId || 'unresolved-project';
  const family = context.activeFamilyId || 'unresolved-family';
  return `Tomb of Light mobile support (${project}/${family})`;
}

function supportBody(context: AccessContextSnapshot | null, profile: UserProfilePayload | null): string {
  const policyVersion = asString(asRecord(profile?.legal_acceptance).policy_version) || asString(profile?.policy_version);

  return [
    'Hello Tomb of Light support,',
    '',
    'I need help with the mobile app.',
    '',
    `Account email: ${asString(profile?.email) || context?.email || 'unavailable'}`,
    `User id: ${asString(profile?.id) || context?.userId || 'unavailable'}`,
    `Package lane: ${context?.packageLane || 'unavailable'}`,
    `Experience mode: ${context?.experienceMode || 'unavailable'}`,
    `Active project id: ${context?.activeProjectId || 'unavailable'}`,
    `Active family id: ${context?.activeFamilyId || 'unavailable'}`,
    `Policy version: ${policyVersion || 'unavailable'}`,
    '',
    'Issue summary:',
    '',
    'Expected outcome:',
    ''
  ].join('\n');
}

export default function SupportScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [isOpeningEmail, setIsOpeningEmail] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const [profile, setProfile] = useState<UserProfilePayload | null>(null);
  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [memberships, setMemberships] = useState<WorkspaceMembership[]>([]);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadSupportView = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');

    try {
      const [profilePayload, accessPayload, membershipsPayload] = await Promise.all([
        fetchMyProfile(),
        fetchAccessContext(),
        fetchMyMemberships()
      ]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setProfile(profilePayload);
      setAccessContext(summarizeAccessContext(asRecord(accessPayload)));
      setMemberships(Array.isArray(membershipsPayload.items) ? membershipsPayload.items : []);
      setLastUpdatedAt(new Date().toISOString());
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setProfile(null);
      setAccessContext(null);
      setMemberships([]);
      setLastUpdatedAt('');
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadSupportView();

    return () => {
      mountedRef.current = false;
    };
  }, [loadSupportView]);

  const onEmailSupport = useCallback(async () => {
    if (isOpeningEmail) {
      return;
    }

    if (!SUPPORT_EMAIL) {
      Alert.alert(
        'Support Email Not Configured',
        'Set EXPO_PUBLIC_SUPPORT_EMAIL to enable direct email handoff from this mobile support screen.'
      );
      return;
    }

    setIsOpeningEmail(true);

    try {
      const subject = encodeURIComponent(supportSubject(accessContext));
      const body = encodeURIComponent(supportBody(accessContext, profile));
      const mailtoUrl = `mailto:${SUPPORT_EMAIL}?subject=${subject}&body=${body}`;
      const canOpen = await Linking.canOpenURL(mailtoUrl);

      if (!canOpen) {
        throw new Error('No email client is available on this device for support handoff.');
      }

      await Linking.openURL(mailtoUrl);
    } catch (error) {
      Alert.alert('Unable To Open Support Email', mapWorkspaceDataError(error));
    } finally {
      setIsOpeningEmail(false);
    }
  }, [accessContext, isOpeningEmail, profile]);

  const roleRows = useMemo(() => toCountRows(memberships, 'member_role'), [memberships]);
  const statusRows = useMemo(() => toCountRows(memberships, 'status'), [memberships]);
  const relationshipRows = useMemo(() => toCountRows(memberships, 'relationship_scope'), [memberships]);

  const legalAcceptance = asRecord(profile?.legal_acceptance);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Support"
        description="Real support entry context with account identity, package scope, and household impact signals for faster issue triage."
        contextLine={profileDisplayName(profile) || undefined}
      />

      <Pressable
        style={[styles.refreshButton, (isLoading || isOpeningEmail) && styles.refreshButtonDisabled]}
        onPress={() => void loadSupportView()}
        disabled={isLoading || isOpeningEmail}
        accessibilityRole="button"
        accessibilityLabel="Refresh support view"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Support Context'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading support context"
          message="Fetching account identity, workspace scope, and household membership signals for support handoff."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load support context"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadSupportView()}
          actionDisabled={isOpeningEmail}
        />
      ) : null}

      {!isLoading && !errorMessage && (!profile || !accessContext) ? (
        <DataStateCard
          kind="empty"
          title="Support metadata unavailable"
          message="Account or workspace context is missing in this session, so support triage details are not ready yet."
          actionLabel="Refresh"
          onAction={() => void loadSupportView()}
          actionDisabled={isOpeningEmail}
        />
      ) : null}

      {!isLoading && !errorMessage && profile && accessContext ? (
        <>
          <SectionCard title="Support Intake Context" subtitle="Top details support needs first for fast triage.">
            <View style={styles.rows}>
              <KeyValueRow label="Account Email" value={asString(profile.email) || accessContext.email || 'Unavailable'} />
              <KeyValueRow label="User ID" value={asString(profile.id) || accessContext.userId || 'Unavailable'} />
              <KeyValueRow label="Role" value={toHumanLabel(accessContext.role || 'unknown')} />
              <KeyValueRow label="Status" value={toHumanLabel(accessContext.status || 'unknown')} />
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Experience Mode" value={toHumanLabel(accessContext.experienceMode || 'unknown')} />
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Active Family ID" value={accessContext.activeFamilyId || 'Unavailable'} />
              <KeyValueRow label="Last Updated" value={formatTimestamp(lastUpdatedAt, 'Unavailable')} />
            </View>
          </SectionCard>

          <SectionCard title="Household Impact" subtitle="Membership visibility and scope distribution in current account context.">
            <View style={styles.chipRow}>
              <WorkspaceChip label={`Memberships ${memberships.length}`} tone="accent" />
              <WorkspaceChip label={`Roles ${roleRows.length}`} tone="success" />
              <WorkspaceChip label={`Statuses ${statusRows.length}`} tone="warning" />
            </View>

            <Text style={styles.sectionLabel}>Member Roles</Text>
            {roleRows.length > 0 ? (
              roleRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No role distribution returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Membership Status</Text>
            {statusRows.length > 0 ? (
              statusRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No status distribution returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Relationship Scope</Text>
            {relationshipRows.length > 0 ? (
              relationshipRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No relationship scope distribution returned.</Text>
            )}
          </SectionCard>

          <SectionCard title="Policy And Security" subtitle="Useful legal/security metadata for support verification.">
            <View style={styles.rows}>
              <KeyValueRow
                label="Policy Version"
                value={asString(legalAcceptance.policy_version) || asString(profile.policy_version) || 'Unavailable'}
              />
              <KeyValueRow
                label="Terms Accepted"
                value={formatTimestamp(legalAcceptance.terms_accepted_at, 'Not yet recorded')}
              />
              <KeyValueRow
                label="Privacy Accepted"
                value={formatTimestamp(legalAcceptance.privacy_accepted_at, 'Not yet recorded')}
              />
              <KeyValueRow
                label="Eligibility Attested"
                value={formatTimestamp(legalAcceptance.eligibility_attested_at, 'Not yet recorded')}
              />
            </View>
          </SectionCard>

          <SectionCard title="Support Actions" subtitle="Fast handoff options and self-service paths for mobile users.">
            <View style={styles.actions}>
              <Pressable
                style={[styles.primaryButton, (!SUPPORT_EMAIL || isOpeningEmail) && styles.buttonDisabled]}
                onPress={() => void onEmailSupport()}
                disabled={!SUPPORT_EMAIL || isOpeningEmail}
                accessibilityRole="button"
                accessibilityLabel="Email support with current context"
              >
                <Text style={styles.primaryButtonText}>
                  {isOpeningEmail ? 'Opening Email...' : SUPPORT_EMAIL ? 'Email Support With Context' : 'Support Email Not Configured'}
                </Text>
              </Pressable>

              <Link href="/(app)/billing" asChild>
                <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open billing">
                  <Text style={styles.secondaryButtonText}>Open Billing</Text>
                </Pressable>
              </Link>

              <Link href="/(auth)/forgot-password" asChild>
                <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open password reset">
                  <Text style={styles.secondaryButtonText}>Open Password Reset</Text>
                </Pressable>
              </Link>

              <Link href="/(app)/settings" asChild>
                <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Return to settings">
                  <Text style={styles.secondaryButtonText}>Return To Settings</Text>
                </Pressable>
              </Link>
            </View>

            {!SUPPORT_EMAIL ? (
              <Text style={styles.inlineFallback}>
                Add `EXPO_PUBLIC_SUPPORT_EMAIL` in your mobile environment to enable direct email handoff from this screen.
              </Text>
            ) : null}
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
  rows: {
    gap: appTheme.spacing.sm
  },
  sectionLabel: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    marginTop: 2
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.xs
  },
  inlineText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  inlineFallback: {
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
  },
  buttonDisabled: {
    opacity: 0.72
  }
});
