import React, { useState } from 'react';
import { Link, useRouter } from 'expo-router';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import {
  AuthTokenResponse,
  beginMfaEnrollment,
  mapAuthError,
  signIn,
  verifyMfaEnrollment,
  verifyMfaLogin
} from '../../src/services/auth';
import { ScreenContainer } from '../../src/components/ScreenContainer';
import { appTheme } from '../../src/theme';

type SignInMode = 'credentials' | 'mfa-verify' | 'mfa-enroll' | 'mfa-backup-codes';
type MfaVerifyMethod = 'authenticator' | 'recovery';

export default function SignInScreen() {
  const router = useRouter();
  const [mode, setMode] = useState<SignInMode>('credentials');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const [mfaChallengeToken, setMfaChallengeToken] = useState('');
  const [mfaVerifyMethod, setMfaVerifyMethod] = useState<MfaVerifyMethod>('authenticator');
  const [mfaCode, setMfaCode] = useState('');
  const [mfaRecoveryCode, setMfaRecoveryCode] = useState('');

  const [enrollmentSetupToken, setEnrollmentSetupToken] = useState('');
  const [enrollmentSecret, setEnrollmentSecret] = useState('');
  const [enrollmentOtpAuthUrl, setEnrollmentOtpAuthUrl] = useState('');
  const [enrollmentCode, setEnrollmentCode] = useState('');

  const [backupCodes, setBackupCodes] = useState<string[]>([]);

  function clearError(): void {
    if (errorMessage) {
      setErrorMessage('');
    }
  }

  function clearMfaState(): void {
    setMfaChallengeToken('');
    setMfaVerifyMethod('authenticator');
    setMfaCode('');
    setMfaRecoveryCode('');
    setEnrollmentSetupToken('');
    setEnrollmentSecret('');
    setEnrollmentOtpAuthUrl('');
    setEnrollmentCode('');
    setBackupCodes([]);
  }

  async function onSubmitCredentials() {
    if (isSubmitting) {
      return;
    }

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !password.trim()) {
      setErrorMessage('Enter both email and password.');
      return;
    }

    if (!normalizedEmail.includes('@')) {
      setErrorMessage('Enter a valid email address.');
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
      setErrorMessage(mapAuthError(error, 'signIn'));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function startMfaFlow(response: AuthTokenResponse) {
    const challengeToken = response.mfa_challenge_token?.trim() || '';
    if (!challengeToken) {
      throw new Error('Additional verification is required. Please sign in again.');
    }

    setMfaChallengeToken(challengeToken);
    setMfaVerifyMethod('authenticator');
    setMfaCode('');
    setMfaRecoveryCode('');
    setEnrollmentCode('');
    setBackupCodes([]);

    if (response.mfa_enrollment_required) {
      await loadEnrollmentChallenge(challengeToken);
      setMode('mfa-enroll');
      return;
    }

    setMode('mfa-verify');
  }

  async function loadEnrollmentChallenge(challengeToken: string) {
    const enrollment = await beginMfaEnrollment(challengeToken);

    if (!enrollment.setup_token?.trim() || !enrollment.secret?.trim() || !enrollment.otpauth_url?.trim()) {
      throw new Error('MFA setup response was incomplete. Please try signing in again.');
    }

    setEnrollmentSetupToken(enrollment.setup_token);
    setEnrollmentSecret(enrollment.secret);
    setEnrollmentOtpAuthUrl(enrollment.otpauth_url);
  }

  async function restartMfaEnrollment() {
    if (isSubmitting) {
      return;
    }

    if (!mfaChallengeToken.trim()) {
      setErrorMessage('MFA session expired. Please sign in again.');
      setMode('credentials');
      return;
    }

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      await loadEnrollmentChallenge(mfaChallengeToken);
      setEnrollmentCode('');
    } catch (error) {
      setErrorMessage(mapAuthError(error, 'mfaEnroll'));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onSubmitMfaVerify() {
    if (isSubmitting) {
      return;
    }

    if (!mfaChallengeToken.trim()) {
      setErrorMessage('MFA session expired. Please sign in again.');
      setMode('credentials');
      return;
    }

    const code = mfaVerifyMethod === 'authenticator' ? mfaCode : '';
    const recoveryCode = mfaVerifyMethod === 'recovery' ? mfaRecoveryCode : '';

    if (!code.trim() && !recoveryCode.trim()) {
      setErrorMessage(
        mfaVerifyMethod === 'authenticator'
          ? 'Enter the authenticator code from your app.'
          : 'Enter one of your recovery codes.'
      );
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
      setErrorMessage(mapAuthError(error, 'mfaVerify'));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function onSubmitMfaEnrollment() {
    if (isSubmitting) {
      return;
    }

    if (!enrollmentSetupToken.trim()) {
      setErrorMessage('MFA setup session expired. Please sign in again.');
      setMode('credentials');
      return;
    }

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
      setErrorMessage(mapAuthError(error, 'mfaEnroll'));
    } finally {
      setIsSubmitting(false);
    }
  }

  function resetMfaFlow() {
    setMode('credentials');
    clearMfaState();
    setPassword('');
    setErrorMessage('');
  }

  function renderCredentialsForm() {
    return (
      <View style={styles.form}>
        <TextInput
          value={email}
          onChangeText={(value) => {
            clearError();
            setEmail(value);
          }}
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
          onChangeText={(value) => {
            clearError();
            setPassword(value);
          }}
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
          <Text style={styles.primaryButtonText}>{isSubmitting ? 'Signing In...' : 'Sign In'}</Text>
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
          Multi-factor verification is required. Choose one method to continue securely.
        </Text>

        <View style={styles.toggleRow}>
          <Pressable
            onPress={() => {
              clearError();
              setMfaVerifyMethod('authenticator');
              setMfaRecoveryCode('');
            }}
            style={[
              styles.toggleButton,
              mfaVerifyMethod === 'authenticator' && styles.toggleButtonActive
            ]}
            accessibilityRole="button"
            accessibilityLabel="Use authenticator code"
          >
            <Text
              style={[
                styles.toggleButtonText,
                mfaVerifyMethod === 'authenticator' && styles.toggleButtonTextActive
              ]}
            >
              Authenticator
            </Text>
          </Pressable>
          <Pressable
            onPress={() => {
              clearError();
              setMfaVerifyMethod('recovery');
              setMfaCode('');
            }}
            style={[styles.toggleButton, mfaVerifyMethod === 'recovery' && styles.toggleButtonActive]}
            accessibilityRole="button"
            accessibilityLabel="Use recovery code"
          >
            <Text
              style={[
                styles.toggleButtonText,
                mfaVerifyMethod === 'recovery' && styles.toggleButtonTextActive
              ]}
            >
              Recovery Code
            </Text>
          </Pressable>
        </View>

        {mfaVerifyMethod === 'authenticator' ? (
          <TextInput
            value={mfaCode}
            onChangeText={(value) => {
              clearError();
              setMfaCode(value);
            }}
            placeholder="Authenticator code"
            accessibilityLabel="Authenticator code"
            placeholderTextColor={appTheme.colors.textSecondary}
            keyboardType="number-pad"
            autoCorrect={false}
            autoCapitalize="none"
            textContentType="oneTimeCode"
            style={styles.input}
          />
        ) : (
          <TextInput
            value={mfaRecoveryCode}
            onChangeText={(value) => {
              clearError();
              setMfaRecoveryCode(value);
            }}
            placeholder="Recovery code"
            accessibilityLabel="Recovery code"
            placeholderTextColor={appTheme.colors.textSecondary}
            autoCapitalize="none"
            autoCorrect={false}
            style={styles.input}
          />
        )}

        <Text style={styles.hintText}>
          {mfaVerifyMethod === 'authenticator'
            ? 'Use the 6-digit code from your authenticator app.'
            : 'Use a saved backup code if your authenticator is unavailable.'}
        </Text>

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
          <Text style={styles.primaryButtonText}>{isSubmitting ? 'Verifying...' : 'Verify And Continue'}</Text>
        </Pressable>

        <Pressable
          onPress={resetMfaFlow}
          disabled={isSubmitting}
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
          Set up your authenticator app with this key, then enter the first generated code.
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
          onChangeText={(value) => {
            clearError();
            setEnrollmentCode(value);
          }}
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
          <Text style={styles.primaryButtonText}>{isSubmitting ? 'Activating...' : 'Activate MFA'}</Text>
        </Pressable>

        <Pressable
          onPress={restartMfaEnrollment}
          disabled={isSubmitting}
          accessibilityRole="button"
          accessibilityLabel="Restart MFA setup"
          style={styles.secondaryButton}
        >
          <Text style={styles.secondaryButtonText}>Restart MFA Setup</Text>
        </Pressable>

        <Pressable
          onPress={resetMfaFlow}
          disabled={isSubmitting}
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
          Save these backup codes in a secure place. Each code can be used once if your authenticator is
          unavailable.
        </Text>

        <View style={styles.backupCodesCard}>
          {backupCodes.map((code) => (
            <Text key={code} style={styles.backupCode} selectable>
              {code}
            </Text>
          ))}
        </View>

        <Text style={styles.hintText}>
          Continue only after you have stored these codes somewhere secure.
        </Text>

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
  hintText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    lineHeight: 20
  },
  toggleRow: {
    flexDirection: 'row',
    gap: appTheme.spacing.sm
  },
  toggleButton: {
    flex: 1,
    borderWidth: 1,
    borderColor: appTheme.colors.border,
    backgroundColor: appTheme.colors.surface,
    borderRadius: appTheme.radius.md,
    paddingVertical: 10,
    alignItems: 'center'
  },
  toggleButtonActive: {
    borderColor: appTheme.colors.primary,
    backgroundColor: '#EFF5FF'
  },
  toggleButtonText: {
    color: appTheme.colors.textSecondary,
    fontSize: appTheme.typography.caption,
    fontWeight: '600'
  },
  toggleButtonTextActive: {
    color: appTheme.colors.primary
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
