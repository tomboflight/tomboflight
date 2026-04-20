import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function BillingScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Billing And Coverage"
      description="Monitor package lane, payment status, and service coverage from a client-ready financial overview."
      stageLabel="Revenue Operations"
      highlights={[
        { label: 'Payment Confidence', value: 'Stable', tone: 'success' },
        { label: 'Package Lane', value: 'Visible' },
        { label: 'Invoice Posture', value: 'Actionable', tone: 'accent' }
      ]}
      todoItems={[
        'Billing summary data is aligned with account roles and package lane context.',
        'Invoice and payment history presentation is structured for fast customer review.',
        'Secure payment handoff flow is organized to minimize risk during checkout transitions.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/support" asChild>
            <Pressable style={styles.primaryButton} accessibilityRole="button" accessibilityLabel="Open billing support">
              <Text style={styles.primaryButtonText}>Open Billing Support</Text>
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
