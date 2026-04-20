/// <reference types="jest" />

type MockResponse = {
  ok: boolean;
  status: number;
  headers: { get: (key: string) => string | null };
  json: () => Promise<unknown>;
  text: () => Promise<string>;
};

function createJsonResponse(status: number, payload: Record<string, unknown>): MockResponse {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {
      get: (key: string) => {
        if (key.toLowerCase() === 'content-type') {
          return 'application/json';
        }
        return null;
      }
    },
    json: async () => payload,
    text: async () => JSON.stringify(payload)
  };
}

describe('api client', () => {
  const originalFetch = global.fetch;
  const originalApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;
  const originalWindow = (global as unknown as { window?: unknown }).window;

  beforeEach(() => {
    jest.resetModules();
    jest.clearAllMocks();
    process.env.EXPO_PUBLIC_API_BASE_URL = 'https://tomboflight-api.onrender.com';
    global.fetch = jest.fn() as unknown as typeof fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
    process.env.EXPO_PUBLIC_API_BASE_URL = originalApiBaseUrl;
    (global as unknown as { window?: unknown }).window = originalWindow;
  });

  it('forms the expected login URL and uses same-origin credentials by default', async () => {
    const apiClient = require('./client') as typeof import('./client');
    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockResolvedValueOnce(createJsonResponse(200, { access_token: 'abc' }));

    await apiClient.apiRequest('/auth/login', {
      method: 'POST',
      body: { email: 'customer@example.com', password: 'secret' }
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toBe('https://tomboflight-api.onrender.com/auth/login');

    const requestOptions = fetchMock.mock.calls[0][1] as {
      credentials?: RequestCredentials;
      headers?: Record<string, string>;
    };
    expect(requestOptions.credentials).toBe('same-origin');
    expect(requestOptions.headers?.['Content-Type']).toBe('application/json');
  });

  it('classifies browser TypeError on cross-origin URL as likely CORS/network issue', async () => {
    const apiClient = require('./client') as typeof import('./client');
    const fetchMock = global.fetch as unknown as jest.Mock;
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    (global as unknown as { window?: { location: { origin: string } } }).window = {
      location: {
        origin: 'http://localhost:8081'
      }
    };

    await expect(
      apiClient.apiRequest('/auth/login', {
        method: 'POST',
        body: { email: 'customer@example.com', password: 'secret' }
      })
    ).rejects.toMatchObject({
      name: 'ApiConnectivityError',
      issue: 'network',
      likelyCors: true
    });
  });

  it('classifies AbortError as timeout connectivity issue', async () => {
    const apiClient = require('./client') as typeof import('./client');
    const fetchMock = global.fetch as unknown as jest.Mock;
    const abortError = new Error('Aborted');
    abortError.name = 'AbortError';
    fetchMock.mockRejectedValueOnce(abortError);

    await expect(apiClient.apiRequest('/auth/login', { method: 'POST' })).rejects.toMatchObject({
      name: 'ApiConnectivityError',
      issue: 'timeout'
    });
  });
});
