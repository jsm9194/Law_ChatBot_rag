// src/utils/urlTransform.ts

// KBS 뉴스 변환
function transformKbs(url: string): string | null {
  if (url.includes("news.kbs.co.kr/news/view.do")) {
    return url.replace("/news/view.do", "/news/mobile/view/view.do");
  }
  if (url.includes("news.kbs.co.kr/news/pc/view/view.do")) {
    return url.replace("/news/pc/view/view.do", "/news/mobile/view/view.do");
  }
  return null;
}

// 네이버 블로그 변환
function transformNaverBlog(url: string): string | null {
  if (url.includes("://blog.naver.com/")) {
    return url.replace("://blog.naver.com/", "://m.blog.naver.com/");
  }
  return null;
}

// ✅ 최종 통합 함수
export function toMobileUrl(url: string): string {
  return (
    transformKbs(url) ??
    transformNaverBlog(url) ??
    url // 기본은 그대로 반환
  );
}
