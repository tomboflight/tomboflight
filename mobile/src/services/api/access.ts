import { API_ENDPOINTS, workspaceAccessPathAliases } from '../../config';
import { ApiError, apiRequest } from './client';
import { getAccessToken } from '../auth/auth-state';

export type AccessContextPayload = Record<string, unknown>;

export type WorkspaceMembership = {
  id?: string;
  project_id?: string;
  member_role?: string;
  relationship_scope?: string;
  [key: string]: unknown;
};

export type WorkspaceMembershipsResponse = {
  items: WorkspaceMembership[];
};

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
      return await apiRequest<WorkspaceMembershipsResponse>(candidatePath, {
        method: 'GET',
        token: resolvedToken
      });
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
