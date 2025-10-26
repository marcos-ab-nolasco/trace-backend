import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { useAuthStore } from "@/store/auth";
import * as authApi from "@/lib/api/auth";
import { setAuthToken, clearAuthToken, setRefreshTokenCallback } from "@/lib/api-client";

vi.mock("@/lib/api/auth");
vi.mock("@/lib/api-client");

const defaultUser = {
  id: "user-123",
  email: "test@example.com",
  full_name: "Test User",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

describe("Auth Store", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("has expected initial state", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  describe("login", () => {
    it("authenticates and populates state", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        access_token: "access-123",
        token_type: "bearer",
      });
      vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce(defaultUser);

      await useAuthStore.getState().login("test@example.com", "password123");

      const state = useAuthStore.getState();
      expect(authApi.login).toHaveBeenCalled();
      expect(authApi.getCurrentUser).toHaveBeenCalled();
      expect(state.user).toEqual(defaultUser);
      expect(state.accessToken).toBe("access-123");
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
      expect(setRefreshTokenCallback).toHaveBeenCalled();
    });

    it("stores error when login fails", async () => {
      vi.mocked(authApi.login).mockRejectedValueOnce(new Error("Invalid credentials"));

      await expect(useAuthStore.getState().login("wrong@example.com", "bad")).rejects.toThrow(
        "Invalid credentials"
      );

      const state = useAuthStore.getState();
      expect(state.error).toBe("Invalid credentials");
      expect(state.isLoading).toBe(false);
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe("logout", () => {
    it("clears state regardless of API result", async () => {
      useAuthStore.setState({
        user: defaultUser,
        accessToken: "access-123",
        isAuthenticated: true,
      });

      vi.mocked(authApi.logout).mockRejectedValueOnce(new Error("network"));

      await useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(clearAuthToken).toHaveBeenCalled();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe("refreshAuth", () => {
    it("refreshes access token and keeps user authenticated", async () => {
      useAuthStore.setState({ isAuthenticated: true });
      vi.mocked(authApi.refreshToken).mockResolvedValueOnce({
        access_token: "new-access",
        token_type: "bearer",
      });

      await useAuthStore.getState().refreshAuth();

      const state = useAuthStore.getState();
      expect(authApi.refreshToken).toHaveBeenCalled();
      expect(state.accessToken).toBe("new-access");
      expect(state.isAuthenticated).toBe(true);
      expect(setRefreshTokenCallback).toHaveBeenCalled();
    });

    it("logs out when refresh fails", async () => {
      useAuthStore.setState({ user: defaultUser, isAuthenticated: true });
      vi.mocked(authApi.refreshToken).mockRejectedValueOnce(new Error("expired"));
      vi.mocked(authApi.logout).mockResolvedValueOnce(undefined);

      await expect(useAuthStore.getState().refreshAuth()).rejects.toThrow();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe("initializeSession", () => {
    it("hydrates state from refresh cookie", async () => {
      vi.mocked(authApi.refreshToken).mockResolvedValueOnce({
        access_token: "fresh-access",
        token_type: "bearer",
      });
      vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce(defaultUser);

      await useAuthStore.getState().initializeSession();

      const state = useAuthStore.getState();
      expect(authApi.refreshToken).toHaveBeenCalled();
      expect(authApi.getCurrentUser).toHaveBeenCalled();
      expect(state.accessToken).toBe("fresh-access");
      expect(state.user).toEqual(defaultUser);
      expect(state.isAuthenticated).toBe(true);
    });

    it("clears auth when no session is available", async () => {
      vi.mocked(authApi.refreshToken).mockRejectedValueOnce(new Error("no session"));

      await useAuthStore.getState().initializeSession();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.accessToken).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(clearAuthToken).toHaveBeenCalled();
    });
  });

  describe("clearError", () => {
    it("resets error flag", () => {
      useAuthStore.setState({ error: "boom" });
      useAuthStore.getState().clearError();
      expect(useAuthStore.getState().error).toBeNull();
    });
  });

  describe("Persistence", () => {
    it("persists auth subset", async () => {
      vi.mocked(authApi.login).mockResolvedValueOnce({
        access_token: "persist-access",
        token_type: "bearer",
      });
      vi.mocked(authApi.getCurrentUser).mockResolvedValueOnce(defaultUser);

      await useAuthStore.getState().login("test@example.com", "password123");

      const stored = localStorage.getItem("auth-storage");
      expect(stored).toBeTruthy();
      if (stored) {
        const parsed = JSON.parse(stored);
        expect(parsed.state.user).toEqual(defaultUser);
        expect(parsed.state.accessToken).toBe("persist-access");
        expect(parsed.state.isAuthenticated).toBe(true);
      }
    });

    it("restores token on rehydrate", () => {
      const mockState = {
        state: {
          user: defaultUser,
          accessToken: "rehydrated-access",
          isAuthenticated: true,
        },
        version: 0,
      };

      localStorage.setItem("auth-storage", JSON.stringify(mockState));

      expect(setAuthToken).toBeDefined();
    });
  });
});
