import { apiClient, authenticatedClient, setAuthToken } from "@/lib/api-client";
import type { components } from "@/types/api";

type UserCreate = components["schemas"]["UserCreate"];
type UserRead = components["schemas"]["UserRead"];

export interface TokenResponse {
  access_token: string;
  token_type?: string;
  refresh_token?: string | null;
}

type ValidationErrorDetail = components["schemas"]["HTTPValidationError"]["detail"] | undefined;

function extractErrorMessage(error: unknown, fallbackMessage: string): string {
  if (typeof error === "string") {
    return error;
  }

  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail?: unknown }).detail;

    if (typeof detail === "string") {
      return detail;
    }

    if (Array.isArray(detail)) {
      const messages = (detail as ValidationErrorDetail)
        ?.map((item) => (item && typeof item.msg === "string" ? item.msg : null))
        .filter((msg): msg is string => Boolean(msg));

      if (messages && messages.length) {
        return messages.join(", ");
      }
    }
  }

  return fallbackMessage;
}

export interface RegisterParams {
  email: string;
  password: string;
  full_name: string;
}

export interface LoginParams {
  email: string;
  password: string;
}

/**
 * Register a new user
 */
export async function register(params: RegisterParams): Promise<UserRead> {
  const { data, error } = await apiClient.POST("/auth/register", {
    body: params as UserCreate,
  });

  if (error) {
    throw new Error(extractErrorMessage(error as unknown, "Registration failed"));
  }

  return data;
}

/**
 * Login with email and password
 */
export async function login(params: LoginParams): Promise<TokenResponse> {
  const { data, error } = await apiClient.POST("/auth/login", {
    headers: {
      Authorization: `Basic ${btoa(`${params.email}:${params.password}`)}`,
    },
  });

  if (error) {
    throw new Error(extractErrorMessage(error as unknown, "Login failed"));
  }

  setAuthToken(data.access_token);

  return data;
}

/**
 * Refresh access token using refresh token
 */
export async function refreshToken(): Promise<TokenResponse> {
  const { data, error } = await apiClient.POST("/auth/refresh");

  if (error) {
    throw new Error(extractErrorMessage(error as unknown, "Token refresh failed"));
  }

  setAuthToken(data.access_token);

  return data;
}

/**
 * Logout the current user
 */
export async function logout(): Promise<void> {
  await authenticatedClient.POST("/auth/logout", {});
  // Note: Backend doesn't blacklist tokens yet (Phase 7)
  // For now, just clear local token
}

/**
 * Get current authenticated user info
 */
export async function getCurrentUser(): Promise<UserRead> {
  const { data, error } = await authenticatedClient.GET("/auth/me");

  if (error) {
    throw new Error(extractErrorMessage(error as unknown, "Failed to get current user"));
  }

  return data;
}
