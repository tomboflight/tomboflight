import { useColorScheme } from 'react-native';

import { appTheme } from '../theme';

/**
 * Starter hook for future light/dark theme expansion.
 */
export function useAppTheme() {
  const colorScheme = useColorScheme();

  return {
    theme: appTheme,
    colorScheme: colorScheme ?? 'light'
  };
}
