#!/usr/bin/env python3
"""
Tissue — Static Site Generator
MUG Edition (Model-User-Grokable)

## Mental Model

Tissue is a three-stage system:

1. Load:   Markdown + frontmatter → Page objects
2. Render: Page objects + templates → HTML strings
3. Write:  HTML + indexes → files on disk

The system is intentionally linear and explicit so that it can be
understood directly from source without external documentation.

## System Invariants

1. Every page must validate against FRONTMATTER_SCHEMA
2. All output paths must remain within BUILD_DIR
3. Templates must exist in TEMPLATE_DIR and match template_*.html
4. The system is a pure transformation:
   markdown → structured pages → rendered HTML
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
from typing import TypedDict, List

VERBOSE = True

# ------------------------------------------------------------

# Configuration

# ------------------------------------------------------------

ROOT_DIR = Path(**file**).resolve().parent

MARKDOWN_DIR  = ROOT_DIR / "markdown"
BUILD_DIR     = ROOT_DIR / "public"
TEMPLATE_DIR  = ROOT_DIR / "templates"
STATIC_DIR    = ROOT_DIR / "static"

sitemap_path       = BUILD_DIR / "sitemap.xml"
sitemap_base_url   = os.getenv("TISSUE_SITEMAP_BASE_URL", "https://kogswellcycles.com")

# ------------------------------------------------------------

# Data Model

# ------------------------------------------------------------

class Page(TypedDict):
title: str
desc: str
image: str
template: str
permalink: str
content: str
section: str
exclude: List[str]

# ------------------------------------------------------------

# Frontmatter Schema

# ------------------------------------------------------------

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

# Utilities (System Rules)

# ------------------------------------------------------------

def assert_within_build_dir(path: Path):
build_root = BUILD_DIR.resolve()
if build_root not in path.parents and path != build_root:
raise ValueError(f"Path escapes build directory: {path}")

def parse_exclude_values(raw):
if raw is None:
return []
if isinstance(raw, list):
return [str(v) for v in raw]
return []

# ------------------------------------------------------------

# Validation

# ------------------------------------------------------------

def validate_template_value(value, filepath):
if (
not value.startswith("template_")
or not value.endswith(".html")
or "/" in value
or "\" in value
or ".." in value
):
return [f"❌ Invalid template in {filepath}: {value}"]

```
if not (TEMPLATE_DIR / value).is_file():
    return [f"❌ Template not found for {filepath}: {value}"]

return []
```

def validate_exclude_value(value, filepath):
exclude_values = parse_exclude_values(value)
invalid = [v for v in exclude_values if v not in VALID_EXCLUDE_VALUES]
if invalid:
return [f"❌ Invalid exclude values in {filepath}: {', '.join(invalid)}"]
return []

def validate_frontmatter(metadata, filepath):
errors = []

```
unknown = set(metadata.keys()) - KNOWN_KEYS
if unknown:
    errors.append(f"❌ Unknown keys in {filepath}: {', '.join(sorted(unknown))}")

for key, rule in FRONTMATTER_SCHEMA.items():
    required = rule.get("required", False)
    expected_type = rule.get("type")

    if required and key not in metadata:
        errors.append(f"❌ Missing required key in {filepath}: {key}")
        continue

    value = metadata.get(key)

    if expected_type and value is not None and not isinstance(value, expected_type):
        errors.append(f"❌ Invalid type for {key} in {filepath}")
        continue

    if key == "template" and isinstance(value, str):
        errors.extend(validate_template_value(value, filepath))

    if key == "exclude" and isinstance(value, list):
        errors.extend(validate_exclude_value(value, filepath))

for err in errors:
    print(err)

return not errors
```

# ------------------------------------------------------------

# Phase 1 — Load

# ------------------------------------------------------------

def generate_permalink(md_path: Path) -> str:
rel = md_path.relative_to(MARKDOWN_DIR)
if rel.as_posix() == "index.md":
return "/"
return "/" + rel.with_suffix("").as_posix() + "/"

def load_pages() -> List[Page]:
"""
Markdown files → Page objects
"""
pages = []
invalid_pages = 0

```
for md_path in MARKDOWN_DIR.rglob("*.md"):
    page = frontmatter.load(md_path)

    if not validate_frontmatter(page.metadata, md_path):
        invalid_pages += 1
        continue

    # Markdown → HTML
    html = markdown.markdown(page.content)

    section = md_path.relative_to(MARKDOWN_DIR).parent.name or "root"

    pages.append({
        "title": page.get("title"),
        "desc": page.get("desc"),
        "image": page.get("image"),
        "template": page.get("template"),
        "permalink": page.get("permalink") or generate_permalink(md_path),
        "content": html,
        "section": section,
        "exclude": parse_exclude_values(page.get("exclude")),
    })

if invalid_pages:
    raise ValueError(f"Build halted: {invalid_pages} invalid pages.")

return pages
```

# ------------------------------------------------------------

# Phase 2 — Render

# ------------------------------------------------------------

def create_environment():
return Environment(
loader=FileSystemLoader(TEMPLATE_DIR),
trim_blocks=True,
lstrip_blocks=True
)

def safe_output_path(permalink: str) -> Path:
build_root = BUILD_DIR.resolve()

```
if permalink == "/":
    return build_root / "index.html"

rel = permalink.strip("/")
out_path = (build_root / rel)

if out_path.suffix == "":
    out_path = out_path / "index.html"

out_path = out_path.resolve()
assert_within_build_dir(out_path)

return out_path
```

def render_pages_to_files(pages: List[Page], env: Environment):
"""
Page objects → HTML files
"""
template_all_pages = [p for p in pages if "all_pages" not in p["exclude"]]

```
for page in pages:
    template = env.get_template(page["template"])

    # Page → Rendered HTML
    rendered = template.render(
        this_page=page,
        all_pages=template_all_pages,
        **page
    )

    out_path = safe_output_path(page["permalink"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")

    if VERBOSE:
        print(f"📝 {out_path.relative_to(BUILD_DIR)}")
```

# ------------------------------------------------------------

# Phase 3 — Write Outputs

# ------------------------------------------------------------

def write_search_index(pages: List[Page]):
search_pages = []

```
for p in pages:
    # Any exclusion removes page from search index
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
path.write_text(json.dumps(search_pages, indent=2), encoding="utf-8")

print(f"🔍 search_index.json ({len(search_pages)} pages)")
```

def write_sitemap(pages: List[Page]):
entries = []

```
for p in pages:
    if "sitemap" in p["exclude"]:
        continue

    url = sitemap_base_url.rstrip("/") + p["permalink"]
    entries.append(f"<url><loc>{xml_escape(url)}</loc></url>")

content = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + "\n".join(entries) +
    "\n</urlset>\n"
)

sitemap_path.write_text(content, encoding="utf-8")
print(f"🗺️ sitemap.xml ({len(entries)} URLs)")
```

# ------------------------------------------------------------

# Build Preparation

# ------------------------------------------------------------

def prepare_build_dir():
if BUILD_DIR.exists():
shutil.rmtree(BUILD_DIR)
BUILD_DIR.mkdir(parents=True)

def prerender_partials():
partial_src = TEMPLATE_DIR / "markdown_partials"
if not partial_src.exists():
return

```
for md_file in partial_src.glob("*.md"):
    html = markdown.markdown(md_file.read_text(encoding="utf-8"))
    out = TEMPLATE_DIR / f"partial_{md_file.stem}.html"
    out.write_text(html, encoding="utf-8")

    if VERBOSE:
        print(f"🧩 partial: {out.name}")
```

def copy_static():
if STATIC_DIR.exists():
shutil.copytree(STATIC_DIR, BUILD_DIR / "static")
if VERBOSE:
print("📁 static copied")

# ------------------------------------------------------------

# Checks

# ------------------------------------------------------------

def check_sitemap_base_url():
parsed = urlparse(sitemap_base_url)

```
if not parsed.scheme or not parsed.netloc:
    raise ValueError("Invalid sitemap_base_url")

host = (parsed.hostname or "").lower()

if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
    print("⚠️ sitemap_base_url is local")
```

# ------------------------------------------------------------

# Main (Pipeline)

# ------------------------------------------------------------

def main():
prepare_build_dir()
prerender_partials()
copy_static()
check_sitemap_base_url()

```
pages = load_pages()

print(f"\nPages: {len(pages)}")

env = create_environment()

render_pages_to_files(pages, env)
write_search_index(pages)
write_sitemap(pages)

print("\n✨ Tissue build complete.\n")
```

if **name** == "**main**":
main()
