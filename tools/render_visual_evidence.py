#!/usr/bin/env python3
"""Render review overlays for uncertain figure evidence in visuals.json files."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pymupdf


def valid_bbox(value: object) -> bool:
    return (isinstance(value, list) and len(value) == 4
            and all(isinstance(point, (int, float)) and not isinstance(point, bool)
                    and math.isfinite(point) and 0 <= point <= 1 for point in value)
            and value[0] < value[2] and value[1] < value[3])


def render_overlay(image_path: Path, elements: list[dict], output_path: Path) -> None:
    with pymupdf.open(image_path) as source:
        if source.page_count != 1:
            raise ValueError("figure image did not open as one page")
        source_page = source[0]
        page_rect = source_page.rect
        with pymupdf.open() as overlay_doc:
            page = overlay_doc.new_page(width=page_rect.width, height=page_rect.height)
            page.insert_image(page.rect, filename=str(image_path))
            line_width = max(1.5, min(page_rect.width, page_rect.height) / 500)
            for index, element in enumerate(elements, start=1):
                left, top, right, bottom = element["bbox"]
                rect = pymupdf.Rect(left * page_rect.width, top * page_rect.height,
                                    right * page_rect.width, bottom * page_rect.height)
                color = ((0.85, 0.18, 0.12) if element["certainty"] == "uncertain"
                         else (0.95, 0.58, 0.05))
                page.draw_rect(rect, color=color, width=line_width)
                tag = pymupdf.Rect(rect.x0, max(0, rect.y0 - 16),
                                   min(page_rect.width, rect.x0 + 28),
                                   min(page_rect.height, max(0, rect.y0 - 16) + 16))
                page.draw_rect(tag, color=color, fill=color, width=0.5)
                page.insert_text((tag.x0 + 3, min(tag.y1 - 3, tag.y0 + 11)), str(index),
                                 fontsize=9, color=(1, 1, 1), fontname="helv")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            page.get_pixmap(alpha=False).save(str(output_path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="converted Markdown root containing .figures")
    parser.add_argument("--output", type=Path,
                        help="review output directory (default: ROOT/.visual-review)")
    parser.add_argument("--only", help="restrict to a substring of the relative figures folder")
    parser.add_argument("--uncertain-only", action="store_true",
                        help="exclude approximate elements and include only uncertain ones")
    parser.add_argument("--max-images", type=int, default=500,
                        help="maximum overlay images to render (default: 500)")
    args = parser.parse_args()
    if args.max_images < 1:
        parser.error("--max-images must be at least 1")

    root = args.root.resolve()
    figure_root = root / ".figures"
    if not figure_root.is_dir():
        parser.error(f"figure directory not found: {figure_root}")
    output_root = (args.output or root / ".visual-review").resolve()
    try:
        output_root.relative_to(figure_root.resolve())
    except ValueError:
        pass
    else:
        parser.error("--output must be outside the .figures directory")
    overlays = failures = 0
    capped = False

    for manifest in sorted(figure_root.rglob("visuals.json")):
        relative_folder = manifest.parent.relative_to(figure_root)
        if args.only and args.only.casefold() not in relative_folder.as_posix().casefold():
            continue
        try:
            records = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures += 1
            continue
        if not isinstance(records, list):
            failures += 1
            continue
        for record in records:
            if not isinstance(record, dict) or not isinstance(record.get("image"), str):
                continue
            evidence = record.get("evidence")
            if not isinstance(evidence, dict) or not isinstance(evidence.get("elements"), list):
                continue
            elements = []
            for item in evidence["elements"]:
                if not isinstance(item, dict) or not valid_bbox(item.get("bbox")):
                    continue
                certainty = item.get("certainty")
                if certainty == "direct":
                    continue
                certainty = certainty if certainty in {"approximate", "uncertain"} else "uncertain"
                if args.uncertain_only and certainty != "uncertain":
                    continue
                elements.append({**item, "certainty": certainty})
            if not elements:
                continue
            if overlays >= args.max_images:
                capped = True
                break

            image_path = (manifest.parent / record["image"]).resolve()
            try:
                image_path.relative_to(figure_root.resolve())
            except ValueError:
                failures += 1
                continue
            if not image_path.is_file():
                failures += 1
                continue

            output_dir = output_root / relative_folder
            output_image = output_dir / f"{image_path.stem}.review.png"
            output_data = output_dir / f"{image_path.stem}.review.json"
            review = {
                "source_image": image_path.relative_to(root).as_posix(),
                "visual_type": evidence.get("visual_type", ""),
                "elements": [
                    {"number": index, "kind": element.get("kind", "element"),
                     "label": element.get("label", ""),
                     "observation": element.get("observation", ""),
                     "certainty": element.get("certainty", "uncertain"),
                     "bbox": element["bbox"],
                     "page_bbox": element.get("page_bbox")}
                    for index, element in enumerate(elements, start=1)
                ],
            }
            try:
                render_overlay(image_path, elements, output_image)
                output_data.parent.mkdir(parents=True, exist_ok=True)
                output_data.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                                       encoding="utf-8")
                overlays += 1
            except (OSError, RuntimeError, ValueError):
                failures += 1
        if capped:
            break

    print(f"Overlays: {overlays}; failures: {failures}; output: {output_root}")
    if capped:
        print(f"Stopped at --max-images={args.max_images}; rerun with a higher limit for more.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
