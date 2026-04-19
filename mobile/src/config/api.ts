import Constants from 'expo-constants';

const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
const extraBaseUrl = Constants.expoConfig?.extra?.apiBaseUrl;
const defaultBaseUrl = 'https://api.tomboflight.com';
const WORKSPACE_ACCESS_CANONICAL_PREFIX = '/workspace-access';
const WORKSPACE_ACCESS_PREFIX_ALIASES = [
  '/workspace-access',
  '/workspace_access',
  '/household-access'
] as const;

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

/**
 * Shared backend route map for the mobile app.
 * Keep these aligned with FastAPI route declarations and web app usage.
 */
export const API_ENDPOINTS = {
  auth: {
    signIn: '/auth/login',
    signUp: '/auth/signup',
    logout: '/auth/logout',
    csrfToken: '/auth/csrf-token',
    passwordResetRequest: '/auth/password-reset/request',
    passwordResetConfirm: '/auth/password-reset/confirm'
  },
  users: {
    accessContext: '/users/me/access-context',
    profile: '/users/me/profile'
  },
  workspaceAccess: {
    myMemberships: '/workspace-access/my-memberships'
  }
} as const;

/**
 * Produces canonical + legacy workspace access paths for backward compatibility.
 * TODO: Remove legacy aliases when backend/web have fully standardized on canonical routes.
 */
export function workspaceAccessPathAliases(path: string): string[] {
  const normalized = `/${path.replace(/^\/+/, '')}`;
  const canonical = normalized
    .replace(/^\/workspace_access\//, `${WORKSPACE_ACCESS_CANONICAL_PREFIX}/`)
    .replace(/^\/household-access\//, `${WORKSPACE_ACCESS_CANONICAL_PREFIX}/`);

  if (!canonical.startsWith(`${WORKSPACE_ACCESS_CANONICAL_PREFIX}/`)) {
    return [normalized];
  }

  return WORKSPACE_ACCESS_PREFIX_ALIASES.map((prefix) =>
    canonical.replace(WORKSPACE_ACCESS_CANONICAL_PREFIX, prefix)
  );
}
