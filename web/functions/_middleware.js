// Cloudflare Pages Function — 사이트 전체 접근 제어 (모든 경로에 먼저 실행됨).
//
// eb 그래프 뷰어는 개인 지식(보통 private)을 서빙하므로 **기본은 잠금(fail-closed)** 이다.
// 정적 호스팅은 data/*.csv 를 그대로 내려주므로, 인증 없이는 노출되지 않게 막는다.
//
// Pages 프로젝트 환경변수(Settings → Environment variables):
//   - BASIC_AUTH_PASS : Basic Auth 비밀번호(ASCII). 설정하면 그 값으로 잠금.
//   - BASIC_AUTH_USER : 사용자명(기본 "eb").
//   - EB_PUBLIC       : "true" 로 두면 인증 없이 **공개**(명시적 옵트아웃).
//
// 우선순위: EB_PUBLIC=true → 공개. 아니면 BASIC_AUTH_PASS 필요 — 없으면 503(잠김).
export async function onRequest(context) {
  const { request, env, next } = context;

  if (env.EB_PUBLIC === "true") return next();

  const pass = env.BASIC_AUTH_PASS;
  if (!pass) {
    return new Response(
      "이 eb 그래프 사이트는 잠겨 있습니다. Pages 환경변수 BASIC_AUTH_PASS 를 설정해 " +
      "Basic Auth 를 켜거나, 의도적으로 공개하려면 EB_PUBLIC=true 로 설정하세요.",
      { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } },
    );
  }

  const user = env.BASIC_AUTH_USER || "eb";
  const expected = "Basic " + btoa(`${user}:${pass}`);
  const got = request.headers.get("Authorization") || "";
  if (got.length === expected.length && got === expected) return next();

  return new Response("인증이 필요합니다.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="eb private graph", charset="UTF-8"' },
  });
}
