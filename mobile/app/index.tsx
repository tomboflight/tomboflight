import React from 'react';
import { Redirect } from 'expo-router';

/**
 * Entry route.
 * TODO: Replace with startup logic that checks secure session and user profile state.
 */
export default function IndexRoute() {
  return <Redirect href="/(auth)/sign-in" />;
}
