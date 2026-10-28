"""创建/更新 Gitea Release，并上传安装包（与 GitHub 对齐）。

用法（PowerShell）:
  $env:GITEA_TOKEN = '...'
  python tools/publish_gitea_release.py --tag v2.1.0 --setup path\\to\\Bible_Pro_Setup.exe
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE = "https://gitea.cccccjd.cn"
DEFAULT_OWNER = "SXD20041213"
DEFAULT_REPO = "bible_projection"


def _api(base: str, token: str, method: str, path: str, data=None, headers=None, timeout=120):
    ctx = ssl.create_default_context()
    h = {
        "Authorization": f"token {token}",
        "User-Agent": "BiblePro-Publish",
    }
    if headers:
        h.update(headers)
    body = data
    if isinstance(data, (dict, list)):
        body = json.dumps(data).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(base.rstrip("/") + path, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw.decode() or "null") if raw else None
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {path}: {err[:800]}") from exc


def ensure_release(base: str, token: str, owner: str, repo: str, tag: str, name: str, body: str):
    path = f"/api/v1/repos/{owner}/{repo}/releases/tags/{tag}"
    try:
        _, rel = _api(base, token, "GET", path)
        print(f"release exists id={rel.get('id')} {rel.get('html_url')}")
        return rel
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise
    _, rel = _api(
        base,
        token,
        "POST",
        f"/api/v1/repos/{owner}/{repo}/releases",
        {
            "tag_name": tag,
            "target_commitish": "main",
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False,
        },
    )
    print(f"release created id={rel.get('id')} {rel.get('html_url')}")
    return rel


def upload_asset(base: str, token: str, owner: str, repo: str, release_id: int, setup: Path, name: str):
    data = setup.read_bytes()
    boundary = "----BibleProBoundary7MA4YWxkTrZu0gW"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="attachment"; filename="{name}"\r\n'.encode(),
            b"Content-Type: application/octet-stream\r\n\r\n",
            data,
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    _, asset = _api(
        base,
        token,
        "POST",
        f"/api/v1/repos/{owner}/{repo}/releases/{release_id}/assets?name={name}",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=600,
    )
    url = asset.get("browser_download_url") or asset.get("id")
    print(f"uploaded {name} size={asset.get('size')} url={url}")
    return asset


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=os.environ.get("GITEA_URL", DEFAULT_BASE))
    p.add_argument("--owner", default=DEFAULT_OWNER)
    p.add_argument("--repo", default=DEFAULT_REPO)
    p.add_argument("--tag", required=True)
    p.add_argument("--setup", required=True, type=Path)
    p.add_argument("--name", default="")
    p.add_argument("--body", default="与 GitHub Release 同步。")
    p.add_argument("--also-versioned", action="store_true", help="额外上传 Bible_Pro_<ver>_Setup.exe")
    args = p.parse_args(argv)

    token = os.environ.get("GITEA_TOKEN", "").strip()
    if not token:
        print("缺少环境变量 GITEA_TOKEN", file=sys.stderr)
        return 2
    if not args.setup.is_file():
        print(f"找不到安装包: {args.setup}", file=sys.stderr)
        return 2

    tag = args.tag if args.tag.startswith("v") else f"v{args.tag}"
    ver = tag.lstrip("vV")
    title = args.name or f"Bible Pro {tag}"
    rel = ensure_release(args.base, token, args.owner, args.repo, tag, title, args.body)
    existing = {a.get("name") for a in (rel.get("assets") or [])}
    rid = int(rel["id"])

    names = ["Bible_Pro_Setup.exe"]
    if args.also_versioned:
        names.append(f"Bible_Pro_{ver}_Setup.exe")
    for name in names:
        if name in existing:
            print(f"skip existing {name}")
            continue
        upload_asset(args.base, token, args.owner, args.repo, rid, args.setup, name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
