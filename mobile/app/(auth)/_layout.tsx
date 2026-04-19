import React from 'react';
import { Redirect, Stack } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { useAuthState } from '../../src/hooks';
import { appTheme } from '../../src/theme';

/**
 * Auth stack for onboarding and sign-in flows.
 */
export default function AuthLayout() {
  const authState = useAuthState();

  if (authState.status === 'idle' || authState.status === 'loading') {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={appTheme.colors.primary} />
      </View>
    );
  }

  if (authState.isAuthenticated) {
    return <Redirect href="/(app)/dashboard" />;
  }

  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: appTheme.colors.surface },
        headerTintColor: appTheme.colors.textPrimary,
        contentStyle: { backgroundColor: appTheme.colors.background }
      }}
    >
      <Stack.Screen name="sign-in" options={{ title: 'Sign In' }} />
      <Stack.Screen name="sign-up" options={{ title: 'Create Account' }} />
      <Stack.Screen name="forgot-password" options={{ title: 'Reset Password' }} />
    </Stack>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: appTheme.colors.background,
    alignItems: 'center',
    justifyContent: 'center'
  }
});
