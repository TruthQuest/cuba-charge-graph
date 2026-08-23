#!/usr/bin/env python3
"""
Step 04: Load, validate, and infer against the merged ontology graph
=====================================================================

Composition order (non-negotiable):
    1. T-Box                     ontology/cuban_prisoners_tbox_v3.ttl
    2. Charge type vocabulary    ontology/cuban_prisoners_charge_types.ttl
    3. Policy overlay            policy/cuban_prisoners_policy.ttl
    4. A-Box                     ontology/cuban_prisoners_abox.ttl (from step 03)
    5. SHACL validation          shapes/cuban_prisoners_shapes.ttl (gate)
    6. SPARQL CONSTRUCT          derive :partOfWave assertions

Usage:
    python 04_run_pipeline.py                          # full pipeline
    python 04_run_pipeline.py --skip-shacl             # dev only
    python 04_run_pipeline.py --output merged.ttl      # serialize
    python 04_run_pipeline.py --strict                 # fail on warnings too

Exit codes:
    0 success
    1 SHACL violation
    2 parse error
    3 missing input file
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph, Namespace
from pyshacl import validate

ROOT = Path(__file__).parent
FILES = {
    "tbox":         ROOT / "cuban_prisoners_tbox_v3.ttl",
    "charge_types": ROOT / "cuban_prisoners_charge_types.ttl",
    "policy":       ROOT / "cuban_prisoners_policy.ttl",
    "abox":         ROOT / "cuban_prisoners_abox.ttl",
    "shapes":       ROOT / "cuban_prisoners_shapes.ttl",
}

ONT = Namespace("http://prisoners.defenders.org/ontology#")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline")


def stage_load() -> Graph:
    g = Graph()
    g.bind("", ONT)
    for name in ("tbox", "charge_types", "policy", "abox"):
        path = FILES[name]
        if not path.exists():
            log.error("Missing input: %s", path)
            sys.exit(3)
        before = len(g)
        try:
            g.parse(str(path), format="turtle")
        except Exception as e:
            log.error("Parse error in %s: %s", path, e)
            sys.exit(2)
        log.info("Loaded %-14s +%6d triples (total %d)", name, len(g) - before, len(g))
    return g


def stage_validate(data: Graph, skip: bool, strict: bool) -> bool:
    if skip:
        log.warning("SHACL validation skipped (dev mode). Never skip in CI.")
        return True
    shapes = Graph().parse(str(FILES["shapes"]), format="turtle")
    conforms, _, report_text = validate(
        data_graph=data,
        shacl_graph=shapes,
        inference="rdfs",
        abort_on_first=False,
        allow_infos=True,
        allow_warnings=not strict,
    )
    if conforms:
        log.info("SHACL validation: PASS")
    else:
        log.error("SHACL validation: FAIL\n%s", report_text)
    return conforms


def stage_infer_waves(g: Graph) -> int:
    """
    Derive :partOfWave assertions.
    Rule: >=5 arrests in same Province within 7 days -> wave.

    Implemented in Python (sliding window per province) because rdflib's
    SPARQL engine executes the equivalent CONSTRUCT as O(n^2) with date
    arithmetic overhead; this version runs in ~1s instead of ~10min.
    """
    from datetime import date as _date, timedelta
    from collections import defaultdict
    from rdflib import URIRef, Literal
    from rdflib.namespace import RDF, XSD

    # Extract (arrest_iri, date, province_iri) tuples once.
    arrests = []
    for a in g.subjects(RDF.type, ONT.Arrest):
        d = next(g.objects(a, ONT.arrestDate), None)
        p = next(g.objects(a, ONT.occurredInProvince), None)
        if d is None or p is None:
            continue
        try:
            parsed = _date.fromisoformat(str(d))
        except ValueError:
            continue
        arrests.append((a, parsed, p))

    if not arrests:
        log.warning("No arrests with date+province found; wave inference skipped.")
        return 0

    # Group per province, then slide a 7-day window over sorted dates.
    by_prov = defaultdict(list)
    for arrest, d, prov in arrests:
        by_prov[prov].append((d, arrest))

    added = 0
    waves_created = 0
    for prov, entries in by_prov.items():
        entries.sort(key=lambda x: x[0])
        n = len(entries)
        j = 0
        for i in range(n):
            anchor = entries[i][0]
            end = anchor + timedelta(days=7)
            # Advance j to first index > end (sliding window forward).
            while j < n and entries[j][0] <= end:
                j += 1
            window = entries[i:j]
            if len(window) < 5:
                continue
            prov_frag = str(prov).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            wave_iri = URIRef(f"{ONT}wave-{prov_frag}-{anchor.isoformat()}")
            g.add((wave_iri, RDF.type, ONT.ArrestWave))
            g.add((wave_iri, ONT.occurredInProvince, prov))
            g.add((wave_iri, ONT.arrestDate,
                   Literal(anchor.isoformat(), datatype=XSD.date)))
            added += 3
            for _, arrest in window:
                g.add((arrest, ONT.partOfWave, wave_iri))
                added += 1
            waves_created += 1

    log.info("Inferred %d wave-related triples across %d wave anchors",
             added, waves_created)
    return added


def stage_serialize(g: Graph, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(out), format="turtle")
    log.info("Wrote merged graph to %s (%d triples)", out, len(g))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-shacl", action="store_true")
    p.add_argument("--skip-inference", action="store_true")
    p.add_argument("--strict", action="store_true", help="Fail on SHACL warnings too")
    p.add_argument("--output", type=Path, default=ROOT / "merged.ttl")
    args = p.parse_args()

    log.info("=== Step 04: Ontology Pipeline ===")
    g = stage_load()

    if not stage_validate(g, skip=args.skip_shacl, strict=args.strict):
        if not args.skip_shacl:
            sys.exit(1)

    if not args.skip_inference:
        stage_infer_waves(g)

    stage_serialize(g, args.output)
    log.info("Pipeline complete: %d triples", len(g))


if __name__ == "__main__":
    main()