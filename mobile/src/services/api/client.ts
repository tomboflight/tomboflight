import { API_CONFIG } from '../../config';

export type ApiRequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  token?: string;
  body?: unknown;
  headers?: Record<string, string>;
};

/**
 * Minimal API client starter.
 * TODO: map backend errors to typed mobile errors.
 */
export async function apiRequest<TResponse>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<TResponse> {
  const url = buildUrl(path);
  const controller = new AbortController();
  const timeoutHandle = setTimeout(() => controller.abort(), API_CONFIG.timeoutMs);
  const headers: Record<string, string> = {
    ...options.headers
  };

  if (options.body !== undefined) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json';
  }

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      signal: controller.signal,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined
    });

    if (!response.ok) {
      throw new Error(`API request failed (${response.status}).`);
    }

    if (response.status === 204) {
      return undefined as TResponse;
    }

    return (await response.json()) as TResponse;
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('API request timed out.');
    }
    throw error;
  } finally {
    clearTimeout(timeoutHandle);
  }
}

function buildUrl(path: string): string {
  const base = API_CONFIG.baseUrl.replace(/\/+$/, '');
  const normalizedPath = path.replace(/^\/+/, '');
  return `${base}/${normalizedPath}`;
}
