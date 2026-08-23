#!/usr/bin/env python3
"""
Step 05: Analysis against the merged v3 graph
==============================================

Refactored from cuban_network_analysis.py to:
  1. Read the merged graph produced by step 04, not the raw v2.1 TTL.
  2. Use the v3 reified StatusPeriod pattern for facility co-location.
  3. Rename "co-detention" to "facility co-location" (concept correction).
  4. Add a permutation test for charge stacking (publication requirement).
  5. Compute displacement now that residesInProvince != facility province.

Outputs (all in results/):
    facility_colocation.csv         (renamed from co-detention)
    charge_stacking.csv             with p-values from permutation test
    arrest_waves.csv                sourced from :ArrestWave (SPARQL-derived)
    geographic_displacement.csv     now populated
    summary_report.md

Usage:
    python 05_analyze.py                        # run all analyses
    python 05_analyze.py --input data/merged.ttl
    python 05_analyze.py --only charge_stacking
    python 05_analyze.py --permutations 10000   # more iterations for pub

Exit codes:
    0 success
    1 input missing
    2 empty graph
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from math import radians, cos, sin, asin, sqrt
from pathlib import Path
from typing import Optional

import networkx as nx
from rdflib import Graph, Namespace, RDF, Literal
from rdflib.namespace import RDFS, SKOS

ONT    = Namespace("http://prisoners.defenders.org/ontology#")
POLICY = Namespace("http://prisoners.defenders.org/policy#")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("analyze")

# ---------------------------------------------------------------------------
# Province centroids for haversine displacement (approximate)
# ---------------------------------------------------------------------------

PROVINCE_COORDS = {
    "Pinar del Río":       (22.4175, -83.6981),
    "Artemisa":            (22.8130, -82.7593),
    "La Habana":           (23.1136, -82.3666),
    "Mayabeque":           (22.9678, -82.1550),
    "Matanzas":            (23.0416, -81.5775),
    "Cienfuegos":          (22.1450, -80.4361),
    "Villa Clara":         (22.4069, -79.9647),
    "Sancti Spíritus":     (21.9297, -79.4425),
    "Ciego de Ávila":      (21.8481, -78.7614),
    "Camagüey":            (21.3833, -77.9169),
    "Las Tunas":           (20.9611, -76.9497),
    "Holguín":             (20.8872, -76.2631),
    "Granma":              (20.3728, -76.6414),
    "Santiago de Cuba":    (20.0247, -75.8219),
    "Guantánamo":          (20.1450, -75.2069),
    "Isla de la Juventud": (21.8814, -82.7622),
}


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(radians, a)
    lat2, lon2 = map(radians, b)
    d_lat = lat2 - lat1
    d_lon = lon2 - lon1
    h = sin(d_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(d_lon / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


# ---------------------------------------------------------------------------
# Graph loader
# ---------------------------------------------------------------------------

@dataclass
class Store:
    graph: Graph
    persons: set = field(default_factory=set)
    person_name: dict = field(default_factory=dict)
    person_home_prov: dict = field(default_factory=dict)
    person_facility: dict = field(default_factory=lambda: defaultdict(set))
    facility_name: dict = field(default_factory=dict)
    facility_prov: dict = field(default_factory=dict)
    person_charges: dict = field(default_factory=lambda: defaultdict(list))
    charge_label: dict = field(default_factory=dict)
    arrests: list = field(default_factory=list)  # (date, prov, person_name)

    @classmethod
    def load(cls, path: Path) -> "Store":
        g = Graph()
        log.info("Parsing %s", path)
        g.parse(str(path), format="turtle")
        log.info("Loaded %d triples", len(g))
        if len(g) == 0:
            sys.exit(2)
        s = cls(graph=g)
        s._index()
        return s

    def _label(self, uri) -> str:
        for label in self.graph.objects(uri, SKOS.prefLabel):
            return str(label)
        for label in self.graph.objects(uri, RDFS.label):
            return str(label)
        for label in self.graph.objects(uri, ONT.fullName):
            return str(label)
        for label in self.graph.objects(uri, ONT.facilityName):
            return str(label)
        for label in self.graph.objects(uri, ONT.provinceName):
            return str(label)
        return str(uri).split("#")[-1].split("/")[-1]

    def _index(self) -> None:
        g = self.graph

        for p in g.subjects(RDF.type, ONT.PoliticalPrisoner):
            self.persons.add(p)
            self.person_name[p] = self._label(p)
            for prov in g.objects(p, ONT.residesInProvince):
                self.person_home_prov[p] = self._label(prov)

        # Facility index
        for f in g.subjects(RDF.type, ONT.DetentionFacility):
            self.facility_name[f] = self._label(f)
            for prov in g.objects(f, ONT.locatedInProvince):
                self.facility_prov[f] = self._label(prov)

        # Person -> facility via reified StatusPeriod (v3 pattern)
        for person in self.persons:
            for period in g.objects(person, ONT.hasStatusPeriod):
                for facility in g.objects(period, ONT.detainedAtDuringPeriod):
                    self.person_facility[person].add(facility)

        # Charges
        for person in self.persons:
            for charge in g.objects(person, ONT.chargedWith):
                for ctype in g.objects(charge, ONT.hasChargeType):
                    label = self._label(ctype)
                    self.charge_label[ctype] = label
                    self.person_charges[person].append(label)

        # Arrests
        for arrest in g.subjects(RDF.type, ONT.Arrest):
            date = next(g.objects(arrest, ONT.arrestDate), None)
            person = next(g.objects(arrest, ONT.arrestOf), None)
            prov = next(g.objects(arrest, ONT.occurredInProvince), None)
            if date and person:
                self.arrests.append((
                    str(date),
                    self._label(prov) if prov else None,
                    self.person_name.get(person, str(person)),
                ))

        log.info(
            "Indexed: %d persons, %d facilities, %d arrests, %d charge-holders",
            len(self.persons), len(self.facility_name),
            len(self.arrests), sum(1 for v in self.person_charges.values() if v),
        )


# ---------------------------------------------------------------------------
# Analyses
# ---------------------------------------------------------------------------

def analyze_facility_colocation(store: Store, out: Path, top_n: int = 20) -> int:
    """
    Renamed from co-detention. Measures state facility clustering behavior,
    NOT prisoner organizing networks. Report language matters.
    """
    log.info("Analyzing facility co-location (state clustering behavior)")

    facility_inmates = defaultdict(list)
    for person, facilities in store.person_facility.items():
        for f in facilities:
            facility_inmates[f].append(person)

    G = nx.Graph()
    for facility, inmates in facility_inmates.items():
        if len(inmates) < 2:
            continue
        fac_name = store.facility_name.get(facility, str(facility))
        for i, p1 in enumerate(inmates):
            n1 = store.person_name.get(p1, str(p1))
            for p2 in inmates[i + 1:]:
                n2 = store.person_name.get(p2, str(p2))
                if G.has_edge(n1, n2):
                    G[n1][n2]["facilities"].add(fac_name)
                    G[n1][n2]["weight"] += 1
                else:
                    G.add_edge(n1, n2, facilities={fac_name}, weight=1)

    components = sorted(nx.connected_components(G), key=len, reverse=True)
    log.info("Components: %d, largest %d", len(components), len(components[0]) if components else 0)

    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["component_id", "size", "shared_facilities", "sample_names"])
        for i, comp in enumerate(components[:top_n], 1):
            people = list(comp)
            shared = set()
            for p1 in people:
                for p2 in people:
                    if p1 != p2 and G.has_edge(p1, p2):
                        shared.update(G[p1][p2]["facilities"])
            w.writerow([
                i,
                len(comp),
                "; ".join(sorted(shared)[:5]),
                "; ".join(sorted(people)[:10]) + ("..." if len(people) > 10 else ""),
            ])
    log.info("Wrote %s", out)
    return len(components)


def analyze_charge_stacking(store: Store, out: Path, permutations: int = 5000,
                             seed: int = 42) -> None:
    """
    Compute observed pair co-occurrence + permutation-test null distribution.
    p-value: proportion of shuffles producing >= observed co-occurrence.
    """
    log.info("Analyzing charge stacking (%d permutations)", permutations)
    rng = random.Random(seed)

    per_person = [list(v) for v in store.person_charges.values() if v]
    marginals = Counter(c for charges in per_person for c in charges)
    total_charges = sum(marginals.values())
    charge_pool = list(marginals.elements())

    def pair_counts(person_charges: list[list[str]]) -> Counter:
        pc = Counter()
        for charges in person_charges:
            unique = sorted(set(charges))
            for i, c1 in enumerate(unique):
                for c2 in unique[i + 1:]:
                    pc[(c1, c2)] += 1
        return pc

    observed = pair_counts(per_person)

    # Permutation test: preserve per-person charge counts and marginals
    null_dist = defaultdict(list)
    for it in range(permutations):
        rng.shuffle(charge_pool)
        rebuilt = []
        idx = 0
        for orig in per_person:
            k = len(orig)
            rebuilt.append(charge_pool[idx:idx + k])
            idx += k
        shuffled = pair_counts(rebuilt)
        for pair in observed:
            null_dist[pair].append(shuffled.get(pair, 0))
        if (it + 1) % 500 == 0:
            log.info("  permutation %d/%d", it + 1, permutations)

    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "charge1", "charge2", "co_occurrence", "charge1_total", "charge2_total",
            "conditional_rate_min", "null_mean", "null_p95", "empirical_p_value",
        ])
        rows = []
        for (c1, c2), obs in observed.items():
            null = null_dist[(c1, c2)]
            null_mean = sum(null) / len(null)
            null_p95 = sorted(null)[int(0.95 * len(null))]
            p_value = sum(1 for v in null if v >= obs) / len(null)
            m1, m2 = marginals[c1], marginals[c2]
            rate = obs / min(m1, m2) if min(m1, m2) else 0
            rows.append((c1, c2, obs, m1, m2, rate, null_mean, null_p95, p_value))
        rows.sort(key=lambda r: r[2], reverse=True)
        for r in rows[:30]:
            w.writerow([
                r[0], r[1], r[2], r[3], r[4],
                f"{r[5]:.4f}", f"{r[6]:.2f}", r[7], f"{r[8]:.4f}",
            ])
    log.info("Wrote %s", out)


def analyze_arrest_waves(store: Store, out: Path, min_daily: int = 5) -> None:
    """Mass arrest days derived from A-Box (independent of SPARQL inference)."""
    log.info("Analyzing arrest waves")
    by_date = defaultdict(list)
    for date, prov, name in store.arrests:
        by_date[date].append((prov, name))

    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "arrest_count", "top_provinces", "first_10_names"])
        rows = [(d, len(entries), entries) for d, entries in by_date.items()
                if len(entries) >= min_daily]
        rows.sort(key=lambda r: r[1], reverse=True)
        for date, count, entries in rows:
            provs = Counter(p for p, _ in entries if p)
            top = "; ".join(f"{p}({n})" for p, n in provs.most_common(3))
            names = "; ".join(n for _, n in entries[:10])
            w.writerow([date, count, top, names])
    log.info("Wrote %s (%d mass-arrest days)", out, len(rows))


def analyze_displacement(store: Store, out: Path) -> None:
    """
    Distance in km between residesInProvince and locatedInProvince(facility).
    Now populated because 03_build_abox emits both, and facility province is
    parsed from the facility string.
    """
    log.info("Analyzing geographic displacement")
    rows = []
    for person, home_prov in store.person_home_prov.items():
        home = PROVINCE_COORDS.get(home_prov)
        if not home:
            continue
        for facility in store.person_facility.get(person, ()):
            fac_prov = store.facility_prov.get(facility)
            if not fac_prov:
                continue
            fac_coord = PROVINCE_COORDS.get(fac_prov)
            if not fac_coord:
                continue
            dist = haversine(home, fac_coord)
            rows.append((
                store.person_name.get(person, str(person)),
                home_prov,
                store.facility_name.get(facility, str(facility)),
                fac_prov,
                round(dist, 1),
            ))

    rows.sort(key=lambda r: r[4], reverse=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "home_province", "facility", "facility_province", "distance_km"])
        w.writerows(rows)
    log.info("Wrote %s (%d prisoners with displacement data)", out, len(rows))


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def write_summary(results_dir: Path, store: Store) -> None:
    lines = [
        "# Cuban Political Prisoners: Analysis Summary",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        "",
        "## Dataset",
        f"- Persons: {len(store.persons)}",
        f"- Facilities: {len(store.facility_name)}",
        f"- Arrests: {len(store.arrests)}",
        "",
        "## Outputs",
        "- facility_colocation.csv (state facility clustering, NOT prisoner organizing)",
        "- charge_stacking.csv (with permutation-test p-values)",
        "- arrest_waves.csv",
        "- geographic_displacement.csv",
        "",
        "## Interpretation guardrails",
        "1. Facility co-location measures state clustering behavior. Do not infer",
        "   pre-arrest political networks or in-prison organizing from this.",
        "2. Charge stacking p-values below 0.001 indicate non-random co-occurrence.",
        "   Interpret higher p-values as consistent with chance under marginal-preserving null.",
        "3. Wave detection is duplicated: derived here from A-Box AND independently",
        "   asserted via SPARQL CONSTRUCT in step 04. Cross-check the two.",
    ]
    (results_dir / "summary_report.md").write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, default=Path("data/merged.ttl"))
    p.add_argument("--output-dir", type=Path, default=Path("results"))
    p.add_argument("--only", choices=["colocation", "stacking", "waves", "displacement"])
    p.add_argument("--permutations", type=int, default=5000)
    args = p.parse_args()

    if not args.input.exists():
        log.error("Input missing: %s. Run 04_run_pipeline.py first.", args.input)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    store = Store.load(args.input)

    if args.only in (None, "colocation"):
        analyze_facility_colocation(store, args.output_dir / "facility_colocation.csv")
    if args.only in (None, "stacking"):
        analyze_charge_stacking(store, args.output_dir / "charge_stacking.csv",
                                 permutations=args.permutations)
    if args.only in (None, "waves"):
        analyze_arrest_waves(store, args.output_dir / "arrest_waves.csv")
    if args.only in (None, "displacement"):
        analyze_displacement(store, args.output_dir / "geographic_displacement.csv")

    write_summary(args.output_dir, store)
    log.info("Analysis complete: %s", args.output_dir)


if __name__ == "__main__":
    main()
