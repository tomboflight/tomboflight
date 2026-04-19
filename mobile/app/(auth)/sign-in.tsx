import React, { useState } from 'react';
import { Link, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import {
  AuthTokenResponse,
  beginMfaEnrollment,
  signIn,
  verifyMfaEnrollment,
  verifyMfaLogin
} from '../../src/services/auth';
import { ScreenContainer } from '../../src/components/ScreenContainer';
import { appTheme } from '../../src/theme';

type SignInMode = 'credentials' | 'mfa-verify' | 'mfa-enroll' | 'mfa-backup-codes';

function toErrorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return 'Unable to sign in. Please try again.';
}

export default function SignInScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<SignInMode>('credentials');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [mfaChallengeToken, setMfaChallengeToken] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [mfaRecoveryCode, setMfaRecoveryCode] = useState('');
  const [enrollmentSetupToken, setEnrollmentSetupToken] = useState('');
  const [enrollmentSecret, setEnrollmentSecret] = useState('');
  const [enrollmentOtpAuthUrl, setEnrollmentOtpAuthUrl] = useState('');
  const [enrollmentCode, setEnrollmentCode] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);

  async function onSubmitCredentials() {
    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !password.trim()) {
      setErrorMessage('Enter both email and password.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await signIn({
        email: normalizedEmail,
        password
      });

      if (response.mfa_required) {
        await startMfaFlow(response);
        return;
      }

      router.replace('/(app)/dashboard');
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startMfaFlow(response: AuthTokenResponse) {
    const challengeToken = response.mfa_challenge_token?.trim() || '';
    if (!challengeToken) {
      throw new Error('MFA challenge token is missing.');
    }

    setMfaChallengeToken(challengeToken);
    setMfaCode('');
    setMfaRecoveryCode('');
    setEnrollmentCode('');
    setBackupCodes([]);

    if (response.mfa_enrollment_required) {
      const enrollment = await beginMfaEnrollment(challengeToken);
      setEnrollmentSetupToken(enrollment.setup_token);
      setEnrollmentSecret(enrollment.secret);
      setEnrollmentOtpAuthUrl(enrollment.otpauth_url);
      setMode('mfa-enroll');
      return;
    }

    setMode('mfa-verify');
  }

  async function onSubmitMfaVerify() {
    const code = mfaCode.trim();
    const recoveryCode = mfaRecoveryCode.trim();

    if (!code && !recoveryCode) {
      setErrorMessage('Enter an authenticator code or a recovery code.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      await verifyMfaLogin({
        mfaChallengeToken,
        code: code || undefined,
        recoveryCode: recoveryCode || undefined
      });
      router.replace('/(app)/dashboard');
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onSubmitMfaEnrollment() {
    const code = enrollmentCode.trim();
    if (!code) {
      setErrorMessage('Enter the authenticator code to complete setup.');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      const response = await verifyMfaEnrollment(enrollmentSetupToken, code);
      const issuedCodes = response.backup_codes || [];
      if (issuedCodes.length > 0) {
        setBackupCodes(issuedCodes);
        setMode('mfa-backup-codes');
        return;
      }
      router.replace('/(app)/dashboard');
    } catch (error) {
      setErrorMessage(toErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  function resetMfaFlow() {
    setMode('credentials');
    setMfaChallengeToken('');
    setMfaCode('');
    setMfaRecoveryCode('');
    setEnrollmentSetupToken('');
    setEnrollmentSecret('');
    setEnrollmentOtpAuthUrl('');
    setEnrollmentCode('');
    setBackupCodes([]);
    setPassword('');
    setErrorMessage('');
  }

  function renderCredentialsForm() {
    return (
      <View style={styles.form}>
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
          placeholder="Password"
          accessibilityLabel="Password"
          placeholderTextColor={appTheme.colors.textSecondary}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          textContentType="password"
          style={styles.input}
        />
        <Pressable
          onPress={onSubmitCredentials}
          disabled={isSubmitting}
          accessibilityRole="button"
          accessibilityLabel="Sign In"
          style={({ pressed }) => [
            styles.primaryButton,
            (pressed || isSubmitting) && styles.primaryButtonPressed
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {isSubmitting ? 'Signing In...' : 'Sign In'}
          </Text>
        </Pressable>
        <View style={styles.links}>
          <Link href="/(auth)/sign-up" style={styles.linkText}>
            Create Account
          </Link>
          <Link href="/(auth)/forgot-password" style={styles.linkText}>
            Forgot Password
          </Link>
        </View>
      </View>
    );
  }

  function renderMfaVerifyForm() {
    return (
      <View style={styles.form}>
        <Text style={styles.subtitle}>
          Multi-factor verification is required for this account. Enter an authenticator code or
          use a recovery code.
        </Text>
        <TextInput
          value={mfaCode}
          onChangeText={setMfaCode}
          placeholder="Authenticator code"
          accessibilityLabel="Authenticator code"
          placeholderTextColor={appTheme.colors.textSecondary}
          keyboardType="number-pad"
          autoCorrect={false}
          autoCapitalize="none"
          textContentType="oneTimeCode"
          style={styles.input}
        />
        <TextInput
          value={mfaRecoveryCode}
          onChangeText={setMfaRecoveryCode}
          placeholder="Recovery code (optional)"
          accessibilityLabel="Recovery code"
          placeholderTextColor={appTheme.colors.textSecondary}
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />
        <Pressable
          onPress={onSubmitMfaVerify}
          disabled={isSubmitting}
          accessibilityRole="button"
          accessibilityLabel="Verify MFA"
          style={({ pressed }) => [
            styles.primaryButton,
            (pressed || isSubmitting) && styles.primaryButtonPressed
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {isSubmitting ? 'Verifying...' : 'Verify And Continue'}
          </Text>
        </Pressable>
        <Pressable
          onPress={resetMfaFlow}
          accessibilityRole="button"
          accessibilityLabel="Use another account"
          style={styles.secondaryButton}
        >
          <Text style={styles.secondaryButtonText}>Use Another Account</Text>
        </Pressable>
      </View>
    );
  }

  function renderMfaEnrollmentForm() {
    return (
      <View style={styles.form}>
        <Text style={styles.subtitle}>
          Set up your authenticator app using the setup key, then enter the first generated code.
        </Text>
        <View style={styles.infoCard}>
          <Text style={styles.infoLabel}>Manual Setup Key</Text>
          <Text style={styles.infoValue} selectable>
            {enrollmentSecret}
          </Text>
        </View>
        <View style={styles.infoCard}>
          <Text style={styles.infoLabel}>Authenticator URL</Text>
          <Text style={styles.infoValue} selectable>
            {enrollmentOtpAuthUrl}
          </Text>
        </View>
        <TextInput
          value={enrollmentCode}
          onChangeText={setEnrollmentCode}
          placeholder="First authenticator code"
          accessibilityLabel="First authenticator code"
          placeholderTextColor={appTheme.colors.textSecondary}
          keyboardType="number-pad"
          autoCorrect={false}
          autoCapitalize="none"
          textContentType="oneTimeCode"
          style={styles.input}
        />
        <Pressable
          onPress={onSubmitMfaEnrollment}
          disabled={isSubmitting}
          accessibilityRole="button"
          accessibilityLabel="Activate MFA"
          style={({ pressed }) => [
            styles.primaryButton,
            (pressed || isSubmitting) && styles.primaryButtonPressed
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {isSubmitting ? 'Activating...' : 'Activate MFA'}
          </Text>
        </Pressable>
        <Pressable
          onPress={resetMfaFlow}
          accessibilityRole="button"
          accessibilityLabel="Use another account"
          style={styles.secondaryButton}
        >
          <Text style={styles.secondaryButtonText}>Use Another Account</Text>
        </Pressable>
      </View>
    );
  }

  function renderBackupCodesPanel() {
    return (
      <View style={styles.form}>
        <Text style={styles.subtitle}>
          Save these backup codes in a secure place. Each code can be used once if your authenticator
          is unavailable.
        </Text>
        <View style={styles.backupCodesCard}>
          {backupCodes.map((code) => (
            <Text key={code} style={styles.backupCode} selectable>
              {code}
            </Text>
          ))}
        </View>
        <Pressable
          onPress={() => router.replace('/(app)/dashboard')}
          accessibilityRole="button"
          accessibilityLabel="Continue to dashboard"
          style={({ pressed }) => [styles.primaryButton, pressed && styles.primaryButtonPressed]}
        >
          <Text style={styles.primaryButtonText}>Continue To Dashboard</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScreenContainer>
      <View style={styles.card}>
        <Text style={styles.badge}>Tomb of Light</Text>
        <Text style={styles.title}>Sign In</Text>

        {errorMessage ? <Text style={styles.errorText}>{errorMessage}</Text> : null}

        {mode === 'credentials' && renderCredentialsForm()}
        {mode === 'mfa-verify' && renderMfaVerifyForm()}
        {mode === 'mfa-enroll' && renderMfaEnrollmentForm()}
        {mode === 'mfa-backup-codes' && renderBackupCodesPanel()}
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
  badge: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.6
  },
  title: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.title,
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
  errorText: {
    color: appTheme.colors.error,
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
  secondaryButton: {
    backgroundColor: appTheme.colors.surface,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    alignItems: 'center',
    paddingVertical: 12
  },
  secondaryButtonText: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600'
  },
  links: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  linkText: {
    color: appTheme.colors.primary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  infoCard: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F9FBFF',
    padding: appTheme.spacing.md,
    gap: appTheme.spacing.xs
  },
  infoLabel: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  infoValue: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '500'
  },
  backupCodesCard: {
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    borderRadius: appTheme.radius.md,
    backgroundColor: '#F9FBFF',
    padding: appTheme.spacing.md,
    gap: appTheme.spacing.xs
  },
  backupCode: {
    color: appTheme.colors.textPrimary,
    fontSize: appTheme.typography.body,
    fontWeight: '600',
    letterSpacing: 0.2
  }
});
