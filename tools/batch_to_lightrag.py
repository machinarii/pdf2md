#!/usr/bin/env python3
"""Resumable PDF/EPUB conversion into a LightRAG input tree."""

import argparse
from collections import Counter, defaultdict
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from audit_markdown_quality import inspect


def converter_command(converter: Path) -> list[str]:
    """Run source checkouts with this process's interpreter and installed deps."""
    return ([sys.executable, str(converter)] if converter.suffix == ".py"
            else [str(converter)])


def strip_yaml(text: str) -> str:
    """Remove a leading YAML document header from a continuation chunk."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    return text[end + 5:].lstrip() if end >= 0 else text


def choose_cleanest_markdown(paths: list[Path]) -> tuple[Path, list[Path]]:
    """Choose the lowest-defect collision output; prefer richer text on ties."""
    ranked = []
    for path in paths:
        issues, meta = inspect(path)
        ranked.append(((meta["score"], sum(issues.values()), -meta["bytes"]), path))
    ranked.sort(key=lambda item: (item[0], str(item[1]).casefold()))
    return ranked[0][1], [path for _, path in ranked[1:]]


def convert_chunked(path: Path, output: Path, relative_md: Path, args,
                    log_stream, chunk_pages: int = 75) -> bool:
    """Bound peak memory by converting an oversized PDF in page ranges."""
    try:
        import pymupdf
        with pymupdf.open(path) as document:
            pages = document.page_count
    except Exception as exc:
        log_stream.write(f"Cannot inspect PDF for chunk fallback: {exc}\n")
        return False

    chunk_root = args.state / "chunks" / relative_md.with_suffix("")
    chunk_root.mkdir(parents=True, exist_ok=True)
    parts = []
    for start in range(1, pages + 1, chunk_pages):
        end = min(start + chunk_pages - 1, pages)
        part = chunk_root / f"pages-{start:05d}-{end:05d}.md"
        figure_dir = args.target / ".figures" / relative_md.with_suffix("") / f"pages-{start:05d}-{end:05d}"
        audit_dir = args.state / "artifacts" / relative_md.with_suffix("") / f"pages-{start:05d}-{end:05d}"
        command = converter_command(args.converter) + [str(path), "-o", str(part),
                   "--pages", f"{start}-{end}", "--no-toc",
                   "--figure-dir", str(figure_dir),
                   "--ocr", "auto", "--artifacts", str(audit_dir)]
        if args.model:
            command += ["--figure-vlm", args.model, "--ollama-host", args.ollama_host]
        log_stream.write(f"\nChunk fallback {start}-{end}: {' '.join(command)}\n")
        log_stream.flush()
        result = subprocess.run(command, stdout=log_stream, stderr=subprocess.STDOUT,
                                timeout=60 * 60, check=False)
        if result.returncode != 0 or not part.is_file() or not part.stat().st_size:
            log_stream.write(f"Chunk {start}-{end} failed with {result.returncode}\n")
            return False
        parts.append(part)

    combined = []
    for index, part in enumerate(parts):
        text = part.read_text(encoding="utf-8")
        combined.append(text if index == 0 else strip_yaml(text))
    output.write_text("\n\n---\n\n".join(combined), encoding="utf-8")
    return bool(output.stat().st_size)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--converter", type=Path, required=True)
    ap.add_argument("--model", help="opt-in Ollama vision model for figure descriptions")
    ap.add_argument("--ollama-host", default="http://host.orb.internal:11434")
    ap.add_argument("--image-ratio", type=float, default=0.6,
                    help="skip documents when this share of pages is image-dominant")
    ap.add_argument("--force", action="store_true",
                    help="reconvert every source and replace existing Markdown output")
    ap.add_argument("--resume-rebuild", action="store_true",
                    help="keep recorded successes/skips but replace unrecorded existing output")
    ap.add_argument("--max-file-size-mb", type=float,
                    help="skip sources larger than this decimal megabyte limit")
    args = ap.parse_args()

    source = args.source.resolve()
    target = args.target.resolve()
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    target.mkdir(parents=True, exist_ok=True)
    lock = (state / "batch.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another pdf2md batch is already running", file=sys.stderr)
        return 2

    files = sorted(
        (p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in {".pdf", ".epub"}),
        key=lambda p: str(p.relative_to(source)).casefold(),
    )
    stems = Counter(p.relative_to(source).with_suffix(".md") for p in files)
    records = state / "results.jsonl"
    successful = set()
    skipped_images = set()
    skipped_sizes = set()
    deduplicated = set()
    if records.exists():
        latest_records = {}
        for line in records.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            latest_records[record["source"]] = record
        for source_key, record in latest_records.items():
            if record.get("status") in {"ok", "ok_chunked"}:
                successful.add(source_key)
            elif record.get("status") == "skipped_images":
                skipped_images.add(source_key)
            elif record.get("status") == "skipped_size":
                skipped_sizes.add(source_key)
            elif record.get("status") == "deduplicated":
                deduplicated.add(source_key)

    print(f"Starting batch: {len(files)} files, {sum(n > 1 for n in stems.values())} name collisions", flush=True)
    for index, path in enumerate(files, 1):
        relative = path.relative_to(source)
        relative_md = relative.with_suffix(".md")
        if stems[relative_md] > 1:
            relative_md = relative.with_name(relative.name + ".md")
        output = target / relative_md
        key = relative.as_posix()
        max_bytes = (int(args.max_file_size_mb * 1_000_000)
                     if args.max_file_size_mb is not None else None)
        source_bytes = path.stat().st_size
        if max_bytes is not None and source_bytes > max_bytes:
            if output.exists():
                output.unlink()
            if key not in skipped_sizes:
                record = {"source": key, "output": relative_md.as_posix(),
                          "status": "skipped_size", "bytes": source_bytes,
                          "max_bytes": max_bytes, "timestamp": int(time.time())}
                with records.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[{index}/{len(files)}] skip over {args.max_file_size_mb:g} MB: {relative}",
                  flush=True)
            continue
        if not args.force and key in successful and output.is_file() and output.stat().st_size:
            continue
        if not args.force and key in skipped_images:
            continue
        if not args.force and key in deduplicated:
            continue
        if not args.force and not args.resume_rebuild and output.exists():
            print(f"[{index}/{len(files)}] skip existing: {relative_md}", flush=True)
            continue

        output.parent.mkdir(parents=True, exist_ok=True)
        log = state / "logs" / relative_md.with_suffix(".log")
        log.parent.mkdir(parents=True, exist_ok=True)
        command = converter_command(args.converter) + [str(path), "-o", str(output)]
        if path.suffix.lower() == ".pdf":
            figure_dir = target / ".figures" / relative_md.with_suffix("")
            audit_dir = state / "artifacts" / relative_md.with_suffix("")
            command += ["--figure-dir", str(figure_dir),
                        "--skip-mostly-images", str(args.image_ratio),
                        "--ocr", "auto", "--artifacts", str(audit_dir)]
            if args.model:
                command += ["--figure-vlm", args.model, "--ollama-host", args.ollama_host]

        print(f"[{index}/{len(files)}] {relative}", flush=True)
        started = time.time()
        with log.open("w", encoding="utf-8") as stream:
            stream.write("Command: " + " ".join(command) + "\n\n")
            stream.flush()
            try:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=4 * 60 * 60, check=False)
                code = result.returncode
                if code == 3:
                    status = "skipped_images"
                    if args.force and output.exists():
                        output.unlink()
                else:
                    status = "ok" if code == 0 and output.is_file() and output.stat().st_size else "failed"
            except subprocess.TimeoutExpired:
                code = 124
                status = "timeout"
            if status == "failed" and code == -9 and path.suffix.lower() == ".pdf":
                stream.write("Converter was killed; retrying in bounded page chunks.\n")
                stream.flush()
                if convert_chunked(path, output, relative_md, args, stream):
                    status = "ok_chunked"
        if status == "failed" and code == 1:
            diagnostic = log.read_text(encoding="utf-8", errors="replace")
            if "no text layer on" in diagnostic and "image-only scan" in diagnostic:
                status = "skipped_images"
                if output.exists():
                    output.unlink()
        record = {"source": key, "output": relative_md.as_posix(), "status": status,
                  "returncode": code, "seconds": round(time.time() - started, 1),
                  "log": str(log), "timestamp": int(time.time())}
        with records.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"  {status} ({record['seconds']}s)", flush=True)

    collision_groups = defaultdict(list)
    for path in files:
        relative = path.relative_to(source)
        if stems[relative.with_suffix(".md")] > 1:
            collision_groups[relative.with_suffix("")].append(path)
    for _, sources in sorted(collision_groups.items(), key=lambda item: str(item[0]).casefold()):
        candidates = []
        output_to_source = {}
        for source_path in sources:
            relative = source_path.relative_to(source)
            output = target / relative.with_name(relative.name + ".md")
            if output.is_file() and output.stat().st_size:
                candidates.append(output)
                output_to_source[output] = relative.as_posix()
        if len(candidates) < 2:
            continue
        kept, removed = choose_cleanest_markdown(candidates)
        for loser in removed:
            loser.unlink()
            record = {"source": output_to_source[loser],
                      "output": loser.relative_to(target).as_posix(),
                      "status": "deduplicated",
                      "kept": kept.relative_to(target).as_posix(),
                      "timestamp": int(time.time())}
            with records.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"deduplicate: kept {kept.relative_to(target)}, removed {loser.relative_to(target)}",
                  flush=True)

    print("Batch pass complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
