import { API_ENDPOINTS } from '../../config';
import { ApiError, apiRequest } from '../api';
import { clearAccessToken, getAccessToken, saveAccessToken } from './auth-state';

export type SignInInput = {
  email: string;
  password: string;
};

export type SignUpInput = {
  fullName: string;
  email: string;
  password: string;
  termsAccepted: boolean;
  privacyAccepted: boolean;
  eligibilityAttested: boolean;
  policyVersion?: string;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: string;
  csrf_token?: string;
  mfa_required?: boolean;
  mfa_enrollment_required?: boolean;
  mfa_challenge_token?: string | null;
  backup_codes?: string[];
};

export type UserSignupResponse = {
  id: string;
  email: string;
  full_name: string;
  role: string;
  status: string;
};

export type PasswordResetResponse = {
  success: boolean;
  message: string;
  expires_at?: string | null;
  reset_token?: string | null;
  reset_url?: string | null;
  delivery_mode?: string | null;
};

export type MfaEnrollmentBeginResponse = {
  setup_token: string;
  secret: string;
  otpauth_url: string;
};

export type MfaLoginVerifyInput = {
  mfaChallengeToken: string;
  code?: string;
  recoveryCode?: string;
};

type AuthAction = 'signIn' | 'signUp' | 'passwordReset' | 'mfaEnroll' | 'mfaVerify';

function normalizeToken(value: string | null | undefined): string {
  return String(value || '').trim();
}

function requiresMfa(response: AuthTokenResponse): boolean {
  return Boolean(response.mfa_required || response.mfa_enrollment_required);
}

async function persistAccessToken(
  response: AuthTokenResponse,
  options: { required: boolean } = { required: true }
): Promise<void> {
  const token = normalizeToken(response.access_token);
  if (!token) {
    if (options.required) {
      throw new Error('Authentication token is missing from server response.');
    }
    return;
  }

  await saveAccessToken(token);
}

function ensureMfaChallengeToken(value: string | null | undefined): string {
  const normalized = normalizeToken(value);
  if (!normalized) {
    throw new Error('Additional verification is required. Please sign in again.');
  }
  return normalized;
}

function normalizeMfaCode(raw: string | undefined): string | undefined {
  const normalized = String(raw || '').replace(/\s+/g, '').trim();
  if (!normalized) {
    return undefined;
  }
  if (!/^\d{6,12}$/.test(normalized)) {
    throw new Error('Authenticator code must be 6 to 12 digits.');
  }
  return normalized;
}

function normalizeRecoveryCode(raw: string | undefined): string | undefined {
  const normalized = String(raw || '').replace(/\s+/g, '').trim();
  if (!normalized) {
    return undefined;
  }
  if (normalized.length < 6) {
    throw new Error('Recovery code must be at least 6 characters.');
  }
  return normalized;
}

function getApiDetailText(detail: unknown): string {
  if (typeof detail === 'string') {
    return detail.trim();
  }

  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => getApiDetailText(item))
      .filter((item) => item.length > 0);
    return parts.join(' ').trim();
  }

  if (detail && typeof detail === 'object') {
    const record = detail as Record<string, unknown>;
    const preferredKeys = ['detail', 'message', 'msg', 'error'];
    for (const key of preferredKeys) {
      const candidate = getApiDetailText(record[key]);
      if (candidate) {
        return candidate;
      }
    }
  }

  return '';
}

function statusFallback(status: number, action: AuthAction): string {
  if (status === 401) {
    if (action === 'mfaVerify') {
      return 'Your login session expired. Please sign in again.';
    }
    return 'Email or password is incorrect.';
  }

  if (status === 403) {
    return 'Your account does not have permission for this action.';
  }

  if (status === 404) {
    return 'Requested account data was not found.';
  }

  if (status === 429) {
    return 'Too many attempts. Please wait a moment and try again.';
  }

  if (status >= 500) {
    return 'Tomb of Light services are temporarily unavailable. Please try again shortly.';
  }

  if (action === 'signUp') {
    return 'Unable to create account. Please review your information and try again.';
  }

  if (action === 'passwordReset') {
    return 'Unable to submit reset request. Please try again.';
  }

  if (action === 'mfaEnroll' || action === 'mfaVerify') {
    return 'Unable to verify multi-factor authentication. Please try again.';
  }

  return 'Unable to sign in. Please try again.';
}

export function mapAuthError(error: unknown, action: AuthAction): string {
  if (error instanceof ApiError) {
    const detailMessage = getApiDetailText(error.detail);
    if (detailMessage) {
      return detailMessage;
    }

    const message = String(error.message || '').trim();
    if (message && !message.startsWith('API request failed')) {
      return message;
    }

    return statusFallback(error.status, action);
  }

  if (error instanceof Error) {
    const message = error.message.trim();
    if (message) {
      return message;
    }
  }

  return statusFallback(0, action);
}

/**
 * Uses FastAPI /auth/login.
 */
export async function signIn(input: SignInInput): Promise<AuthTokenResponse> {
  const response = await apiRequest<AuthTokenResponse>(API_ENDPOINTS.auth.signIn, {
    method: 'POST',
    body: {
      email: input.email.trim().toLowerCase(),
      password: input.password
    }
  });

  if (requiresMfa(response)) {
    ensureMfaChallengeToken(response.mfa_challenge_token);
    await clearAccessToken();
    return response;
  }

  await persistAccessToken(response, { required: true });
  return response;
}

/**
 * Uses FastAPI /auth/signup.
 * TODO: Build sign-up UI fields for policy acceptance and policy version display.
 */
export async function signUp(input: SignUpInput): Promise<UserSignupResponse> {
  return apiRequest<UserSignupResponse>(API_ENDPOINTS.auth.signUp, {
    method: 'POST',
    body: {
      full_name: input.fullName.trim(),
      email: input.email.trim().toLowerCase(),
      password: input.password,
      terms_accepted: input.termsAccepted,
      privacy_accepted: input.privacyAccepted,
      eligibility_attested: input.eligibilityAttested,
      policy_version: input.policyVersion
    }
  });
}

/**
 * Uses FastAPI /auth/password-reset/request.
 * TODO: Implement token-confirm reset flow via /auth/password-reset/confirm.
 */
export async function requestPasswordReset(email: string): Promise<PasswordResetResponse> {
  return apiRequest<PasswordResetResponse>(API_ENDPOINTS.auth.passwordResetRequest, {
    method: 'POST',
    body: {
      email: email.trim().toLowerCase()
    }
  });
}

/**
 * Starts MFA enrollment after a login challenge.
 */
export async function beginMfaEnrollment(mfaChallengeToken: string): Promise<MfaEnrollmentBeginResponse> {
  return apiRequest<MfaEnrollmentBeginResponse>(API_ENDPOINTS.auth.mfaEnrollBegin, {
    method: 'POST',
    body: {
      mfa_challenge_token: ensureMfaChallengeToken(mfaChallengeToken)
    }
  });
}

/**
 * Verifies MFA enrollment code and finalizes authenticated session.
 */
export async function verifyMfaEnrollment(setupToken: string, code: string): Promise<AuthTokenResponse> {
  const normalizedSetupToken = normalizeToken(setupToken);
  if (!normalizedSetupToken) {
    throw new Error('MFA setup session expired. Please sign in again.');
  }

  const normalizedCode = normalizeMfaCode(code);
  if (!normalizedCode) {
    throw new Error('Enter an authenticator code to complete setup.');
  }

  const response = await apiRequest<AuthTokenResponse>(API_ENDPOINTS.auth.mfaEnrollVerify, {
    method: 'POST',
    body: {
      setup_token: normalizedSetupToken,
      code: normalizedCode
    }
  });

  await persistAccessToken(response, { required: true });
  return response;
}

/**
 * Verifies MFA login challenge and finalizes authenticated session.
 */
export async function verifyMfaLogin(input: MfaLoginVerifyInput): Promise<AuthTokenResponse> {
  const challengeToken = ensureMfaChallengeToken(input.mfaChallengeToken);
  const code = normalizeMfaCode(input.code);
  const recoveryCode = normalizeRecoveryCode(input.recoveryCode);

  if (!code && !recoveryCode) {
    throw new Error('Enter an authenticator code or a recovery code.');
  }

  if (code && recoveryCode) {
    throw new Error('Use either an authenticator code or a recovery code, not both.');
  }

  const response = await apiRequest<AuthTokenResponse>(API_ENDPOINTS.auth.mfaLoginVerify, {
    method: 'POST',
    body: {
      mfa_challenge_token: challengeToken,
      code,
      recovery_code: recoveryCode
    }
  });

  await persistAccessToken(response, { required: true });
  return response;
}

/**
 * Uses FastAPI /auth/logout and always clears local token state.
 */
export async function signOut(): Promise<void> {
  const token = getAccessToken() || undefined;

  try {
    await apiRequest(API_ENDPOINTS.auth.logout, {
      method: 'POST',
      token
    });
  } finally {
    await clearAccessToken();
  }
}
