import Constants from 'expo-constants';

const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
const extraBaseUrl = Constants.expoConfig?.extra?.apiBaseUrl;
const defaultBaseUrl = 'https://api.tomboflight.com';

function resolveApiBaseUrl(): string {
  const candidate = String(envBaseUrl || extraBaseUrl || defaultBaseUrl)
    .trim()
    .replace(/\/+$/, '');

  try {
    const parsed = new URL(candidate);
    const localHosts = new Set(['localhost', '127.0.0.1']);
    const isLocal = localHosts.has(parsed.hostname);
    const isSecure = parsed.protocol === 'https:';

    // Only allow plaintext HTTP for explicit local development hosts.
    if (!isSecure && !isLocal) {
      return defaultBaseUrl;
    }

    return candidate;
  } catch {
    return defaultBaseUrl;
  }
}

/**
 * Shared API config.
 * TODO: wire this to FastAPI environment-specific values.
 */
export const API_CONFIG = {
  baseUrl: resolveApiBaseUrl(),
  timeoutMs: 15000
} as const;
