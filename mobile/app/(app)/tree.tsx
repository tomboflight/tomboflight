import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { NativeFamilyTree } from '../../src/features/tree/NativeFamilyTree';
import { asRecord, asString, toHumanLabel } from '../../src/features/workspace/format';
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

function extractFamilyIdFromManifest(manifest: ViewerManifestPayload | null): string {
  const family = asRecord(manifest?.family);
  const project = asRecord(manifest?.project);
  return asString(family.id) || asString(family._id) || asString(project.family_id);
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

  const loadTree = useCallback(async () => {
    const requestId = requestSequence.current + 1;
    requestSequence.current = requestId;
    setIsLoading(true);
    setErrorMessage('');
    setNotes([]);

    try {
      const contextPayload = await fetchAccessContext();
      const context = summarizeContext(asRecord(contextPayload));
      let manifest: ViewerManifestPayload | null = null;
      let tree: FamilyTreePayload | null = null;
      const responseNotes: string[] = [];
      let familyId = context.activeFamilyId;

      try {
        manifest = await fetchViewerManifest({
          projectId: context.activeProjectId,
          familyId: context.activeFamilyId
        });
        familyId = familyId || extractFamilyIdFromManifest(manifest);
      } catch (error) {
        if (isOptionalDataError(error)) {
          responseNotes.push('Viewer manifest is not available for this package context.');
        } else {
          responseNotes.push(`Viewer manifest unavailable: ${mapWorkspaceDataError(error)}`);
        }
      }

      if (familyId) {
        try {
          tree = await fetchFamilyTree(familyId);
        } catch (error) {
          if (isOptionalDataError(error)) {
            responseNotes.push('Family tree data is not available for this family or entitlement.');
          } else {
            responseNotes.push(`Family tree unavailable: ${mapWorkspaceDataError(error)}`);
          }
        }
      } else {
        responseNotes.push('No active family identifier was returned by the workspace context.');
      }

      if (!mountedRef.current || requestId !== requestSequence.current) return;
      setAccessContext(context);
      setViewerManifest(manifest);
      setTreePayload(tree);
      setResolvedFamilyId(familyId);
      setNotes(responseNotes);
    } catch (error) {
      if (!mountedRef.current || requestId !== requestSequence.current) return;
      setErrorMessage(mapWorkspaceDataError(error));
      setAccessContext(null);
      setViewerManifest(null);
      setTreePayload(null);
      setResolvedFamilyId('');
    } finally {
      if (mountedRef.current && requestId === requestSequence.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadTree();
    return () => {
      mountedRef.current = false;
    };
  }, [loadTree]);

  const members = Array.isArray(treePayload?.members) ? treePayload.members : [];
  const relationships = Array.isArray(treePayload?.relationships) ? treePayload.relationships : [];
  const states = Array.isArray(viewerManifest?.states) ? viewerManifest.states : [];
  const familyRecord = asRecord(treePayload?.family);

  return (
    <ScreenContainer>
      <WorkspaceHero
        title="Family Tree"
        description="A native, customer-only view of the family records and relationship edges your active workspace authorizes."
        contextLine={resolvedFamilyId ? `Family ${resolvedFamilyId}` : undefined}
      />

      <Pressable
        style={[styles.refreshButton, isLoading && styles.refreshButtonDisabled]}
        onPress={() => void loadTree()}
        disabled={isLoading}
        accessibilityRole="button"
        accessibilityLabel="Refresh family tree"
      >
        <Text style={styles.refreshText}>{isLoading ? 'Refreshing…' : 'Refresh Family Tree'}</Text>
      </Pressable>

      {isLoading ? (
        <DataStateCard
          kind="loading"
          title="Loading family tree"
          message="Checking your workspace authorization, viewer readiness, and family relationship data."
        />
      ) : null}

      {!isLoading && errorMessage ? (
        <DataStateCard
          kind="error"
          title="Unable to load family tree"
          message={errorMessage}
          actionLabel="Retry"
          onAction={() => void loadTree()}
        />
      ) : null}

      {!isLoading && !errorMessage && accessContext ? (
        <>
          <SectionCard title="Authorized Workspace" subtitle="The identifiers and lane used for this tree request.">
            <View style={styles.rows}>
              <KeyValueRow label="Project" value={accessContext.activeProjectId || 'Unavailable'} />
              <KeyValueRow label="Family" value={resolvedFamilyId || 'Unavailable'} />
              <KeyValueRow label="Package lane" value={toHumanLabel(accessContext.packageLane || 'unknown')} />
              <KeyValueRow label="Family name" value={asString(familyRecord.family_name) || 'Unavailable'} />
            </View>
          </SectionCard>

          {treePayload && members.length ? (
            <SectionCard
              title="Native Family Tree"
              subtitle={`${members.length} member${members.length === 1 ? '' : 's'} • ${relationships.length} relationship edge${relationships.length === 1 ? '' : 's'}`}
            >
              <NativeFamilyTree payload={treePayload} projectId={accessContext.activeProjectId} />
            </SectionCard>
          ) : (
            <DataStateCard
              kind="empty"
              title="No tree records are ready"
              message="The account is signed in, but this authorized family does not yet have member records available to render."
              actionLabel="Open Uploads"
              onAction={() => undefined}
            />
          )}

          <SectionCard title="Viewer Readiness" subtitle="The viewer manifest remains separate from the family graph.">
            <View style={styles.rows}>
              <KeyValueRow label="Manifest mode" value={toHumanLabel(asString(viewerManifest?.mode) || 'unavailable')} />
              <KeyValueRow label="Viewer states" value={String(states.length)} />
              <KeyValueRow label="Portraits ready" value={viewerManifest ? (viewerManifest.has_uploaded_portraits ? 'Yes' : 'No') : 'Unavailable'} />
            </View>
            <View style={styles.chipRow}>
              {states.slice(0, 5).map((state) => (
                <WorkspaceChip
                  key={asString(state.id) || asString(state.title)}
                  label={`${asString(state.title) || 'Untitled'} • ${toHumanLabel(asString(state.status) || 'unknown')}`}
                  tone="accent"
                />
              ))}
              {!states.length ? <WorkspaceChip label="No viewer states returned" tone="muted" /> : null}
            </View>
          </SectionCard>

          {notes.length ? (
            <SectionCard title="Data Notes" subtitle="Non-blocking conditions observed during the request.">
              {notes.map((note) => <Text key={note} style={styles.noteLine}>{note}</Text>)}
            </SectionCard>
          ) : null}

          <View style={styles.actions}>
            <Link href="/(app)/family" asChild>
              <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Review family context">
                <Text style={styles.secondaryButtonText}>Review Family Context</Text>
              </Pressable>
            </Link>
            <Link href="/(app)/uploads" asChild>
              <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open uploads">
                <Text style={styles.primaryButtonText}>Open Uploads</Text>
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
  refreshButtonDisabled: { opacity: 0.72 },
  refreshText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.caption,
    fontWeight: '700'
  },
  rows: { gap: appTheme.spacing.sm },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: appTheme.spacing.xs, marginTop: appTheme.spacing.sm },
  noteLine: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.body, lineHeight: 22 },
  actions: { gap: appTheme.spacing.sm },
  primaryButton: {
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    paddingVertical: 12
  },
  primaryButtonText: { color: appTheme.colors.surface, fontSize: appTheme.typography.body, fontWeight: '700' },
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
  secondaryButtonText: { color: appTheme.colors.textPrimary, fontSize: appTheme.typography.body, fontWeight: '600' }
});
