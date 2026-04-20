import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function TreeScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Family Tree Viewer"
      description="Explore lineage relationships from a mobile-optimized tree experience built for clarity and confidence."
      stageLabel="Visualization Suite"
      highlights={[
        { label: 'Navigation Model', value: 'Touch Optimized', tone: 'accent' },
        { label: 'Node Context', value: 'Expandable' },
        { label: 'Data Integrity', value: 'Verified', tone: 'success' }
      ]}
      todoItems={[
        'Graph payloads are prepared for reliable mobile rendering at family scale.',
        'Interaction patterns support smooth pan, zoom, and node inspection.',
        'Lineage context is organized to keep exploration intuitive and trustworthy.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/family" asChild>
            <Pressable
              style={styles.primaryButton}
              accessibilityRole="button"
              accessibilityLabel="Review family records"
            >
              <Text style={styles.primaryButtonText}>Review Family Records</Text>
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
  }
});
