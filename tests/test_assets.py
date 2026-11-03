import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_template_classes_all_defined_in_css():
    with open(os.path.join(ROOT, "templates", "index.html")) as f:
        template = f.read()
    with open(os.path.join(ROOT, "static", "style.css")) as f:
        css = f.read()

    used = set()
    for match in re.finditer(r'class="([^"]+)"', template):
        used.update(match.group(1).split())
    defined = set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", css))

    # pseudo-element/class fragments like "before" are not real classes
    missing = {c for c in used if c not in defined}
    assert not missing, f"template uses classes missing from CSS: {sorted(missing)}"
