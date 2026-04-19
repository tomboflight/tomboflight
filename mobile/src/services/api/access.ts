import { API_ENDPOINTS, workspaceAccessPathAliases } from '../../config';
import { ApiError, apiRequest } from './client';
import { getAccessToken } from '../auth/auth-state';

export type AccessContextPayload = {
  user_id?: string;
  email?: string;
  role?: string;
  status?: string;
  package_lane?: string;
  active_project_id?: string | null;
  active_family_id?: string | null;
  active_entitlements?: string[];
  project_permissions?: string[];
  allowed_experience_modules?: string[];
  experience_mode?: string;
  legal_acceptance?: Record<string, unknown>;
  [key: string]: unknown;
};

export type WorkspaceMembership = {
  id?: string;
  project_id?: string;
  user_id?: string | null;
  email?: string | null;
  full_name?: string | null;
  member_role?: string;
  relationship_scope?: string;
  privacy_scope?: string;
  status?: string;
  joined_at?: string | null;
  created_at?: string | null;
  [key: string]: unknown;
};

export type WorkspaceMembershipsResponse = {
  items: WorkspaceMembership[];
};

function normalizeMembershipsResponse(payload: WorkspaceMembershipsResponse): WorkspaceMembershipsResponse {
  return {
    items: Array.isArray(payload.items) ? payload.items : []
  };
}

export function mapWorkspaceAccessError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Your session expired. Please sign in again.';
    }
    if (error.status === 403) {
      return 'You do not have permission to access this workspace.';
    }
    if (error.status === 404) {
      return 'Workspace access routes are unavailable on this environment.';
    }
    if (error.status === 429) {
      return 'Too many requests. Please wait a moment and try again.';
    }

    const message = String(error.message || '').trim();
    if (message && !message.startsWith('API request failed')) {
      return message;
    }
  }

  if (error instanceof Error) {
    const message = error.message.trim();
    if (message) {
      return message;
    }
  }

  return 'Unable to load workspace data right now.';
}

/**
 * Loads the authenticated user's access context.
 * Mirrors website usage of /users/me/access-context.
 */
export async function fetchAccessContext(token?: string): Promise<AccessContextPayload> {
  return apiRequest<AccessContextPayload>(API_ENDPOINTS.users.accessContext, {
    method: 'GET',
    token: token || getAccessToken() || undefined
  });
}

/**
 * Loads workspace memberships using canonical and legacy aliases.
 * Mirrors website fallback behavior for route compatibility.
 */
export async function fetchMyMemberships(token?: string): Promise<WorkspaceMembershipsResponse> {
  const candidates = workspaceAccessPathAliases(API_ENDPOINTS.workspaceAccess.myMemberships);
  const resolvedToken = token || getAccessToken() || undefined;
  let lastNotFoundError: ApiError | null = null;

  for (const candidatePath of candidates) {
    try {
      const payload = await apiRequest<WorkspaceMembershipsResponse>(candidatePath, {
        method: 'GET',
        token: resolvedToken
      });
      return normalizeMembershipsResponse(payload);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        lastNotFoundError = error;
        continue;
      }
      throw error;
    }
  }

  if (lastNotFoundError) {
    throw lastNotFoundError;
  }

  throw new Error('Workspace membership endpoints are unavailable.');
}
