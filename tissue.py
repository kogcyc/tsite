#!/usr/bin/env python3
"""
Tissue — Static Site Generator
Council of Portland Edition (2025)
With Homepage Support
"""

import json
import os
import shutil
import frontmatter
import markdown
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape as xml_escape
from jinja2 import Environment, FileSystemLoader

VERBOSE = True

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent

MARKDOWN_DIR  = ROOT_DIR / "markdown"
BUILD_DIR     = ROOT_DIR / "public"
TEMPLATE_DIR  = ROOT_DIR / "templates"
STATIC_DIR    = ROOT_DIR / "static"

# Sitemap settings — e.g. "https://example.com"
sitemap_path       = BUILD_DIR / "sitemap.xml"
sitemap_base_url   = os.getenv("TISSUE_SITEMAP_BASE_URL", "https://kogswellcycles.com")

# Frontmatter keys
VALID_EXCLUDE_VALUES = {"all_pages", "section", "sitemap", "search"}
FRONTMATTER_SCHEMA = {
    "title": {"required": True, "type": str},
    "desc": {"required": True, "type": str},
    "image": {"required": True, "type": str},
    "template": {"required": True, "type": str},
    "permalink": {"required": False, "type": str},
    "exclude": {"required": False, "type": list},
}
KNOWN_KEYS = set(FRONTMATTER_SCHEMA.keys())


# ------------------------------------------------------------
# Validate frontmatter
# ------------------------------------------------------------

def validate_template_value(value, filepath):
    if (
        not value.startswith("template_")
        or not value.endswith(".html")
        or "/" in value
        or "\\" in value
        or ".." in value
    ):
        return [
            f"❌ Invalid template name in {filepath}: {value} "
            "(must match template_*.html in templates/)"
        ]

    if not (TEMPLATE_DIR / value).is_file():
        return [f"❌ Template not found for {filepath}: {value}"]

    return []


def validate_exclude_value(value, filepath):
    exclude_values = parse_exclude_values(value)
    invalid_exclude = [v for v in exclude_values if v not in VALID_EXCLUDE_VALUES]
    if invalid_exclude:
        return [
            f"❌ Invalid exclude values in {filepath}: {', '.join(invalid_exclude)} "
            f"(valid: {', '.join(sorted(VALID_EXCLUDE_VALUES))})"
        ]
    return []


def validate_frontmatter(metadata, filepath):
    errors = []

    unknown = set(metadata.keys()) - KNOWN_KEYS
    if unknown:
        errors.append(f"❌ Unknown frontmatter keys in {filepath}: {', '.join(sorted(unknown))}")

    for key, rule in FRONTMATTER_SCHEMA.items():
        required = rule.get("required", False)
        expected_type = rule.get("type")
        has_key = key in metadata

        if required and not has_key:
            errors.append(f"❌ Missing required key in {filepath}: {key}")
            continue
        if not has_key:
            continue

        value = metadata.get(key)
        if expected_type and value is not None and not isinstance(value, expected_type):
            errors.append(
                f"❌ Invalid type for {key} in {filepath}: "
                f"expected {expected_type.__name__}"
            )
            continue

        if key == "template" and isinstance(value, str):
            errors.extend(validate_template_value(value, filepath))
        if key == "exclude" and isinstance(value, list):
            errors.extend(validate_exclude_value(value, filepath))

    for err in errors:
        print(err)
    return not errors


def parse_exclude_values(raw_exclude):
    if raw_exclude is None:
        return []
    if isinstance(raw_exclude, list):
        return [str(v) for v in raw_exclude]
    return []


# ------------------------------------------------------------
# Generate permalink (homepage special case if index.md)
# ------------------------------------------------------------

def generate_permalink(md_path):
    rel = md_path.relative_to(MARKDOWN_DIR)
    if rel.as_posix() == "index.md":
        return "/"
    return "/" + rel.with_suffix("").as_posix() + "/"


# ------------------------------------------------------------
# Prerender markdown partials to templates
# ------------------------------------------------------------

def prerender_partials():
    partial_src = TEMPLATE_DIR / "markdown_partials"
    if not partial_src.exists():
        return

    for md_file in partial_src.glob("*.md"):
        html = markdown.markdown(md_file.read_text(encoding="utf-8"))
        out  = TEMPLATE_DIR / f"partial_{md_file.stem}.html"
        out.write_text(html, encoding="utf-8")
        if VERBOSE:
            print(f"🧩 Pre-rendered partial: {out.relative_to(TEMPLATE_DIR)}")


# ------------------------------------------------------------
# Prepare the build directory
# ------------------------------------------------------------

def prepare_build_dir():
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    BUILD_DIR.mkdir(parents=True)


# ------------------------------------------------------------
# Copy static assets
# ------------------------------------------------------------

def copy_static():
    if STATIC_DIR.exists():
        shutil.copytree(STATIC_DIR, BUILD_DIR / "static")
        if VERBOSE:
            print("📁 Copied static assets.")
    else:
        print("⚠️  No static directory found.")


# ------------------------------------------------------------
# Build index of Markdown pages
# ------------------------------------------------------------

def build_index():
    index = []
    invalid_pages = 0

    for md_path in MARKDOWN_DIR.rglob("*.md"):
        page = frontmatter.load(md_path)

        valid = validate_frontmatter(page.metadata, md_path)
        if not valid:
            invalid_pages += 1
            continue

        html    = markdown.markdown(page.content)
        section = md_path.relative_to(MARKDOWN_DIR).parent.name or "root"
        exclude = parse_exclude_values(page.get("exclude", []))

        index.append({
            "title": page.get("title"),
            "desc":  page.get("desc"),
            "image": page.get("image"),
            "template": page.get("template", "template_default.html"),
            "permalink": page.get("permalink") or generate_permalink(md_path),
            "content": html,
            "section": section,
            "exclude": exclude,
        })

    if invalid_pages:
        raise ValueError(f"Build halted: {invalid_pages} page(s) failed validation.")

    return index


def safe_output_path(permalink):
    build_root = BUILD_DIR.resolve()

    if permalink == "/":
        return build_root / "index.html"

    rel = permalink.strip("/")
    out_path = (build_root / rel).resolve()

    # Ensure user-provided permalink cannot escape BUILD_DIR.
    if build_root not in out_path.parents and out_path != build_root:
        raise ValueError(f"Invalid permalink escapes build directory: {permalink}")

    if out_path.suffix == "":
        out_path = out_path / "index.html"

    out_path = out_path.resolve()
    if build_root not in out_path.parents and out_path != build_root:
        raise ValueError(f"Invalid permalink escapes build directory: {permalink}")

    return out_path


# ------------------------------------------------------------
# Render pages
# ------------------------------------------------------------

def render_pages(all_pages, env):
    template_all_pages = [p for p in all_pages if "all_pages" not in p["exclude"]]

    for page in all_pages:
        template = env.get_template(page["template"])

        rendered = template.render(
            this_page=page,
            all_pages=template_all_pages,
            **page
        )

        out_path = safe_output_path(page["permalink"])

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")

        if VERBOSE:
            print(f"📝 Rendered page: {out_path.relative_to(BUILD_DIR)}")


# ------------------------------------------------------------
# Search index
# ------------------------------------------------------------

def generate_search_index(all_pages):
    search_pages = []
    for p in all_pages:
        # Any excluded page is removed from the search index.
        if p["exclude"]:
            continue
        search_pages.append({
            "title": p["title"],
            "desc": p["desc"],
            "image": p["image"],
            "permalink": p["permalink"],
            "section": p["section"],
            "content": p["content"],
        })

    path = BUILD_DIR / "search_index.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(search_pages, f, indent=2)
    print(f"🔍 search_index.json written ({len(search_pages)} pages).")


# ------------------------------------------------------------
# Sitemap
# ------------------------------------------------------------

def generate_sitemap(all_pages):
    entries = []
    for p in all_pages:
        if "sitemap" in p["exclude"]:
            continue
        url = sitemap_base_url.rstrip("/") + p["permalink"]
        safe_url = xml_escape(url)
        entries.append(f"<url><loc>{safe_url}</loc></url>")

    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries) +
        "\n</urlset>\n"
    )
    sitemap_path.write_text(content, encoding="utf-8")
    print(f"🗺️  sitemap.xml written ({len(entries)} URLs).")


def check_sitemap_base_url():
    parsed = urlparse(sitemap_base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(
            "Invalid sitemap_base_url. Set TISSUE_SITEMAP_BASE_URL to a full URL, "
            "for example https://example.com"
        )

    host = (parsed.hostname or "").lower()
    is_local = host in {"localhost", "127.0.0.1", "0.0.0.0"}
    if is_local:
        message = (
            "⚠️  sitemap_base_url points to localhost. This is fine for local testing, "
            "but harms SEO if published. Set TISSUE_SITEMAP_BASE_URL to your public domain."
        )
        if os.getenv("TISSUE_STRICT_SITEMAP", "0") == "1":
            raise ValueError(message)
        print(message)


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    prepare_build_dir()
    prerender_partials()
    copy_static()
    check_sitemap_base_url()

    # trim_blocks & lstrip_blocks produce cleaner output
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        trim_blocks=True,
        lstrip_blocks=True
    )

    all_pages = build_index()

    print(f"\nPages processed: {len(all_pages)}")

    if any(p["permalink"] == "/" for p in all_pages):
        print("🏠 Homepage detected (markdown/index.md → public/index.html)")
    else:
        print("⚠️  No homepage found (missing markdown/index.md)")

    render_pages(all_pages, env)
    generate_search_index(all_pages)
    generate_sitemap(all_pages)

    print("\n✨ Tissue build complete.\n")
    return all_pages


if __name__ == "__main__":
    main()
