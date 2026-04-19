import React from 'react';
import { Redirect } from 'expo-router';

/**
 * Entry route for MVP.
 * TODO: Replace with auth/session-driven routing.
 */
export default function IndexRoute() {
  return <Redirect href="/(auth)/sign-in" />;
}
