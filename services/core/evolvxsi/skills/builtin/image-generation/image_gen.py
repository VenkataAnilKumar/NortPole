#!/usr/bin/env python3
"""Generate or edit images through the EvolvXSI image-generation API.

    python image_gen.py generate -p "<prompt>" [--shape square|portrait|landscape] [-q high] [-n 1] [-o output.png]
    python image_gen.py edit -i input.png [-i more.png] -p "<instruction>" [-o output.png]

Reads EVOLVXSI_SERVER_URL (the API base) and EVOLVXSI_PAT from the environment. Prints the saved file
path(s), one per line; several images get a _N suffix. Standard library only, so it runs in any sandbox.
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_HTTP_TIMEOUT_SECONDS = 330  # the server ends a generation after five minutes
_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _post(base: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(  # noqa: S310 - main() only accepts http(s) bases
        f"{base.rstrip('/')}/image-generation/generate",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            # The server sends whitespace keepalives before the JSON body; json.loads ignores them.
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except ValueError:
            return {"detail": f"HTTP {e.code}: {raw[:500]}"}


def _output_paths(output: Path, count: int, mime_type: str) -> list[Path]:
    suffix = output.suffix or _EXTENSIONS.get(mime_type, ".png")
    stem = output.with_suffix("")
    if count == 1:
        return [stem.with_suffix(suffix)]
    return [Path(f"{stem}_{i}{suffix}") for i in range(1, count + 1)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="image_gen.py")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "edit"):
        cmd = sub.add_parser(name)
        cmd.add_argument("-p", "--prompt", required=True)
        cmd.add_argument("-o", "--output", default="output.png")
        cmd.add_argument(
            "--shape", choices=["square", "portrait", "landscape"], default="square"
        )
        cmd.add_argument("-q", "--quality")
        cmd.add_argument("-n", "--num", type=int, default=1)
        cmd.add_argument(
            "-i",
            "--input-image",
            action="append",
            default=[],
            required=(name == "edit"),
        )
    args = parser.parse_args(argv)

    base = os.environ.get("EVOLVXSI_SERVER_URL", "").strip()
    token = os.environ.get("EVOLVXSI_PAT", "").strip()
    if not base or not token:
        return _fail("EVOLVXSI_SERVER_URL and EVOLVXSI_PAT must be set")
    if not base.startswith(("http://", "https://")):
        return _fail("EVOLVXSI_SERVER_URL must be an http(s) URL")

    references = []
    for path in args.input_image:
        try:
            data = Path(path).read_bytes()
        except OSError as e:
            return _fail(f"cannot read input image {path}: {e}")
        references.append(
            {
                "data_base64": base64.b64encode(data).decode("ascii"),
                "mime_type": mimetypes.guess_type(path)[0] or "image/png",
            }
        )

    body: dict[str, Any] = {
        "prompt": args.prompt,
        "shape": args.shape,
        "n": args.num,
        "reference_images": references,
    }
    if args.quality:
        body["quality"] = args.quality
    try:
        payload = _post(base, token, body)
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        return _fail(f"image generation request failed: {e}")

    images = payload.get("images")
    if not images:
        return _fail(payload.get("detail") or "image generation failed")

    paths = _output_paths(
        Path(args.output), len(images), images[0].get("mime_type", "image/png")
    )
    for image, path in zip(images, paths, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(image["data_base64"]))
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
