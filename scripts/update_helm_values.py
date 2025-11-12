#!/usr/bin/env python3
"""Update image.tag in charts/app/values.yaml (used by CI to bump image tag for GitOps).

Usage: python scripts/update_helm_values.py --file charts/app/values.yaml --image-tag <tag>
This script edits the YAML in-place and commits the change (when run in CI with git configured).
"""

import argparse
import sys
from pathlib import Path

import yaml


def load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump(path: Path, data):
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, default_flow_style=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", required=True)
    p.add_argument("--image-tag", required=True)
    args = p.parse_args()

    path = Path(args.file)
    if not path.exists():
        print("file not found:", path)
        sys.exit(2)

    data = load(path)
    # Safe navigation to image.tag
    if "image" in data and isinstance(data["image"], dict):
        data["image"]["tag"] = args.image_tag
    else:
        # Try nested api.image
        if "api" in data and isinstance(data["api"].get("image"), dict):
            data["api"]["image"]["tag"] = args.image_tag
        else:
            print("Could not find image tag field to update in", path)
            sys.exit(3)

    dump(path, data)
    print("updated", path, "-> image.tag=", args.image_tag)


if __name__ == "__main__":
    main()
