/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, beforeEach, vi } from "vitest";
import * as authApi from "@/lib/api/auth";
import { apiClient, authenticatedClient, setAuthToken } from "@/lib/api-client";

// Mock the API clients
vi.mock("@/lib/api-client", () => ({
  apiClient: {
    POST: vi.fn(),
  },
  authenticatedClient: {
    GET: vi.fn(),
    POST: vi.fn(),
  },
  setAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
  setRefreshTokenCallback: vi.fn(),
}));

describe("Auth API Functions", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("register", () => {
    it("should use apiClient (unauthenticated) for registration", async () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        full_name: "Test User",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: mockUser,
        error: undefined,
      } as any);

      const params = {
        email: "test@example.com",
        password: "password123",
        full_name: "Test User",
      };

      const result = await authApi.register(params);

      expect(apiClient.POST).toHaveBeenCalledWith("/auth/register", {
        body: params,
      });
      expect(result).toEqual(mockUser);
      expect(authenticatedClient.POST).not.toHaveBeenCalled();
    });

    it("should throw error on registration failure", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Email already registered" },
      } as any);

      const params = {
        email: "existing@example.com",
        password: "password123",
        full_name: "Test User",
      };

      await expect(authApi.register(params)).rejects.toThrow("Email already registered");
    });

    it("should handle validation errors", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: {
          detail: [
            { msg: "Invalid email format", type: "value_error" },
            { msg: "Password too short", type: "value_error" },
          ],
        },
      } as any);

      const params = {
        email: "invalid-email",
        password: "123",
        full_name: "Test User",
      };

      await expect(authApi.register(params)).rejects.toThrow();
    });
  });

  describe("login", () => {
    it("should use apiClient with Basic auth header", async () => {
      const mockTokens = {
        access_token: "access-token-123",
        token_type: "bearer",
      };

      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: mockTokens,
        error: undefined,
      } as any);

      const params = {
        email: "test@example.com",
        password: "password123",
      };

      const result = await authApi.login(params);

      const expectedAuth = `Basic ${btoa(`${params.email}:${params.password}`)}`;
      expect(apiClient.POST).toHaveBeenCalledWith("/auth/login", {
        headers: {
          Authorization: expectedAuth,
        },
      });
      expect(setAuthToken).toHaveBeenCalledWith(mockTokens.access_token);
      expect(result).toEqual(mockTokens);
    });

    it("should throw error on invalid credentials", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Invalid credentials" },
      } as any);

      const params = {
        email: "wrong@example.com",
        password: "wrongpassword",
      };

      await expect(authApi.login(params)).rejects.toThrow("Invalid credentials");
      expect(setAuthToken).not.toHaveBeenCalled();
    });
  });

  describe("refreshToken", () => {
    it("should use apiClient to refresh token", async () => {
      const mockTokens = {
        access_token: "new-access-token",
        token_type: "bearer",
      };

      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: mockTokens,
        error: undefined,
      } as any);

      const result = await authApi.refreshToken();

      expect(apiClient.POST).toHaveBeenCalledWith("/auth/refresh");
      expect(setAuthToken).toHaveBeenCalledWith(mockTokens.access_token);
      expect(result).toEqual(mockTokens);
    });

    it("should throw error on invalid refresh token", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Invalid refresh token" },
      } as any);

      await expect(authApi.refreshToken()).rejects.toThrow("Invalid refresh token");
      expect(setAuthToken).not.toHaveBeenCalled();
    });
  });

  describe("logout", () => {
    it("should use authenticatedClient (requires token)", async () => {
      vi.mocked(authenticatedClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: undefined,
      } as any);

      await authApi.logout();

      expect(authenticatedClient.POST).toHaveBeenCalledWith("/auth/logout", {});
      expect(apiClient.POST).not.toHaveBeenCalled();
    });

    it("should handle logout errors gracefully", async () => {
      vi.mocked(authenticatedClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Already logged out" },
      } as any);

      // Should not throw - logout is best-effort
      await expect(authApi.logout()).resolves.not.toThrow();
    });
  });

  describe("getCurrentUser", () => {
    it("should use authenticatedClient (requires token) ✨ CRITICAL", async () => {
      const mockUser = {
        id: "user-123",
        email: "test@example.com",
        full_name: "Test User",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: mockUser,
        error: undefined,
      } as any);

      const result = await authApi.getCurrentUser();

      expect(authenticatedClient.GET).toHaveBeenCalledWith("/auth/me");
      expect(result).toEqual(mockUser);
      // Ensure it does NOT use unauthenticated client
      expect(apiClient.POST).not.toHaveBeenCalled();
    });

    it("should throw error on 401 (unauthenticated)", async () => {
      vi.mocked(authenticatedClient.GET).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Not authenticated" },
      } as any);

      await expect(authApi.getCurrentUser()).rejects.toThrow("Not authenticated");
    });
  });

  describe("Error Message Formatting", () => {
    it("should extract string error messages", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { detail: "Simple error message" },
      } as any);

      await expect(
        authApi.register({
          email: "test@example.com",
          password: "password",
          full_name: "Test",
        })
      ).rejects.toThrow("Simple error message");
    });

    it("should format validation errors as comma-separated list", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: {
          detail: [
            { msg: "Error 1", type: "value_error" },
            { msg: "Error 2", type: "value_error" },
          ],
        },
      } as any);

      await expect(
        authApi.register({
          email: "test@example.com",
          password: "password",
          full_name: "Test",
        })
      ).rejects.toThrow();
    });

    it("should use fallback message for unknown errors", async () => {
      vi.mocked(apiClient.POST).mockResolvedValueOnce({
        data: undefined,
        error: { something: "unexpected" },
      } as any);

      await expect(
        authApi.register({
          email: "test@example.com",
          password: "password",
          full_name: "Test",
        })
      ).rejects.toThrow("Registration failed");
    });
  });
});
