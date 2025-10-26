import { useAuthStore } from "@/store/auth";

/**
 * Hook to access authentication state and actions
 *
 * @example
 * ```tsx
 * const { user, isAuthenticated, login, logout } = useAuth();
 *
 * // Login
 * await login("user@example.com", "password");
 *
 * // Logout
 * await logout();
 *
 * // Check auth status
 * if (isAuthenticated) {
 *   console.log("Logged in as:", user?.email);
 * }
 * ```
 */
export function useAuth() {
  return useAuthStore();
}
