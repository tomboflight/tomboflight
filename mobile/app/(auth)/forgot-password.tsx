import React, { useState } from 'react';
import { Link } from 'expo-router';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { requestPasswordReset } from '../../src/services/auth';
import { appTheme } from '../../src/theme';

function toErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return 'Unable to submit reset request. Please try again.';
}

export default function ForgotPasswordScreen() {
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  async function onSubmit() {
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !normalizedEmail.includes('@')) {
      setErrorMessage('Enter a valid email address.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');
    setSuccessMessage('');

    try {
      const result = await requestPasswordReset(normalizedEmail);
      setSuccessMessage(result.message || 'If that account exists, reset instructions were sent.');
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScreenContainer>
      <View style={styles.card}>
        <Text style={styles.title}>Reset Password</Text>
        <Text style={styles.subtitle}>
          Submit your email to request a secure password reset link.
        </Text>

        <TextInput
          value={email}
          onChangeText={setEmail}
          placeholder="Email"
          accessibilityLabel="Email"
          placeholderTextColor={appTheme.colors.textSecondary}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          textContentType="emailAddress"
          style={styles.input}
        />

        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
        {successMessage ? <Text style={styles.successText}>{successMessage}</Text> : null}

        <Pressable
          onPress={onSubmit}
          disabled={isSubmitting}
          accessibilityRole="button"
          accessibilityLabel="Request Reset"
          style={({ pressed }) => [
            styles.primaryButton,
            (pressed || isSubmitting) && styles.primaryButtonPressed
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {isSubmitting ? 'Submitting...' : 'Request Reset'}
          </Text>
        </Pressable>

        <Link href="/(auth)/sign-in" style={styles.linkText}>
          Return To Sign In
        </Link>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.lg,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    padding: appTheme.spacing.lg,
    gap: appTheme.spacing.md
  },
  title: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.heading,
    fontWeight: '700'
  },
  subtitle: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.body,
    lineHeight: 22
  },
  input: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: appTheme.typography.body,
    color: appTheme.colors.textPrimary
  },
  errorText: {
    color: appTheme.colors.error,
    fontSize: appTheme.typography.caption
  },
  successText: {
    color: appTheme.colors.success,
    fontSize: appTheme.typography.caption
  },
  primaryButton: {
    backgroundColor: appTheme.colors.primary,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    paddingVertical: 12
  },
  primaryButtonPressed: {
    backgroundColor: appTheme.colors.primaryPressed
  },
  primaryButtonText: {
    color: appTheme.colors.surface,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  linkText: {
    color: appTheme.colors.primary,
    textAlign: 'center',
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  }
});
