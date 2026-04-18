import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function SignInScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Welcome Back"
      description="Customer sign-in flow for Tomb of Light mobile."
      todoItems={[
        'Connect submit action to FastAPI sign-in endpoint.',
        'Store issued token securely and bootstrap session state.',
        'Handle backend validation errors and lockout states.'
      ]}
      footer={
        <View style={styles.actions}>
          <Link href="/(auth)/sign-up" asChild>
            <Pressable style={styles.button}>
              <Text style={styles.buttonText}>Go To Sign Up</Text>
            </Pressable>
          </Link>
          <Link href="/(auth)/forgot-password" asChild>
            <Pressable style={styles.secondaryButton}>
              <Text style={styles.secondaryText}>Forgot Password</Text>
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
  button: {
    backgroundColor: appTheme.colors.primary,
    paddingVertical: 12,
    borderRadius: appTheme.radius.md,
    alignItems: 'center'
  },
  buttonText: {
    color: appTheme.colors.surface,
    fontWeight: '600',
    fontSize: appTheme.typography.body
  },
  secondaryButton: {
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    paddingVertical: 12,
    borderRadius: appTheme.radius.md,
    alignItems: 'center'
  },
  secondaryText: {
    color: appTheme.colors.textPrimary,
    fontWeight: '600',
    fontSize: appTheme.typography.body
  }
});
