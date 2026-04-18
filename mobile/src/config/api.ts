import Constants from 'expo-constants';

const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
const extraBaseUrl = Constants.expoConfig?.extra?.apiBaseUrl;

/**
 * Central API config for future FastAPI integration.
 */
export const API_CONFIG = {
  baseUrl:
    envBaseUrl ||
    (typeof extraBaseUrl === 'string' ? extraBaseUrl : 'http://localhost:8000'),
  timeoutMs: 15000
} as const;

// TODO: Replace notes with real endpoint contract details when FastAPI mobile API specs are finalized.
export const API_TODO = {
  integration: 'Connect mobile network services to existing FastAPI backend.'
} as const;
