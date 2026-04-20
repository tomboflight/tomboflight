import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function FamilyScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Family Workspace"
      description="Review household members, roles, and lineage context with clear privacy-safe visibility controls."
      stageLabel="Access Controlled"
      highlights={[
        { label: 'Privacy Model', value: 'Role Based', tone: 'success' },
        { label: 'Household Views', value: 'Unified' },
        { label: 'Visibility Scope', value: 'Policy Aligned', tone: 'accent' }
      ]}
      todoItems={[
        'Household records are structured for quick member review and profile drill-down.',
        'Visibility boundaries align with billing owner, co-owner, and family manager roles.',
        'Privacy scope and relationship scope are surfaced with clear account context.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/tree" asChild>
            <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open family tree">
              <Text style={styles.primaryButtonText}>Open Family Tree</Text>
            </Pressable>
          </Link>
          <Link href="/(app)/project" asChild>
            <Pressable
              style={styles.secondaryButton}
              accessibilityRole="button"
              accessibilityLabel="Return to project center"
            >
              <Text style={styles.secondaryButtonText}>Return To Project Center</Text>
            </Pressable>
          </Link>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
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
