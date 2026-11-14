"""Command line for the pack SDK.

  python -m nortpole_pack_sdk validate <pack-dir> [<pack-dir> ...]
  python -m nortpole_pack_sdk build    <pack-dir> --out dist/
  python -m nortpole_pack_sdk sign     <pack-dir> --key-file key.json --out dist/
  python -m nortpole_pack_sdk keygen   <key-id> > key.json

The key file is the JSON `keygen` prints. Keep it out of the repository; register only its public key on the server.
"""

import argparse
import json
import sys
from pathlib import Path

from nortpole_pack_sdk.core import PackError
from nortpole_pack_sdk.core import build
from nortpole_pack_sdk.core import digest
from nortpole_pack_sdk.core import keygen
from nortpole_pack_sdk.core import sign
from nortpole_pack_sdk.core import validate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nortpole_pack_sdk", description="Validate, build and sign workflow packs.")
    sub = parser.add_subparsers(dest="command", required=True)
    v = sub.add_parser("validate", help="check pack folders against the schema and folder rules")
    v.add_argument("packs", nargs="+", type=Path)
    b = sub.add_parser("build", help="write the unsigned manifest JSON")
    b.add_argument("pack", type=Path)
    b.add_argument("--out", type=Path, default=Path("dist"))
    s = sub.add_parser("sign", help="write the signed package the admin console installs")
    s.add_argument("pack", type=Path)
    s.add_argument("--key-file", type=Path, required=True)
    s.add_argument("--out", type=Path, default=Path("dist"))
    k = sub.add_parser("keygen", help="print a new Ed25519 key pair as JSON")
    k.add_argument("key_id")
    args = parser.parse_args(argv)

    try:
        if args.command == "validate":
            failed = 0
            for pack in args.packs:
                try:
                    manifest = validate(pack)
                    print(f"ok    {pack}  {manifest['id']} {manifest['version']}  digest {digest(manifest)[:12]}")
                except PackError as e:
                    failed += 1
                    print(f"FAIL  {pack}: {e}", file=sys.stderr)
            return 1 if failed else 0
        if args.command == "build":
            print(build(args.pack, args.out))
            return 0
        if args.command == "sign":
            key = json.loads(args.key_file.read_text(encoding="utf-8"))
            manifest = validate(args.pack)
            package = sign(manifest, key["private_key"], key["key_id"])
            out = args.out / f"{manifest['id']}-{manifest['version']}.signed.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(out)
            print(f"digest: {digest(manifest)}", file=sys.stderr)
            return 0
        print(json.dumps(keygen(args.key_id), indent=2))
        return 0
    except (PackError, KeyError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
