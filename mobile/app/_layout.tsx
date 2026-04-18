import React from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';

import { appTheme } from '../src/theme';

/**
 * Root navigation shell.
 * TODO: Add launch-time auth/session bootstrap before selecting auth/app groups.
 */
export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: appTheme.colors.surface },
          headerTintColor: appTheme.colors.textPrimary,
          headerShadowVisible: false,
          contentStyle: { backgroundColor: appTheme.colors.background }
        }}
      >
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(app)" options={{ headerShown: false }} />
      </Stack>
    </>
  );
}
