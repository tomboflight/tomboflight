import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import {
  ApiError,
  FamilyTreePayload,
  fetchAccessContext,
  fetchFamilyTree,
  fetchViewerManifest,
  mapWorkspaceDataError,
  ViewerManifestPayload
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

function summarizeContext(payload: Record<string, unknown>): AccessContextSnapshot {
  return {
    activeProjectId: asString(payload.active_project_id),
    activeFamilyId: asString(payload.active_family_id),
    packageLane: asString(payload.package_lane)
  };
}

function isOptionalDataError(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404);
}

function manifestStateCount(manifest: ViewerManifestPayload | null): number {
  if (!manifest || !Array.isArray(manifest.states)) {
    return 0;
  }

  return manifest.states.length;
}

function extractFamilyIdFromManifest(manifest: ViewerManifestPayload | null): string {
  if (!manifest) {
    return '';
  }

  const familyRecord = asRecord(manifest.family);
  const projectRecord = asRecord(manifest.project);

  return (
    asString(familyRecord.id) || asString(familyRecord._id) || asString(projectRecord.family_id) || ''
  );
}

function treeDataStatus(treePayload: FamilyTreePayload | null, viewerManifest: ViewerManifestPayload | null): string {
  const memberCount = Array.isArray(treePayload?.members) ? treePayload.members?.length || 0 : 0;
  const relationshipCount = Array.isArray(treePayload?.relationships)
    ? treePayload.relationships?.length || 0
    : 0;
  const hasViewerStates = manifestStateCount(viewerManifest) > 0;
  const hasUploadedPortraits = Boolean(viewerManifest?.has_uploaded_portraits);

  if (memberCount > 0 || relationshipCount > 0) {
    return 'Tree payload available and ready for graph rendering.';
  }

  if (hasViewerStates && hasUploadedPortraits) {
    return 'Viewer payload is ready; tree graph data is still sparse for this family.';
  }

  if (hasViewerStates && !hasUploadedPortraits) {
    return 'Viewer workspace anchor exists and is waiting for portrait uploads.';
  }

  return 'No tree or viewer payload records are currently available for this context.';
}

export default function TreeScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  const [accessContext, setAccessContext] = useState<AccessContextSnapshot | null>(null);
  const [viewerManifest, setViewerManifest] = useState<ViewerManifestPayload | null>(null);
  const [treePayload, setTreePayload] = useState<FamilyTreePayload | null>(null);
  const [resolvedFamilyId, setResolvedFamilyId] = useState('');
  const [notes, setNotes] = useState<string[]>([]);

  const mountedRef = useRef(true);
  const requestSequence = useRef(0);

  const loadTreeEntry = useCallback(async () => {
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

      const contextSummary = summarizeContext(asRecord(contextPayload));
      setAccessContext(contextSummary);

      const responseNotes: string[] = [];
      let manifestPayload: ViewerManifestPayload | null = null;
      let treeDataPayload: FamilyTreePayload | null = null;
      let familyIdForTree = contextSummary.activeFamilyId;

      if (contextSummary.activeProjectId || contextSummary.activeFamilyId) {
        try {
          manifestPayload = await fetchViewerManifest({
            projectId: contextSummary.activeProjectId,
            familyId: contextSummary.activeFamilyId
          });
        } catch (error) {
          if (isOptionalDataError(error)) {
            responseNotes.push(
              'Viewer manifest is not yet available for this package context. Tree entry remains based on direct family/tree payload checks.'
            );
          } else {
            responseNotes.push(`Viewer manifest unavailable: ${mapWorkspaceDataError(error)}`);
          }
        }
      } else {
        responseNotes.push('No active project/family identifiers were returned by /users/me/access-context.');
      }

      if (!familyIdForTree) {
        familyIdForTree = extractFamilyIdFromManifest(manifestPayload);
      }

      if (familyIdForTree) {
        try {
          treeDataPayload = await fetchFamilyTree(familyIdForTree);
        } catch (error) {
          if (isOptionalDataError(error)) {
            responseNotes.push(
              'Family tree payload is currently unavailable for this family or package entitlement. Viewer payload checks remain active.'
            );
          } else {
            responseNotes.push(`Family tree payload unavailable: ${mapWorkspaceDataError(error)}`);
          }
        }
      } else {
        responseNotes.push('Unable to resolve a family id from access context or viewer manifest.');
      }

      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setViewerManifest(manifestPayload);
      setTreePayload(treeDataPayload);
      setResolvedFamilyId(familyIdForTree);
      setNotes(responseNotes);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) {
        return;
      }

      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setViewerManifest(null);
      setTreePayload(null);
      setResolvedFamilyId('');
      setNotes([]);
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadTreeEntry();

    return () => {
      mountedRef.current = false;
    };
  }, [loadTreeEntry]);

  const stateCount = manifestStateCount(viewerManifest);
  const memberCount = Array.isArray(treePayload?.members) ? treePayload.members?.length || 0 : 0;
  const nodeCount = Array.isArray(treePayload?.nodes) ? treePayload.nodes?.length || 0 : 0;
  const relationshipCount = Array.isArray(treePayload?.relationships) ? treePayload.relationships?.length || 0 : 0;
  const linkedFamilyIds = Array.isArray(treePayload?.linked_family_ids) ? treePayload.linked_family_ids : [];

  const treeFamilyRecord = useMemo(() => asRecord(treePayload?.family), [treePayload]);

  const treeEntryStatus = treeDataStatus(treePayload, viewerManifest);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Tree Entry"
        description="Mobile tree entry scaffold powered by live project/family identifiers, viewer payload checks, and direct tree data probes."
        contextLine={resolvedFamilyId ? `Family ${resolvedFamilyId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadTreeEntry()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh tree entry"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing...' : 'Refresh Tree Data'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading tree entry"
          message="Checking access context, viewer manifest readiness, and family tree payload availability."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load tree entry"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadTreeEntry()}
        />
      ) : null}

      {!isLoading && !errorMessage && !accessContext ? (
        <DataStateCard
          kind="empty"
          title="No tree entry context available"
          message="No active project/family context is currently exposed for this account."
          actionLabel="Refresh"
          onAction={() => void loadTreeEntry()}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Identifier Context" subtitle="Resolved IDs used to probe tree and viewer payload routes.">
            <View style={styles.rows}>
              <KeyValueRow label="Active Project ID" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Active Family ID" value={accessContext.activeFamilyId || 'Unavailable'} />
              <KeyValueRow label="Resolved Family ID" value={resolvedFamilyId || 'Unavailable'} />
              <KeyValueRow label="Package Lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
            </View>
          </SectionCard>

          <SectionCard title="Viewer Payload Check" subtitle="Uses /viewer/manifest to determine viewer readiness for this context.">
            <View style={styles.rows}>
              <KeyValueRow label="Manifest Mode" value={toHumanLabel(asString(viewerManifest?.mode) || 'unavailable')} />
              <KeyValueRow label="Workspace Name" value={asString(viewerManifest?.workspace_name) || 'Unavailable'} />
              <KeyValueRow label="Viewer States" value={String(stateCount)} />
              <KeyValueRow
                label="Has Uploaded Portraits"
                value={viewerManifest ? (viewerManifest.has_uploaded_portraits ? 'Yes' : 'No') : 'Unavailable'}
              />
              <KeyValueRow label="Initial State ID" value={asString(viewerManifest?.initial_state_id) || 'Unavailable'} />
            </View>

            <View style={styles.chipRow}>
              {stateCount > 0 ? (
                viewerManifest?.states?.slice(0, 5).map((state) => (
                  <WorkspaceChip
                    key={asString(state.id) || asString(state.title)}
                    label={`${asString(state.title) || 'Untitled'} • ${asString(state.status) || 'Unknown'}`}
                    tone="accent"
                  />
                ))
              ) : (
                <WorkspaceChip label="No viewer states returned" tone="muted" />
              )}
            </View>
          </SectionCard>

          <SectionCard title="Tree Payload Check" subtitle="Uses /tree/{family_id} to determine whether graph data exists.">
            <View style={styles.rows}>
              <KeyValueRow label="Family Name" value={asString(treeFamilyRecord.family_name) || 'Unavailable'} />
              <KeyValueRow label="Tree Mode" value={toHumanLabel(asString(treePayload?.mode) || 'default')} />
              <KeyValueRow label="Members" value={String(memberCount)} />
              <KeyValueRow label="Nodes" value={String(nodeCount)} />
              <KeyValueRow label="Relationships" value={String(relationshipCount)} />
              <KeyValueRow
                label="Family Visibility"
                value={toHumanLabel(asString(treeFamilyRecord.visibility) || 'unknown')}
              />
            </View>

            <Text style={styles.sectionLabel}>Linked Families</Text>
            <View style={styles.chipRow}>
              {linkedFamilyIds.length > 0 ? (
                linkedFamilyIds.map((familyId) => <WorkspaceChip key={familyId} label={familyId} tone="warning" />)
              ) : (
                <WorkspaceChip label="No linked family ids returned" tone="muted" />
              )}
            </View>
          </SectionCard>

          <SectionCard title="Entry Status" subtitle="Meaningful mobile state while full native tree rendering is in progress.">
            <Text style={styles.statusText}>{treeEntryStatus}</Text>
            <View style={styles.chipRow}>
              <WorkspaceChip label={`Viewer states: ${stateCount}`} tone="accent" />
              <WorkspaceChip label={`Tree members: ${memberCount}`} tone="success" />
              <WorkspaceChip label={`Relationships: ${relationshipCount}`} />
            </View>
          </SectionCard>

          {notes.length > 0 ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking route constraints observed while loading tree entry.">
              {notes.map((note) => (
                <Text key={note} style={styles.noteLine}>
                  - {note}
                </Text>
              ))}
            </SectionCard>
          ) : null}

          <View style={styles.actions}>
            <Link href="/(app)/family" asChild>
              <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Review family context">
                <Text style={styles.primaryButtonText}>Review Family Context</Text>
              </Pressable>
            </Link>
            <Link href="/(app)/uploads" asChild>
              <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open uploads">
                <Text style={styles.secondaryButtonText}>Open Uploads</Text>
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
  statusText: {
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
