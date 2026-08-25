#!/usr/bin/env python3
"""
09_community_detection.py
=========================
Step 09 of the Cuba Political Prisoners Knowledge Graph Pipeline.

Purpose:
    Independent validation of the two-regime hypothesis via unsupervised
    community detection on the charge co-occurrence graph. If the
    analyst-defined partition (Regime A: Contempt+PublicDisorder+Assault+
    Resistance bundle; Regime B: Sedicion standalone) is a real structural
    feature of the data rather than an artifact of the analyst's framing,
    then an unsupervised algorithm given only the co-occurrence matrix and
    no domain knowledge should discover the same partition.

Method:
    1. Build a weighted undirected graph where nodes are charge types and
       edge weights are co-occurrence counts (number of prisoners charged
       with both charges).
    2. Run Louvain community detection (Blondel et al. 2008) at the
       default resolution parameter (1.0).
    3. Test stability across 100 random seeds.
    4. Compare the algorithmically discovered partition against the
       analyst-defined regimes.
    5. Compute supplementary network metrics (degree centrality,
       betweenness centrality, clustering coefficient, algebraic
       connectivity).
    6. Classify each prisoner into the algorithmically discovered regime
       and compare to the analyst-defined classification.

Inputs:
    prisoners.csv (from Step 01/02)

Outputs:
    09_community_detection_results.json   Full structured results
    09_community_detection.log            Execution log
    09_charge_communities.csv             Per-charge community assignment
    09_prisoner_regime_algo.csv           Per-prisoner algorithmic regime

Dependencies:
    pip install networkx python-louvain numpy scipy

Author: E. Brattin / Trace Origin LLC
License: All rights reserved. (c) 2026 Trace Origin LLC.
"""

import argparse
import csv
import json
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import numpy as np
from scipy import stats

try:
    import community as community_louvain
except ImportError:
    print("ERROR: python-louvain not installed. Run: pip install python-louvain")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────

# Analyst-defined regime charges (from Step 07/08 analysis)
REGIME_A_CHARGES = frozenset({
    "Desacato",
    "Desórdenes públicos",
    "Atentado",
    "Resistencia",
})

REGIME_B_CHARGES = frozenset({
    "Sedición",
})

# Charges to exclude from co-occurrence analysis (parse artifacts, placeholders)
EXCLUDE_CHARGES = {
    "No disponible",
    "",
}

# Stability test parameters
STABILITY_SEEDS = 100
DEFAULT_RESOLUTION = 1.0

# Output paths
OUTPUT_DIR = Path(".")
RESULTS_JSON = OUTPUT_DIR / "09_community_detection_results.json"
CHARGE_CSV = OUTPUT_DIR / "09_charge_communities.csv"
PRISONER_CSV = OUTPUT_DIR / "09_prisoner_regime_algo.csv"
LOG_FILE = OUTPUT_DIR / "09_community_detection.log"


# ─────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("09_community_detection")


# ─────────────────────────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────

@dataclass
class Prisoner:
    """Parsed prisoner record with tokenized charges."""
    id: str
    name: str
    charges: List[str]
    arrest_date: str
    province: str
    sentence_years: str


@dataclass
class CommunityResult:
    """Result of a single Louvain run."""
    n_communities: int
    modularity: float
    partition: Dict[str, int]
    sedicion_community: int
    regime_a_community: int
    sedicion_separate: bool
    regime_a_together: bool


@dataclass
class StabilityResult:
    """Aggregated stability across multiple seeds."""
    n_runs: int
    sedicion_separate_count: int
    sedicion_separate_pct: float
    regime_a_together_count: int
    regime_a_together_pct: float


@dataclass
class NetworkMetrics:
    """Per-charge network metrics."""
    charge: str
    degree: int
    weighted_degree: int
    degree_centrality: float
    betweenness_centrality: float
    clustering_coefficient: float
    community_id: int
    analyst_regime: str  # "A", "B", or "other"


# ─────────────────────────────────────────────────────────────────
# CORPUS LOADING
# ─────────────────────────────────────────────────────────────────

def load_corpus(csv_path: Path) -> List[Prisoner]:
    """Load and parse the prisoner CSV. Tokenize charge_type field."""
    prisoners = []
    skipped = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            charge_raw = row.get("charge_type", "").strip()
            if not charge_raw or charge_raw in EXCLUDE_CHARGES:
                skipped += 1
                continue

            charges = [
                c.strip()
                for c in charge_raw.split(",")
                if c.strip() and c.strip() not in EXCLUDE_CHARGES
            ]
            if not charges:
                skipped += 1
                continue

            prisoners.append(Prisoner(
                id=row.get("id", ""),
                name=row.get("name", ""),
                charges=charges,
                arrest_date=row.get("arrest_date", ""),
                province=row.get("province", ""),
                sentence_years=row.get("sentence_years", ""),
            ))

    logger.info(f"Loaded {len(prisoners)} prisoners with parseable charges ({skipped} skipped)")
    return prisoners


# ─────────────────────────────────────────────────────────────────
# GRAPH CONSTRUCTION
# ─────────────────────────────────────────────────────────────────

def build_charge_cooccurrence_graph(prisoners: List[Prisoner]) -> nx.Graph:
    """
    Build a weighted undirected graph where:
      - Nodes are charge types
      - Edge weight = number of prisoners charged with both charges
      - Node attribute 'count' = number of prisoners with this charge
    """
    G = nx.Graph()

    for p in prisoners:
        unique_charges = list(set(p.charges))

        # Add/increment node counts
        for c in unique_charges:
            if c not in G:
                G.add_node(c, count=0)
            G.nodes[c]["count"] += 1

        # Add/increment edge weights for all charge pairs
        for c1, c2 in combinations(unique_charges, 2):
            if G.has_edge(c1, c2):
                G[c1][c2]["weight"] += 1
            else:
                G.add_edge(c1, c2, weight=1)

    logger.info(
        f"Charge co-occurrence graph: {G.number_of_nodes()} nodes, "
        f"{G.number_of_edges()} edges, density={nx.density(G):.4f}"
    )
    return G


# ─────────────────────────────────────────────────────────────────
# COMMUNITY DETECTION
# ─────────────────────────────────────────────────────────────────

def run_louvain(
    G: nx.Graph,
    resolution: float = DEFAULT_RESOLUTION,
    seed: int = 42,
) -> CommunityResult:
    """Run Louvain community detection and characterize the partition."""
    partition = community_louvain.best_partition(
        G, weight="weight", resolution=resolution, random_state=seed
    )
    modularity = community_louvain.modularity(partition, G, weight="weight")
    n_communities = len(set(partition.values()))

    # Identify which community contains Sedicion and which contains Regime A
    sed_comm = partition.get("Sedición", -1)
    des_comm = partition.get("Desacato", -1)
    ate_comm = partition.get("Atentado", -1)
    dpo_comm = partition.get("Desórdenes públicos", -1)
    res_comm = partition.get("Resistencia", -1)

    regime_a_comms = {des_comm, ate_comm, dpo_comm, res_comm}
    regime_a_together = len(regime_a_comms) == 1 and -1 not in regime_a_comms
    sedicion_separate = sed_comm != des_comm and sed_comm != -1

    return CommunityResult(
        n_communities=n_communities,
        modularity=modularity,
        partition=partition,
        sedicion_community=sed_comm,
        regime_a_community=des_comm,
        sedicion_separate=sedicion_separate,
        regime_a_together=regime_a_together,
    )


def run_stability_test(
    G: nx.Graph,
    n_runs: int = STABILITY_SEEDS,
    resolution: float = DEFAULT_RESOLUTION,
) -> StabilityResult:
    """Run Louvain n_runs times with different seeds. Report stability."""
    sedicion_separate_count = 0
    regime_a_together_count = 0

    for seed in range(n_runs):
        result = run_louvain(G, resolution=resolution, seed=seed)
        if result.sedicion_separate:
            sedicion_separate_count += 1
        if result.regime_a_together:
            regime_a_together_count += 1

    stability = StabilityResult(
        n_runs=n_runs,
        sedicion_separate_count=sedicion_separate_count,
        sedicion_separate_pct=sedicion_separate_count / n_runs * 100,
        regime_a_together_count=regime_a_together_count,
        regime_a_together_pct=regime_a_together_count / n_runs * 100,
    )

    logger.info(
        f"Stability test ({n_runs} runs): "
        f"Sedición separate {sedicion_separate_count}/{n_runs} "
        f"({stability.sedicion_separate_pct:.1f}%), "
        f"Regime A together {regime_a_together_count}/{n_runs} "
        f"({stability.regime_a_together_pct:.1f}%)"
    )
    return stability


def run_resolution_sweep(
    G: nx.Graph,
    resolutions: List[float] = None,
) -> List[Dict]:
    """Sweep resolution parameter to characterize partition stability."""
    if resolutions is None:
        resolutions = [0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 3.0]

    results = []
    for res in resolutions:
        r = run_louvain(G, resolution=res, seed=42)
        results.append({
            "resolution": res,
            "n_communities": r.n_communities,
            "modularity": r.modularity,
            "sedicion_separate": r.sedicion_separate,
            "regime_a_together": r.regime_a_together,
            "sedicion_community": r.sedicion_community,
            "regime_a_community": r.regime_a_community,
        })
        logger.info(
            f"  res={res:.1f}: {r.n_communities} communities, "
            f"Q={r.modularity:.4f}, "
            f"Sed separate={r.sedicion_separate}, "
            f"A together={r.regime_a_together}"
        )
    return results


# ─────────────────────────────────────────────────────────────────
# NETWORK METRICS
# ─────────────────────────────────────────────────────────────────

def compute_network_metrics(
    G: nx.Graph,
    partition: Dict[str, int],
) -> List[NetworkMetrics]:
    """Compute per-charge network metrics."""
    deg_cent = nx.degree_centrality(G)
    bet_cent = nx.betweenness_centrality(G, weight="weight")
    clustering = nx.clustering(G, weight="weight")

    metrics = []
    for charge in G.nodes():
        # Determine analyst regime
        if charge in REGIME_A_CHARGES:
            analyst_regime = "A"
        elif charge in REGIME_B_CHARGES:
            analyst_regime = "B"
        else:
            analyst_regime = "other"

        metrics.append(NetworkMetrics(
            charge=charge,
            degree=G.degree(charge),
            weighted_degree=G.degree(charge, weight="weight"),
            degree_centrality=deg_cent[charge],
            betweenness_centrality=bet_cent[charge],
            clustering_coefficient=clustering[charge],
            community_id=partition.get(charge, -1),
            analyst_regime=analyst_regime,
        ))

    return sorted(metrics, key=lambda m: m.weighted_degree, reverse=True)


def compute_algebraic_connectivity(G: nx.Graph) -> Dict:
    """Compute Fiedler value (algebraic connectivity) of the graph."""
    result = {"connected": nx.is_connected(G)}

    if nx.is_connected(G):
        fiedler = nx.algebraic_connectivity(G, weight="weight")
        result["fiedler_value"] = fiedler
        result["n_components"] = 1
    else:
        components = list(nx.connected_components(G))
        result["n_components"] = len(components)
        largest = max(components, key=len)
        H = G.subgraph(largest)
        fiedler = nx.algebraic_connectivity(H, weight="weight")
        result["fiedler_value_largest_component"] = fiedler
        result["largest_component_size"] = len(largest)

        # Which component contains Sedicion and Desacato?
        for i, comp in enumerate(components):
            if "Sedición" in comp:
                result["sedicion_component"] = i
                result["sedicion_component_size"] = len(comp)
            if "Desacato" in comp:
                result["desacato_component"] = i
                result["desacato_component_size"] = len(comp)

    return result


# ─────────────────────────────────────────────────────────────────
# SEDICION ISOLATION ANALYSIS
# ─────────────────────────────────────────────────────────────────

def analyze_sedicion_isolation(
    G: nx.Graph,
    prisoners: List[Prisoner],
) -> Dict:
    """Quantify how isolated Sedicion is in the co-occurrence graph."""
    sed_edges = [
        (u, v, d)
        for u, v, d in G.edges(data=True)
        if u == "Sedición" or v == "Sedición"
    ]
    sed_edges.sort(key=lambda x: x[2]["weight"], reverse=True)

    # Standalone vs. combined
    sed_total = sum(1 for p in prisoners if "Sedición" in p.charges)
    sed_only = sum(
        1 for p in prisoners if set(p.charges) == {"Sedición"}
    )
    sed_plus = sed_total - sed_only

    cooccurrences = []
    for u, v, d in sed_edges:
        other = v if u == "Sedición" else u
        cooccurrences.append({
            "charge": other,
            "weight": d["weight"],
            "is_regime_a": other in REGIME_A_CHARGES,
        })

    return {
        "total_prisoners_with_sedicion": sed_total,
        "sedicion_standalone": sed_only,
        "sedicion_standalone_pct": round(sed_only / sed_total * 100, 1) if sed_total > 0 else 0,
        "sedicion_combined": sed_plus,
        "sedicion_degree": G.degree("Sedición") if "Sedición" in G else 0,
        "sedicion_weighted_degree": G.degree("Sedición", weight="weight") if "Sedición" in G else 0,
        "desacato_weighted_degree": G.degree("Desacato", weight="weight") if "Desacato" in G else 0,
        "cooccurrences": cooccurrences,
    }


# ─────────────────────────────────────────────────────────────────
# PRISONER REGIME CLASSIFICATION (ALGORITHMIC)
# ─────────────────────────────────────────────────────────────────

def classify_prisoners_by_algorithm(
    prisoners: List[Prisoner],
    partition: Dict[str, int],
    sedicion_community: int,
    regime_a_community: int,
) -> List[Dict]:
    """
    Classify each prisoner into an algorithmic regime based on which
    community their charges primarily belong to.
    """
    results = []
    for p in prisoners:
        # Count how many of this prisoner's charges fall into each community
        comm_counts = Counter()
        for charge in p.charges:
            if charge in partition:
                comm_counts[partition[charge]] += 1

        # Determine primary community
        if comm_counts:
            primary_comm = comm_counts.most_common(1)[0][0]
        else:
            primary_comm = -1

        # Map to algorithmic regime label
        if primary_comm == sedicion_community:
            algo_regime = "B_algo"
        elif primary_comm == regime_a_community:
            algo_regime = "A_algo"
        else:
            algo_regime = "other_algo"

        # Analyst-defined regime for comparison
        has_sedicion = "Sedición" in p.charges
        has_regime_a = bool(set(p.charges) & REGIME_A_CHARGES)
        if has_sedicion and not has_regime_a:
            analyst_regime = "B"
        elif has_regime_a and not has_sedicion:
            analyst_regime = "A"
        elif has_sedicion and has_regime_a:
            analyst_regime = "mixed"
        else:
            analyst_regime = "other"

        results.append({
            "id": p.id,
            "name": p.name,
            "charges": ",".join(p.charges),
            "arrest_date": p.arrest_date,
            "province": p.province,
            "analyst_regime": analyst_regime,
            "algo_regime": algo_regime,
            "match": (
                (analyst_regime == "A" and algo_regime == "A_algo") or
                (analyst_regime == "B" and algo_regime == "B_algo") or
                (analyst_regime == "other" and algo_regime == "other_algo")
            ),
            "primary_community": primary_comm,
        })

    return results


# ─────────────────────────────────────────────────────────────────
# OUTPUT
# ─────────────────────────────────────────────────────────────────

def write_results(
    primary_result: CommunityResult,
    stability: StabilityResult,
    resolution_sweep: List[Dict],
    metrics: List[NetworkMetrics],
    algebraic: Dict,
    sedicion_analysis: Dict,
    prisoner_classifications: List[Dict],
    prisoners: List[Prisoner],
    G: nx.Graph,
) -> None:
    """Write all results to JSON, CSV, and log."""

    # ── Compute classification agreement ──
    n_match = sum(1 for p in prisoner_classifications if p["match"])
    n_a = sum(1 for p in prisoner_classifications if p["analyst_regime"] == "A")
    n_b = sum(1 for p in prisoner_classifications if p["analyst_regime"] == "B")
    n_a_match = sum(
        1 for p in prisoner_classifications
        if p["analyst_regime"] == "A" and p["algo_regime"] == "A_algo"
    )
    n_b_match = sum(
        1 for p in prisoner_classifications
        if p["analyst_regime"] == "B" and p["algo_regime"] == "B_algo"
    )

    # ── Community membership lists ──
    communities = defaultdict(list)
    for charge, comm_id in primary_result.partition.items():
        communities[comm_id].append({
            "charge": charge,
            "count": G.nodes[charge]["count"],
        })
    for comm_id in communities:
        communities[comm_id].sort(key=lambda x: x["count"], reverse=True)

    # ── Top co-occurrence pairs ──
    top_edges = sorted(
        G.edges(data=True), key=lambda x: x[2]["weight"], reverse=True
    )[:20]
    top_cooccurrences = [
        {"charge_1": u, "charge_2": v, "weight": d["weight"]}
        for u, v, d in top_edges
    ]

    # ── Assemble full results ──
    results = {
        "metadata": {
            "script": "09_community_detection.py",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "corpus_size": len(prisoners),
            "graph_nodes": G.number_of_nodes(),
            "graph_edges": G.number_of_edges(),
            "graph_density": round(nx.density(G), 6),
            "method": "Louvain (Blondel et al. 2008)",
            "resolution": DEFAULT_RESOLUTION,
            "stability_seeds": STABILITY_SEEDS,
        },
        "primary_result": {
            "n_communities": primary_result.n_communities,
            "modularity": round(primary_result.modularity, 6),
            "sedicion_community": primary_result.sedicion_community,
            "regime_a_community": primary_result.regime_a_community,
            "sedicion_separate_from_regime_a": primary_result.sedicion_separate,
            "all_regime_a_charges_in_same_community": primary_result.regime_a_together,
        },
        "stability": {
            "n_runs": stability.n_runs,
            "sedicion_separate": {
                "count": stability.sedicion_separate_count,
                "pct": stability.sedicion_separate_pct,
            },
            "regime_a_together": {
                "count": stability.regime_a_together_count,
                "pct": stability.regime_a_together_pct,
            },
        },
        "resolution_sweep": resolution_sweep,
        "communities": {
            str(k): v for k, v in communities.items()
        },
        "sedicion_isolation": sedicion_analysis,
        "algebraic_connectivity": algebraic,
        "top_cooccurrences": top_cooccurrences,
        "prisoner_classification_agreement": {
            "total_classified": len(prisoner_classifications),
            "total_match": n_match,
            "match_pct": round(n_match / len(prisoner_classifications) * 100, 1),
            "regime_a_analysts": n_a,
            "regime_a_match": n_a_match,
            "regime_a_match_pct": round(n_a_match / n_a * 100, 1) if n_a > 0 else 0,
            "regime_b_analysts": n_b,
            "regime_b_match": n_b_match,
            "regime_b_match_pct": round(n_b_match / n_b * 100, 1) if n_b > 0 else 0,
        },
    }

    # ── Write JSON ──
    with open(RESULTS_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info(f"Results written to {RESULTS_JSON}")

    # ── Write charge community CSV ──
    with open(CHARGE_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "charge", "count", "community_id", "analyst_regime",
            "degree", "weighted_degree", "degree_centrality",
            "betweenness_centrality", "clustering_coefficient",
        ])
        for m in metrics:
            writer.writerow([
                m.charge, G.nodes[m.charge]["count"], m.community_id,
                m.analyst_regime, m.degree, m.weighted_degree,
                round(m.degree_centrality, 6),
                round(m.betweenness_centrality, 6),
                round(m.clustering_coefficient, 6),
            ])
    logger.info(f"Per-charge communities written to {CHARGE_CSV}")

    # ── Write prisoner regime CSV ──
    with open(PRISONER_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "name", "charges", "arrest_date", "province",
            "analyst_regime", "algo_regime", "match", "primary_community",
        ])
        for p in prisoner_classifications:
            writer.writerow([
                p["id"], p["name"], p["charges"], p["arrest_date"],
                p["province"], p["analyst_regime"], p["algo_regime"],
                p["match"], p["primary_community"],
            ])
    logger.info(f"Per-prisoner regime classification written to {PRISONER_CSV}")

    # ── Summary to log and stdout ──
    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Corpus: {len(prisoners)} prisoners with parseable charges")
    logger.info(f"Graph: {G.number_of_nodes()} charge types, {G.number_of_edges()} co-occurrence edges")
    logger.info(f"Louvain communities (default resolution): {primary_result.n_communities}")
    logger.info(f"Modularity: {primary_result.modularity:.4f}")
    logger.info("")
    logger.info(f"REGIME SEPARATION:")
    logger.info(f"  Sedición in community {primary_result.sedicion_community}")
    logger.info(f"  Regime A bundle in community {primary_result.regime_a_community}")
    logger.info(f"  Sedición separate from Regime A: {primary_result.sedicion_separate}")
    logger.info(f"  All four Regime A charges together: {primary_result.regime_a_together}")
    logger.info("")
    logger.info(f"STABILITY ({stability.n_runs} runs):")
    logger.info(f"  Sedición separate: {stability.sedicion_separate_count}/{stability.n_runs} ({stability.sedicion_separate_pct:.1f}%)")
    logger.info(f"  Regime A together: {stability.regime_a_together_count}/{stability.n_runs} ({stability.regime_a_together_pct:.1f}%)")
    logger.info("")
    logger.info(f"SEDICIÓN ISOLATION:")
    logger.info(f"  Standalone: {sedicion_analysis['sedicion_standalone']}/{sedicion_analysis['total_prisoners_with_sedicion']} ({sedicion_analysis['sedicion_standalone_pct']}%)")
    logger.info(f"  Weighted degree: {sedicion_analysis['sedicion_weighted_degree']} (vs Desacato: {sedicion_analysis['desacato_weighted_degree']})")
    logger.info("")
    logger.info(f"PRISONER CLASSIFICATION AGREEMENT:")
    logger.info(f"  Regime A: {n_a_match}/{n_a} match ({round(n_a_match/n_a*100,1) if n_a else 0}%)")
    logger.info(f"  Regime B: {n_b_match}/{n_b} match ({round(n_b_match/n_b*100,1) if n_b else 0}%)")
    logger.info(f"  Overall:  {n_match}/{len(prisoner_classifications)} match ({round(n_match/len(prisoner_classifications)*100,1)}%)")
    logger.info("=" * 70)


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Step 09: Community detection on the charge co-occurrence graph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python 09_community_detection.py prisoners.csv
    python 09_community_detection.py prisoners.csv --resolution 1.0 --seeds 200
    python 09_community_detection.py prisoners.csv --output-dir results/
        """,
    )
    parser.add_argument(
        "csv_path",
        type=Path,
        help="Path to the prisoners.csv file (from Step 01/02)",
    )
    parser.add_argument(
        "--resolution",
        type=float,
        default=DEFAULT_RESOLUTION,
        help=f"Louvain resolution parameter (default: {DEFAULT_RESOLUTION})",
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=STABILITY_SEEDS,
        help=f"Number of random seeds for stability test (default: {STABILITY_SEEDS})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for results (default: current directory)",
    )
    args = parser.parse_args()

    # Update output paths from args
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    results_json = out / "09_community_detection_results.json"
    charge_csv = out / "09_charge_communities.csv"
    prisoner_csv = out / "09_prisoner_regime_algo.csv"
    stability_seeds = args.seeds
    resolution = args.resolution

    logger.info(f"Step 09: Community detection on charge co-occurrence graph")
    logger.info(f"Input: {args.csv_path}")
    logger.info(f"Resolution: {resolution}, Seeds: {stability_seeds}")

    # ── Load corpus ──
    prisoners = load_corpus(args.csv_path)

    # ── Build charge co-occurrence graph ──
    G = build_charge_cooccurrence_graph(prisoners)

    # ── Primary Louvain run ──
    logger.info("Running Louvain community detection (primary run)...")
    primary = run_louvain(G, resolution=resolution, seed=42)
    logger.info(
        f"Primary result: {primary.n_communities} communities, "
        f"Q={primary.modularity:.4f}, "
        f"Sedición separate={primary.sedicion_separate}, "
        f"Regime A together={primary.regime_a_together}"
    )

    # ── Stability test ──
    logger.info(f"Running stability test ({stability_seeds} seeds)...")
    stability = run_stability_test(G, n_runs=stability_seeds, resolution=resolution)

    # ── Resolution sweep ──
    logger.info("Running resolution sweep...")
    sweep = run_resolution_sweep(G)

    # ── Network metrics ──
    logger.info("Computing network metrics...")
    metrics = compute_network_metrics(G, primary.partition)

    # ── Algebraic connectivity ──
    logger.info("Computing algebraic connectivity...")
    algebraic = compute_algebraic_connectivity(G)

    # ── Sedicion isolation ──
    logger.info("Analyzing Sedicion isolation...")
    sed_analysis = analyze_sedicion_isolation(G, prisoners)

    # ── Prisoner classification ──
    logger.info("Classifying prisoners by algorithmic regime...")
    classifications = classify_prisoners_by_algorithm(
        prisoners, primary.partition,
        primary.sedicion_community, primary.regime_a_community,
    )

    # ── Patch output paths into write_results ──
    global RESULTS_JSON, CHARGE_CSV, PRISONER_CSV
    RESULTS_JSON = results_json
    CHARGE_CSV = charge_csv
    PRISONER_CSV = prisoner_csv

    # ── Write everything ──
    write_results(
        primary, stability, sweep, metrics, algebraic,
        sed_analysis, classifications, prisoners, G,
    )

    logger.info("Step 09 complete.")


if __name__ == "__main__":
    main()
