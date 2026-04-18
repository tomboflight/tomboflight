import Constants from 'expo-constants';

const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
const extraBaseUrl = Constants.expoConfig?.extra?.apiBaseUrl;

/**
 * Shared API config.
 * TODO: wire this to FastAPI environment-specific values.
 */
export const API_CONFIG = {
  baseUrl:
    envBaseUrl ||
    (typeof extraBaseUrl === 'string' ? extraBaseUrl : 'http://localhost:8000'),
  timeoutMs: 15000
} as const;
