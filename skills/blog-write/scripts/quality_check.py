#!/usr/bin/env python3
"""Phase 6 quality check for blog-write output.

Runs all post-draft checks the SKILL.md Phase 6 specifies:
- Word count and reading time
- Em dash count vs. 1-per-400-words budget
- Banned phrase and pattern scan (from skills/blog/references/banned-phrases.md)
- Structural presence: frontmatter, H1, FAQ, Sources, Medical Disclaimer
- Counts of [IMAGE NEEDED], [CITATION CAPSULE], internal-link zones, info-gain markers

Usage:
    python3 quality_check.py <path-to-markdown-file>
    python3 quality_check.py <path-to-markdown-file> --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BANNED_PHRASES_REL = Path("skills/blog/references/banned-phrases.md")

# Banned single words (matched as whole words, case-insensitive)
BANNED_WORDS = [
    "delve", "crucial", "elevate", "foster", "multifaceted", "robust",
    "tapestry", "embark", "additionally", "boasts", "bolstered",
    "emphasizing", "enhance", "fostering", "garner", "intricate",
    "interplay", "meticulous", "pivotal", "showcase", "testament",
    "underscore", "valuable", "vibrant", "journey", "empower",
    "empowering", "vital", "realm", "seamlessly", "revolutionize",
]

# Banned multi-word phrases / patterns (case-insensitive substring match)
BANNED_PHRASES = [
    "in today's digital landscape",
    "it's important to note",
    "dive into",
    "game-changer",
    "navigate the landscape",
    "harness the power of",
    "cutting-edge",
    "align with",
    "serves as",
    "stands as",
    "marks a pivotal moment",
    "reflects a broader trend",
    "serves as a testament",
    "highlights the importance",
    "stands as a reminder",
    "shapes the landscape",
    "leaves an indelible mark",
    "transformative power",
    "lasting impact",
    "enduring influence",
    "broader movement",
    "it's not just",
    "it's more than",
    "more than just",
    "isn't merely",
    "the real issue isn't",
    "at first glance",
]

# Contextual checks
LEVERAGE_PATTERN = re.compile(r"\bleverage\b", re.IGNORECASE)
KEY_VAGUE_PATTERN = re.compile(
    r"\bkey (takeaway|factor|insight|finding|element|aspect|point|player|driver)\b",
    re.IGNORECASE,
)
HIGHLIGHT_PATTERN = re.compile(r"\bhighlight(s|ed|ing)?\b", re.IGNORECASE)


def strip_code_and_svg(text: str) -> str:
    """Remove fenced code blocks and inline <svg>...</svg> for word counting."""
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"<svg\b.*?</svg>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    return text


def count_words(text: str) -> int:
    clean = strip_code_and_svg(text)
    tokens = re.findall(r"\b\w[\w'-]*\b", clean)
    return len(tokens)


def scan_banned(text: str) -> dict[str, list[dict]]:
    hits = {"words": [], "phrases": [], "contextual": []}

    for word in BANNED_WORDS:
        pat = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        matches = list(pat.finditer(text))
        if matches:
            hits["words"].append({"term": word, "count": len(matches)})

    for phrase in BANNED_PHRASES:
        pat = re.compile(re.escape(phrase), re.IGNORECASE)
        matches = list(pat.finditer(text))
        if matches:
            hits["phrases"].append({"term": phrase, "count": len(matches)})

    leverage = len(LEVERAGE_PATTERN.findall(text))
    if leverage:
        hits["contextual"].append({"term": "leverage (verb check needed)", "count": leverage})

    key_vague = len(KEY_VAGUE_PATTERN.findall(text))
    if key_vague:
        hits["contextual"].append({"term": "key (as vague intensifier)", "count": key_vague})

    highlight = len(HIGHLIGHT_PATTERN.findall(text))
    if highlight:
        hits["contextual"].append({"term": "highlight/highlights", "count": highlight})

    return hits


def check_structure(text: str) -> dict:
    return {
        "frontmatter": text.startswith("---\n"),
        "h1": bool(re.search(r"^# [^#]", text, re.MULTILINE)),
        "key_takeaways_box": "Key Takeaways" in text,
        "faq_section": bool(re.search(r"#+ (Frequently Asked Questions|FAQ)", text, re.IGNORECASE)),
        "sources_block": bool(re.search(r"#+ Sources", text, re.IGNORECASE)),
        "medical_disclaimer": bool(re.search(r"#+ Medical Disclaimer", text, re.IGNORECASE)),
    }


def count_markers(text: str) -> dict:
    return {
        "image_needed": len(re.findall(r"\[IMAGE NEEDED:", text)),
        "internal_link_zones": len(re.findall(r"\[INTERNAL-LINK:", text)),
        "citation_capsules": len(re.findall(r"\[CITATION CAPSULE", text)),
        "info_gain_original_data": len(re.findall(r"\[ORIGINAL DATA\]", text)),
        "info_gain_personal_experience": len(re.findall(r"\[PERSONAL EXPERIENCE\]", text)),
        "info_gain_unique_insight": len(re.findall(r"\[UNIQUE INSIGHT\]", text)),
        "svg_charts": len(re.findall(r"<svg\b", text, re.IGNORECASE)),
        "h2_sections": len(re.findall(r"^## [^#]", text, re.MULTILINE)),
    }


def emdash_budget(words: int) -> int:
    return max(1, words // 400)


def analyze(file_path: Path) -> dict:
    text = file_path.read_text(encoding="utf-8")
    words = count_words(text)
    em_dashes = text.count("—")
    budget = emdash_budget(words)

    markers = count_markers(text)
    info_gain_total = (
        markers["info_gain_original_data"]
        + markers["info_gain_personal_experience"]
        + markers["info_gain_unique_insight"]
    )

    return {
        "file": str(file_path),
        "word_count": words,
        "reading_time_min": round(words / 225),
        "em_dashes": {
            "count": em_dashes,
            "budget": budget,
            "status": "pass" if em_dashes <= budget else "fail",
        },
        "banned": scan_banned(text),
        "structure": check_structure(text),
        "markers": {**markers, "info_gain_total": info_gain_total},
    }


def render_report(result: dict) -> str:
    lines = []
    lines.append(f"=== QC REPORT: {result['file']} ===\n")
    lines.append(f"Word count: {result['word_count']} (~{result['reading_time_min']} min read)")
    ed = result["em_dashes"]
    lines.append(f"Em dashes: {ed['count']} / budget {ed['budget']} [{ed['status'].upper()}]")
    lines.append("")

    banned = result["banned"]
    total_banned = sum(len(v) for v in banned.values())
    lines.append(f"Banned scan: {total_banned} flagged term(s)")
    for category, items in banned.items():
        for item in items:
            lines.append(f"  [{category}] {item['term']} x{item['count']}")
    if total_banned == 0:
        lines.append("  (clean)")
    lines.append("")

    lines.append("Structure:")
    for key, present in result["structure"].items():
        mark = "PASS" if present else "MISSING"
        lines.append(f"  [{mark}] {key}")
    lines.append("")

    lines.append("Markers:")
    m = result["markers"]
    lines.append(f"  [IMAGE NEEDED] placeholders: {m['image_needed']}")
    lines.append(f"  [INTERNAL-LINK] zones: {m['internal_link_zones']}")
    lines.append(f"  [CITATION CAPSULE]: {m['citation_capsules']}")
    lines.append(f"  Info-gain markers: {m['info_gain_total']} "
                 f"(orig:{m['info_gain_original_data']} "
                 f"pe:{m['info_gain_personal_experience']} "
                 f"ui:{m['info_gain_unique_insight']})")
    lines.append(f"  Inline SVG charts: {m['svg_charts']}")
    lines.append(f"  H2 sections: {m['h2_sections']}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Path to the markdown file to check")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text report")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 2

    result = analyze(args.file)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_report(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())
