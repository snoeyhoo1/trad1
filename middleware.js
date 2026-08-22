import { NextResponse } from "next/server";

export function middleware(req) {
  const validUser = process.env.DASHBOARD_USER || "admin";
  const validPass = process.env.DASHBOARD_PASSWORD;

  if (!validPass) {
    // 배포 직후 DASHBOARD_PASSWORD를 아직 안 넣었을 때 화면이 완전히 막히지
    // 않도록 통과시키되, README에서 반드시 설정하라고 강조함.
    return NextResponse.next();
  }

  const auth = req.headers.get("authorization");
  if (auth && auth.startsWith("Basic ")) {
    const decoded = atob(auth.slice(6));
    const sep = decoded.indexOf(":");
    const user = decoded.slice(0, sep);
    const pass = decoded.slice(sep + 1);
    if (user === validUser && pass === validPass) {
      return NextResponse.next();
    }
  }

  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="aitrader dashboard"' },
  });
}

export const config = {
  matcher: ["/dashboard/:path*", "/api/dashboard-feed"],
};
