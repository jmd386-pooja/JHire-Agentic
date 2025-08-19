// import { NextResponse } from "next/server";
// import type { NextRequest } from "next/server";

// export function middleware(request: NextRequest) {
//   const token = request.cookies.get("token");
//   const isAuthPage = request.nextUrl.pathname.startsWith("/login") || 
//                      request.nextUrl.pathname.startsWith("/register");

//   if (!token && !isAuthPage) {
//     return NextResponse.redirect(new URL("/login", request.url));
//   }

//   if (token && isAuthPage) {
//     return NextResponse.redirect(new URL("/candidates", request.url));
//   }

//   return NextResponse.next();
// }

// export const config = {
//   matcher: [
//     "/candidates/:path*",
//     "/Programming_Questions/:path*",
//     "/login",
//     "/register",
//   ],
// };




import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const userToken = request.cookies.get("user_token");
  const candidateToken = request.cookies.get("candidate_token");
  const { pathname } = request.nextUrl;

  const isAuthPage = pathname.startsWith("/login") || pathname.startsWith("/register");

  // Redirect to login if no token is found and user tries to access protected routes
  if (!userToken && !candidateToken && !isAuthPage) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Redirect logged-in users or candidates to their respective dashboards if they try to access auth pages
  if (isAuthPage) {
    console.log("isAuth ",isAuthPage);
    
    if (userToken) {
      console.log("Usertokenn",userToken);
      
      return NextResponse.redirect(new URL("/candidates", request.url));
    }
    if (candidateToken) {
      return NextResponse.redirect(new URL("/Instructions", request.url));
    }
  }

  // User-side access control
  if (userToken) {
    if (!pathname.startsWith("/candidates") && !pathname.startsWith("/Programming_Questions")) {
      return NextResponse.redirect(new URL("/candidates", request.url));
    }
  }

  // Candidate-side access control
  if (candidateToken) {
    if (!pathname.startsWith("/Instructions") && 
        !pathname.startsWith("/Interview")) {
      return NextResponse.redirect(new URL("/Instructions", request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/candidates/:path*",
    "/Programming_Questions/:path*",
    "/Instructions",
    "/Interview",
    "/login",
    "/register",
  ],
};
