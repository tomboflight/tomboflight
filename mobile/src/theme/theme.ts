/**
 * Tomb of Light mobile design tokens.
 * Direction: premium bright blue, gray, white, clean rich-tech feel.
 */
export const appTheme = {
  colors: {
    primary: '#1157CC',
    primaryPressed: '#0D46A6',
    background: '#EEF3FA',
    surface: '#FFFFFF',
    border: '#CBD7EA',
    textPrimary: '#081733',
    textSecondary: '#44597A',
    success: '#1AAB8B',
    warning: '#D88E12',
    error: '#D64545'
  },
  spacing: {
    xs: 6,
    sm: 10,
    md: 16,
    lg: 24,
    xl: 32
  },
  radius: {
    sm: 10,
    md: 14,
    lg: 20
  },
  typography: {
    title: 28,
    heading: 23,
    body: 16,
    caption: 13
  }
} as const;

export type AppTheme = typeof appTheme;
