/**
 * Tomb of Light mobile design tokens.
 * Direction: premium bright blue, gray, white, clean rich-tech feel.
 */
export const appTheme = {
  colors: {
    primary: '#2F64D6',
    primaryPressed: '#244FAF',
    background: '#F3F6FB',
    surface: '#FFFFFF',
    border: '#D7E2F0',
    textPrimary: '#081733',
    textSecondary: '#526684',
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
    md: 16,
    lg: 24
  },
  typography: {
    title: 28,
    heading: 23,
    body: 16,
    caption: 13
  }
} as const;

export type AppTheme = typeof appTheme;
