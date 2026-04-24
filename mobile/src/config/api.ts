const envBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
const extraBaseUrl = getExpoExtraBaseUrl();
const defaultBaseUrl = 'https://tomboflight-api.onrender.com';
const WORKSPACE_ACCESS_CANONICAL_PREFIX = '/workspace-access';
const WORKSPACE_ACCESS_PREFIX_ALIASES = [
  '/workspace-access',
  '/workspace_access',
  '/household-access'
] as const;

function isPrivateNetworkHost(hostname: string): boolean {
  const normalized = hostname.trim().toLowerCase();

  if (!normalized) {
    return false;
  }

  if (normalized === 'localhost' || normalized === '127.0.0.1' || normalized === '::1') {
    return true;
  }

  if (normalized.endsWith('.local')) {
    return true;
  }

  if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(normalized)) {
    return true;
  }

  if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(normalized)) {
    return true;
  }

  if (/^172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}$/.test(normalized)) {
    return true;
  }

  return false;
}

function getExpoExtraBaseUrl(): string | undefined {
  try {
    const constants = require('expo-constants') as {
      expoConfig?: {
        extra?: {
          apiBaseUrl?: string;
        };
      };
    };
    return constants?.expoConfig?.extra?.apiBaseUrl;
  } catch {
    return undefined;
  }
}

function resolveApiBaseUrl(): string {
  const candidate = String(envBaseUrl || extraBaseUrl || defaultBaseUrl)
    .trim()
    .replace(/\/+$/, '');

  try {
    const parsed = new URL(candidate);
    const isSecure = parsed.protocol === 'https:';
    const isLocalNetwork = isPrivateNetworkHost(parsed.hostname);

    // Allow plaintext HTTP only for local + private network development hosts.
    if (!isSecure && !isLocalNetwork) {
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
    mfaEnrollBegin: '/auth/mfa/enroll/begin',
    mfaEnrollVerify: '/auth/mfa/enroll/verify',
    mfaLoginVerify: '/auth/mfa/login/verify',
    passwordResetRequest: '/auth/password-reset/request',
    passwordResetConfirm: '/auth/password-reset/confirm'
  },
  users: {
    accessContext: '/users/me/access-context',
    profile: '/users/me/profile'
  },
  workspaceAccess: {
    myMemberships: '/workspace-access/my-memberships',
    projectMembers: (projectId: string) =>
      `/workspace-access/project/${encodeURIComponent(projectId)}/members`
  },
  projects: {
    list: '/projects',
    experienceLane: (projectId: string) =>
      `/projects/${encodeURIComponent(projectId)}/experience-lane`
  },
  projectEntitlements: {
    byProject: (projectId: string) =>
      `/project-entitlements/project/${encodeURIComponent(projectId)}`
  },
  uploads: {
    byFamily: (familyId: string) => `/uploads/family/${encodeURIComponent(familyId)}`,
    cinematicByFamily: (familyId: string) => `/uploads/cinematic/family/${encodeURIComponent(familyId)}`
  },
  issuedCertificates: {
    list: '/issued-certificates'
  },
  billing: {
    config: '/billing/config',
    overview: '/billing/overview',
    portalSession: '/billing/portal-session'
  },
  orders: {
    myOrders: '/orders/my-orders'
  },
  tree: {
    byFamily: (familyId: string) => `/tree/${encodeURIComponent(familyId)}`
  },
  viewer: {
    manifest: '/viewer/manifest'
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
