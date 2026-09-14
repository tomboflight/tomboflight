import React, { useEffect, useMemo, useState } from 'react';
import { Image, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { FamilyTreePayload, cacheProtectedUpload } from '../../services/api';
import { appTheme } from '../../theme';
import { asString, toHumanLabel } from '../workspace/format';

type TreeMember = Record<string, unknown>;
type TreeRelationship = Record<string, unknown>;

type NativeFamilyTreeProps = {
  payload: FamilyTreePayload;
  projectId?: string;
};

function memberId(member: TreeMember): string {
  return asString(member.id) || asString(member.person_id) || asString(member._id);
}

function memberName(member: TreeMember): string {
  return (
    asString(member.full_name) ||
    `${asString(member.first_name)} ${asString(member.last_name)}`.trim() ||
    'Unnamed family member'
  );
}

function memberGeneration(member: TreeMember): number {
  const value = Number(member.generation);
  return Number.isFinite(value) ? value : 0;
}

function relationshipType(relationship: TreeRelationship): string {
  return asString(relationship.relationship_type) || 'related';
}

function relationshipSource(relationship: TreeRelationship): string {
  return asString(relationship.source_member_id) || asString(relationship.source);
}

function relationshipTarget(relationship: TreeRelationship): string {
  return asString(relationship.target_member_id) || asString(relationship.target);
}

function idsFromMember(member: TreeMember, key: string): string[] {
  const value = member[key];
  if (Array.isArray(value)) {
    return value.map((item) => asString(item)).filter(Boolean);
  }
  const single = asString(value);
  return single ? [single] : [];
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

export function NativeFamilyTree({ payload, projectId }: NativeFamilyTreeProps) {
  const members = useMemo(
    () => (Array.isArray(payload.members) ? payload.members : []).filter(Boolean),
    [payload.members]
  );
  const relationships = useMemo(
    () => (Array.isArray(payload.relationships) ? payload.relationships : []).filter(Boolean),
    [payload.relationships]
  );
  const [selectedId, setSelectedId] = useState('');
  const [portraitUris, setPortraitUris] = useState<Record<string, string>>({});

  const membersById = useMemo(() => {
    const result = new Map<string, TreeMember>();
    members.forEach((member) => {
      const id = memberId(member);
      if (id) result.set(id, member);
    });
    return result;
  }, [members]);

  const lanes = useMemo(() => {
    const grouped = new Map<number, TreeMember[]>();
    members.forEach((member) => {
      const generation = memberGeneration(member);
      grouped.set(generation, [...(grouped.get(generation) || []), member]);
    });
    return Array.from(grouped.entries())
      .sort(([left], [right]) => left - right)
      .map(([generation, laneMembers]) => ({
        generation,
        members: laneMembers.sort((left, right) => memberName(left).localeCompare(memberName(right)))
      }));
  }, [members]);

  const portraitRequests = useMemo(
    () =>
      members
        .map((member) => ({
          id: memberId(member),
          uploadId: asString(member.approved_photo_upload_id)
        }))
        .filter((item) => item.id && item.uploadId),
    [members]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadPortraits() {
      const entries = await Promise.all(
        portraitRequests.map(async ({ id, uploadId }) => {
          try {
            const uri = await cacheProtectedUpload({
              uploadId,
              operation: 'preview',
              viewerProjectId: projectId
            });
            return [id, uri] as const;
          } catch {
            return null;
          }
        })
      );

      if (cancelled) return;
      setPortraitUris(
        entries.reduce<Record<string, string>>((result, entry) => {
          if (entry) result[entry[0]] = entry[1];
          return result;
        }, {})
      );
    }

    if (portraitRequests.length) {
      void loadPortraits();
    } else {
      setPortraitUris({});
    }

    return () => {
      cancelled = true;
    };
  }, [portraitRequests, projectId]);

  const selectedMember = selectedId ? membersById.get(selectedId) : undefined;
  const selectedRelationships = selectedId
    ? relationships
        .filter(
          (relationship) =>
            relationshipSource(relationship) === selectedId || relationshipTarget(relationship) === selectedId
        )
        .map((relationship) => {
          const source = relationshipSource(relationship);
          const target = relationshipTarget(relationship);
          const otherId = source === selectedId ? target : source;
          return {
            type: relationshipType(relationship),
            name: memberName(membersById.get(otherId) || {})
          };
        })
    : [];

  if (!members.length) {
    return (
      <View style={styles.emptyCard}>
        <Text style={styles.emptyTitle}>No family members are ready</Text>
        <Text style={styles.emptyText}>
          The authorized tree endpoint returned no members yet. Add or approve family records on the customer workspace before opening the native tree.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.wrapper}>
      <Text style={styles.helperText}>Tap a person to inspect the relationships visible in your authorized family context.</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.lanes}>
        {lanes.map((lane) => (
          <View key={lane.generation} style={styles.lane}>
            <Text style={styles.laneTitle}>{lane.generation ? `Generation ${lane.generation}` : 'Family records'}</Text>
            {lane.members.map((member) => {
              const id = memberId(member);
              const name = memberName(member);
              const isSelected = id === selectedId;
              const portraitUri = portraitUris[id];
              return (
                <Pressable
                  key={id || name}
                  style={[styles.memberCard, isSelected && styles.memberCardSelected]}
                  onPress={() => setSelectedId(id)}
                  accessibilityRole="button"
                  accessibilityLabel={`View ${name}`}
                  accessibilityState={{ selected: isSelected }}
                >
                  {portraitUri ? (
                    <Image source={{ uri: portraitUri }} style={styles.portrait} accessibilityLabel={`${name} portrait`} />
                  ) : (
                    <View style={styles.initials} accessible accessibilityLabel={`${name} portrait unavailable`}>
                      <Text style={styles.initialsText}>{initials(name) || '?'}</Text>
                    </View>
                  )}
                  <View style={styles.memberCopy}>
                    <Text style={styles.memberName} numberOfLines={2}>{name}</Text>
                    {asString(member.birth_year) ? <Text style={styles.memberMeta}>{asString(member.birth_year)}</Text> : null}
                    <Text style={styles.memberMeta}>{toHumanLabel(asString(member.placement_status) || 'placed')}</Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
        ))}
      </ScrollView>

      {selectedMember ? (
        <View style={styles.detailCard}>
          <Text style={styles.detailKicker}>Selected family member</Text>
          <Text style={styles.detailTitle}>{memberName(selectedMember)}</Text>
          <Text style={styles.detailText}>
            {selectedRelationships.length
              ? selectedRelationships.map((item) => `${toHumanLabel(item.type)}: ${item.name}`).join('  •  ')
              : 'No relationship edges are currently recorded for this member.'}
          </Text>
          <View style={styles.detailRows}>
            <Text style={styles.detailRow}>Parents: {idsFromMember(selectedMember, 'parent_ids').length || (idsFromMember(selectedMember, 'mother_id').length + idsFromMember(selectedMember, 'father_id').length)}</Text>
            <Text style={styles.detailRow}>Spouses: {idsFromMember(selectedMember, 'spouse_ids').length}</Text>
            <Text style={styles.detailRow}>Children: {idsFromMember(selectedMember, 'child_ids').length}</Text>
          </View>
        </View>
      ) : (
        <View style={styles.selectionHint}>
          <Text style={styles.selectionHintText}>Select a person to see relationship details.</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    gap: appTheme.spacing.sm
  },
  helperText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 19
  },
  lanes: {
    gap: appTheme.spacing.md,
    paddingVertical: 4,
    paddingRight: appTheme.spacing.md
  },
  lane: {
    width: 220,
    gap: appTheme.spacing.sm
  },
  laneTitle: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5
  },
  memberCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: appTheme.spacing.sm,
    minHeight: 84,
    padding: appTheme.spacing.sm,
    borderRadius: appTheme.radius.md,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    backgroundColor: appTheme.colors.surface
  },
  memberCardSelected: {
    borderColor: appTheme.colors.primary,
    backgroundColor: '#F1F6FF'
  },
  portrait: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#E7EEF9'
  },
  initials: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#DCE8FB'
  },
  initialsText: {
    color: appTheme.colors.primary,
    fontWeight: '800',
    fontSize: 17
  },
  memberCopy: {
    flex: 1,
    gap: 2
  },
  memberName: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  memberMeta: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption
  },
  detailCard: {
    gap: appTheme.spacing.xs,
    padding: appTheme.spacing.md,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#0E2A52'
  },
  detailKicker: {
    color: '#8AB6FF',
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase'
  },
  detailTitle: {
    color: '#FFFFFF',
    fontSize: appTheme.typography.heading,
    fontWeight: '800'
  },
  detailText: {
    color: '#E6EEFF',
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  detailRows: {
    gap: 2,
    marginTop: appTheme.spacing.xs
  },
  detailRow: {
    color: '#BFD2F4',
    fontSize: appTheme.typography.caption
  },
  selectionHint: {
    padding: appTheme.spacing.md,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F7F9FD',
    borderWidth: 1,
    borderColor: appTheme.colors.border
  },
  selectionHintText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption
  },
  emptyCard: {
    gap: appTheme.spacing.xs,
    padding: appTheme.spacing.md,
    borderRadius: appTheme.radius.md,
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.border
  },
  emptyTitle: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '700'
  },
  emptyText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 19
  }
});
