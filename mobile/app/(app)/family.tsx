import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  ApiError,
  FamilyTreePayload,
  fetchAccessContext,
  fetchFamilyTree,
  fetchMyMemberships,
  fetchProjectMembers,
  mapWorkspaceDataError,
  WorkspaceMembership
} from '../../src/services/api';
import { appTheme } from '../../src/theme';
import { asRecord, asString, toHumanLabel } from '../../src/features/workspace/format';
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
};

type CountRow = {
  label: string;
  count: number;
};

function summarizeContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    packageLane: asString(payload.package_lane)
  };
}

function summarizeMemberName(member: WorkspaceMembership): string {
  const firstName = asString(member.first_name);
  const lastName = asString(member.last_name);
  const fullName = asString(member.full_name);

  return fullName || `${firstName} ${lastName}`.trim() || asString(member.email) || 'Unnamed member';
}

function toCountRows(items: WorkspaceMembership[], key: keyof WorkspaceMembership): CountRow[] {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const normalized = asString(item[key]).toLowerCase() || 'unknown';
    counts.set(normalized, (counts.get(normalized) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function isOptionalRouteError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

function formatFamilyName(treePayload: FamilyTreePayload | null): string {
  if (!treePayload) {
    return 'Unavailable';
  }

  const family = asRecord(treePayload.family);
  return asString(family.family_name) || asString(family.name) || 'Unnamed family context';
}

export default function FamilyScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [membershipList, setMembershipList] = useState<WorkspaceMembership[]>([]);
  const [projectMembers, setProjectMembers] = useState<WorkspaceMembership[]>([]);
  const [treePayload, setTreePayload] = useState<FamilyTreePayload | null>(null);
  const [notes, setNotes] = useState<string[]>([]);

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadFamilyView = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');
    setNotes([]);

    try {
      const [contextPayload, membershipsPayload] = await Promise.all([fetchAccessContext(), fetchMyMemberships()]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const contextSummary = summarizeContext(asRecord(contextPayload));
      const allMemberships = Array.isArray(membershipsPayload.items) ? membershipsPayload.items : [];

      setAccessContext(contextSummary);
      setMembershipList(allMemberships);

      const responseNotes: string[] = [];
      let resolvedProjectMembers: WorkspaceMembership[] = allMemberships;
      let resolvedTreePayload: FamilyTreePayload | null = null;

      if (contextSummary.activeProjectId) {
        try {
          const payload = await fetchProjectMembers(contextSummary.activeProjectId);
          if (Array.isArray(payload.items)) {
            resolvedProjectMembers = payload.items;
          }
        } catch (error) {
          if (isOptionalRouteError(error)) {
            resolvedProjectMembers = allMemberships.filter(
              (membership) => asString(membership.project_id) === contextSummary.activeProjectId
            );
            responseNotes.push(
              'Project member detail route is package-gated or unavailable. Showing membership context from /workspace-access/my-memberships.'
            );
          } else {
            responseNotes.push(`Project member details unavailable: ${mapWorkspaceDataError(error)}`);
          }
        }
      }

      if (contextSummary.activeFamilyId) {
        try {
          resolvedTreePayload = await fetchFamilyTree(contextSummary.activeFamilyId);
        } catch (error) {
          if (isOptionalRouteError(error)) {
            responseNotes.push(
              'Family tree metadata is not exposed for this package scope yet. Household cards remain based on workspace memberships.'
            );
          } else {
            responseNotes.push(`Family tree metadata unavailable: ${mapWorkspaceDataError(error)}`);
          }
        }
      }

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setProjectMembers(resolvedProjectMembers);
      setTreePayload(resolvedTreePayload);
      setNotes(responseNotes);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setMembershipList([]);
      setProjectMembers([]);
      setTreePayload(null);
      setNotes([]);
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadFamilyView();

    return () => {
      mountedRef.current = false;
    };
  }, [loadFamilyView]);

  const visibleMembers = useMemo(() => {
    if (projectMembers.length > 0) {
      return projectMembers;
    }

    if (accessContext?.activeProjectId) {
      return membershipList.filter((membership) => asString(membership.project_id) === accessContext.activeProjectId);
    }

    return membershipList;
  }, [projectMembers, membershipList, accessContext]);

  const roleRows = useMemo(() => toCountRows(visibleMembers, 'member_role'), [visibleMembers]);
  const relationshipRows = useMemo(() => toCountRows(visibleMembers, 'relationship_scope'), [visibleMembers]);
  const privacyRows = useMemo(() => toCountRows(visibleMembers, 'privacy_scope'), [visibleMembers]);

  const familyMembersCount = Array.isArray(treePayload?.members) ? treePayload?.members?.length || 0 : 0;
  const treeRelationshipsCount = Array.isArray(treePayload?.relationships) ? treePayload?.relationships?.length || 0 : 0;
  const treeNodesCount = Array.isArray(treePayload?.nodes) ? treePayload?.nodes?.length || 0 : 0;

  const projectIdsInScope = useMemo(() => {
    const ids = new Set<string>();
    membershipList.forEach((membership) => {
      const projectId = asString(membership.project_id);
      if (projectId) {
        ids.add(projectId);
      }
    });

    return Array.from(ids.values()).sort((left, right) => left.localeCompare(right));
  }, [membershipList]);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Family"
        description="Household membership, role scope, privacy boundaries, and current family context sourced from live workspace APIs."
        contextLine={accessContext?.activeFamilyId ? `Family ${accessContext.activeFamilyId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadFamilyView()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh family view"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Family Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading family workspace"
          message="Fetching active household memberships, project member scope, and family metadata."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load family view"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadFamilyView()}
        />
      ) : null}

      {!isLoading && !errorMessage && !accessContext ? (
        <DataStateCard
          kind="empty"
          title="No household context returned"
          message="This session does not currently expose active family or project workspace context."
          actionLabel="Refresh"
          onAction={() => void loadFamilyView()}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Current Household Context" subtitle="Active context from access + memberships API payloads.">
            <View style={styles.rows}>
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Active Family ID" value={accessContext.activeFamilyId || 'Unavailable'} />
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Membership Records In Scope" value={String(visibleMembers.length)} />
              <KeyValueRow label="Projects Linked To This Account" value={String(projectIdsInScope.length)} />
            </View>

            <View style={styles.chipRow}>
              {projectIdsInScope.slice(0, 4).map((projectId) => (
                <WorkspaceChip key={projectId} label={`Project ${projectId}`} tone="muted" />
              ))}
            </View>
          </SectionCard>

          <SectionCard title="Family Record Summary" subtitle="Tree route metadata shown when available for this package scope.">
            <View style={styles.rows}>
              <KeyValueRow label="Family Name" value={formatFamilyName(treePayload)} />
              <KeyValueRow label="Family Members In Tree Payload" value={String(familyMembersCount)} />
              <KeyValueRow label="Tree Nodes" value={String(treeNodesCount)} />
              <KeyValueRow label="Tree Relationships" value={String(treeRelationshipsCount)} />
              <KeyValueRow
                label="Tree Mode"
                value={toHumanLabel(asString(treePayload?.mode) || 'default')}
              />
            </View>
          </SectionCard>

          <SectionCard
            title="Roles And Scope"
            subtitle="Role, relationship scope, and privacy scope distributions for the current household context."
          >
            <Text style={styles.sectionLabel}>Member Roles</Text>
            {roleRows.length > 0 ? (
              roleRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No role distribution rows returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Relationship Scope</Text>
            {relationshipRows.length > 0 ? (
              relationshipRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No relationship scope rows returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Privacy Scope</Text>
            {privacyRows.length > 0 ? (
              privacyRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No privacy scope rows returned.</Text>
            )}
          </SectionCard>

          <SectionCard title="Household Members" subtitle="Membership-level records visible to this account in mobile scope.">
            {visibleMembers.length > 0 ? (
              visibleMembers.slice(0, 10).map((member, index) => (
                <View key={`${asString(member.id) || summarizeMemberName(member)}-${index}`} style={styles.memberRow}>
                  <Text style={styles.memberName}>{summarizeMemberName(member)}</Text>
                  <Text style={styles.memberMeta}>Role: {toHumanLabel(asString(member.member_role) || 'unknown')}</Text>
                  <Text style={styles.memberMeta}>
                    Relationship Scope: {toHumanLabel(asString(member.relationship_scope) || 'unknown')}
                  </Text>
                  <Text style={styles.memberMeta}>
                    Privacy Scope: {toHumanLabel(asString(member.privacy_scope) || 'unknown')}
                  </Text>
                  <Text style={styles.memberMeta}>Status: {toHumanLabel(asString(member.status) || 'unknown')}</Text>
                </View>
              ))
            ) : (
              <DataStateCard
                kind="empty"
                title="No household members returned"
                message="No member rows are currently visible for this project/family context."
              />
            )}
          </SectionCard>

          {notes.length > 0 ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking API constraints observed while loading this screen.">
              {notes.map((note) => (
                <Text key={note} style={styles.noteLine}>
                  - {note}
                </Text>
              ))}
            </SectionCard>
          ) : null}

          <View style={styles.actions}>
            <Link href="/(app)/tree" asChild>
              <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open family tree entry">
                <Text style={styles.primaryButtonText}>Open Tree Entry</Text>
              </Pressable>
            </Link>
            <Link href="/(app)/project" asChild>
              <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Return to project">
                <Text style={styles.secondaryButtonText}>Return To Project</Text>
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
  inlineText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  inlineFallback: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body
  },
  memberRow: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#FAFCFF',
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
    paddingVertical: 12
  },
  secondaryButtonText: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  }
});
