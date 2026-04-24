import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { signOut } from '../../src/services/auth';
import { fetchAccessContext, fetchMyProfile, mapWorkspaceDataError, UserProfilePayload } from '../../src/services/api';
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
  packageLane: string;
  experienceMode: string;
  activeProjectId: string;
  activeFamilyId: string;
};

function summarizeAccessContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    userId: asString(payload.user_id),
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

  return asString(profile.full_name) || asString(profile.email) || '';
}

export default function SettingsScreen() {
  const router = useRouter();

  const [isLoading, setIsLoading] = useState(true);
  const [isSigningOut, setIsSigningOut] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const [profile, setProfile] = useState<UserProfilePayload | null>(null);
  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadSettings = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');

    try {
      const [profilePayload, accessPayload] = await Promise.all([fetchMyProfile(), fetchAccessContext()]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setProfile(profilePayload);
      setAccessContext(summarizeAccessContext(asRecord(accessPayload)));
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setProfile(null);
      setAccessContext(null);
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadSettings();

    return () => {
      mountedRef.current = false;
    };
  }, [loadSettings]);

  const onSignOut = useCallback(async () => {
    setIsSigningOut(true);

    try {
      await signOut();
    } finally {
      setIsSigningOut(false);
      router.replace('/(auth)/sign-in');
    }
  }, [router]);

  const legalAcceptance = asRecord(profile?.legal_acceptance);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Settings"
        description="Account identity, session controls, security entry points, and support/legal metadata for this mobile session."
        contextLine={profileDisplayName(profile) || undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadSettings()}
        disabled={isLoading || isSigningOut}
        accessibilityRole="button"
        accessibilityLabel="Refresh settings"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Account Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading account settings"
          message="Fetching profile identity, workspace context, and legal acceptance metadata."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load settings"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadSettings()}
          actionDisabled={isSigningOut}
        />
      ) : null}

      {!isLoading && !errorMessage && (!profile || !accessContext) ? (
        <DataStateCard
          kind="empty"
          title="No account metadata returned"
          message="Profile or workspace context is currently unavailable for this session."
          actionLabel="Refresh"
          onAction={() => void loadSettings()}
          actionDisabled={isSigningOut}
        />
      ) : null}

      {!isLoading && !errorMessage && profile && accessContext ? (
        <>
          <SectionCard title="Account Identity" subtitle="Authenticated account identity and user profile metadata.">
            <View style={styles.rows}>
              <KeyValueRow label="Full Name" value={asString(profile.full_name) || 'Unavailable'} />
              <KeyValueRow label="Email" value={asString(profile.email) || 'Unavailable'} />
              <KeyValueRow label="User ID" value={asString(profile.id) || accessContext.userId || 'Unavailable'} />
              <KeyValueRow label="Role" value={toHumanLabel(asString(profile.role) || 'user')} />
              <KeyValueRow label="Status" value={toHumanLabel(asString(profile.status) || 'active')} />
            </View>
          </SectionCard>

          <SectionCard title="Session And Workspace" subtitle="Current session context tied to the authenticated account.">
            <View style={styles.rows}>
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Experience Mode" value={toHumanLabel(accessContext.experienceMode || 'unknown')} />
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Active Family ID" value={accessContext.activeFamilyId || 'Unavailable'} />
              <KeyValueRow label="Account Created" value={formatTimestamp(profile.created_at, 'Unavailable')} />
              <KeyValueRow label="Last Login" value={formatTimestamp(profile.last_login_at, 'Unavailable')} />
            </View>

            <View style={styles.chipRow}>
              <WorkspaceChip label={`Policy ${asString(profile.policy_version) || 'unknown'}`} tone="accent" />
              <WorkspaceChip
                label={isSigningOut ? 'Signing out...' : 'Session active'}
                tone={isSigningOut ? 'warning' : 'success'}
              />
            </View>
          </SectionCard>

          <SectionCard title="Legal Acceptance" subtitle="Current terms/privacy acceptance fields returned by /users/me/profile.">
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

          <SectionCard title="Security And Support" subtitle="Account control entry points available in this mobile MVP.">
            <View style={styles.actions}>
              <Link href="/(app)/support" asChild>
                <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open support center">
                  <Text style={styles.secondaryButtonText}>Open Support Center</Text>
                </Pressable>
              </Link>

              <Link href="/(auth)/forgot-password" asChild>
                <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open password reset flow">
                  <Text style={styles.secondaryButtonText}>Open Password Reset</Text>
                </Pressable>
              </Link>

              <Pressable
                style={[styles.signOutButton, isSigningOut && styles.buttonDisabled]}
                onPress={() => void onSignOut()}
                disabled={isSigningOut}
                accessibilityRole="button"
                accessibilityLabel="Sign out"
              >
                <Text style={styles.signOutText}>{isSigningOut ? 'Signing Out...' : 'Sign Out'}</Text>
              </Pressable>
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
  rows: {
    gap: appTheme.spacing.sm
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: appTheme.spacing.xs
  },
  actions: {
    gap: appTheme.spacing.sm
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
  signOutButton: {
    backgroundColor: '#FFF6F6',
    borderWidth: 1,
    borderColor: appTheme.colors.error,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 12
  },
  signOutText: {
    color: appTheme.colors.error,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  buttonDisabled: {
    opacity: 0.72
  }
});
