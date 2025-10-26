import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { components } from "@/types/api";
import * as authApi from "@/lib/api/auth";
import { setAuthToken, clearAuthToken, setRefreshTokenCallback } from "@/lib/api-client";

type UserRead = components["schemas"]["UserRead"];

interface AuthState {
  // State
  user: UserRead | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
  initializeSession: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      // Initial state
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      // Login action
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const tokens = await authApi.login({ email, password });
          const user = await authApi.getCurrentUser();

          set({
            user,
            accessToken: tokens.access_token,
            isAuthenticated: true,
            isLoading: false,
          });

          setRefreshTokenCallback(async () => {
            await get().refreshAuth();
          });
        } catch (error) {
          const message = error instanceof Error ? error.message : "Login failed";
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // Register action
      register: async (email: string, password: string, fullName: string) => {
        set({ isLoading: true, error: null });
        try {
          await authApi.register({ email, password, full_name: fullName });
          // After registration, automatically log in
          await get().login(email, password);
        } catch (error) {
          const message = error instanceof Error ? error.message : "Registration failed";
          set({ error: message, isLoading: false });
          throw error;
        }
      },

      // Logout action
      logout: async () => {
        try {
          await authApi.logout();
        } catch (error) {
          console.error("Logout error:", error);
        } finally {
          clearAuthToken();
          set({
            user: null,
            accessToken: null,
            isAuthenticated: false,
            error: null,
          });
        }
      },

      // Refresh token action
      refreshAuth: async () => {
        try {
          const tokens = await authApi.refreshToken();
          set({
            accessToken: tokens.access_token,
            isAuthenticated: true,
          });

          setRefreshTokenCallback(async () => {
            await get().refreshAuth();
          });
        } catch (error) {
          // If refresh fails, logout
          await get().logout();
          throw error;
        }
      },

      initializeSession: async () => {
        try {
          const tokens = await authApi.refreshToken();
          set({ accessToken: tokens.access_token, isAuthenticated: true });
          const user = await authApi.getCurrentUser();
          set({ user, isAuthenticated: true });
          setRefreshTokenCallback(async () => {
            await get().refreshAuth();
          });
        } catch {
          // Session not available; ensure clean state
          clearAuthToken();
          set({ user: null, accessToken: null, isAuthenticated: false });
        }
      },

      // Clear error action
      clearError: () => set({ error: null }),
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        isAuthenticated: state.isAuthenticated,
      }),
      onRehydrateStorage: () => (state) => {
        const accessToken = state?.accessToken;
        if (accessToken) {
          setAuthToken(accessToken);
          setRefreshTokenCallback(async () => {
            await useAuthStore.getState().refreshAuth();
          });
        } else {
          void useAuthStore.getState().initializeSession();
        }
      },
    }
  )
);
