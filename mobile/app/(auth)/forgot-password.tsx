import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function ForgotPasswordScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Password Recovery"
      description="Customer password reset request entry point."
      todoItems={[
        'TODO: Submit reset request to FastAPI auth recovery endpoint.',
        'TODO: Show secure confirmation messaging.',
        'TODO: Complete reset token + return-to-signin flow.'
      ]}
      footer={
        <Link href="/(auth)/sign-in" asChild>
          <Pressable style={styles.button}>
            <Text style={styles.buttonText}>Return To Sign In</Text>
          </Pressable>
        </Link>
      }
    />
  );
}

const styles = StyleSheet.create({
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
  }
});
