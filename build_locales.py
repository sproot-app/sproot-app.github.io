#!/usr/bin/env python3
"""言語別URL（/ja/ /ko/ /en/）の静的生成。

ルートの4ページ（3言語同居・JS切替）を正本として、各言語だけを含む
ページを ja/ ko/ en/ に書き出す。SEO 用に canonical / hreflang / sitemap も生成。
ルートは x-default（従来どおり自動判定＋その場切替）として残す —
App Store 審査に提出済みの privacy.html 等の URL を壊さないため。

使い方: ルートの HTML を編集したら `python3 build_locales.py` を実行してコミットする。
"""
import os
import re

BASE = "https://sproot-app.github.io"
PAGES = ["index.html", "releases.html", "privacy.html", "terms.html"]
LANGS = ["ja", "ko", "en"]

DESCRIPTIONS = {
    "index.html": {
        "ja": "作る手間はAIに。くり返すほど、言葉はあなたに根づく。AI単語帳 Sproot。",
        "ko": "만드는 수고는 AI에게. 반복할수록 말은 당신에게 뿌리내려요. AI 단어장 Sproot.",
        "en": "Let AI do the making — every review roots the words deeper. Sproot, the AI flashcard app.",
    },
    "releases.html": {
        "ja": "Sproot の新機能・改善のお知らせ。",
        "ko": "Sproot의 새로운 기능과 개선 소식.",
        "en": "New features and improvements in Sproot.",
    },
    "privacy.html": {
        "ja": "Sproot は個人情報を収集しません。データはすべて端末の中に。",
        "ko": "Sproot는 개인정보를 수집하지 않습니다. 데이터는 모두 기기 안에.",
        "en": "Sproot collects no personal information. All data stays on your device.",
    },
    "terms.html": {
        "ja": "Sproot の利用規約。",
        "ko": "Sproot 이용약관.",
        "en": "Sproot Terms of Service.",
    },
}

OPEN_RE = re.compile(
    r'<(span|div|a|figure|p|h1|h2|h3|li|option)\b[^>]*class="[^"]*\bl-(ja|ko|en)\b[^"]*"[^>]*>')


def strip_langs(html: str, keep: str) -> str:
    """keep 以外の言語要素（class に l-xx を持つ要素）を子孫ごと取り除く。"""
    out, i = [], 0
    while True:
        m = OPEN_RE.search(html, i)
        if not m:
            out.append(html[i:])
            break
        tag, lang = m.group(1), m.group(2)
        out.append(html[i:m.start()])
        if lang == keep:
            out.append(m.group(0))
            i = m.end()
            continue
        # 同名タグの入れ子を数えながら対応する閉じタグまで捨てる
        depth, j = 1, m.end()
        tok = re.compile(r"<%s\b[^>]*>|</%s>" % (tag, tag))
        while depth:
            t = tok.search(html, j)
            if not t:
                raise SystemExit(f"unbalanced <{tag}> while stripping {keep}")
            depth += -1 if t.group(0).startswith("</") else 1
            j = t.end()
        i = j
    return "".join(out)


def hreflang_block(page: str) -> str:
    p = "" if page == "index.html" else page
    lines = [f'<link rel="alternate" hreflang="x-default" href="{BASE}/{p}">']
    for l in LANGS:
        lines.append(f'<link rel="alternate" hreflang="{l}" href="{BASE}/{l}/{p}">')
    return "\n".join(lines)


def build_locale(page: str, lang: str, src: str) -> str:
    html = strip_langs(src, lang)

    # html 属性と言語判定スクリプトを静的化
    html = html.replace('<html lang="ja">', f'<html lang="{lang}">', 1)
    html = re.sub(r"<script>\(function\(\)\{var l=null;.*?\}\)\(\)</script>",
                  f"<script>document.documentElement.dataset.lang='{lang}'</script>",
                  html, count=1, flags=re.S)

    # 言語切替は同ページの別ロケール URL へ移動
    html = re.sub(r"function setLang\(l,instant\)\{.*?\},180\)\}",
                  "function setLang(l,instant){if(instant){applyLang(l);return}\n"
                  "var seg=location.pathname.split('/');seg[seg.length-2]=l;location.href=seg.join('/')}",
                  html, count=1, flags=re.S)

    # サブディレクトリからのアセット参照を絶対パスに
    html = html.replace('href="favicon.svg"', 'href="/favicon.svg"')
    html = html.replace('href="apple-touch-icon.png"', 'href="/apple-touch-icon.png"')
    html = html.replace('src="shots/', 'src="/shots/')

    # タイトル（既存の TITLES マップから該当言語を採用）
    tm = re.search(r"var TITLES=\{ja:'([^']*)',ko:'([^']*)',en:(?:'([^']*)'|\"([^\"]*)\")\}", html)
    if tm:
        title = {"ja": tm.group(1), "ko": tm.group(2), "en": tm.group(3) or tm.group(4)}[lang]
        html = re.sub(r"<title>[^<]*</title>", f"<title>{title}</title>", html, count=1)
        html = re.sub(r'<meta property="og:title" content="[^"]*">',
                      f'<meta property="og:title" content="{title}">', html, count=1)

    # description / og:description / og:url / canonical / hreflang
    desc = DESCRIPTIONS[page][lang]
    if 'name="description"' in html:
        html = re.sub(r'<meta name="description" content="[^"]*">',
                      f'<meta name="description" content="{desc}">', html, count=1)
    else:
        html = html.replace('<meta property="og:type"',
                            f'<meta name="description" content="{desc}">\n<meta property="og:type"', 1)
    html = re.sub(r'<meta property="og:description" content="[^"]*">',
                  f'<meta property="og:description" content="{desc}">', html, count=1)
    p = "" if page == "index.html" else page
    url = f"{BASE}/{lang}/{p}"
    if 'property="og:url"' in html:
        html = re.sub(r'<meta property="og:url" content="[^"]*">',
                      f'<meta property="og:url" content="{url}">', html, count=1)
    links = f'<link rel="canonical" href="{url}">\n{hreflang_block(page)}\n'
    html = html.replace("<title>", links + "<title>", 1)
    return html


def inject_root_links(page: str, src: str) -> str:
    """ルート（x-default）ページに canonical + hreflang を冪等に注入する。"""
    src = re.sub(r'<link rel="canonical" href="[^"]*">\n', "", src)
    src = re.sub(r'<link rel="alternate" hreflang="[^"]*" href="[^"]*">\n?', "", src)
    p = "" if page == "index.html" else page
    links = f'<link rel="canonical" href="{BASE}/{p}">\n{hreflang_block(page)}\n'
    return src.replace("<title>", links + "<title>", 1)


def main():
    urls = []
    for page in PAGES:
        src = open(page).read()
        src = inject_root_links(page, src)
        open(page, "w").write(src)
        p = "" if page == "index.html" else page
        urls.append(f"{BASE}/{p}")
        for lang in LANGS:
            os.makedirs(lang, exist_ok=True)
            out = build_locale(page, lang, src)
            with open(os.path.join(lang, page), "w") as f:
                f.write(out)
            urls.append(f"{BASE}/{lang}/{p}")
        print(f"{page}: root + {len(LANGS)} locales")

    with open("sitemap.xml", "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u in urls:
            f.write(f"<url><loc>{u}</loc></url>\n")
        f.write("</urlset>\n")
    with open("robots.txt", "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    print(f"sitemap: {len(urls)} URLs / robots.txt")


if __name__ == "__main__":
    main()
