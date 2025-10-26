import createClient from "openapi-fetch";
import type { paths } from "@/types/api";

const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const withCredentialsFetch: typeof fetch = (input, init) =>
  fetch(input, { ...init, credentials: "include" });

const createClientInstance = () => createClient<paths>({ baseUrl, fetch: withCredentialsFetch });

export const apiClient = createClientInstance();

/**
 * API client with authentication token injection and auto-refresh on 401
 */
export const authenticatedClient = createClientInstance();

// Store for refresh callback (set by auth store)
let refreshTokenCallback: (() => Promise<void>) | null = null;

/**
 * Register callback to refresh token on 401
 */
export function setRefreshTokenCallback(callback: () => Promise<void>) {
  refreshTokenCallback = callback;
}

/**
 * Set the authentication token for all authenticated requests
 */
export function setAuthToken(token: string | null) {
  if (token) {
    authenticatedClient.use({
      onRequest({ request }) {
        request.headers.set("Authorization", `Bearer ${token}`);
        return request;
      },
    });

    // Add response interceptor for auto-refresh on 401
    authenticatedClient.use({
      async onResponse({ response }) {
        if (response.status === 401 && refreshTokenCallback) {
          try {
            // Try to refresh token
            await refreshTokenCallback();
            // Token refreshed, caller should retry the request
          } catch (error) {
            // Refresh failed, user will be logged out by the store
            console.error("Token refresh failed:", error);
          }
        }
        return response;
      },
    });
  }
}

/**
 * Clear the authentication token
 */
export function clearAuthToken() {
  // Create a new client instance without auth headers
  Object.assign(authenticatedClient, createClientInstance());
  refreshTokenCallback = null;
}
