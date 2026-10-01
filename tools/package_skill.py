#!/usr/bin/env python3
"""Build portable plugin and standalone skill archives from an explicit file list."""

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "pdf2md"
SKILL_FILES = ("SKILL.md", "LICENSE", "agents/openai.yaml")


def write_archive(path, files):
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        for source, name in sorted(files, key=lambda pair: pair[1]):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    print(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    codex = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
    claude = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    if (codex["name"], codex["version"]) != (claude["name"], claude["version"]):
        parser.error("Claude and Codex plugin names and versions must agree")
    version = codex["version"]
    skill_files = [(PLUGIN / "skills/pdf2md" / name, name) for name in SKILL_FILES]
    plugin_files = [
        (PLUGIN / name, name)
        for name in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", "README.md")
    ] + [(ROOT / "LICENSE", "LICENSE")]
    plugin_files += [(source, f"skills/pdf2md/{name}") for source, name in skill_files]
    # An allowlist prevents local configuration, credentials, and document inputs
    # from accidentally entering a distributable archive.
    for source, _ in plugin_files:
        if not source.is_file() or source.is_symlink():
            parser.error(f"Missing or symlinked release input: {source}")
    args.output.mkdir(parents=True, exist_ok=True)
    write_archive(args.output / f"pdf2md-plugin-{version}.zip", plugin_files)
    write_archive(args.output / f"pdf2md-skill-{version}.zip", skill_files)


if __name__ == "__main__":
    main()
