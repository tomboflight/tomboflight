import React from 'react';
import { Redirect, Tabs } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { useAuthState } from '../../src/hooks';
import { appTheme } from '../../src/theme';

/**
 * Customer app shell.
 * TODO: Refine navigation IA as features mature.
 */
export default function AppLayout() {
  const authState = useAuthState();

  if (authState.status === 'idle' || authState.status === 'loading') {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={appTheme.colors.primary} />
      </View>
    );
  }

  if (!authState.isAuthenticated) {
    return <Redirect href="/(auth)/sign-in" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: appTheme.colors.surface },
        headerTintColor: appTheme.colors.textPrimary,
        headerShadowVisible: false,
        tabBarActiveTintColor: appTheme.colors.primary,
        tabBarInactiveTintColor: '#7A8AA3',
        tabBarStyle: {
          backgroundColor: appTheme.colors.surface,
          borderTopColor: appTheme.colors.border
        }
      }}
    >
      <Tabs.Screen name="dashboard" options={{ title: 'Dashboard', tabBarLabel: 'Home' }} />
      <Tabs.Screen name="project" options={{ title: 'Project' }} />
      <Tabs.Screen name="family" options={{ title: 'Family' }} />
      <Tabs.Screen name="tree" options={{ title: 'Tree' }} />
      <Tabs.Screen name="uploads" options={{ title: 'Uploads' }} />
      <Tabs.Screen name="certificates" options={{ title: 'Certificates' }} />
      <Tabs.Screen name="billing" options={{ title: 'Billing' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
      <Tabs.Screen name="support" options={{ title: 'Support' }} />
    </Tabs>
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
