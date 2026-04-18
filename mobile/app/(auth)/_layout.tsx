import React from 'react';
import { Stack } from 'expo-router';

import { appTheme } from '../../src/theme';

/**
 * Auth stack for sign-in/sign-up/recovery routes.
 */
export default function AuthLayout() {
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
      <Stack.Screen
        name="forgot-password"
        options={{ title: 'Reset Password' }}
      />
    </Stack>
  );
}
