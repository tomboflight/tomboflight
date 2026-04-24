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

export type UploadRecordPayload = {
  id?: string;
  project_id?: string;
  family_id?: string;
  member_id?: string;
  category?: string;
  evidence_kind?: string;
  verification_type?: string;
  original_filename?: string;
  content_type?: string;
  size_bytes?: number;
  uploaded_by?: string;
  uploaded_by_user_id?: string;
  vault_scope?: string;
  visibility_scope?: string;
  privacy_scope?: string;
  relationship_scope?: string;
  verification_status?: string;
  consent_status?: string;
  approved_for_cinematic?: boolean;
  customer_visible?: boolean;
  internal_only?: boolean;
  quarantined?: boolean;
  scan_status?: string;
  created_at?: string;
  download_path?: string;
  [key: string]: unknown;
};

export type FamilyUploadsPayload = {
  family_id?: string;
  count?: number;
  uploads?: UploadRecordPayload[];
  [key: string]: unknown;
};

export type CinematicAssetsPayload = {
  family_id?: string;
  count?: number;
  items?: UploadRecordPayload[];
  [key: string]: unknown;
};

export type IssuedCertificateRecordPayload = {
  id?: string;
  record_type?: string;
  certificate_id?: string;
  base_certificate_id?: string;
  family_id?: string;
  family_name?: string;
  status?: string;
  version?: number;
  integrity_hash?: string;
  issued_at?: string;
  issued_by?: string;
  notes?: string;
  is_latest?: boolean;
  created_at?: string;
  updated_at?: string;
  certificate_payload?: Record<string, unknown>;
  [key: string]: unknown;
};

export type IssuedCertificatesListPayload = {
  success?: boolean;
  count?: number;
  issued_certificates: IssuedCertificateRecordPayload[];
};

export type BillingConfigPayload = {
  publishable_key?: string;
  max_cards?: number;
  portal_return_url?: string | null;
  [key: string]: unknown;
};

export type BillingPaymentMethodPayload = {
  id?: string;
  brand?: string | null;
  last4?: string | null;
  exp_month?: number | null;
  exp_year?: number | null;
  funding?: string | null;
  is_default?: boolean;
  created_at?: string | null;
  [key: string]: unknown;
};

export type BillingSubscriptionPayload = {
  id?: string;
  status?: string;
  collection_method?: string | null;
  cancel_at_period_end?: boolean;
  current_period_end?: string | null;
  default_payment_method_id?: string | null;
  product_names?: string[];
  [key: string]: unknown;
};

export type BillingOverviewPayload = {
  customer_id?: string | null;
  chain_label?: string | null;
  max_cards?: number;
  cards_on_file?: number;
  can_add_card?: boolean;
  default_payment_method_id?: string | null;
  payment_methods?: BillingPaymentMethodPayload[];
  subscriptions?: BillingSubscriptionPayload[];
  [key: string]: unknown;
};

export type BillingPortalSessionPayload = {
  url?: string;
  [key: string]: unknown;
};

export type OrderPayload = {
  id?: string;
  user_id?: string;
  email?: string;
  package_code?: string;
  package_slug?: string;
  package_name?: string;
  price_label?: string;
  item_type?: string;
  billing_plan?: string;
  source?: string;
  status?: string;
  project_id?: string | null;
  stripe_session_id?: string | null;
  stripe_payment_link_id?: string | null;
  created_at?: string;
  [key: string]: unknown;
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

function normalizeUploadList(payload: unknown, key: 'uploads' | 'items'): UploadRecordPayload[] {
  if (!payload || typeof payload !== 'object') {
    return [];
  }

  const record = payload as Record<string, unknown>;
  const items = record[key];
  if (!Array.isArray(items)) {
    return [];
  }

  return items.filter((entry) => Boolean(entry && typeof entry === 'object')) as UploadRecordPayload[];
}

function normalizeIssuedCertificates(payload: unknown): IssuedCertificatesListPayload {
  if (Array.isArray(payload)) {
    const items = payload.filter((entry) => Boolean(entry && typeof entry === 'object')) as IssuedCertificateRecordPayload[];
    return {
      success: true,
      count: items.length,
      issued_certificates: items
    };
  }

  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    const issued = record.issued_certificates;
    if (Array.isArray(issued)) {
      const items = issued.filter((entry) => Boolean(entry && typeof entry === 'object')) as IssuedCertificateRecordPayload[];
      return {
        success: typeof record.success === 'boolean' ? record.success : true,
        count: typeof record.count === 'number' ? record.count : items.length,
        issued_certificates: items
      };
    }
  }

  return {
    success: true,
    count: 0,
    issued_certificates: []
  };
}

function normalizeOrders(payload: unknown): OrderPayload[] {
  if (!Array.isArray(payload)) {
    return [];
  }

  return payload.filter((entry) => Boolean(entry && typeof entry === 'object')) as OrderPayload[];
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

export async function fetchFamilyUploads(
  familyId: string,
  args: {
    category?: string;
  } = {},
  token?: string
): Promise<FamilyUploadsPayload> {
  const normalizedFamilyId = String(familyId || '').trim();
  if (!normalizedFamilyId) {
    throw new Error('Family id is required to load uploads.');
  }

  const params = new URLSearchParams();
  const category = String(args.category || '').trim();
  if (category) {
    params.set('category', category);
  }

  const basePath = API_ENDPOINTS.uploads.byFamily(normalizedFamilyId);
  const path = params.toString() ? `${basePath}?${params.toString()}` : basePath;
  const payload = await apiRequest<unknown>(path, {
    method: 'GET',
    token: withAuthToken(token)
  });

  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    return {
      ...record,
      family_id: String(record.family_id || '').trim(),
      count: typeof record.count === 'number' ? record.count : 0,
      uploads: normalizeUploadList(record, 'uploads')
    };
  }

  return {
    family_id: normalizedFamilyId,
    count: 0,
    uploads: []
  };
}

export async function fetchCinematicAssets(
  familyId: string,
  token?: string
): Promise<CinematicAssetsPayload> {
  const normalizedFamilyId = String(familyId || '').trim();
  if (!normalizedFamilyId) {
    throw new Error('Family id is required to load cinematic assets.');
  }

  const payload = await apiRequest<unknown>(API_ENDPOINTS.uploads.cinematicByFamily(normalizedFamilyId), {
    method: 'GET',
    token: withAuthToken(token)
  });

  if (payload && typeof payload === 'object') {
    const record = payload as Record<string, unknown>;
    const items = Array.isArray(record.items)
      ? (record.items.filter((entry) => Boolean(entry && typeof entry === 'object')) as UploadRecordPayload[])
      : [];

    return {
      ...record,
      family_id: String(record.family_id || '').trim(),
      count: typeof record.count === 'number' ? record.count : items.length,
      items
    };
  }

  return {
    family_id: normalizedFamilyId,
    count: 0,
    items: []
  };
}

export async function fetchIssuedCertificates(
  args: {
    limit?: number;
  } = {},
  token?: string
): Promise<IssuedCertificatesListPayload> {
  const params = new URLSearchParams();
  if (typeof args.limit === 'number' && Number.isFinite(args.limit)) {
    params.set('limit', String(Math.max(1, Math.min(200, Math.floor(args.limit)))));
  }

  const path = params.toString() ? `${API_ENDPOINTS.issuedCertificates.list}?${params.toString()}` : API_ENDPOINTS.issuedCertificates.list;
  const payload = await apiRequest<unknown>(path, {
    method: 'GET',
    token: withAuthToken(token)
  });

  return normalizeIssuedCertificates(payload);
}

export async function fetchBillingConfig(token?: string): Promise<BillingConfigPayload> {
  return apiRequest<BillingConfigPayload>(API_ENDPOINTS.billing.config, {
    method: 'GET',
    token: withAuthToken(token)
  });
}

export async function fetchBillingOverview(token?: string): Promise<BillingOverviewPayload> {
  return apiRequest<BillingOverviewPayload>(API_ENDPOINTS.billing.overview, {
    method: 'GET',
    token: withAuthToken(token)
  });
}

export async function createBillingPortalSession(
  args: {
    returnUrl?: string;
  } = {},
  token?: string
): Promise<BillingPortalSessionPayload> {
  const returnUrl = String(args.returnUrl || '').trim();
  const body = returnUrl ? { return_url: returnUrl } : undefined;

  return apiRequest<BillingPortalSessionPayload>(API_ENDPOINTS.billing.portalSession, {
    method: 'POST',
    token: withAuthToken(token),
    body
  });
}

export async function fetchMyOrders(token?: string): Promise<OrderPayload[]> {
  const payload = await apiRequest<unknown>(API_ENDPOINTS.orders.myOrders, {
    method: 'GET',
    token: withAuthToken(token)
  });

  return normalizeOrders(payload);
}
