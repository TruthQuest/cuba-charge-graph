"""
Cuban Political Prisoners Network Analysis
===========================================

Production-grade network analysis using DIRECT TRIPLE ITERATION.
SPARQL is slow and stupid - we just walk the triples in Python.

Author: Designed for investigative journalism and international legal proceedings
License: Non-commercial use only
"""

import networkx as nx
from rdflib import Graph, Namespace, RDF
from datetime import datetime
from collections import defaultdict, Counter
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set, Any
from dataclasses import dataclass
import math
import logging
import sys
import json
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('network_analysis.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Base exception for network analysis errors."""
    pass


class GraphConstructionError(AnalysisError):
    """Raised when graph construction fails."""
    pass


class ValidationError(AnalysisError):
    """Raised when data validation fails."""
    pass


class NodeType(Enum):
    """Enumeration of node types in the heterogeneous graph."""
    PERSON = "person"
    CHARGE = "charge"
    CHARGE_TYPE = "charge_type"
    FACILITY = "facility"
    ARREST = "arrest"
    ARREST_WAVE = "arrest_wave"
    PROVINCE = "province"


@dataclass
class NetworkMetrics:
    """Container for computed network metrics."""
    node_count: int = 0
    edge_count: int = 0
    person_nodes: int = 0
    charge_instances: int = 0
    facilities: int = 0
    arrest_events: int = 0
    density: float = 0.0
    avg_degree: float = 0.0
    components: int = 0
    largest_component_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
        return {
            'node_count': self.node_count,
            'edge_count': self.edge_count,
            'person_nodes': self.person_nodes,
            'charge_instances': self.charge_instances,
            'facilities': self.facilities,
            'arrest_events': self.arrest_events,
            'density': round(self.density, 6),
            'avg_degree': round(self.avg_degree, 2),
            'components': self.components,
            'largest_component_size': self.largest_component_size
        }


@dataclass
class CoDetentionAnalysis:
    """Results from co-detention network analysis."""
    edge_count: int
    node_count: int
    largest_cluster_size: int
    avg_shared_facilities: float
    max_shared_facilities: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'edge_count': self.edge_count,
            'node_count': self.node_count,
            'largest_cluster_size': self.largest_cluster_size,
            'avg_shared_facilities': round(self.avg_shared_facilities, 2),
            'max_shared_facilities': self.max_shared_facilities
        }


class PrisonerNetworkAnalyzer:
    """
    Production-grade network analyzer using direct triple iteration.

    NO SPARQL - just walk the triples. Orders of magnitude faster.
    """

    # RDF Namespaces
    ONT = Namespace("http://prisoners.defenders.org/ontology#")
    PD = Namespace("http://prisoners.defenders.org/data#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")

    def __init__(self, ttl_path: Path):
        """
        Initialize analyzer with TTL file.

        Args:
            ttl_path: Path to Turtle RDF file

        Raises:
            FileNotFoundError: If TTL file doesn't exist
            GraphConstructionError: If RDF parsing fails
        """
        self.ttl_path = Path(ttl_path)
        if not self.ttl_path.exists():
            raise FileNotFoundError(f"TTL file not found: {self.ttl_path}")

        logger.info(f"Initializing analyzer with {self.ttl_path}")

        self.rdf_graph: Optional[Graph] = None
        self.network_graph: Optional[nx.MultiDiGraph] = None
        self.metrics: Optional[NetworkMetrics] = None

        # Node type tracking
        self._person_nodes: Set[str] = set()
        self._charge_nodes: Set[str] = set()
        self._facility_nodes: Set[str] = set()
        self._arrest_nodes: Set[str] = set()

        # Triple indices for fast lookups
        self._subjects_by_predicate: Dict[str, Set[str]] = defaultdict(set)
        self._objects_by_subject_predicate: Dict[Tuple[str, str], Set[str]] = defaultdict(set)

        # Load RDF graph
        try:
            self._load_rdf()
        except Exception as e:
            logger.error(f"Failed to load RDF graph: {e}", exc_info=True)
            raise GraphConstructionError(f"RDF loading failed: {e}") from e

    def _load_rdf(self) -> None:
        """Load and validate RDF graph from TTL file."""
        logger.info("Loading RDF graph from TTL")

        try:
            self.rdf_graph = Graph()
            self.rdf_graph.parse(self.ttl_path, format="turtle")

            triple_count = len(self.rdf_graph)
            logger.info(f"Loaded {triple_count:,} RDF triples")

            if triple_count == 0:
                raise ValidationError("RDF graph is empty")

            # Build indices for fast lookups
            logger.info("Building triple indices...")
            for s, p, o in self.rdf_graph:
                s_str = str(s)
                p_str = str(p)
                o_str = str(o)

                self._subjects_by_predicate[p_str].add(s_str)
                self._objects_by_subject_predicate[(s_str, p_str)].add(o_str)

            logger.info(f"Indexed {len(self._subjects_by_predicate)} unique predicates")

        except Exception as e:
            logger.error(f"RDF parsing error: {e}", exc_info=True)
            raise

    def _get_objects(self, subject: str, predicate: str) -> Set[str]:
        """Fast lookup of objects for subject-predicate pair."""
        return self._objects_by_subject_predicate.get((subject, predicate), set())

    def build_heterogeneous_graph(self) -> nx.MultiDiGraph:
        """
        Build multi-layer heterogeneous network from RDF.

        Uses DIRECT TRIPLE ITERATION - no SPARQL.

        Returns:
            NetworkX MultiDiGraph with typed nodes and relationships

        Raises:
            GraphConstructionError: If graph construction fails
        """
        logger.info("Building heterogeneous network graph (direct triple iteration)")

        if self.rdf_graph is None:
            raise GraphConstructionError("RDF graph not loaded")

        try:
            self.network_graph = nx.MultiDiGraph()

            # Find all political prisoners
            rdf_type = str(RDF.type)
            political_prisoner_type = str(self.ONT.PoliticalPrisoner)

            prisoners = self._subjects_by_predicate.get(rdf_type, set())
            prisoners = {p for p in prisoners if political_prisoner_type in self._get_objects(p, rdf_type)}

            logger.info(f"Found {len(prisoners)} political prisoners")

            if len(prisoners) == 0:
                raise ValidationError("No political prisoners found in dataset")

            edge_count = 0

            # Process each prisoner
            for i, person_uri in enumerate(prisoners, 1):
                if i % 100 == 0:
                    logger.info(f"Processing prisoner {i}/{len(prisoners)}...")

                try:
                    # Add person node
                    name_objs = self._get_objects(person_uri, str(self.ONT.fullName))
                    name = list(name_objs)[0] if name_objs else ''

                    self.network_graph.add_node(
                        person_uri,
                        type=NodeType.PERSON.value,
                        name=name
                    )
                    self._person_nodes.add(person_uri)

                    # Get charges
                    charges = self._get_objects(person_uri, str(self.ONT.chargedWith))
                    for charge_uri in charges:
                        self.network_graph.add_node(charge_uri, type=NodeType.CHARGE.value)
                        self._charge_nodes.add(charge_uri)
                        self.network_graph.add_edge(person_uri, charge_uri, rel='charged_with')
                        edge_count += 1

                        # Get charge type
                        charge_types = self._get_objects(charge_uri, str(self.ONT.hasChargeType))
                        for type_uri in charge_types:
                            self.network_graph.add_node(type_uri, type=NodeType.CHARGE_TYPE.value)
                            self.network_graph.add_edge(charge_uri, type_uri, rel='has_type')
                            edge_count += 1

                    # Get facilities
                    facilities = self._get_objects(person_uri, str(self.ONT.detainedAt))
                    for fac_uri in facilities:
                        self.network_graph.add_node(fac_uri, type=NodeType.FACILITY.value)
                        self._facility_nodes.add(fac_uri)
                        self.network_graph.add_edge(person_uri, fac_uri, rel='detained_at')
                        edge_count += 1

                    # Get arrests
                    arrests = self._get_objects(person_uri, str(self.ONT.arrested))
                    for arrest_uri in arrests:
                        date_objs = self._get_objects(arrest_uri, str(self.ONT.arrestDate))
                        date = list(date_objs)[0] if date_objs else None

                        self.network_graph.add_node(
                            arrest_uri,
                            type=NodeType.ARREST.value,
                            date=str(date) if date else None
                        )
                        self._arrest_nodes.add(arrest_uri)
                        self.network_graph.add_edge(person_uri, arrest_uri, rel='arrested')
                        edge_count += 1

                        # Get arrest wave
                        waves = self._get_objects(arrest_uri, str(self.ONT.partOfWave))
                        for wave_uri in waves:
                            self.network_graph.add_node(wave_uri, type=NodeType.ARREST_WAVE.value)
                            self.network_graph.add_edge(arrest_uri, wave_uri, rel='part_of_wave')
                            edge_count += 1

                    # Get province
                    provinces = self._get_objects(person_uri, str(self.ONT.residesInProvince))
                    for prov_uri in provinces:
                        self.network_graph.add_node(prov_uri, type=NodeType.PROVINCE.value)
                        self.network_graph.add_edge(person_uri, prov_uri, rel='resides_in')
                        edge_count += 1

                except Exception as e:
                    logger.warning(f"Error processing prisoner {person_uri}: {e}")
                    continue

            logger.info(f"Graph construction complete: {self.network_graph.number_of_nodes():,} nodes, "
                       f"{self.network_graph.number_of_edges():,} edges")

            # Compute metrics
            self._compute_metrics()

            return self.network_graph

        except Exception as e:
            logger.error(f"Graph construction failed: {e}", exc_info=True)
            raise GraphConstructionError(f"Failed to build graph: {e}") from e

    def _compute_metrics(self) -> None:
        """Compute basic network metrics."""
        try:
            if self.network_graph is None:
                raise GraphConstructionError("Network graph not built")

            logger.info("Computing network metrics...")

            # Convert to undirected for component analysis
            G_undirected = self.network_graph.to_undirected()

            components = list(nx.connected_components(G_undirected))
            largest_component = max(components, key=len) if components else set()

            self.metrics = NetworkMetrics(
                node_count=self.network_graph.number_of_nodes(),
                edge_count=self.network_graph.number_of_edges(),
                person_nodes=len(self._person_nodes),
                charge_instances=len(self._charge_nodes),
                facilities=len(self._facility_nodes),
                arrest_events=len(self._arrest_nodes),
                density=nx.density(G_undirected) if G_undirected.number_of_nodes() > 0 else 0,
                avg_degree=sum(dict(G_undirected.degree()).values()) / max(G_undirected.number_of_nodes(), 1),
                components=len(components),
                largest_component_size=len(largest_component)
            )

            logger.info(f"Metrics computed: {self.metrics.to_dict()}")

        except Exception as e:
            logger.error(f"Metrics computation failed: {e}", exc_info=True)
            raise

    def analyze_codetention(self) -> CoDetentionAnalysis:
        """
        Analyze co-detention patterns (people in same facility).

        Returns:
            CoDetentionAnalysis with cluster metrics

        Raises:
            AnalysisError: If analysis fails
        """
        logger.info("Starting co-detention analysis")

        if self.network_graph is None:
            raise AnalysisError("Network graph not built. Call build_heterogeneous_graph() first.")

        try:
            # Build person-to-person network based on shared facilities
            CoDetention = nx.Graph()

            # Group inmates by facility
            facility_inmates = defaultdict(list)
            for person in self._person_nodes:
                for neighbor in self.network_graph.neighbors(person):
                    if self.network_graph.nodes[neighbor]['type'] == NodeType.FACILITY.value:
                        facility_inmates[neighbor].append(person)

            logger.info(f"Found {len(facility_inmates)} facilities with inmates")

            # Add edges between co-detained persons
            shared_facility_counts = []

            for facility, inmates in facility_inmates.items():
                for i, p1 in enumerate(inmates):
                    for p2 in inmates[i+1:]:
                        if CoDetention.has_edge(p1, p2):
                            CoDetention[p1][p2]['weight'] += 1
                            CoDetention[p1][p2]['facilities'].append(facility)
                        else:
                            CoDetention.add_edge(p1, p2, weight=1, facilities=[facility])

            # Calculate metrics
            if CoDetention.number_of_nodes() > 0:
                components = sorted(nx.connected_components(CoDetention), key=len, reverse=True)
                largest_cluster = len(components[0]) if components else 0

                # Shared facility statistics
                for u, v, data in CoDetention.edges(data=True):
                    shared_facility_counts.append(data['weight'])

                avg_shared = sum(shared_facility_counts) / len(shared_facility_counts) if shared_facility_counts else 0
                max_shared = max(shared_facility_counts) if shared_facility_counts else 0
            else:
                largest_cluster = 0
                avg_shared = 0
                max_shared = 0

            analysis = CoDetentionAnalysis(
                edge_count=CoDetention.number_of_edges(),
                node_count=CoDetention.number_of_nodes(),
                largest_cluster_size=largest_cluster,
                avg_shared_facilities=avg_shared,
                max_shared_facilities=max_shared
            )

            logger.info(f"Co-detention analysis complete: {analysis.to_dict()}")

            return analysis

        except Exception as e:
            logger.error(f"Co-detention analysis failed: {e}", exc_info=True)
            raise AnalysisError(f"Co-detention analysis failed: {e}") from e

    def analyze_charge_stacking(self) -> Dict[str, Any]:
        """
        Analyze charge co-occurrence patterns.

        Returns:
            Dictionary with stacking patterns and metrics

        Raises:
            AnalysisError: If analysis fails
        """
        logger.info("Starting charge stacking analysis")

        if self.network_graph is None:
            raise AnalysisError("Network graph not built")

        try:
            ChargeCoOccur = nx.Graph()

            # Build charge type co-occurrence network
            for person in self._person_nodes:
                charge_types = []

                # Get all charge types for this person
                for charge in self.network_graph.neighbors(person):
                    if self.network_graph.nodes[charge]['type'] == NodeType.CHARGE.value:
                        for charge_type in self.network_graph.neighbors(charge):
                            if self.network_graph.nodes[charge_type]['type'] == NodeType.CHARGE_TYPE.value:
                                charge_types.append(charge_type)

                # Add co-occurrence edges
                if len(charge_types) > 1:
                    for i, c1 in enumerate(charge_types):
                        for c2 in charge_types[i+1:]:
                            if ChargeCoOccur.has_edge(c1, c2):
                                ChargeCoOccur[c1][c2]['weight'] += 1
                            else:
                                ChargeCoOccur.add_edge(c1, c2, weight=1)

            # Find most common combinations
            edges_by_weight = sorted(
                ChargeCoOccur.edges(data=True),
                key=lambda x: x[2]['weight'],
                reverse=True
            )

            top_combinations = [
                {
                    'charge1': str(c1).split('#')[-1],
                    'charge2': str(c2).split('#')[-1],
                    'count': data['weight']
                }
                for c1, c2, data in edges_by_weight[:10]
            ]

            result = {
                'total_edges': ChargeCoOccur.number_of_edges(),
                'total_nodes': ChargeCoOccur.number_of_nodes(),
                'top_combinations': top_combinations,
                'density': nx.density(ChargeCoOccur) if ChargeCoOccur.number_of_nodes() > 0 else 0
            }

            logger.info(f"Charge stacking analysis complete: {result['total_edges']} co-occurrences")

            return result

        except Exception as e:
            logger.error(f"Charge stacking analysis failed: {e}", exc_info=True)
            raise AnalysisError(f"Charge stacking analysis failed: {e}") from e

    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two points.

        Args:
            lat1, lon1: First point coordinates
            lat2, lon2: Second point coordinates

        Returns:
            Distance in kilometers
        """
        try:
            R = 6371  # Earth radius in km
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

            dlat = lat2 - lat1
            dlon = lon2 - lon1

            a = (math.sin(dlat/2)**2 +
                 math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2)

            c = 2 * math.asin(math.sqrt(a))

            return R * c

        except Exception as e:
            logger.warning(f"Haversine calculation error: {e}")
            return 0.0

    def analyze_geographic_displacement(self) -> Dict[str, Any]:
        """
        Analyze distance between home province and detention facility.

        Returns:
            Dictionary with displacement statistics

        Raises:
            AnalysisError: If analysis fails
        """
        logger.info("Starting geographic displacement analysis")

        if self.rdf_graph is None:
            raise AnalysisError("RDF graph not loaded")

        try:
            distances = []

            # Walk triples directly - no SPARQL
            for person in self._person_nodes:
                try:
                    # Get province coordinates
                    provinces = self._get_objects(person, str(self.ONT.residesInProvince))
                    facilities = self._get_objects(person, str(self.ONT.detainedAt))

                    if not provinces or not facilities:
                        continue

                    province = list(provinces)[0]
                    facility = list(facilities)[0]

                    # Get province lat/long
                    p_lats = self._get_objects(province, str(self.GEO.lat))
                    p_longs = self._get_objects(province, str(self.GEO.long))

                    # Get facility lat/long
                    f_lats = self._get_objects(facility, str(self.GEO.lat))
                    f_longs = self._get_objects(facility, str(self.GEO.long))

                    if p_lats and p_longs and f_lats and f_longs:
                        p_lat = float(list(p_lats)[0])
                        p_long = float(list(p_longs)[0])
                        f_lat = float(list(f_lats)[0])
                        f_long = float(list(f_longs)[0])

                        dist = self.haversine_distance(p_lat, p_long, f_lat, f_long)
                        distances.append(dist)

                except (ValueError, TypeError, IndexError) as e:
                    continue

            logger.info(f"Calculated displacement for {len(distances)} cases")

            if not distances:
                return {
                    'cases_analyzed': 0,
                    'avg_displacement_km': 0,
                    'max_displacement_km': 0,
                    'min_displacement_km': 0
                }

            result = {
                'cases_analyzed': len(distances),
                'avg_displacement_km': round(sum(distances) / len(distances), 2),
                'max_displacement_km': round(max(distances), 2),
                'min_displacement_km': round(min(distances), 2)
            }

            logger.info(f"Geographic displacement analysis complete: {result}")

            return result

        except Exception as e:
            logger.error(f"Geographic displacement analysis failed: {e}", exc_info=True)
            raise AnalysisError(f"Geographic displacement analysis failed: {e}") from e

    def export_metrics(self, output_path: Path) -> None:
        """
        Export all computed metrics to JSON.

        Args:
            output_path: Path for JSON output file

        Raises:
            IOError: If file write fails
        """
        try:
            if self.metrics is None:
                raise AnalysisError("No metrics computed. Run analyses first.")

            output_data = {
                'timestamp': datetime.now().isoformat(),
                'source_file': str(self.ttl_path),
                'basic_metrics': self.metrics.to_dict(),
            }

            with open(output_path, 'w') as f:
                json.dump(output_data, f, indent=2)

            logger.info(f"Metrics exported to {output_path}")

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            raise IOError(f"Failed to export metrics: {e}") from e


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function with full error handling."""
    try:
        logger.info("="*80)
        logger.info("CUBAN POLITICAL PRISONERS NETWORK ANALYSIS")
        logger.info("Direct Triple Iteration - NO SPARQL")
        logger.info("="*80)

        # Initialize analyzer
        ttl_path = Path("cuban_prisoners_final_skos.ttl")
        analyzer = PrisonerNetworkAnalyzer(ttl_path)

        # Build heterogeneous graph
        logger.info("\n" + "="*80)
        logger.info("STEP 1: Building Heterogeneous Network")
        logger.info("="*80)
        analyzer.build_heterogeneous_graph()

        if analyzer.metrics:
            print("\nBasic Network Metrics:")
            for key, value in analyzer.metrics.to_dict().items():
                print(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")

        # Co-detention analysis
        logger.info("\n" + "="*80)
        logger.info("STEP 2: Co-Detention Network Analysis")
        logger.info("="*80)
        codetention = analyzer.analyze_codetention()

        print("\nCo-Detention Analysis:")
        for key, value in codetention.to_dict().items():
            print(f"  {key}: {value}")

        # Charge stacking analysis
        logger.info("\n" + "="*80)
        logger.info("STEP 3: Charge Stacking Analysis")
        logger.info("="*80)
        stacking = analyzer.analyze_charge_stacking()

        print("\nCharge Stacking Analysis:")
        print(f"  Total co-occurrences: {stacking['total_edges']}")
        print(f"  Unique charge types: {stacking['total_nodes']}")
        print("\n  Top 5 combinations:")
        for combo in stacking['top_combinations'][:5]:
            print(f"    {combo['count']:3d}x  {combo['charge1']} + {combo['charge2']}")

        # Geographic displacement
        logger.info("\n" + "="*80)
        logger.info("STEP 4: Geographic Displacement Analysis")
        logger.info("="*80)
        displacement = analyzer.analyze_geographic_displacement()

        print("\nGeographic Displacement:")
        for key, value in displacement.items():
            print(f"  {key}: {value}")

        # Export results
        output_path = Path("network_analysis_results.json")
        analyzer.export_metrics(output_path)

        logger.info("\n" + "="*80)
        logger.info("ANALYSIS COMPLETE")
        logger.info("="*80)
        print(f"\nResults exported to: {output_path}")

        return 0

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        print(f"ERROR: Data validation failed - {e}", file=sys.stderr)
        return 1

    except GraphConstructionError as e:
        logger.error(f"Graph construction error: {e}")
        print(f"ERROR: Failed to build network graph - {e}", file=sys.stderr)
        return 1

    except AnalysisError as e:
        logger.error(f"Analysis error: {e}")
        print(f"ERROR: Network analysis failed - {e}", file=sys.stderr)
        return 1

    except Exception as e:
        logger.critical(f"Unexpected error: {e}", exc_info=True)
        print(f"CRITICAL ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())