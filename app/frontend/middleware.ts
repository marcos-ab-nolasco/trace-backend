import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const refreshCookieName = process.env.NEXT_PUBLIC_REFRESH_COOKIE_NAME || "refresh_token";

  // Get auth token from cookies (Zustand persist stores in localStorage, not accessible in middleware)
  // For now, we'll handle auth checks client-side in the pages
  // Middleware just handles basic route protection

  // Public routes that don't require auth
  const publicRoutes = ["/", "/login", "/register"];
  const isPublicRoute = publicRoutes.includes(pathname);

  // Protected routes
  const protectedRoutes = ["/dashboard"];
  const isProtectedRoute = protectedRoutes.some((route) => pathname.startsWith(route));

  if (isProtectedRoute && !isPublicRoute) {
    const refreshCookie = request.cookies.get(refreshCookieName);

    if (!refreshCookie || !refreshCookie.value) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  // For now, let client-side handle redirects
  // Middleware can be enhanced later with cookie-based token checking

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api (API routes)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!api|_next/static|_next/image|favicon.ico).*)",
  ],
};
