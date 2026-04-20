import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function ProjectScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Project Command Center"
      description="Keep project scope, milestones, and delivery confidence visible from one executive-grade view."
      stageLabel="Delivery Ready"
      highlights={[
        { label: 'Current Phase', value: 'Production Readiness', tone: 'accent' },
        { label: 'Open Milestones', value: '4' },
        { label: 'Risk Posture', value: 'Controlled', tone: 'success' }
      ]}
      todoItems={[
        'Scope, ownership, and accountability are mapped for each active workstream.',
        'Milestone sequencing and dependency visibility are optimized for quick decisions.',
        'Delivery updates are organized for client-facing communication and confidence.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/uploads" asChild>
            <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open uploads center">
              <Text style={styles.primaryButtonText}>Open Uploads Center</Text>
            </Pressable>
          </Link>
          <Link href="/(app)/certificates" asChild>
            <Pressable
              style={styles.secondaryButton}
              accessibilityRole="button"
              accessibilityLabel="Review certificates"
            >
              <Text style={styles.secondaryButtonText}>Review Certificates</Text>
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
