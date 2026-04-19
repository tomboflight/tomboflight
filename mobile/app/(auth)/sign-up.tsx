import React, { useState } from 'react';
import { Link, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { ScreenContainer } from '../../src/components/ScreenContainer';
import { mapAuthError, signIn, signUp } from '../../src/services/auth';
import { appTheme } from '../../src/theme';

function normalizeEmail(input: string): string {
  return input.trim().toLowerCase();
}

export default function SignUpScreen() {
  const router = useRouter();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [eligibilityAttested, setEligibilityAttested] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  async function onSubmit() {
    const normalizedName = fullName.trim();
    const normalizedEmail = normalizeEmail(email);

    if (!normalizedName || !normalizedEmail || !password) {
      setErrorMessage('Complete all required fields.');
      return;
    }

    if (!normalizedEmail.includes('@')) {
      setErrorMessage('Enter a valid email address.');
      return;
    }

    if (password.length < 12) {
      setErrorMessage('Password must be at least 12 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage('Password confirmation does not match.');
      return;
    }

    if (!termsAccepted || !privacyAccepted || !eligibilityAttested) {
      setErrorMessage('You must accept terms, privacy, and eligibility statements.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');
    setSuccessMessage('');

    try {
      await signUp({
        fullName: normalizedName,
        email: normalizedEmail,
        password,
        termsAccepted,
        privacyAccepted,
        eligibilityAttested
      });

      const loginResponse = await signIn({
        email: normalizedEmail,
        password
      });

      if (loginResponse.mfa_required) {
        setSuccessMessage('Account created. Sign in to continue secure verification.');
        router.replace('/(auth)/sign-in');
        return;
      }

      router.replace('/(app)/dashboard');
    } catch (error) {
      setErrorMessage(mapAuthError(error, 'signUp'));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScreenContainer>
      <View style={styles.card}>
        <Text style={styles.title}>Create Account</Text>
        <Text style={styles.subtitle}>
          Register your customer account to access projects, family data, and support.
        </Text>

        <View style={styles.form}>
          <TextInput
            value={fullName}
            onChangeText={setFullName}
            placeholder="Full Name"
            accessibilityLabel="Full Name"
            placeholderTextColor={appTheme.colors.textSecondary}
            autoCapitalize="words"
            textContentType="name"
            style={styles.input}
          />
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
          <TextInput
            value={password}
            onChangeText={setPassword}
            placeholder="Password (12+ characters)"
            accessibilityLabel="Password"
            placeholderTextColor={appTheme.colors.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry
            textContentType="newPassword"
            style={styles.input}
          />
          <TextInput
            value={confirmPassword}
            onChangeText={setConfirmPassword}
            placeholder="Confirm Password"
            accessibilityLabel="Confirm Password"
            placeholderTextColor={appTheme.colors.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            secureTextEntry
            textContentType="newPassword"
            style={styles.input}
          />
        </View>

        <View style={styles.consentGroup}>
          <ConsentToggle
            checked={termsAccepted}
            onPress={() => setTermsAccepted((current) => !current)}
            label="I accept the Terms of Service."
          />
          <ConsentToggle
            checked={privacyAccepted}
            onPress={() => setPrivacyAccepted((current) => !current)}
            label="I accept the Privacy Policy."
          />
          <ConsentToggle
            checked={eligibilityAttested}
            onPress={() => setEligibilityAttested((current) => !current)}
            label="I attest that I am eligible to use this service."
          />
        </View>

        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}
        {successMessage ? <Text style={styles.successText}>{successMessage}</Text> : null}

        <Pressable
          onPress={onSubmit}
          disabled={isSubmitting}
          accessibilityRole="button"
          accessibilityLabel="Create Account"
          style={({ pressed }) => [
            styles.primaryButton,
            (pressed || isSubmitting) && styles.primaryButtonPressed
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {isSubmitting ? 'Creating Account...' : 'Create Account'}
          </Text>
        </Pressable>

        <Link href="/(auth)/sign-in" style={styles.linkText}>
          Back To Sign In
        </Link>
      </View>
    </ScreenContainer>
  );
}

type ConsentToggleProps = {
  checked: boolean;
  label: string;
  onPress: () => void;
};

function ConsentToggle({ checked, label, onPress }: ConsentToggleProps) {
  return (
    <Pressable
      onPress={onPress}
      style={styles.consentRow}
      accessibilityRole="checkbox"
      accessibilityState={{ checked }}
      accessibilityLabel={label}
    >
      <View style={[styles.checkbox, checked && styles.checkboxChecked]}>
        {checked ? <Text style={styles.checkboxMark}>✓</Text> : null}
      </View>
      <Text style={styles.consentText}>{label}</Text>
    </Pressable>
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
  form: {
    gap: appTheme.spacing.sm
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
  consentGroup: {
    gap: appTheme.spacing.sm
  },
  consentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: appTheme.spacing.sm
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: appTheme.colors.surface
  },
  checkboxChecked: {
    backgroundColor: appTheme.colors.primary,
    borderColor: appTheme.colors.primary
  },
  checkboxMark: {
    color: appTheme.colors.surface,
    fontSize: 12,
    fontWeight: '700'
  },
  consentText: {
    flex: 1,
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 18
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
