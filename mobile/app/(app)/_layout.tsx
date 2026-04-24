import React from 'react';
import { Redirect, Tabs } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuthState } from '../../src/hooks';
import { appTheme } from '../../src/theme';

/**
 * Customer app shell with focused primary navigation.
 */
export default function AppLayout() {
  const authState = useAuthState();
  const insets = useSafeAreaInsets();

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
        tabBarLabelStyle: {
          fontSize: 12,
          fontWeight: '600'
        },
        tabBarHideOnKeyboard: true,
        tabBarItemStyle: {
          paddingVertical: 2
        },
        tabBarStyle: {
          backgroundColor: appTheme.colors.surface,
          borderTopColor: appTheme.colors.border,
          height: 56 + insets.bottom,
          paddingBottom: Math.max(insets.bottom, 8),
          paddingTop: 8
        }
      }}
    >
      <Tabs.Screen name="dashboard" options={{ title: 'Dashboard', tabBarLabel: 'Home' }} />
      <Tabs.Screen name="project" options={{ title: 'Project' }} />
      <Tabs.Screen name="family" options={{ title: 'Family' }} />
      <Tabs.Screen name="tree" options={{ title: 'Tree' }} />
      <Tabs.Screen name="settings" options={{ title: 'Settings' }} />
      <Tabs.Screen name="uploads" options={{ title: 'Uploads', href: null }} />
      <Tabs.Screen name="certificates" options={{ title: 'Certificates', href: null }} />
      <Tabs.Screen name="billing" options={{ title: 'Billing', href: null }} />
      <Tabs.Screen name="support" options={{ title: 'Support', href: null }} />
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
