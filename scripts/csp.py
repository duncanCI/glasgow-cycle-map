"""Write the page's Content Security Policy into index.html.

The policy tells browsers which code and services the page may use, so that if anything unexpected ever gets into
the page (through the community map, OpenStreetMap names, or a compromised library host) the browser refuses to run
it. GitHub Pages can't send security headers, so the policy goes in a <meta> tag, which has to name the exact
contents of the page's own script by its SHA-256 hash. Run this after any change to the page's script:

    python3 scripts/csp.py

It is also run by the weekly refresh after the community data is embedded (that data is not script, so the hash
normally stays the same).
"""
import base64, hashlib, re, sys
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "index.html"

def policy(script_hash):
    return "; ".join([
        "default-src 'self'",
        # the page's own script (by hash), the pinned map and 3D libraries from jsDelivr, and WebAssembly for the AI
        f"script-src 'self' 'sha256-{script_hash}' https://cdn.jsdelivr.net 'wasm-unsafe-eval'",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "font-src 'self' data:",
        # map tiles, imagery and 3D data come from several open services
        "img-src 'self' data: blob: https:",
        "connect-src 'self' https:",
        "media-src 'self' https:",
        "worker-src 'self' blob:",
        "child-src blob:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-src 'none'",
        "manifest-src 'self'",
        "upgrade-insecure-requests",
    ])

def main():
    text = PAGE.read_text()
    scripts = re.findall(r"<script>(.*?)</script>", text, flags=re.S)  # inline scripts with no attributes: the code
    if len(scripts) != 1:
        sys.exit(f"Expected one inline script, found {len(scripts)}.")
    digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode()
    tag = f'<meta http-equiv="Content-Security-Policy" content="{policy(digest)}">'
    if 'http-equiv="Content-Security-Policy"' in text:
        text = re.sub(r'<meta http-equiv="Content-Security-Policy" content="[^"]*">', lambda m: tag, text, count=1)
    else:  # straight after the charset, before anything that loads
        text = re.sub(r'(<meta charset="[^"]*">)', lambda m: m.group(1) + "\n" + tag, text, count=1)
    PAGE.write_text(text)
    print("policy written; script hash", digest)

if __name__ == "__main__":
    main()
