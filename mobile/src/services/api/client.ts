import { API_CONFIG } from '../../config';

export type ApiRequestOptions = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  token?: string;
  body?: unknown;
  headers?: Record<string, string>;
  credentials?: RequestCredentials;
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

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
  const body = prepareBody(options.body, headers);

  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }

  try {
    const response = await fetch(url, {
      method: options.method ?? 'GET',
      headers,
      credentials: options.credentials ?? 'include',
      signal: controller.signal,
      body
    });

    if (!response.ok) {
      throw await toApiError(response);
    }

    if (response.status === 204 || response.status === 205 || response.headers.get('content-length') === '0') {
      return undefined as TResponse;
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.toLowerCase().includes('application/json')) {
      return (await response.json()) as TResponse;
    }

    if (contentType.toLowerCase().startsWith('text/')) {
      return (await response.text()) as TResponse;
    }

    return undefined as TResponse;
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

function hasHeader(headers: Record<string, string>, name: string): boolean {
  const lowerName = name.toLowerCase();
  return Object.keys(headers).some((key) => key.toLowerCase() === lowerName);
}

function prepareBody(body: unknown, headers: Record<string, string>): BodyInit | undefined {
  if (body === undefined || body === null) {
    return undefined;
  }

  if (
    typeof body === 'string' ||
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body)
  ) {
    return body as BodyInit;
  }

  if (!hasHeader(headers, 'Content-Type')) {
    headers['Content-Type'] = 'application/json';
  }

  return JSON.stringify(body);
}

async function toApiError(response: Response): Promise<ApiError> {
  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  let detail: unknown;
  let message = `API request failed (${response.status}).`;

  try {
    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as {
        detail?: unknown;
        message?: unknown;
      };
      detail = payload.detail ?? payload.message ?? payload;

      if (typeof payload.detail === 'string' && payload.detail.trim()) {
        message = payload.detail;
      } else if (typeof payload.message === 'string' && payload.message.trim()) {
        message = payload.message;
      }
    } else {
      const rawText = (await response.text()).trim();
      if (rawText) {
        detail = rawText;
        message = rawText;
      }
    }
  } catch {
    // Keep fallback message when response body cannot be parsed.
  }

  return new ApiError(response.status, message, detail);
}
