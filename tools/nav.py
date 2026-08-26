# -*- coding: utf-8 -*-
"""The kit's cross-page navigation rail, in one place.

Fifteen instrument pages each carried a hand-maintained rail of chips. Measured
before this file existed, they were badly out of step: Micro Bench appeared in
4 of the 15 rails and Cell Bench in 4, so a student on one bench could not
reach the other; rails ranged from 9 chips to 18; and every new page meant
fifteen edits with fifteen chances to miss one. That is precisely the failure
ADR-031 named for entry controls, one layer up.

The fix is the same one: a single source, and a regenerator (tools/nav_emit.py)
that is the only writer.

Adding a page to the kit is now one line in GROUPS.
"""
VERSION = "1.0.0"

# (href, icon, label). Order and grouping follow the hub's own four groups, so
# a reader who learned the hub does not have to learn a second taxonomy.
GROUPS = [
    ("Record it — in the field", [
        ("field-notebook.html",    "\U0001F4D3", "Field Notebook"),
        ("ethogram.html",          "\U0001F43E", "Ethogram"),
        ("selection-log.html",     "\U0001F4CF", "Selection Log"),
        ("stand-sheet.html",       "\U0001F332", "Stand Sheet"),
        ("releve.html",            "\U0001F33E", "Relevé"),
        ("collection-sheet.html",  "\U0001F344", "Collection Sheet"),
        ("farm-scout.html",        "\U0001F9D1‍\U0001F33E", "Farm Scout"),
        ("pheno-tracker.html",     "\U0001F331", "Pheno Tracker"),
        ("deployment-log.html",    "\U0001F399\uFE0F", "Deployment Log"),
    ]),
    ("At the bench", [
        ("cp-bench.html",          "\U0001FAD9", "CP Bench"),
        ("soil-bench.html",        "\U0001FAB1", "Soil Bench"),
        ("breeding-bench.html",    "\U0001F955", "Breeding Bench"),
        ("cell-bench.html",        "\U0001F52C", "Cell Bench"),
        ("micro-bench.html",       "\U0001F9EB", "Micro Bench"),
    ]),
    ("Analyse it", [
        ("survey-design.html",     "\U0001F9ED", "Survey Design"),
        ("ordination.html",        "\U0001F4C9", "Ordination"),
        ("food-web.html",          "\U0001F578️", "Food Web Builder"),
        ("field-season.html",      "\U0001F3AF", "Field Season"),
    ]),
    ("Print it", [
        ("plant-characters.html",  "\U0001F331", "Plant Characters"),
        ("fungal-characters.html", "\U0001F52C", "Fungal Characters"),
        ("cp-characters.html",     "\U0001FAA4", "CP Characters"),
    ]),
]

# Plain text links, no icon, kept last. These are references rather than
# instruments and are styled quietly on purpose.
REFS = [
    ("ecology.html",             "← kit hub"),
    ("ecology-field-card.html",  "field card"),
    ("ecology-glossary.html",    "glossary"),
]

# Three refs for every page erased a fourth that some pages had: an "up to the
# suite" link. The published Soil Bench still carries "↑ Soil & compost suite";
# the repo copy lost it the day the rail became generated, because the generator
# had no concept of a page-specific ref. Nobody noticed until a republish
# compared the two. Generated navigation is only as good as what the generator
# knows about, and it did not know about this.
#
# A suite is a page's parent, not a sibling: it belongs above the hub link.
UP = {}
for _suite, _label, _members in [
    ("soil-suite.html",     "↑ Soil &amp; compost suite",
     ["soil-bench.html"]),
    # cp-characters is a chip IN the rail but carries no rail of its own, so an
    # entry for it here would be config that can never fire. Left out on purpose.
    ("cp-suite.html",       "↑ Carnivorous plant suite",
     ["cp-bench.html"]),
    ("breeding-suite.html", "↑ Breeding suite",
     ["breeding-bench.html", "selection-log.html"]),
]:
    for _m in _members:
        UP[_m] = (_suite, _label)


def hrefs():
    out = [h for _, chips in GROUPS for h, _, _ in chips]
    return out + [h for h, _ in REFS] + [h for h, _ in UP.values()]


def rail(current=None):
    """The rail markup for one page. `current` marks its own chip.

    The group headings after the first carry an inline top margin rather than a
    class, because a class would mean a CSS edit in all fifteen consumers and
    this file cannot reach their stylesheets. Generated markup, one reason,
    written down.
    """
    L = ['<div class="rail">']
    for gi, (title, chips) in enumerate(GROUPS):
        style = ' style="margin-top:16px"' if gi else ""
        L.append('  <p class="rl"%s>%s</p>' % (style, title))
        L.append('  <div class="chips">')
        for href, icon, label in chips:
            cur = ' aria-current="page"' if href == current else ""
            L.append('    <a href="%s"%s><span>%s</span>%s</a>' % (href, cur, icon, label))
        L.append('  </div>')
    L.append('  <div class="chips" style="margin-top:16px">')
    for href, label in ([UP[current]] if current in UP else []) + REFS:
        cur = ' aria-current="page"' if href == current else ""
        L.append('    <a class="ref" href="%s"%s>%s</a>' % (href, cur, label))
    L.append('  </div>')
    L.append('</div>')
    return "\n".join(L)
