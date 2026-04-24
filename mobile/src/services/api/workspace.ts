import { API_ENDPOINTS, workspaceAccessPathAliases } from '../../config';
import { getAccessToken } from '../auth/auth-state';
import { ApiError, apiRequest } from './client';
import { WorkspaceMembership } from './access';

export type UserProfilePayload = {
  id?: string;
  email?: string;
  full_name?: string;
  role?: string;
  status?: string;
  created_at?: string;
  last_login_at?: string | null;
  policy_version?: string | null;
  legal_acceptance?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ProjectPayload = {
  id?: string;
  name?: string;
  project_lane?: string;
  owner_user_id?: string;
  owner_email?: string;
  package_code?: string;
  package_name?: string;
  status?: string;
  phase?: string;
  source?: string;
  family_id?: string | null;
  household_id?: string | null;
  organization_id?: string | null;
  intake_submission_id?: string | null;
  created_at?: string;
  updated_at?: string | null;
  [key: string]: unknown;
};

export type ProjectsResponse = {
  items: ProjectPayload[];
};

export type ProjectEntitlementPayload = {
  id?: string;
  project_id?: string;
  user_id?: string;
  package_code?: string;
  package_name?: string;
  package_lane?: string;
  status?: string;
  active_addons?: string[];
  maintenance_plan?: string;
  maintenance_status?: string;
  resolved_entitlements?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
};

export type ProjectExperienceLanePayload = {
  project_id?: string;
  project_lane?: string;
  package_code?: string;
  package_name?: string;
  experience_mode?: string;
  allowed_chambers?: string[];
  unlocked_modules?: string[];
  [key: string]: unknown;
};

export type ViewerManifestState = {
  id?: string;
  title?: string;
  status?: string;
  image?: string;
  description?: string;
  [key: string]: unknown;
};

export type ViewerManifestPayload = {
  mode?: string;
  navigation_mode?: string;
  hero_title?: string;
  hero_body?: string;
  workspace_name?: string;
  path_title?: string;
  path_items?: string[];
  controls?: Record<string, unknown>;
  states?: ViewerManifestState[];
  initial_state_id?: string;
  has_uploaded_portraits?: boolean;
  project?: Record<string, unknown> | null;
  family?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type FamilyTreePayload = {
  family_id?: string;
  mode?: string;
  family?: Record<string, unknown> | null;
  members?: Record<string, unknown>[];
  nodes?: Record<string, unknown>[];
  relationships?: Record<string, unknown>[];
  edges?: Record<string, unknown>[];
  linked_family_ids?: string[];
  tree_model?: Record<string, unknown>;
  [key: string]: unknown;
};

export type ProjectMembersResponse = {
  items: WorkspaceMembership[];
};

function withAuthToken(token?: string): string | undefined {
  return token || getAccessToken() || undefined;
}

function normalizeProjectList(payload: unknown): ProjectsResponse {
  if (Array.isArray(payload)) {
    return {
      items: payload.filter((entry) => Boolean(entry && typeof entry === 'object')) as ProjectPayload[]
    };
  }

  if (payload && typeof payload === 'object') {
    const record = payload as { items?: unknown };
    if (Array.isArray(record.items)) {
      return {
        items: record.items.filter((entry) => Boolean(entry && typeof entry === 'object')) as ProjectPayload[]
      };
    }
  }

  return { items: [] };
}

function normalizeMemberships(payload: unknown): ProjectMembersResponse {
  if (payload && typeof payload === 'object') {
    const record = payload as { items?: unknown };
    if (Array.isArray(record.items)) {
      return {
        items: record.items.filter((entry) => Boolean(entry && typeof entry === 'object')) as WorkspaceMembership[]
      };
    }
  }

  return { items: [] };
}

export function mapWorkspaceDataError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400) {
      return 'Requested workspace data is invalid for the current context.';
    }

    if (error.status === 401) {
      return 'Your session expired. Please sign in again.';
    }

    if (error.status === 403) {
      return 'Your package access level does not allow this data in mobile yet.';
    }

    if (error.status === 404) {
      return 'No workspace record was found for this account context.';
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

  return 'Unable to load mobile workspace data right now.';
}

export async function fetchMyProfile(token?: string): Promise<UserProfilePayload> {
  return apiRequest<UserProfilePayload>(API_ENDPOINTS.users.profile, {
    method: 'GET',
    token: withAuthToken(token)
  });
}

export async function fetchProjects(token?: string): Promise<ProjectsResponse> {
  const payload = await apiRequest<unknown>(API_ENDPOINTS.projects.list, {
    method: 'GET',
    token: withAuthToken(token)
  });

  return normalizeProjectList(payload);
}

export async function fetchProjectEntitlement(
  projectId: string,
  token?: string
): Promise<ProjectEntitlementPayload> {
  const normalizedProjectId = String(projectId || '').trim();
  if (!normalizedProjectId) {
    throw new Error('Project id is required to load entitlements.');
  }

  return apiRequest<ProjectEntitlementPayload>(
    API_ENDPOINTS.projectEntitlements.byProject(normalizedProjectId),
    {
      method: 'GET',
      token: withAuthToken(token)
    }
  );
}

export async function fetchProjectExperienceLane(
  projectId: string,
  token?: string
): Promise<ProjectExperienceLanePayload> {
  const normalizedProjectId = String(projectId || '').trim();
  if (!normalizedProjectId) {
    throw new Error('Project id is required to load experience lane data.');
  }

  return apiRequest<ProjectExperienceLanePayload>(API_ENDPOINTS.projects.experienceLane(normalizedProjectId), {
    method: 'GET',
    token: withAuthToken(token)
  });
}

export async function fetchProjectMembers(
  projectId: string,
  token?: string
): Promise<ProjectMembersResponse> {
  const normalizedProjectId = String(projectId || '').trim();
  if (!normalizedProjectId) {
    throw new Error('Project id is required to load household members.');
  }

  const resolvedToken = withAuthToken(token);
  const routeCandidates = workspaceAccessPathAliases(
    API_ENDPOINTS.workspaceAccess.projectMembers(normalizedProjectId)
  );
  let lastNotFoundError: ApiError | null = null;

  for (const routePath of routeCandidates) {
    try {
      const payload = await apiRequest<unknown>(routePath, {
        method: 'GET',
        token: resolvedToken
      });
      return normalizeMemberships(payload);
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

  return { items: [] };
}

export async function fetchFamilyTree(
  familyId: string,
  token?: string
): Promise<FamilyTreePayload> {
  const normalizedFamilyId = String(familyId || '').trim();
  if (!normalizedFamilyId) {
    throw new Error('Family id is required to load tree data.');
  }

  return apiRequest<FamilyTreePayload>(API_ENDPOINTS.tree.byFamily(normalizedFamilyId), {
    method: 'GET',
    token: withAuthToken(token)
  });
}

export async function fetchViewerManifest(
  args: {
    projectId?: string;
    familyId?: string;
  },
  token?: string
): Promise<ViewerManifestPayload> {
  const params = new URLSearchParams();

  const projectId = String(args.projectId || '').trim();
  const familyId = String(args.familyId || '').trim();

  if (projectId) {
    params.set('project_id', projectId);
  }

  if (familyId) {
    params.set('family_id', familyId);
  }

  const query = params.toString();
  const path = query ? `${API_ENDPOINTS.viewer.manifest}?${query}` : API_ENDPOINTS.viewer.manifest;

  return apiRequest<ViewerManifestPayload>(path, {
    method: 'GET',
    token: withAuthToken(token)
  });
}
