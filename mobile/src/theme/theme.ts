/**
 * Tomb of Light mobile MVP design tokens.
 * Visual direction: premium bright blue, gray, white, clean rich-tech feel.
 */
export const appTheme = {
  colors: {
    primary: '#1677FF',
    primaryPressed: '#0E63D9',
    background: '#F5F8FC',
    surface: '#FFFFFF',
    border: '#D8E1EE',
    textPrimary: '#0B1B35',
    textSecondary: '#4E617E',
    success: '#1AAB8B',
    warning: '#E7A530',
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
    heading: 22,
    body: 16,
    caption: 13
  }
} as const;

export type AppTheme = typeof appTheme;
