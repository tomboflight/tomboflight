import React from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text } from 'react-native';

import { FeaturePlaceholderScreen } from '../../src/components/FeaturePlaceholderScreen';
import { appTheme } from '../../src/theme';

export default function SignUpScreen() {
  return (
    <FeaturePlaceholderScreen
      title="Create Your Account"
      description="Starter screen for customer onboarding into Tomb of Light mobile."
      todoItems={[
        'Collect required identity and account fields for customer onboarding.',
        'Send sign-up payload to FastAPI and handle conflict/validation responses.',
        'Trigger post-signup verification and first-session bootstrap.'
      ]}
      footer={
        <Link href="/(auth)/sign-in" asChild>
          <Pressable style={styles.button}>
            <Text style={styles.buttonText}>Back To Sign In</Text>
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
