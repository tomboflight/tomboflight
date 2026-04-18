import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function ForgotPasswordScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Password Recovery"
      description="Password reset request screen for customer account recovery."
      todoItems={[
        'Send email reset request to FastAPI recovery endpoint.',
        'Show secure success messaging without exposing account existence.',
        'Link to post-reset sign-in once backend flow is implemented.'
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
