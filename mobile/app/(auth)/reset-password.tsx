import React, { useState } from 'react';
import { Link, useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { confirmPasswordReset, mapAuthError } from '../../src/services/auth';
import { appTheme } from '../../src/theme';

export default function ResetPasswordScreen() {
  const params = useLocalSearchParams<{ token?: string }>();
  const token = String(params.token || '').trim();
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  async function onSubmit() {
    setErrorMessage('');
    setSuccessMessage('');

    if (!token) {
      setErrorMessage('Open this screen from the secure password reset link in your email.');
      return;
    }
    if (password.length < 12) {
      setErrorMessage('Use a password with at least 12 characters.');
      return;
    }
    if (password !== confirmation) {
      setErrorMessage('New passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await confirmPasswordReset({ token, newPassword: password });
      setSuccessMessage(result.message || 'Password reset completed. You can sign in now.');
      setPassword('');
      setConfirmation('');
    } catch (error) {
      setErrorMessage(mapAuthError(error, 'passwordReset'));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScreenContainer>
      <View style={styles.card}>
        <Text style={styles.title}>Choose a New Password</Text>
        <Text style={styles.subtitle}>Use the one-time token from the secure Tomb of Light reset link.</Text>

        <TextInput
          value={password}
          onChangeText={setPassword}
          placeholder="New password (12+ characters)"
          accessibilityLabel="New password"
          placeholderTextColor={appTheme.colors.textSecondary}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />
        <TextInput
          value={confirmation}
          onChangeText={setConfirmation}
          placeholder="Confirm new password"
          accessibilityLabel="Confirm new password"
          placeholderTextColor={appTheme.colors.textSecondary}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />

        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
        {successMessage ? <Text style={styles.successText}>{successMessage}</Text> : null}

        <Pressable onPress={() => void onSubmit()} disabled={isSubmitting} accessibilityRole="button" accessibilityLabel="Confirm password reset" style={({ pressed }) => [styles.primaryButton, (pressed || isSubmitting) && styles.primaryButtonPressed]}>
          <Text style={styles.primaryButtonText}>{isSubmitting ? 'Saving...' : 'Save New Password'}</Text>
        </Pressable>

        <Link href="/(auth)/sign-in" style={styles.linkText}>Return To Sign In</Link>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  card: { backgroundColor: appTheme.colors.surface, borderRadius: appTheme.radius.lg, borderWidth: 1, borderColor: appTheme.colors.border, padding: appTheme.spacing.lg, gap: appTheme.spacing.md },
  title: { color: appTheme.colors.textPrimary, fontSize: appTheme.typography.heading, fontWeight: '700' },
  subtitle: { color: appTheme.colors.textSecondary, fontSize: appTheme.typography.body, lineHeight: 22 },
  input: { borderWidth: 1, borderColor: appTheme.colors.border, backgroundColor: appTheme.colors.surface, borderRadius: appTheme.radius.md, paddingHorizontal: 14, paddingVertical: 12, fontSize: appTheme.typography.body, color: appTheme.colors.textPrimary },
  errorText: { color: appTheme.colors.error, fontSize: appTheme.typography.caption },
  successText: { color: appTheme.colors.success, fontSize: appTheme.typography.caption },
  primaryButton: { backgroundColor: appTheme.colors.primary, borderRadius: appTheme.radius.md, alignItems: 'center', paddingVertical: 12 },
  primaryButtonPressed: { backgroundColor: appTheme.colors.primaryPressed },
  primaryButtonText: { color: appTheme.colors.surface, fontSize: appTheme.typography.body, fontWeight: '600' },
  linkText: { color: appTheme.colors.primary, textAlign: 'center', fontSize: appTheme.typography.caption, fontWeight: '600' }
});
