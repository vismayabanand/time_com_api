#!/usr/bin/env python3
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

TIME_HOME = "https://time.com"
DEFAULT_PORT = 8000


def fetch_time_homepage() -> str:
    req = Request(
        TIME_HOME,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) time-stories-api/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(req, timeout=15) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def html_strip_tags(s: str) -> str:
    s = re.sub(r"<script\b[^>]*>.*?</script>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<style\b[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return normalize_whitespace(s)


def absolutize_link(href: str) -> str:
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return TIME_HOME.rstrip("/") + href
    return TIME_HOME.rstrip("/") + "/" + href


def extract_latest_stories(html: str, limit: int = 6):
    lower = html.lower()

    markers = [
        "latest stories",
        "latest-stories",
        "data-testid=\"latest",
        "data-testid='latest",
        "aria-label=\"latest",
        "aria-label='latest",
    ]

    start_idx = -1
    for m in markers:
        idx = lower.find(m)
        if idx != -1:
            start_idx = idx
            break

    if start_idx == -1:
        chunk = html
    else:
        chunk = html[start_idx : start_idx + 60000]

    anchor_re = re.compile(
        r"<a\b[^>]*\bhref\s*=\s*([\"'])(?P<href>.*?)\1[^>]*>(?P<inner>.*?)</a>",
        flags=re.I | re.S,
    )

    results = []
    seen_links = set()

    for m in anchor_re.finditer(chunk):
        href = m.group("href")
        inner = m.group("inner")

        link = absolutize_link(href)

        if "time.com/" not in link:
            continue

        if any(x in link for x in ["/video/", "/tag/", "/section/", "/subscribe", "/newsletter"]):
            continue

        if not re.search(r"time\.com/\d{6,}/", link):
            continue

        title = html_strip_tags(inner)
        if not title:
            continue

        if link in seen_links:
            continue
        seen_links.add(link)

        results.append({"title": title, "link": link})
        if len(results) >= limit:
            break

    if len(results) < limit and chunk is not html:
        for m in anchor_re.finditer(html):
            href = m.group("href")
            inner = m.group("inner")
            link = absolutize_link(href)

            if "time.com/" not in link:
                continue
            if any(x in link for x in ["/video/", "/tag/", "/section/", "/subscribe", "/newsletter"]):
                continue
            if not re.search(r"time\.com/\d{6,}/", link):
                continue

            title = html_strip_tags(inner)
            if not title:
                continue
            if link in seen_links:
                continue
            seen_links.add(link)

            results.append({"title": title, "link": link})
            if len(results) >= limit:
                break

    return results


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") != "/getTimeStories":
            self._send_json(
                404,
                {"error": "Not Found", "hint": "Use GET /getTimeStories"},
            )
            return

        try:
            html = fetch_time_homepage()
            stories = extract_latest_stories(html, limit=6)
            if not stories:
                self._send_json(
                    502,
                    {
                        "error": "Failed to extract stories",
                        "hint": "TIME homepage HTML structure may have changed. Update extract_latest_stories markers/filters.",
                    },
                )
                return

            self._send_json(200, stories)

        except HTTPError as e:
            self._send_json(502, {"error": "Upstream HTTP error", "status": e.code})
        except URLError as e:
            self._send_json(502, {"error": "Upstream URL error", "details": str(e.reason)})
        except Exception as e:
            self._send_json(500, {"error": "Server error", "details": str(e)})

    def log_message(self, format, *args):
        return


def main():
    port = DEFAULT_PORT
    if len(sys.argv) >= 2:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Usage: python app.py [port]", file=sys.stderr)
            sys.exit(1)

    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running: http://localhost:{port}/getTimeStories")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()