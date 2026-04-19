import React from 'react';
import { Redirect } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { useAuthState } from '../src/hooks';
import { appTheme } from '../src/theme';

/**
 * Entry route bootstrap.
 * Resolves persisted auth session before routing to app/auth stacks.
 */
export default function IndexRoute() {
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

  return <Redirect href="/(auth)/sign-in" />;
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: appTheme.colors.background,
    alignItems: 'center',
    justifyContent: 'center'
  }
});
