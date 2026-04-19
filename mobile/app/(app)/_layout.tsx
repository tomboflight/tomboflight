import React from 'react';
import { Tabs } from 'expo-router';

import { appTheme } from '../../src/theme';

/**
 * Customer app shell.
 * TODO: Refine navigation IA as features mature.
 */
export default function AppLayout() {
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
