// Cloudflare Pages — advanced 모드 단일 Worker. 모든 요청(정적 자산 포함)을 가로채
// 접근 제어를 먼저 적용한다. eb 그래프 뷰어는 개인 지식(보통 private)을 서빙하므로
// **기본 fail-closed**: 잠금이 안 풀리면 503, CSV 직접 접근도 막힌다.
//
// Pages 프로젝트 환경변수:
//   BASIC_AUTH_PASS : Basic Auth 비밀번호(ASCII) — 설정하면 잠금 해제 가능
//   BASIC_AUTH_USER : 사용자명(기본 "eb")
//   EB_PUBLIC       : "true" 면 인증 없이 공개(명시적 옵트아웃)
export default {
  async fetch(request, env) {
    if (env.EB_PUBLIC !== "true") {
      const pass = env.BASIC_AUTH_PASS;
      if (!pass) {
        return new Response(
          "이 eb 그래프 사이트는 잠겨 있습니다. Pages 환경변수 BASIC_AUTH_PASS 를 설정해 " +
          "Basic Auth 를 켜거나, 공개하려면 EB_PUBLIC=true 로 설정하세요.",
          { status: 503, headers: { "content-type": "text/plain; charset=utf-8" } },
        );
      }
      const user = env.BASIC_AUTH_USER || "eb";
      const expected = "Basic " + btoa(`${user}:${pass}`);
      const got = request.headers.get("Authorization") || "";
      if (!(got.length === expected.length && got === expected)) {
        return new Response("인증이 필요합니다.", {
          status: 401,
          headers: { "WWW-Authenticate": 'Basic realm="eb private graph", charset="UTF-8"' },
        });
      }
    }
    return env.ASSETS.fetch(request);
  },
};
