import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function SupportScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Support"
      description="Reach support, escalation guidance, and account assistance through a professional service workflow."
      stageLabel="Service Desk"
      highlights={[
        { label: 'Coverage Window', value: 'Operational' },
        { label: 'Escalation Route', value: 'Defined', tone: 'accent' },
        { label: 'Response Quality', value: 'High Touch', tone: 'success' }
      ]}
      todoItems={[
        'Support requests are classified by issue category for fast triage and ownership.',
        'FAQ guidance and escalation pathways are available to reduce friction.',
        'Diagnostic capture is structured to speed up incident investigation when needed.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/settings" asChild>
            <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open account settings">
              <Text style={styles.secondaryButtonText}>Open Account Settings</Text>
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
