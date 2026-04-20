import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function CertificatesScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Certificates"
      description="Access certificate metadata and lineage proofs through a high-trust, customer-first vault experience."
      stageLabel="Proof Vault"
      highlights={[
        { label: 'Verification Signal', value: 'Strong', tone: 'success' },
        { label: 'Access Policy', value: 'Least Privilege' },
        { label: 'Lifecycle State', value: 'Managed', tone: 'accent' }
      ]}
      todoItems={[
        'Certificate metadata is structured for fast rendering and trustworthy review.',
        'Preview and download controls are aligned with secure access expectations.',
        'Issuance and verification states are tracked with clear customer context.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/billing" asChild>
            <Pressable style={styles.secondaryButton} accessibilityRole="button" accessibilityLabel="Open billing">
              <Text style={styles.secondaryButtonText}>Open Billing</Text>
            </Pressable>
          </Link>
          <Link href="/(app)/support" asChild>
            <Pressable
              style={styles.primaryButton}
              accessibilityRole="button"
              accessibilityLabel="Request certificate support"
            >
              <Text style={styles.primaryButtonText}>Request Certificate Support</Text>
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
