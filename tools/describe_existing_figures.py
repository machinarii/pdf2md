#!/usr/bin/env python3
"""Add Ollama visual descriptions to already-converted Markdown documents.

The persistent local cache is keyed by model and image SHA-256. That lets a
corpus reuse exact duplicate crops and resume after an interruption without
reparsing PDFs.
"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pdf2md_all as converter


def cache_key(model: str, image_hash: str, caption: str) -> str:
    return converter.figure_description_cache_key(model, image_hash, caption)


def load_cache(path: Path) -> dict[str, dict]:
    cache = {}
    if not path.is_file():
        return cache
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                row = json.loads(line)
                if row.get("key") and row.get("text"):
                    cache[row["key"]] = {
                        "text": row["text"],
                        "evidence": row.get("evidence"),
                        "prompt_version": row.get("prompt_version"),
                    }
            except (json.JSONDecodeError, OSError):
                continue
    return cache


def figure_md_path(root: Path, figure_folder: Path, figure_root: Path) -> Path | None:
    relative = figure_folder.relative_to(figure_root)
    candidates = [
        root / Path(str(relative) + ".md"),
        (root / relative).with_suffix(".md"),
    ]
    return next((path for path in candidates if path.is_file()), None)


def markdown_caption(lines: list[str], image_index: int) -> str:
    cursor = image_index + 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    if cursor >= len(lines) or not lines[cursor].startswith("> **"):
        return ""
    text = re.sub(r"^>\s*\*\*(.*?)\*\*\s*$", r"\1", lines[cursor]).strip()
    return "" if text.casefold() in {"figure", "image", "diagram"} else text


def clean_figure_block(markdown: str, image_name: str, description: str,
                       caption: str = "", evidence: dict | None = None) -> tuple[str, bool]:
    lines = markdown.splitlines()
    image_line = None
    for index, line in enumerate(lines):
        match = re.match(r"^!\[[^\]]*\]\((.+?)\)(?:\s+.*)?$", line)
        if not match:
            continue
        linked_name = Path(unquote(urlsplit(match.group(1)).path)).name
        if linked_name == image_name:
            image_line = index
            break
    if image_line is None:
        return markdown, False

    cursor = image_line + 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    caption_line = f"> **{caption.strip()}**" if caption.strip() else "> **Figure**"
    consumed = False
    seen_ai_context = False
    while cursor < len(lines):
        line = lines[cursor]
        if line.startswith("> **AI-generated"):
            seen_ai_context = True
            consumed = True
            cursor += 1
            continue
        if line.startswith("> **") and not seen_ai_context:
            consumed = True
            cursor += 1
            continue
        if line.startswith(">"):
            consumed = True
            cursor += 1
            continue
        if not line.strip():
            look = cursor + 1
            while look < len(lines) and not lines[look].strip():
                look += 1
            if look < len(lines) and (lines[look].startswith(">") or
                                      lines[look].strip() == "<details>"):
                cursor = look
                continue
            break
        if line.strip() == "<details>":
            consumed = True
            while cursor < len(lines) and lines[cursor].strip() != "</details>":
                cursor += 1
            if cursor < len(lines):
                cursor += 1
            continue
        if consumed and line.startswith(("- ", "<summary>", "</summary>")):
            cursor += 1
            continue
        break

    description = converter.clean_vlm_description(description) or description.strip()
    cleaned = lines[:image_line + 1]
    cleaned.extend(["", caption_line, "",
                    "> **AI-generated visual context — verify against the image:**"])
    if evidence:
        formatted = converter.format_figure_evidence(description, evidence)
        summary, _, evidence_details = formatted.partition("\n<details>")
        cleaned.extend("> " + line if line else ">" for line in summary.splitlines())
        cleaned.append("")
        if evidence_details:
            cleaned.append("<details>" + evidence_details)
    else:
        cleaned.extend("> " + line if line else ">" for line in description.splitlines())
    cleaned.extend([""])
    cleaned.extend(lines[cursor:])
    result = "\n".join(cleaned).rstrip() + "\n"
    return converter.normalize_markdown_layout(result), True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="converted Markdown root containing .figures")
    parser.add_argument("--state", type=Path, required=True, help="local cache and progress directory")
    parser.add_argument("--model", default="glm-5.3-flash:cloud")
    parser.add_argument("--ollama-host", default="http://localhost:11434")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--only", help="restrict to a substring of the relative figures folder")
    parser.add_argument("--completed-results", type=Path,
                        help="limit work to output paths with an ok/ok_chunked result in this JSONL file")
    parser.add_argument("--refresh", action="store_true",
                        help="regenerate descriptions even when manifests already have them")
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be at least 1")

    root = args.root.resolve()
    figure_root = root / ".figures"
    if not figure_root.is_dir():
        parser.error(f"figure directory not found: {figure_root}")
    args.state.mkdir(parents=True, exist_ok=True)
    cache_path = args.state / "figure-descriptions.jsonl"
    cache = load_cache(cache_path)
    completed_outputs = None
    if args.completed_results:
        latest_results = {}
        with args.completed_results.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("source"):
                    latest_results[row["source"]] = row
        completed_outputs = {
            Path(row["output"]).as_posix()
            for row in latest_results.values()
            if row.get("status") in {"ok", "ok_chunked"} and row.get("output")
        }

    def folder_is_completed(folder: Path) -> bool:
        if completed_outputs is None:
            return True
        relative = folder.relative_to(figure_root)
        possibilities = {Path(str(relative) + ".md").as_posix(),
                         relative.with_suffix(".md").as_posix()}
        return bool(possibilities & completed_outputs)

    manifest_data: dict[Path, tuple[list[dict], Path | None]] = {}
    jobs: dict[str, tuple[Path, str, str, list[dict], list[float] | None]] = {}
    for manifest in sorted(figure_root.rglob("visuals.json")):
        folder = manifest.parent
        relative = folder.relative_to(figure_root).as_posix()
        if args.only and args.only.casefold() not in relative.casefold():
            continue
        if not folder_is_completed(folder):
            continue
        try:
            records = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        manifest_data[manifest] = (records, figure_md_path(root, folder, figure_root))

    # Some converters or older runs saved image crops without a visuals.json.
    # Recover those figure references from the Markdown so the caption pass
    # covers exactly the images LightRAG can see.
    image_pattern = re.compile(r"^!\[[^\]]*\]\((.+?)\)(?:\s+.*)?$")
    for md_path in sorted(root.rglob("*.md")):
        if ".figures" in md_path.parts:
            continue
        if (completed_outputs is not None and
                md_path.relative_to(root).as_posix() not in completed_outputs):
            continue
        try:
            lines = md_path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(lines):
            match = image_pattern.match(line)
            if not match:
                continue
            image_path = (md_path.parent / unquote(urlsplit(match.group(1)).path)).resolve()
            try:
                image_path.relative_to(figure_root.resolve())
            except ValueError:
                continue
            if not image_path.is_file() or image_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            manifest = image_path.parent / "visuals.json"
            relative = image_path.parent.relative_to(figure_root).as_posix()
            if args.only and args.only.casefold() not in relative.casefold():
                continue
            records, current_md = manifest_data.setdefault(manifest, ([], md_path))
            if current_md is None:
                manifest_data[manifest] = (records, md_path)
            if not any(row.get("image") == image_path.name for row in records):
                match_name = re.match(r"fig-p(\d+)-(\d+)-(\d+)", image_path.stem)
                image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
                record = {"image": image_path.name, "image_sha256": image_hash,
                          "caption": markdown_caption(lines, index),
                          "model": args.model, "generated": False,
                          "status": "pending", "text": None, "review_required": True}
                if match_name:
                    record["page"] = int(match_name.group(1))
                records.append(record)

    manifests = []
    for manifest, (records, md_path) in sorted(manifest_data.items()):
        if not records and not md_path:
            continue
        folder = manifest.parent
        manifests.append((manifest, records, md_path))
        for record in records:
            image_name = record.get("image")
            image_path = folder / image_name if image_name else None
            if not image_path or not image_path.is_file():
                continue
            if (not args.refresh and record.get("status") == "generated" and record.get("text")
                    and record.get("model") == args.model
                    and record.get("prompt_version") == converter.FIGURE_DESCRIPTION_PROMPT_VERSION):
                continue
            image_hash = record.get("image_sha256") or hashlib.sha256(image_path.read_bytes()).hexdigest()
            key = cache_key(args.model, image_hash, record.get("caption", ""))
            if key in cache and not args.refresh:
                continue
            jobs.setdefault(key, (image_path, record.get("caption", ""), image_hash,
                                 record.get("known_labels", []), record.get("crop_bbox")))

    cache_hits = 0
    for manifest, records, _ in manifests:
        for row in records:
            if (not args.refresh and row.get("text") and row.get("model") == args.model
                    and row.get("prompt_version") == converter.FIGURE_DESCRIPTION_PROMPT_VERSION):
                cache_hits += 1
                continue
            image_name = row.get("image")
            if not image_name:
                continue
            image_path = manifest.parent / image_name
            if not image_path.is_file():
                continue
            image_hash = row.get("image_sha256") or hashlib.sha256(image_path.read_bytes()).hexdigest()
            key = cache_key(args.model, image_hash, row.get("caption", ""))
            if not args.refresh and key in cache:
                cache_hits += 1
    print(f"Manifests: {len(manifests)}; unique crops to describe: {len(jobs)}; "
          f"cache hits: {cache_hits}", flush=True)
    args.state.mkdir(parents=True, exist_ok=True)
    def describe(key: str, job: tuple[Path, str, str, list[dict], list[float] | None]) -> tuple[str, dict | None]:
        image_path, caption, image_hash, known_labels, crop_bbox = job
        result = None
        for attempt in range(3):
            result = converter.describe_region_vlm(
                image_path, caption, args.model, host=args.ollama_host,
                cache_path=cache_path, refresh_cache=args.refresh,
                known_labels=known_labels, crop_bbox=crop_bbox, return_record=True)
            if result:
                break
            if attempt < 2:
                # Ollama Cloud can return HTTP 429 under load. Give the service
                # room to recover before retrying; successful work is already
                # durable in the image-hash cache.
                time.sleep(20 * (2 ** attempt))
        if result:
            return key, result
        return key, None

    failures = 0
    if jobs:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            job_iter = iter(jobs.items())
            futures = {}

            def submit_next() -> bool:
                try:
                    key, job = next(job_iter)
                except StopIteration:
                    return False
                futures[pool.submit(describe, key, job)] = key
                return True

            # Keep only a small multiple of the worker count queued. Submitting
            # every crop at once retains thousands of Future objects for hours.
            for _ in range(min(len(jobs), args.workers * 2)):
                submit_next()
            done = 0
            while futures:
                completed, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in completed:
                    key = futures.pop(future)
                    _, result = future.result()
                    done += 1
                    if result:
                        # The converter already appended this description to
                        # the durable JSONL cache; keep it available for the
                        # manifest write-back without a second result map.
                        cache[key] = {
                            "text": result["text"],
                            "evidence": converter.figure_evidence_for_cache(result.get("evidence")),
                        }
                    else:
                        failures += 1
                    submit_next()
                if done % 25 < len(completed) or done == len(jobs):
                    print(f"Descriptions: {done}/{len(jobs)}; failed: {failures}", flush=True)

    updated_manifests = updated_markdown = 0
    for manifest, records, md_path in manifests:
        changed = False
        markdown = (md_path.read_text(encoding="utf-8")
                    if md_path and md_path.is_file() else None)
        for record in records:
            image_name = record.get("image")
            if not image_name:
                continue
            image_path = manifest.parent / image_name
            if not image_path.is_file():
                continue
            image_hash = record.get("image_sha256") or hashlib.sha256(image_path.read_bytes()).hexdigest()
            key = cache_key(args.model, image_hash, record.get("caption", ""))
            cached = (None if args.refresh else cache.get(key))
            if (not cached and record.get("model") == args.model and record.get("text")
                    and record.get("prompt_version") == converter.FIGURE_DESCRIPTION_PROMPT_VERSION):
                cached = {"text": record["text"], "evidence": record.get("evidence")}
            if not cached or not cached.get("text"):
                continue
            description = converter.clean_vlm_description(cached["text"])
            if not description:
                continue
            evidence = converter.map_figure_evidence_to_page(
                cached.get("evidence"), record.get("crop_bbox"))
            record.update(model=args.model, generated=True, status="generated", text=description,
                          image_sha256=image_hash, review_required=True,
                          prompt_version=converter.FIGURE_DESCRIPTION_PROMPT_VERSION,
                          evidence=evidence)
            changed = True
            if markdown is not None:
                markdown, inserted = clean_figure_block(markdown, image_name, description,
                                                        record.get("caption", ""), evidence)
                updated_markdown += int(inserted)
        if changed:
            temp = manifest.with_suffix(".json.tmp")
            temp.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temp.replace(manifest)
            updated_manifests += 1
            if md_path and markdown is not None:
                temp_md = md_path.with_suffix(md_path.suffix + ".tmp")
                temp_md.write_text(converter.normalize_markdown_layout(markdown), encoding="utf-8")
                temp_md.replace(md_path)

    print(f"Updated manifests: {updated_manifests}; Markdown figure blocks: {updated_markdown}; "
          f"failures: {failures}; cache: {cache_path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
