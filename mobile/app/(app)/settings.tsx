import React from 'react';
import { Link, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { signOut } from '../../src/services/auth';
import { appTheme } from '../../src/theme';

export default function SettingsScreen() {
  const router = useRouter();

  async function onSignOut() {
    try {
      await signOut();
    } finally {
      router.replace('/(auth)/sign-in');
    }
  }

  return (
    <FeaturePlaceholderScreen
      title="Settings"
      description="Customer settings starter for profile and preferences."
      todoItems={[
        'TODO: Save account settings to FastAPI.',
        'TODO: Add notification preference management.',
        'TODO: Add legal/support/account controls.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(app)/support" asChild>
            <Pressable style={styles.button} accessibilityRole="button" accessibilityLabel="Open Support">
              <Text style={styles.buttonText}>Open Support</Text>
            </Pressable>
          </Link>
          <Pressable
            style={styles.signOutButton}
            onPress={onSignOut}
            accessibilityRole="button"
            accessibilityLabel="Sign Out"
          >
            <Text style={styles.signOutText}>Sign Out</Text>
          </Pressable>
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  actions: {
    gap: appTheme.spacing.sm
  },
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
  },
  signOutButton: {
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.error,
    paddingVertical: 12,
    borderRadius: appTheme.radius.md,
    alignItems: 'center'
  },
  signOutText: {
    color: appTheme.colors.error,
    fontWeight: '600',
    fontSize: appTheme.typography.body
  }
});
