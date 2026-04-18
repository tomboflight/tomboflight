import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function SettingsScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Settings"
      description="Customer account and preferences area for mobile configuration."
      todoItems={[
        'Connect profile preferences to existing backend account endpoints.',
        'Add notification preferences and secure credential actions.',
        'Expose support and legal links from this central screen.'
      ]}
      footer={
        <Link href="/(app)/support" asChild>
          <Pressable style={styles.button}>
            <Text style={styles.buttonText}>Open Support</Text>
          </Pressable>
        </Link>
      }
    />
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    paddingVertical: 12,
    borderRadius: appTheme.radius.md,
    alignItems: 'center'
  },
  buttonText: {
    color: appTheme.colors.textPrimary,
    fontWeight: '600',
    fontSize: appTheme.typography.body
  }
});
