import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function UploadsScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Uploads"
      description="Manage project documents and media with a secure, customer-safe ingestion workflow."
      stageLabel="Secure Intake"
      highlights={[
        { label: 'Transfer Security', value: 'Encrypted', tone: 'success' },
        { label: 'Queue Visibility', value: 'Structured' },
        { label: 'Record Linking', value: 'Traceable', tone: 'accent' }
      ]}
      todoItems={[
        'Upload handling is prepared for multipart intake and metadata normalization.',
        'Queue status and progress states are organized for transparent delivery tracking.',
        'Assets are associated with project and member records for full lineage traceability.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/project" asChild>
            <Pressable
              style={styles.secondaryButton}
              accessibilityRole="button"
              accessibilityLabel="Return to project center"
            >
              <Text style={styles.secondaryButtonText}>Return To Project Center</Text>
            </Pressable>
          </Link>
          <Link href="/(app)/support" asChild>
            <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Contact support">
              <Text style={styles.primaryButtonText}>Contact Support</Text>
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
