import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  ApiError,
  fetchAccessContext,
  fetchMyMemberships,
  fetchProjectEntitlement,
  fetchProjectExperienceLane,
  fetchProjectMembers,
  fetchProjects,
  mapWorkspaceDataError,
  ProjectEntitlementPayload,
  ProjectExperienceLanePayload,
  ProjectPayload,
  WorkspaceMembership
} from '../../src/services/api';
import { appTheme } from '../../src/theme';
import {
  asRecord,
  asString,
  formatTimestamp,
  toHumanLabel,
  toProjectId,
  truthyFlags
} from '../../src/features/workspace/format';
import {
  DataStateCard,
  KeyValueRow,
  SectionCard,
  WorkspaceChip,
  WorkspaceHero
} from '../../src/features/workspace/ui';

type AccessContextSnapshot = {
  packageLane: string;
  experienceMode: string;
  activeProjectId: string;
  activeFamilyId: string;
  activeEntitlements: string[];
};

type CountRow = {
  label: string;
  count: number;
};

function summarizeMembershipName(membership: WorkspaceMembership): string {
  return asString(membership.full_name) || asString(membership.email) || 'Unnamed member';
}

function toMembershipCounts(items: WorkspaceMembership[], key: keyof WorkspaceMembership): CountRow[] {
  const counts = new Map<string, number>();

  items.forEach((item) => {
    const label = asString(item[key]).toLowerCase() || 'unknown';
    counts.set(label, (counts.get(label) || 0) + 1);
  });

  return Array.from(counts.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label));
}

function summarizeContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    packageLane: asString(payload.package_lane),
    experienceMode: asString(payload.experience_mode),
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    activeEntitlements: Array.isArray(payload.active_entitlements)
      ? payload.active_entitlements
          .map((entry) => asString(entry))
          .filter((entry): entry is string => Boolean(entry))
      : []
  };
}

function pickActiveProject(projects: ProjectPayload[], activeProjectId: string): ProjectPayload | null {
  if (!projects.length) {
    return null;
  }

  const normalizedActiveId = activeProjectId.trim();
  if (normalizedActiveId) {
    const matched = projects.find((project) => toProjectId(project) === normalizedActiveId);
    if (matched) {
      return matched;
    }
  }

  return projects[0] || null;
}

function extractResolvedEntitlements(payload: ProjectEntitlementPayload | null): string[] {
  if (!payload) {
    return [];
  }

  return truthyFlags(asRecord(payload.resolved_entitlements), 'can_');
}

function deriveReadiness(project: ProjectPayload | null, entitlement: ProjectEntitlementPayload | null): string {
  if (!project) {
    return 'Project context not resolved';
  }

  const status = asString(project.status).toLowerCase();
  const phase = asString(project.phase).toLowerCase();
  const maintenance = asString(entitlement?.maintenance_status).toLowerCase();

  if (status === 'active' || status === 'purchased') {
    if (phase.includes('completed') || phase.includes('ready') || phase === 'checkout_completed') {
      return 'Ready for viewer setup and household collaboration';
    }

    return 'Provisioning in progress for current package lane';
  }

  if (status === 'draft') {
    return 'Provisioning not completed yet';
  }

  if (maintenance === 'active') {
    return 'Operational with active maintenance coverage';
  }

  return status ? `Status ${toHumanLabel(status)}` : 'Readiness unavailable';
}

function formatProjectLane(
  accessContext: AccessContextSnapshot | null,
  project: ProjectPayload | null,
  lanePayload: ProjectExperienceLanePayload | null,
  entitlement: ProjectEntitlementPayload | null
): string {
  return (
    asString(project?.project_lane) ||
    asString(lanePayload?.project_lane) ||
    asString(entitlement?.package_lane) ||
    asString(accessContext?.packageLane) ||
    'unknown'
  );
}

function isExpectedOptionalError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

export default function ProjectScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [projects, setProjects] = useState<ProjectPayload[]>([]);
  const [activeProject, setActiveProject] = useState<ProjectPayload | null>(null);
  const [experienceLane, setExperienceLane] = useState<ProjectExperienceLanePayload | null>(null);
  const [entitlement, setEntitlement] = useState<ProjectEntitlementPayload | null>(null);
  const [projectMembers, setProjectMembers] = useState<WorkspaceMembership[]>([]);
  const [nonBlockingNotes, setNonBlockingNotes] = useState<string[]>([]);

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadProjectView = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;

    setIsLoading(true);
    setErrorMessage('');
    setNonBlockingNotes([]);

    try {
      const [contextPayload, projectsPayload, membershipsPayload] = await Promise.all([
        fetchAccessContext(),
        fetchProjects(),
        fetchMyMemberships()
      ]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const summarizedContext = summarizeContext(asRecord(contextPayload));
      const projectItems = Array.isArray(projectsPayload.items) ? projectsPayload.items : [];
      const selectedProject = pickActiveProject(projectItems, summarizedContext.activeProjectId);

      setAccessContext(summarizedContext);
      setProjects(projectItems);
      setActiveProject(selectedProject);

      if (!selectedProject) {
        setExperienceLane(null);
        setEntitlement(null);
        setProjectMembers([]);
        return;
      }

      const selectedProjectId = toProjectId(selectedProject);
      const [laneResult, entitlementResult, membersResult] = await Promise.allSettled([
        fetchProjectExperienceLane(selectedProjectId),
        fetchProjectEntitlement(selectedProjectId),
        fetchProjectMembers(selectedProjectId)
      ]);

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      const fallbackMembers = Array.isArray(membershipsPayload.items)
        ? membershipsPayload.items.filter((membership) => asString(membership.project_id) === selectedProjectId)
        : [];

      const notes: string[] = [];

      if (laneResult.status === 'fulfilled') {
        setExperienceLane(laneResult.value);
      } else {
        setExperienceLane(null);
        notes.push(`Experience lane metadata unavailable: ${mapWorkspaceDataError(laneResult.reason)}`);
      }

      if (entitlementResult.status === 'fulfilled') {
        setEntitlement(entitlementResult.value);
      } else {
        setEntitlement(null);
        notes.push(`Project entitlement details unavailable: ${mapWorkspaceDataError(entitlementResult.reason)}`);
      }

      if (membersResult.status === 'fulfilled') {
        setProjectMembers(Array.isArray(membersResult.value.items) ? membersResult.value.items : []);
      } else {
        if (isExpectedOptionalError(membersResult.reason)) {
          setProjectMembers(fallbackMembers);
          notes.push(
            'Detailed project member endpoint is not available for this package scope. Showing membership context from /workspace-access/my-memberships.'
          );
        } else {
          setProjectMembers(fallbackMembers);
          notes.push(`Project membership details unavailable: ${mapWorkspaceDataError(membersResult.reason)}`);
        }
      }

      setNonBlockingNotes(notes);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setProjects([]);
      setActiveProject(null);
      setExperienceLane(null);
      setEntitlement(null);
      setProjectMembers([]);
      setNonBlockingNotes([]);
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadProjectView();

    return () => {
      mountedRef.current = false;
    };
  }, [loadProjectView]);

  const resolvedProjectId = activeProject ? toProjectId(activeProject) : '';

  const projectRoleRows = useMemo(() => {
    return toMembershipCounts(projectMembers, 'member_role');
  }, [projectMembers]);

  const relationshipScopeRows = useMemo(() => {
    return toMembershipCounts(projectMembers, 'relationship_scope');
  }, [projectMembers]);

  const privacyScopeRows = useMemo(() => {
    return toMembershipCounts(projectMembers, 'privacy_scope');
  }, [projectMembers]);

  const resolvedLane = formatProjectLane(accessContext, activeProject, experienceLane, entitlement);
  const resolvedEntitlementFlags = extractResolvedEntitlements(entitlement);
  const resolvedContextEntitlements = accessContext?.activeEntitlements || [];

  const laneModules = useMemo(() => {
    if (!experienceLane) {
      return [] as string[];
    }

    return Array.isArray(experienceLane.unlocked_modules)
      ? experienceLane.unlocked_modules.map((entry) => asString(entry)).filter((entry) => entry.length > 0)
      : [];
  }, [experienceLane]);

  const laneChambers = useMemo(() => {
    if (!experienceLane) {
      return [] as string[];
    }

    return Array.isArray(experienceLane.allowed_chambers)
      ? experienceLane.allowed_chambers.map((entry) => asString(entry)).filter((entry) => entry.length > 0)
      : [];
  }, [experienceLane]);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Project"
        description="Package lane, readiness, entitlement coverage, and project-scoped household context from live backend records."
        contextLine={resolvedProjectId ? `Project ${resolvedProjectId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadProjectView()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh project view"
      >
        <Text style={styles.refreshButtonText}>{isLoading ? 'Refreshing...' : 'Refresh Project Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading project workspace"
          message="Fetching active project context, package entitlements, and household member metadata."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load project view"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadProjectView()}
        />
      ) : null}

      {!isLoading && !errorMessage && !activeProject ? (
        <DataStateCard
          kind="empty"
          title="No project assigned"
          message="This account does not currently expose an active project in the mobile workspace context."
          actionLabel="Refresh"
          onAction={() => void loadProjectView()}
        />
      ) : null}

      {!isLoading && !errorMessage && activeProject ? (
        <>
          <SectionCard
            title="Project Identity"
            subtitle={`Showing ${projects.length} accessible project${projects.length === 1 ? '' : 's'} in this account context.`}
          >
            <View style={styles.rows}>
              <KeyValueRow label="Project ID" value={resolvedProjectId || 'Unavailable'} />
              <KeyValueRow label="Project Name" value={asString(activeProject.name) || 'Unnamed Project'} />
              <KeyValueRow label="Package Lane" value={toHumanLabel(resolvedLane)} />
              <KeyValueRow
                label="Active Family ID"
                value={asString(activeProject.family_id) || accessContext?.activeFamilyId || 'Not linked'}
              />
              <KeyValueRow
                label="Experience Mode"
                value={toHumanLabel(asString(experienceLane?.experience_mode) || accessContext?.experienceMode || 'unknown')}
              />
            </View>
          </SectionCard>

          <SectionCard title="Readiness And Lifecycle" subtitle="Backend project lifecycle fields surfaced without filler copy.">
            <View style={styles.chipRow}>
              <WorkspaceChip label={`Status: ${toHumanLabel(asString(activeProject.status) || 'unknown')}`} tone="accent" />
              <WorkspaceChip label={`Phase: ${toHumanLabel(asString(activeProject.phase) || 'unknown')}`} />
              <WorkspaceChip label={`Maintenance: ${toHumanLabel(asString(entitlement?.maintenance_status) || 'not_started')}`} tone="muted" />
            </View>

            <Text style={styles.readinessLabel}>Readiness</Text>
            <Text style={styles.readinessValue}>{deriveReadiness(activeProject, entitlement)}</Text>

            <View style={styles.rowsCompact}>
              <KeyValueRow label="Package Code" value={asString(activeProject.package_code) || asString(entitlement?.package_code) || 'Unavailable'} />
              <KeyValueRow label="Package Name" value={asString(activeProject.package_name) || asString(entitlement?.package_name) || 'Unavailable'} />
              <KeyValueRow label="Source" value={toHumanLabel(asString(activeProject.source) || 'unknown')} />
              <KeyValueRow label="Created" value={formatTimestamp(activeProject.created_at, 'Unavailable')} />
              <KeyValueRow label="Updated" value={formatTimestamp(activeProject.updated_at, 'Unavailable')} />
            </View>
          </SectionCard>

          <SectionCard title="Entitlements" subtitle="Capability flags and unlocked module/chamber payloads for this project.">
            <Text style={styles.sectionLabel}>Resolved Capability Flags</Text>
            <View style={styles.chipRow}>
              {resolvedEntitlementFlags.length > 0 ? (
                resolvedEntitlementFlags.map((flag) => <WorkspaceChip key={flag} label={flag} tone="success" />)
              ) : (
                <WorkspaceChip label="No resolved can_* flags returned" tone="muted" />
              )}
            </View>

            <Text style={styles.sectionLabel}>Access Context Entitlements</Text>
            <View style={styles.chipRow}>
              {resolvedContextEntitlements.length > 0 ? (
                resolvedContextEntitlements.map((entry) => <WorkspaceChip key={entry} label={entry} tone="accent" />)
              ) : (
                <WorkspaceChip label="No context entitlements returned" tone="muted" />
              )}
            </View>

            <Text style={styles.sectionLabel}>Unlocked Modules</Text>
            <View style={styles.chipRow}>
              {laneModules.length > 0 ? (
                laneModules.map((entry) => <WorkspaceChip key={entry} label={entry} />)
              ) : (
                <WorkspaceChip label="No unlocked_modules payload returned" tone="muted" />
              )}
            </View>

            <Text style={styles.sectionLabel}>Allowed Chambers</Text>
            <View style={styles.chipRow}>
              {laneChambers.length > 0 ? (
                laneChambers.map((entry) => <WorkspaceChip key={entry} label={entry} tone="warning" />)
              ) : (
                <WorkspaceChip label="No allowed_chambers payload returned" tone="muted" />
              )}
            </View>
          </SectionCard>

          <SectionCard
            title="Project Household Context"
            subtitle={`Members in current project scope: ${projectMembers.length}`}
          >
            <Text style={styles.sectionLabel}>Roles</Text>
            {projectRoleRows.length > 0 ? (
              projectRoleRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No project member role rows returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Relationship Scope</Text>
            {relationshipScopeRows.length > 0 ? (
              relationshipScopeRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No relationship scope rows returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Privacy Scope</Text>
            {privacyScopeRows.length > 0 ? (
              privacyScopeRows.map((row) => (
                <Text key={row.label} style={styles.inlineText}>
                  {toHumanLabel(row.label)}: {row.count}
                </Text>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No privacy scope rows returned.</Text>
            )}

            <Text style={styles.sectionLabel}>Current Members</Text>
            {projectMembers.length > 0 ? (
              projectMembers.slice(0, 8).map((member, index) => (
                <View key={`${asString(member.id) || summarizeMembershipName(member)}-${index}`} style={styles.memberRow}>
                  <Text style={styles.memberTitle}>{summarizeMembershipName(member)}</Text>
                  <Text style={styles.memberMeta}>Role: {toHumanLabel(asString(member.member_role) || 'unknown')}</Text>
                  <Text style={styles.memberMeta}>
                    Relationship Scope: {toHumanLabel(asString(member.relationship_scope) || 'unknown')}
                  </Text>
                  <Text style={styles.memberMeta}>
                    Privacy Scope: {toHumanLabel(asString(member.privacy_scope) || 'unknown')}
                  </Text>
                </View>
              ))
            ) : (
              <Text style={styles.inlineFallback}>No project members are currently exposed for this account.</Text>
            )}
          </SectionCard>

          <SectionCard
            title="Milestones And Checklist"
            subtitle="Interim mobile state while milestone/checklist APIs are not yet available."
          >
            <View style={styles.rowsCompact}>
              <WorkspaceChip label="Milestone endpoint: not yet exposed" tone="muted" />
              <WorkspaceChip label="Checklist endpoint: not yet exposed" tone="muted" />
            </View>
            <Text style={styles.interimLine}>
              Current mobile project readiness is based on status, phase, package lane, entitlement payloads, and project member scope.
            </Text>
            <Text style={styles.interimLine}>
              Once backend milestone/checklist routes are available, this card can promote to timeline and action tracking without replacing today’s real project metadata.
            </Text>
          </SectionCard>

          {nonBlockingNotes.length > 0 ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking route limitations observed while loading this screen.">
              {nonBlockingNotes.map((note) => (
                <Text key={note} style={styles.noteLine}>
                  - {note}
                </Text>
              ))}
            </SectionCard>
          ) : null}

          <View style={styles.actions}>
            <Link href="/(app)/uploads" asChild>
              <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open Uploads Center">
                <Text style={styles.primaryButtonText}>Open Uploads Center</Text>
              </Pressable>
            </Link>
            <Link href="/(app)/certificates" asChild>
              <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Review Certificates">
                <Text style={styles.secondaryButtonText}>Review Certificates</Text>
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
  refreshButtonText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  rows: {
    gap: appTheme.spacing.sm
  },
  rowsCompact: {
    gap: appTheme.spacing.xs
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
  readinessLabel: {
    marginTop: 4,
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  readinessValue: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '700',
    lineHeight: 22
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
  memberTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  memberMeta: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 18
  },
  interimLine: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
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
