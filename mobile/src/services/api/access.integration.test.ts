/// <reference types="jest" />

type JsonRecord = Record<string, unknown>;

type MockResponse = {
  ok: boolean;
  status: number;
  headers: { get: (key: string) => string | null };
  json: () => Promise<unknown>;
  text: () => Promise<string>;
};

function createJsonResponse(status: number, payload: JsonRecord): MockResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key: string) => {
        const normalized = key.toLowerCase();
        if (normalized === 'content-type') {
          return 'application/json';
        }
        return null;
      }
    },
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  };
}

describe('workspace access integration', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    global.fetch = jest.fn() as unknown as typeof fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it('falls back to legacy membership route aliases after canonical 404', async () => {
    const authState = require('../auth/auth-state') as typeof import('../auth/auth-state');
    const accessService = require('./access') as typeof import('./access');

    await authState.saveAccessToken('session-token-1');

    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValueOnce(createJsonResponse(404, { detail: 'Not Found' }));
    fetchMock.mockResolvedValueOnce(
      createJsonResponse(200, {
        items: [
          {
            id: 'membership-1',
            project_id: 'project-1',
            member_role: 'co_owner',
            relationship_scope: 'household_member',
            privacy_scope: 'household_private',
            status: 'active'
          }
        ]
      })
    );

    const response = await accessService.fetchMyMemberships();

    expect(response.items).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);

    const firstUrl = String(fetchMock.mock.calls[0][0]);
    const secondUrl = String(fetchMock.mock.calls[1][0]);
    expect(firstUrl).toContain('/workspace-access/my-memberships');
    expect(secondUrl).toContain('/workspace_access/my-memberships');

    const secondRequestOptions = fetchMock.mock.calls[1][1] as {
      headers?: Record<string, string>;
    };
    expect(secondRequestOptions.headers?.Authorization).toBe('Bearer session-token-1');
  });

  it('returns mapped error when all membership aliases return 404', async () => {
    const accessService = require('./access') as typeof import('./access');

    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValue(createJsonResponse(404, { detail: 'Not Found' }));

    await expect(accessService.fetchMyMemberships()).rejects.toMatchObject({ status: 404 });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    const lastUrl = String(fetchMock.mock.calls[2][0]);
    expect(lastUrl).toContain('/household-access/my-memberships');
  });

  it('reads access-context with bearer token from auth state', async () => {
    const authState = require('../auth/auth-state') as typeof import('../auth/auth-state');
    const accessService = require('./access') as typeof import('./access');

    await authState.saveAccessToken('session-token-2');

    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValueOnce(
      createJsonResponse(200, {
        user_id: 'user-1',
        email: 'customer@example.com',
        role: 'user',
        package_lane: 'portrait',
        experience_mode: 'guided'
      })
    );

    const context = await accessService.fetchAccessContext();

    expect(context.email).toBe('customer@example.com');

    const requestOptions = fetchMock.mock.calls[0][1] as {
      headers?: Record<string, string>;
    };
    expect(requestOptions.headers?.Authorization).toBe('Bearer session-token-2');
  });
});
