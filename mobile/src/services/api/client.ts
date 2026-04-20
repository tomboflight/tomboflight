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

export type ApiConnectivityIssue = 'network' | 'timeout';

export class ApiConnectivityError extends Error {
  readonly issue: ApiConnectivityIssue;
  readonly url: string;
  readonly method: string;
  readonly likelyCors: boolean;

  constructor(args: {
    issue: ApiConnectivityIssue;
    message: string;
    url: string;
    method: string;
    likelyCors?: boolean;
  }) {
    super(args.message);
    this.name = 'ApiConnectivityError';
    this.issue = args.issue;
    this.url = args.url;
    this.method = args.method;
    this.likelyCors = Boolean(args.likelyCors);
  }
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function extractDetailMessage(detail: unknown): string {
  if (!detail) {
    return '';
  }

  if (typeof detail === 'string') {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => extractDetailMessage(item))
      .filter((value) => value.length > 0);
    return messages.join(' ').trim();
  }

  if (typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    const preferredKeys = ['detail', 'message', 'msg', 'error'];
    for (const key of preferredKeys) {
      const message = extractDetailMessage(record[key]);
      if (message) {
        return message;
      }
    }
  }

  return '';
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
  const method = options.method ?? 'GET';
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
      method,
      headers,
      credentials: options.credentials ?? 'same-origin',
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
      throw new ApiConnectivityError({
        issue: 'timeout',
        message: 'The request timed out before Tomb of Light services responded.',
        url,
        method
      });
    }
    if (error instanceof TypeError) {
      throw toNetworkError(url, method);
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
      message =
        extractDetailMessage(payload.detail) ||
        extractDetailMessage(payload.message) ||
        extractDetailMessage(payload) ||
        message;
    } else {
      const rawText = asString(await response.text());
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

function toNetworkError(url: string, method: string): ApiConnectivityError {
  const likelyCors = isLikelyCorsMismatch(url);

  return new ApiConnectivityError({
    issue: 'network',
    message: likelyCors
      ? 'Unable to reach Tomb of Light services from this web app origin. API CORS may be blocking this request.'
      : 'Unable to reach Tomb of Light services. Check your network connection and try again.',
    url,
    method,
    likelyCors
  });
}

function isLikelyCorsMismatch(url: string): boolean {
  if (typeof window === 'undefined' || !window.location) {
    return false;
  }

  try {
    const requestOrigin = new URL(url).origin;
    return requestOrigin !== window.location.origin;
  } catch {
    return false;
  }
}
