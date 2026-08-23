#!/usr/bin/env python3
"""
Step 03: Build A-Box from scraped prisoner data
================================================

Reads prisoners.jsonl (from 01_scrape_prisoners.py) and emits a v3-compliant
A-Box TTL that plugs into the T-Box at ontology/cuban_prisoners_tbox_v3.ttl.

Emits the v3 shape:
    :Person             typed to bfo:BFO_0000040 (Material Entity)
    :StatusPeriod       reified temporal binding with time:Interval
    :DetentionFacility  neutral, with :locatedInProvince parsed from facility string
    :Arrest             with :occurredInProvince
    :Charge             with :hasChargeType linking to SKOS vocabulary
    policy:hasRiskLevel default HighRisk (conservative; downgrade manually)

Does NOT emit :TortureFacility (deleted in v3). Reported practices require
per-instance evidence and are added via a separate curation workflow.

Usage:
    python 03_build_abox.py \
        --input  data/prisoners.jsonl \
        --output ontology/cuban_prisoners_abox.ttl \
        --base-uri http://prisoners.defenders.org/data/

Exit codes:
    0 success
    1 input parse error
    2 output write error
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef, BNode
from rdflib.namespace import RDF, RDFS, XSD, SKOS, FOAF, DCTERMS

# ---------------------------------------------------------------------------
# Namespaces
# ---------------------------------------------------------------------------

ONT    = Namespace("http://prisoners.defenders.org/ontology#")
POLICY = Namespace("http://prisoners.defenders.org/policy#")
BFO    = Namespace("http://purl.obolibrary.org/obo/")
PROV   = Namespace("http://www.w3.org/ns/prov#")
TIME   = Namespace("http://www.w3.org/2006/time#")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_abox")

# ---------------------------------------------------------------------------
# Cuban provinces (canonical list for province-string extraction)
# ---------------------------------------------------------------------------

CUBAN_PROVINCES = [
    "Pinar del Río", "Artemisa", "La Habana", "Mayabeque", "Matanzas",
    "Cienfuegos", "Villa Clara", "Sancti Spíritus", "Ciego de Ávila",
    "Camagüey", "Las Tunas", "Holguín", "Granma", "Santiago de Cuba",
    "Guantánamo", "Isla de la Juventud",
]

# ---------------------------------------------------------------------------
# Charge type normalization (map source labels → SKOS concept slugs)
# ---------------------------------------------------------------------------

CHARGE_TYPE_MAP = {
    "desacato":                                  "DesacatoType",
    "contempt":                                  "DesacatoType",
    "desórdenes públicos":                       "DesordenesPublicosType",
    "desordenes publicos":                       "DesordenesPublicosType",
    "public disorder":                           "DesordenesPublicosType",
    "atentado":                                  "AtentadoType",
    "assault":                                   "AtentadoType",
    "sabotaje":                                  "SabotajeType",
    "sabotage":                                  "SabotajeType",
    "resistencia":                               "ResistenciaType",
    "resistance":                                "ResistenciaType",
    "sedición":                                  "SedicionType",
    "sedicion":                                  "SedicionType",
    "sedition":                                  "SedicionType",
    "propaganda contra el orden constitucional": "PropagandaContraOrdenType",
    "propaganda contra el orden socialista":     "PropagandaContraOrdenType",
    "propaganda enemiga":                        "PropagandaEnemigaType",
    "enemy propaganda":                          "PropagandaEnemigaType",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str, maxlen: int = 80) -> str:
    """Produce a safe URI fragment."""
    s = re.sub(r"[^\w\-]+", "-", text.strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:maxlen] or "unknown"


def parse_province_from_facility(facility_string: str) -> Optional[str]:
    """
    Extract province from strings like:
        'Prisión Combinado del Este, La Habana'
        'Prisión Las Mangas Nuevas, Bayamo, Granma'
    """
    if not facility_string:
        return None
    for prov in sorted(CUBAN_PROVINCES, key=len, reverse=True):
        if prov.lower() in facility_string.lower():
            return prov
    return None


def parse_date(value: str) -> Optional[str]:
    """Return YYYY-MM-DD or None."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_int(value) -> Optional[int]:
    if value is None:
        return None
    s = str(value).strip()
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        n = int(m.group(0))
        if 0 <= n <= 120:
            return n
    except (ValueError, TypeError):
        pass
    return None


def parse_decimal(value) -> Optional[float]:
    try:
        n = float(str(value).strip())
        if 0 <= n <= 100:
            return n
    except (ValueError, TypeError):
        pass
    return None


def split_charges(raw: str) -> list[str]:
    """Split a comma/semicolon/pipe separated charge string."""
    if not raw:
        return []
    parts = re.split(r"[,;|/]", raw)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

@dataclass
class Builder:
    base_uri: str
    graph: Graph = field(default_factory=Graph)
    facility_cache: dict[str, URIRef] = field(default_factory=dict)
    province_cache: dict[str, URIRef] = field(default_factory=dict)
    charge_type_cache: dict[str, URIRef] = field(default_factory=dict)
    _known_slugs: set = field(default_factory=set)
    stats: dict[str, int] = field(default_factory=lambda: {
        "persons": 0, "arrests": 0, "charges": 0, "sentences": 0,
        "facilities": 0, "status_periods": 0, "skipped": 0,
    })

    def __post_init__(self):
        self.DATA = Namespace(self.base_uri)
        self._known_slugs = set(CHARGE_TYPE_MAP.values())
        g = self.graph
        g.bind("",       ONT)
        g.bind("data",   self.DATA)
        g.bind("policy", POLICY)
        g.bind("bfo",    BFO)
        g.bind("prov",   PROV)
        g.bind("time",   TIME)
        g.bind("skos",   SKOS)
        g.bind("foaf",   FOAF)
        g.bind("dcterms", DCTERMS)

    def person_iri(self, prisoner_id: str) -> URIRef:
        return self.DATA[f"person-{quote(prisoner_id, safe='')}"]

    def facility_iri(self, facility_name: str) -> URIRef:
        key = facility_name.strip()
        if key not in self.facility_cache:
            iri = self.DATA[f"facility-{slugify(key)}"]
            self.facility_cache[key] = iri
            self._emit_facility(iri, key)
        return self.facility_cache[key]

    def province_iri(self, province_name: str) -> URIRef:
        key = province_name.strip()
        if key not in self.province_cache:
            iri = self.DATA[f"province-{slugify(key)}"]
            self.province_cache[key] = iri
            self.graph.add((iri, RDF.type, ONT.Province))
            self.graph.add((iri, ONT.provinceName, Literal(key)))
            self.graph.add((iri, RDFS.label, Literal(key, lang="es")))
        return self.province_cache[key]

    def charge_type_iri(self, raw_label: str) -> URIRef:
        key = raw_label.strip().lower()
        slug = CHARGE_TYPE_MAP.get(key)
        if not slug:
            slug = slugify(raw_label)
        if slug not in self.charge_type_cache:
            iri = ONT[slug]  # Charge types live in the T-Box/vocab namespace
            self.charge_type_cache[slug] = iri
            # For uncurated source labels, emit a minimal SKOS record so
            # SHACL doesn't reject the auto-inferred ChargeType.
            if slug not in self._known_slugs:
                g = self.graph
                g.add((iri, RDF.type, ONT.ChargeType))
                g.add((iri, SKOS.prefLabel, Literal(raw_label.strip(), lang="es")))
                g.add((iri, SKOS.inScheme, ONT.CubanPenalCode))
                g.add((iri, SKOS.editorialNote, Literal(
                    "Auto-generated from source data; not manually curated against Cuban Penal Code.",
                    lang="en")))
        return self.charge_type_cache[slug]

    def _emit_facility(self, iri: URIRef, name: str) -> None:
        g = self.graph
        g.add((iri, RDF.type, ONT.DetentionFacility))
        g.add((iri, ONT.facilityName, Literal(name)))
        g.add((iri, RDFS.label, Literal(name, lang="es")))
        province = parse_province_from_facility(name)
        if province:
            g.add((iri, ONT.locatedInProvince, self.province_iri(province)))
        self.stats["facilities"] += 1

    def _emit_interval(self, start_iso: Optional[str], end_iso: Optional[str]) -> URIRef:
        """Emit a time:Interval as a blank-node instant pair."""
        interval = BNode()
        self.graph.add((interval, RDF.type, TIME.Interval))
        if start_iso:
            start = BNode()
            self.graph.add((start, RDF.type, TIME.Instant))
            self.graph.add((start, TIME.inXSDDate, Literal(start_iso, datatype=XSD.date)))
            self.graph.add((interval, TIME.hasBeginning, start))
        if end_iso:
            end = BNode()
            self.graph.add((end, RDF.type, TIME.Instant))
            self.graph.add((end, TIME.inXSDDate, Literal(end_iso, datatype=XSD.date)))
            self.graph.add((interval, TIME.hasEnd, end))
        return interval

    def add_prisoner(self, record: dict) -> bool:
        """Emit a full prisoner subgraph. Returns False if record is unusable."""
        pid = str(record.get("id") or record.get("slug") or "").strip()
        name = (record.get("name") or "").strip()
        if not pid or not name:
            self.stats["skipped"] += 1
            return False

        g = self.graph
        person = self.person_iri(pid)

        g.add((person, RDF.type, ONT.PoliticalPrisoner))
        g.add((person, RDF.type, ONT.Person))
        g.add((person, ONT.fullName, Literal(name)))
        g.add((person, RDFS.label, Literal(name)))

        # Provenance
        url = record.get("url")
        if url:
            g.add((person, ONT.sourceURL, Literal(url, datatype=XSD.anyURI)))
            g.add((person, PROV.wasDerivedFrom, URIRef(url)))
        scraped = record.get("scraped_at")
        if scraped:
            g.add((person, ONT.scrapedAt, Literal(scraped, datatype=XSD.dateTime)))
        else:
            g.add((person, ONT.scrapedAt,
                   Literal(datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)))

        # Ages
        age_now = parse_int(record.get("age_current"))
        if age_now is not None:
            g.add((person, ONT.currentAge, Literal(age_now, datatype=XSD.nonNegativeInteger)))
        age_arr = parse_int(record.get("age_at_arrest"))
        if age_arr is not None:
            g.add((person, ONT.ageAtArrest, Literal(age_arr, datatype=XSD.nonNegativeInteger)))

        # Home province (single field in source; treated as residence)
        province_str = (record.get("province") or "").strip()
        if province_str:
            g.add((person, ONT.residesInProvince, self.province_iri(province_str)))

        # Arrest
        arrest_date_iso = parse_date(record.get("arrest_date"))
        if arrest_date_iso:
            arrest = self.DATA[f"arrest-{quote(pid, safe='')}"]
            g.add((arrest, RDF.type, ONT.Arrest))
            g.add((arrest, ONT.arrestDate, Literal(arrest_date_iso, datatype=XSD.date)))
            g.add((arrest, ONT.arrestOf, person))
            g.add((person, ONT.arrested, arrest))
            if province_str:
                g.add((arrest, ONT.occurredInProvince, self.province_iri(province_str)))
            self.stats["arrests"] += 1
        else:
            log.debug("Person %s has no parseable arrest_date", pid)

        # Charges
        for i, charge_label in enumerate(split_charges(record.get("charge_type", "")), 1):
            charge = self.DATA[f"charge-{quote(pid, safe='')}-{i}"]
            g.add((charge, RDF.type, ONT.Charge))
            g.add((charge, ONT.hasChargeType, self.charge_type_iri(charge_label)))
            g.add((charge, ONT.filedAgainst, person))
            g.add((person, ONT.chargedWith, charge))
            self.stats["charges"] += 1

        # Sentence
        sentence_years = parse_decimal(record.get("sentence_years"))
        if sentence_years is not None:
            sentence = self.DATA[f"sentence-{quote(pid, safe='')}"]
            g.add((sentence, RDF.type, ONT.Sentence))
            g.add((sentence, ONT.sentenceLengthYears,
                   Literal(sentence_years, datatype=XSD.decimal)))
            g.add((person, ONT.sentenced, sentence))
            self.stats["sentences"] += 1

        # Facility + reified StatusPeriod (v3 pattern)
        facility_str = (record.get("prison") or "").strip()
        prisoner_type = (record.get("prisoner_type") or "").strip().lower()
        if facility_str:
            facility = self.facility_iri(facility_str)
            status_period = self.DATA[f"status-{quote(pid, safe='')}"]
            g.add((status_period, RDF.type, ONT.StatusPeriod))
            g.add((status_period, ONT.statusOf, person))
            g.add((status_period, ONT.detainedAtDuringPeriod, facility))
            g.add((person, ONT.hasStatusPeriod, status_period))

            # Map prisoner_type string to PenalStatus class
            status_class = self._map_penal_status(prisoner_type)
            g.add((status_period, ONT.penalStatusInPeriod, status_class))

            # Interval: begins at arrest date if known, open-ended
            interval = self._emit_interval(arrest_date_iso, None)
            g.add((status_period, ONT.periodInterval, interval))
            self.stats["status_periods"] += 1

        # Default risk level: HighRisk (conservative). Curator downgrades manually.
        g.add((person, POLICY.hasRiskLevel, POLICY.HighRisk))

        self.stats["persons"] += 1
        return True

    @staticmethod
    def _map_penal_status(prisoner_type: str) -> URIRef:
        pt = prisoner_type.lower()
        if "condicional" in pt or "conditional" in pt:
            return ONT.ConditionalRelease
        if "domiciliar" in pt or "house" in pt:
            return ONT.HouseArrest
        if "provisional" in pt or "preventiva" in pt:
            return ONT.ProvisionalDetention
        if "trabajo" in pt or "labor" in pt:
            return ONT.ForcedLaborWithoutInternment
        if "amenaza" in pt or "threat" in pt:
            return ONT.UnderThreats
        return ONT.Imprisoned  # default


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="Build v3 A-Box from scraped JSONL")
    p.add_argument("--input", type=Path, required=True, help="Path to prisoners.jsonl")
    p.add_argument("--output", type=Path, required=True, help="Output A-Box .ttl")
    p.add_argument("--base-uri", default="http://prisoners.defenders.org/data/",
                   help="Base URI for instance data")
    p.add_argument("--limit", type=int, default=None, help="Debug: limit N records")
    args = p.parse_args()

    if not args.input.exists():
        log.error("Input file not found: %s", args.input)
        sys.exit(1)

    builder = Builder(base_uri=args.base_uri)

    log.info("Reading %s", args.input)
    try:
        with args.input.open("r", encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    log.warning("Line %d: JSON error: %s", i, e)
                    continue
                builder.add_prisoner(record)
                if args.limit and i >= args.limit:
                    break
    except Exception as e:
        log.error("Read failed: %s", e)
        sys.exit(1)

    log.info("Statistics: %s", builder.stats)
    log.info("Total triples: %d", len(builder.graph))

    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        builder.graph.serialize(destination=str(args.output), format="turtle")
    except Exception as e:
        log.error("Write failed: %s", e)
        sys.exit(2)

    log.info("Wrote A-Box to %s", args.output)


if __name__ == "__main__":
    main()