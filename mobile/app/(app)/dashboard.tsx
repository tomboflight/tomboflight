import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { fetchAccessContext, fetchMyMemberships, WorkspaceMembership } from '../../src/services/api';
import { appTheme } from '../../src/theme';

type AccessContextSummary = {
  email: string;
  role: string;
  packageLane: string;
  activeProjectId: string;
  activeFamilyId: string;
  modules: string[];
  entitlements: string[];
};

function toErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return 'Unable to load dashboard data.';
}

function toAccessContextSummary(payload: Record<string, unknown>): AccessContextSummary {
  const asString = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');
  const asStringArray = (value: unknown): string[] =>
    Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];

  return {
    email: asString(payload.email),
    role: asString(payload.role),
    packageLane: asString(payload.package_lane),
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    modules: asStringArray(payload.allowed_experience_modules),
    entitlements: asStringArray(payload.active_entitlements)
  };
}

function buildMembershipCounts(items: WorkspaceMembership[]): Record<string, number> {
  const counts: Record<string, number> = {};
  items.forEach((item) => {
    const role = String(item.member_role || 'unknown').trim().toLowerCase() || 'unknown';
    counts[role] = (counts[role] || 0) + 1;
  });
  return counts;
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
      setMemberships(membershipsPayload.items || []);
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const membershipCounts = useMemo(() => buildMembershipCounts(memberships), [memberships]);
  const roleCountEntries = useMemo(() => Object.entries(membershipCounts), [membershipCounts]);

  return (
    <ScreenContainer>
      <View style={styles.hero}>
        <Text style={styles.badge}>Tomb of Light Mobile</Text>
        <Text style={styles.title}>Dashboard</Text>
        <Text style={styles.description}>
          Your customer workspace summary, package lane, and membership context.
        </Text>
      </View>

      <Pressable style={styles.refreshButton} onPress={() => void loadDashboard()}>
        <Text style={styles.refreshText}>Refresh</Text>
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
          <Text style={styles.errorHint}>
            Ensure your API base URL and authenticated session are configured correctly.
          </Text>
        </View>
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Account Context</Text>
            <Text style={styles.cardLine}>Email: {accessContext.email || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Role: {accessContext.role || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>Package Lane: {accessContext.packageLane || 'Unavailable'}</Text>
            <Text style={styles.cardLine}>
              Active Project: {accessContext.activeProjectId || 'Not selected'}
            </Text>
            <Text style={styles.cardLine}>
              Active Family: {accessContext.activeFamilyId || 'Not selected'}
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Workspace Memberships</Text>
            <Text style={styles.cardLine}>Memberships: {memberships.length}</Text>
            {roleCountEntries.length > 0 ? (
              roleCountEntries.map(([role, count]) => (
                <Text key={role} style={styles.cardLine}>
                  {role}: {count}
                </Text>
              ))
            ) : (
              <Text style={styles.cardLine}>No memberships found.</Text>
            )}
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Entitlements & Modules</Text>
            <Text style={styles.cardLine}>
              Entitlements: {accessContext.entitlements.length > 0 ? accessContext.entitlements.join(', ') : 'None'}
            </Text>
            <Text style={styles.cardLine}>
              Modules: {accessContext.modules.length > 0 ? accessContext.modules.join(', ') : 'None'}
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
    fontWeight: '600'
  },
  cardLine: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  }
});
