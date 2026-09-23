#!/usr/bin/env python3
"""Build or check public/claims-source.json from data-claim markers in index.html.

Edit claims in index.html, then run:
  python3 scripts/build_claims_source.py --write
The Pages workflow runs --check so the JSON cannot drift from the page.
"""

from __future__ import annotations

import argparse
import json
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "index.html"
JSON_PATH = ROOT / "public" / "claims-source.json"

FACT_FIELDS = {
    "verified_purpose",
    "verified_implemented_functions",
    "verified_technologies",
    "verified_architecture",
    "verified_testing_evidence",
    "verified_metrics",
    "verified_limitations",
    "verified_maturity",
    "verified_public_safe_facts",
    "recommended_interview_talking_points",
    "do_not_claim",
    "maturity_label",
    "fact_locked_at",
}

POLARITIES = {"assertion", "denial", "limitation", "caveat", "constraint", "bounded"}

# Fragments that must only appear inside an element whose polarity is allowed.
SENSITIVE = {
    "PRODUCTION": {"denial", "limitation", "constraint"},
    "800/800": {"denial", "limitation"},
    "15/15": {"denial"},
    "67 tests": {"denial"},
    "251": {"denial", "limitation"},
    "Manual J": {"limitation", "denial"},
    "leaderboard": {"limitation", "denial"},
    "offline after first load": {"limitation", "denial"},
    "Play Store": {"denial", "limitation", "constraint"},
    "Play-ready": {"denial"},
    "LAANC": {"denial", "limitation", "bounded"},
    "real bets": {"denial", "bounded"},
    "761/761": {"caveat", "denial"},
}

MATURITY = {
    "local-llm-benchmark": "ADVANCED PROTOTYPE",
    "bruno-ac-pwa": "WORKING APPLICATION",
    "propeller-calculator": "WORKING APPLICATION",
    "bruno-electric-pwa": "WORKING APPLICATION",
    "casino-game-analytics": "WORKING APPLICATION",
    "drone-pilot-usa": "ADVANCED PROTOTYPE",
    "uas-stage1-app": "EARLY DEVELOPMENT",
}

ARTICLE_ORDER = [
    ("local-llm-benchmark", "centerpiece"),
    ("bruno-ac-pwa", "featured"),
    ("propeller-calculator", "featured"),
    ("bruno-electric-pwa", "featured"),
    ("casino-game-analytics", "mention"),
    ("drone-pilot-usa", "mention"),
    ("uas-stage1-app", "mention"),
]

BADGE_TEXT = {
    "llm.badge.maturity": "ADVANCED PROTOTYPE",
    "ac.badge.maturity": "WORKING APPLICATION",
    "prop.badge.maturity": "WORKING APPLICATION",
    "elec.badge.maturity": "WORKING APPLICATION",
    "casino.badge.maturity": "WORKING APPLICATION",
    "drone.badge.maturity": "ADVANCED PROTOTYPE",
    "uas.badge.maturity": "EARLY DEVELOPMENT",
}

PINS = {
    "local-llm-benchmark": "9c3ffa05fd0162b79c0b86cf18ea4679eb4868eb",
    "bruno-ac-pwa": "c410f9d12ca5c0e4c0fdf0e2f36569af73657039",
    "propeller-calculator": "781fba90d5d807d183937f58b1ed1d9a722c1ad2",
    "bruno-electric-pwa": "227d1eee6117c4f7af7b1d205c3061278162e939",
    "casino-game-analytics": "3cca344a08ac1a22f3fae71c46e9ace2052d3faa",
    "drone-pilot-usa": "c422c6fbeb0f6cea6b1c4ea815efa724b75dbd38",
    "uas-stage1-app": "e50f80f7e51f702dc1af3f275d916194fe0a1675",
}

DO_NOT_CLAIM = {
    "local-llm-benchmark": [
        "Raw results.jsonl published for independent recomputation",
        "Full planned away matrix completed in the night run",
        "251 / 286 / 385 pytest tests verified green at HEAD",
        "Production SaaS / multi-tenant / cross-OS portable product",
        "Definitive multi-hardware leaderboard rankings",
        "WORKING APPLICATION maturity",
        "One generator script per HOME without noting gen_home_11.py missing",
        "PR #1 recruiter README is merged onto main",
    ],
    "bruno-ac-pwa": [
        "PRODUCTION / multi-user cloud backend",
        "Manual J/S/D or code-compliant tonnage-from-sqft",
        "Full node unit suite green in permanent pin CI",
        "SW cache version docs already consistent (v4/v64/v31)",
        "No CSP at all (meta CSP exists)",
        "Subject PR #26 features are on pin",
        "Payroll figures are tax-compliant withholding software",
    ],
    "propeller-calculator": [
        "PRODUCTION maturity",
        "Live-verified EXE runtime or live DB COUNT from release zip this session",
        "CI-green builds",
        "Signed Windows distribution",
        "Invented AI tool identity",
        "Cavitation-accurate water/marine modeling",
    ],
    "bruno-electric-pwa": [
        "Works offline after first load",
        "CI capability-gates green for pin 227d1eee…",
        "Playwright e2e pass counts verified at pin",
        "800/800 or similar metrics from PR #15 / older audits",
        "Texas document compliance from unmerged PR #12",
        "Production multi-user backend",
        "Auditor independently re-verified 761/761",
    ],
    "casino-game-analytics": [
        "Real-money betting, payments, or predictive gambling advice",
        "Full baccarat roadmap suite as live predictive UI",
        "pytest green / 67 tests as current verified HEAD metric",
        "CI-verified builds at pin",
        "Live casino production deployment",
        "Multi-user auth / cloud SaaS",
        "PRODUCTION maturity",
    ],
    "drone-pilot-usa": [
        "PRODUCTION maturity or Play Store release readiness",
        "Live LAANC / airspace / TFR authorization",
        "CI-verified green smoke/APK at pin",
        "Official FAA exam or affiliation",
        "Offline-first map (tiles/search/weather need network)",
        "PR #1 docs README is on main",
    ],
    "uas-stage1-app": [
        "WORKING APPLICATION as default employment maturity without CI-YAML caveats",
        "Conventional checked-in Android app/ tree at pin",
        "Signed release / Play distribution",
        "Automated functional or device UX verification",
        "Flight-critical or certified training software",
    ],
}

ALLOWED_EXTERNAL = {"https://github.com/kot0070"}
ASSERTION_POLARITIES = {"assertion"}


def normalize(text: str) -> str:
    return " ".join(text.split())


class Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[dict] = []
        self.claims: list[dict] = []
        self.articles: list[dict] = []
        self.errors: list[str] = []
        self.seen_ids: set[str] = set()
        self.sensitive_hits: list[tuple[str, str, int]] = []
        self.tags_seen: set[str] = set()
        self.hrefs: list[tuple[str, int]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v if v is not None else "") for k, v in attrs}
        node = {"tag": tag, "attrs": ad}
        self.stack.append(node)
        self.tags_seen.add(tag)
        href = ad.get("href")
        if href:
            self.hrefs.append((href, self.getpos()[0]))
        if tag == "article" and ad.get("data-project"):
            self.articles.append(
                {
                    "project": ad["data-project"],
                    "role": ad.get("data-role", ""),
                    "maturity": ad.get("data-maturity", ""),
                    "line": self.getpos()[0],
                }
            )
        if "data-claim" in ad:
            if any(item.get("capture") for item in self.stack[:-1]):
                self.errors.append(
                    f"Nested data-claim {ad['data-claim']!r} at line {self.getpos()[0]}"
                )
            node["capture"] = {
                "id": ad["data-claim"],
                "depth": len(self.stack),
                "parts": [],
                "line": self.getpos()[0],
            }
        if tag in VOID_TAGS:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            self.errors.append(f"Unexpected </{tag}> at line {self.getpos()[0]}")
            return
        node = self.stack[-1]
        capture = node.get("capture")
        if capture and len(self.stack) == capture["depth"]:
            self._finish(capture)
        if node["tag"] != tag:
            self.errors.append(
                f"End tag </{tag}> does not match <{node['tag']}> at line {self.getpos()[0]}"
            )
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        polarity = self._polarity()
        if any(item.get("capture") for item in self.stack):
            for item in reversed(self.stack):
                if item.get("capture"):
                    item["capture"]["parts"].append(data)
                    break
        lowered = data
        for token, allowed in SENSITIVE.items():
            if token in lowered and polarity not in allowed:
                self.sensitive_hits.append((token, polarity, self.getpos()[0]))

    def _attr(self, key: str) -> str | None:
        for node in reversed(self.stack):
            if key in node["attrs"] and node["attrs"][key] != "":
                return node["attrs"][key]
        return None

    def _polarity(self) -> str:
        for node in reversed(self.stack):
            if node["attrs"].get("data-polarity"):
                return node["attrs"]["data-polarity"]
        return "unscoped"

    def _anchor(self) -> str | None:
        for node in reversed(self.stack):
            if node["attrs"].get("id"):
                return node["attrs"]["id"]
        return None

    def _finish(self, capture: dict) -> None:
        cid = capture["id"]
        if cid in self.seen_ids:
            self.errors.append(f"Duplicate data-claim id {cid}")
        self.seen_ids.add(cid)
        text = normalize("".join(capture["parts"]))
        if not text:
            self.errors.append(f"Empty claim text for {cid}")
        fields_raw = self._attr("data-fields")
        if not fields_raw:
            self.errors.append(f"{cid} is missing data-fields")
            fields: list[str] = []
        else:
            fields = fields_raw.split()
        polarity = self._attr("data-polarity") or "assertion"
        if polarity not in POLARITIES:
            self.errors.append(f"{cid} has unknown polarity {polarity}")
        sources = []
        raw_sources = self._attr("data-sources")
        if raw_sources:
            sources = [part.strip() for part in raw_sources.split("|") if part.strip()]
        projects = []
        raw_projects = self._attr("data-project")
        if raw_projects:
            projects = raw_projects.split()
        if fields == ["selection"]:
            fact_fields: list[str] = []
            backing = "PORTFOLIO_SELECTION"
            if not sources:
                self.errors.append(f"{cid} uses selection backing but has no data-sources")
        else:
            fact_fields = fields
            backing = "FINAL_PROJECT_FACTS"
            unknown = [field for field in fields if field not in FACT_FIELDS]
            if unknown:
                self.errors.append(f"{cid} has unknown fact fields {unknown}")
        for slug in projects:
            if slug not in MATURITY:
                self.errors.append(f"{cid} names unknown project {slug}")
        raw_denies = self._attr("data-denies")
        denies = [part.strip() for part in raw_denies.split("||")] if raw_denies else []
        self.claims.append(
            {
                "id": cid,
                "html_anchor": self._anchor(),
                "line": capture["line"],
                "project_slugs": projects,
                "backing": backing,
                "fact_lock_fields": fact_fields,
                "sources": sources,
                "polarity": polarity,
                "denies": denies,
                "note": self._attr("data-note"),
                "text": text,
            }
        )


def _must_contain(claims: dict[str, dict], cid: str, snippets: list[str], errors: list[str]) -> None:
    claim = claims.get(cid)
    if not claim:
        errors.append(f"Missing required claim {cid}")
        return
    text = claim["text"]
    for snippet in snippets:
        if snippet not in text:
            errors.append(f"{cid} does not contain {snippet!r}")


def validate(extracted: Extractor) -> list[str]:
    errors = list(extracted.errors)
    by_id = {claim["id"]: claim for claim in extracted.claims}
    if len(by_id) != len(extracted.claims):
        errors.append("Claim id collision")

    got = [(item["project"], item["role"], item["maturity"]) for item in extracted.articles]
    expected = [(slug, role, MATURITY[slug]) for slug, role in ARTICLE_ORDER]
    if got != expected:
        errors.append(f"Article order/maturity/role mismatch.\n expected {expected}\n got {got}")

    for cid, label in BADGE_TEXT.items():
        claim = by_id.get(cid)
        if not claim:
            errors.append(f"Missing maturity badge claim {cid}")
        elif claim["text"] != label:
            errors.append(f"{cid} text {claim['text']!r} != {label!r}")

    _must_contain(by_id, "elec.offline", ["not supported", "retired", "online"], errors)
    _must_contain(
        by_id,
        "ac.limit.docgap",
        ["bruno-ac-v4", "bruno-ac-v64", "bruno-ac-v31", "not a strength"],
        errors,
    )
    _must_contain(by_id, "prop.metric.counts", ["1053", "335434", "not re-queried"], errors)
    _must_contain(by_id, "llm.metric.night", ["4190", "799", "~19%"], errors)
    _must_contain(by_id, "llm.metric.tests", ["331", "30", "not a green-run claim"], errors)
    _must_contain(by_id, "elec.metric.suite", ["761/761", "did not re-verify"], errors)
    _must_contain(by_id, "uas.badge.maturity", ["EARLY DEVELOPMENT"], errors)
    _must_contain(by_id, "uas.layout", ["CI YAML", "no automated functional"], errors)

    for token, polarity, line in extracted.sensitive_hits:
        errors.append(f"Sensitive token {token!r} at line {line} in polarity {polarity!r}")

    forbidden_tags = {"img", "iframe", "video", "object", "embed", "canvas"}
    found = sorted(forbidden_tags & extracted.tags_seen)
    if found:
        errors.append(f"Disallowed embedded content tags: {found}")

    for href, line in extracted.hrefs:
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        if href.startswith(("http://", "https://")):
            if href.rstrip("/") not in ALLOWED_EXTERNAL:
                errors.append(f"Unexpected external URL {href} at line {line}")
            continue
        if href.startswith(("javascript:", "data:")):
            errors.append(f"Disallowed URL {href} at line {line}")

    # A do_not_claim string must not be stated inside an assertion.
    assertion_text = "\n".join(
        claim["text"].casefold()
        for claim in extracted.claims
        if claim["polarity"] in ASSERTION_POLARITIES
    )
    for slug, items in DO_NOT_CLAIM.items():
        for item in items:
            if item.casefold() in assertion_text:
                errors.append(f"do_not_claim asserted for {slug}: {item}")

    return errors


def coverage(claims: list[dict]) -> list[dict]:
    rows = []
    non_assertion = [
        claim
        for claim in claims
        if claim["polarity"] not in ASSERTION_POLARITIES
    ]
    for slug, items in DO_NOT_CLAIM.items():
        for item in items:
            folded = item.casefold()

            def covers(claim: dict) -> bool:
                slugs = claim["project_slugs"]
                return not slugs or slug in slugs

            denied_by = [
                claim["id"]
                for claim in claims
                if covers(claim)
                and any(denied.casefold() == folded for denied in claim.get("denies") or [])
            ]
            mentioned_in = [
                claim["id"]
                for claim in non_assertion
                if covers(claim) and (folded in claim["text"].casefold() or claim["id"] in denied_by)
            ]
            # denied_by may be assertion-polarity too; keep them
            mentioned_in = sorted(set(mentioned_in + denied_by))
            if denied_by:
                status = "denied_on_page"
            elif mentioned_in:
                status = "mentioned_only_as_limitation_or_denial"
            else:
                status = "not_asserted"
            rows.append(
                {
                    "project_slug": slug,
                    "do_not_claim": item,
                    "status": status,
                    "claim_ids": mentioned_in,
                }
            )
    return rows


def build_document(extracted: Extractor) -> dict:
    return {
        "schema": "portfolio_claims_source_v1",
        "owner": {"name": "Ivan Soprun", "github": "kot0070"},
        "site_repo": "kot0070/portfolio",
        "audience": "Employment / interview — AI Automation / Applied AI / software",
        "fact_lock_date": "2026-09-23",
        "fact_lock_base_sha": "50e8f9e7f64f5cc552963fdc83b614c65ffb1c8f",
        "selection_working_zone_sha": "efb1c591dd00022ba17d51033e3b5a3a4ad2feda",
        "evidence_rule": (
            "Each public claim lists the FINAL_PROJECT_FACTS fields that back it. "
            "Selection-backed lines are presentation structure (order, mention-only, interview role) "
            "and carry fact_lock_fields: []. No claim uses a PRODUCTION maturity label. "
            "Polarity assertion is an affirmative fact. denial, limitation, caveat, constraint, "
            "and bounded statements are how do_not_claim items are kept off the boast side of the page."
        ),
        "production_labels_used": False,
        "featured_order": [
            {"rank": 1, "slug": "local-llm-benchmark", "maturity_label": "ADVANCED PROTOTYPE", "role": "centerpiece"},
            {"rank": 2, "slug": "bruno-ac-pwa", "maturity_label": "WORKING APPLICATION", "role": "featured"},
            {"rank": 3, "slug": "propeller-calculator", "maturity_label": "WORKING APPLICATION", "role": "featured"},
            {"rank": 4, "slug": "bruno-electric-pwa", "maturity_label": "WORKING APPLICATION", "role": "featured"},
        ],
        "mention_only": [
            {"slug": "casino-game-analytics", "maturity_label": "WORKING APPLICATION"},
            {"slug": "drone-pilot-usa", "maturity_label": "ADVANCED PROTOTYPE"},
            {"slug": "uas-stage1-app", "maturity_label": "EARLY DEVELOPMENT"},
        ],
        "subject_pins": PINS,
        "maturity_labels": MATURITY,
        "subject_repo_full_names": {
            "local-llm-benchmark": "kot0070/local-llm-benchmark",
            "bruno-ac-pwa": "kot0070/bruno-ac-pwa",
            "propeller-calculator": "kot0070/propeller-calculator",
            "bruno-electric-pwa": "kot0070/bruno-electric-pwa",
            "casino-game-analytics": "kot0070/casino-game-analytics",
            "drone-pilot-usa": "kot0070/drone-pilot-usa",
            "uas-stage1-app": "kot0070/uas-stage1-app.",
        },
        "claims": extracted.claims,
        "do_not_claim_coverage": coverage(extracted.claims),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write public/claims-source.json")
    parser.add_argument("--check", action="store_true", help="Fail if the JSON file drifts")
    args = parser.parse_args()
    if not args.write and not args.check:
        args.check = True

    html = HTML_PATH.read_text(encoding="utf-8")
    extracted = Extractor()
    extracted.feed(html)
    extracted.close()
    errors = validate(extracted)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"{len(errors)} claim-map error(s)", file=sys.stderr)
        return 1

    document = build_document(extracted)
    payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if args.check and JSON_PATH.exists():
        current = JSON_PATH.read_text(encoding="utf-8")
        if current != payload:
            print(
                "public/claims-source.json does not match index.html. "
                "Run: python3 scripts/build_claims_source.py --write",
                file=sys.stderr,
            )
            return 1
    if args.write:
        JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        JSON_PATH.write_text(payload, encoding="utf-8")
        print(f"Wrote {JSON_PATH} ({len(document['claims'])} claims)")
    if not errors:
        print(f"OK ({len(document['claims'])} claims)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
