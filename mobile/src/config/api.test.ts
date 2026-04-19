/// <reference types="jest" />

describe('api config', () => {
  const originalApiBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL;

  beforeEach(() => {
    jest.resetModules();
  });

  afterAll(() => {
    process.env.EXPO_PUBLIC_API_BASE_URL = originalApiBaseUrl;
  });

  it('builds canonical and legacy workspace-access aliases', () => {
    const { workspaceAccessPathAliases } = require('./api') as typeof import('./api');

    expect(workspaceAccessPathAliases('/workspace-access/my-memberships')).toEqual([
      '/workspace-access/my-memberships',
      '/workspace_access/my-memberships',
      '/household-access/my-memberships'
    ]);
  });

  it('normalizes legacy household-access path to canonical alias set', () => {
    const { workspaceAccessPathAliases } = require('./api') as typeof import('./api');

    expect(workspaceAccessPathAliases('/household-access/my-memberships')).toEqual([
      '/workspace-access/my-memberships',
      '/workspace_access/my-memberships',
      '/household-access/my-memberships'
    ]);
  });

  it('falls back to secure default base url when env base url is insecure remote HTTP', () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = 'http://api.tomboflight.com';

    const { API_CONFIG } = require('./api') as typeof import('./api');
    expect(API_CONFIG.baseUrl).toBe('https://api.tomboflight.com');
  });

  it('allows localhost HTTP for local development', () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = 'http://localhost:8000/';

    const { API_CONFIG } = require('./api') as typeof import('./api');
    expect(API_CONFIG.baseUrl).toBe('http://localhost:8000');
  });
});
