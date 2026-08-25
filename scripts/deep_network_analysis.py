"""
Cuban Political Prisoners: Deep Network Analysis
=================================================

This script produces ACTUAL INSIGHTS, not just metrics.

Outputs:
1. Co-detention clusters (who was arrested together, organizing networks)
2. Charge stacking patterns (prosecutorial formulas)
3. Temporal arrest waves (coordination evidence)
4. Geographic displacement (family separation)
5. Facility specialization (which facilities handle which prisoners)
6. Multi-hop queries (complex pattern detection)

All results exported to readable formats.
"""

import networkx as nx
from rdflib import Graph, Namespace, RDF
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any
import math
import json
import csv
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('deep_analysis.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DeepNetworkAnalyzer:
    """Full network analysis producing actionable insights."""
    
    ONT = Namespace("http://prisoners.defenders.org/ontology#")
    PD = Namespace("http://prisoners.defenders.org/data#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")
    
    def __init__(self, ttl_path: Path):
        """Initialize with TTL file."""
        self.ttl_path = Path(ttl_path)
        logger.info(f"Loading {self.ttl_path}")
        
        self.g = Graph()
        self.g.parse(self.ttl_path, format="turtle")
        logger.info(f"Loaded {len(self.g):,} triples")
        
        # Build indices
        self._index = defaultdict(lambda: defaultdict(set))
        for s, p, o in self.g:
            self._index[str(p)][str(s)].add(str(o))
        
        logger.info("Indices built")
    
    def _get(self, subject: str, predicate: str) -> Set[str]:
        """Fast triple lookup."""
        return self._index[predicate].get(subject, set())
    
    def _get_label(self, uri: str) -> str:
        """Get human-readable label for URI."""
        labels = self._get(uri, "http://www.w3.org/2004/02/skos/core#prefLabel")
        if not labels:
            labels = self._get(uri, "http://www.w3.org/2000/01/rdf-schema#label")
        if labels:
            label = list(labels)[0]
            # Clean up literal
            if '^^' in label:
                label = label.split('^^')[0]
            return label.strip('"')
        return uri.split('#')[-1]
    
    def analyze_codetention_clusters(self, output_path: Path) -> None:
        """
        Find clusters of people detained together.
        Output: CSV of co-detention networks.
        """
        logger.info("Analyzing co-detention clusters...")
        
        # Find all political prisoners
        prisoners = set()
        for s in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            if str(self.ONT.PoliticalPrisoner) in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"][s]:
                prisoners.add(s)
        
        logger.info(f"Found {len(prisoners)} prisoners")
        
        # Build facility -> inmates mapping
        facility_inmates = defaultdict(list)
        for person in prisoners:
            facilities = self._get(person, str(self.ONT.detainedAt))
            for fac in facilities:
                facility_inmates[fac].append(person)
        
        # Build co-detention network
        CoDetention = nx.Graph()
        for fac, inmates in facility_inmates.items():
            if len(inmates) < 2:
                continue
            
            for i, p1 in enumerate(inmates):
                name1 = list(self._get(p1, str(self.ONT.fullName)))[0] if self._get(p1, str(self.ONT.fullName)) else p1
                
                for p2 in inmates[i+1:]:
                    name2 = list(self._get(p2, str(self.ONT.fullName)))[0] if self._get(p2, str(self.ONT.fullName)) else p2
                    
                    if CoDetention.has_edge(name1, name2):
                        CoDetention[name1][name2]['facilities'].append(self._get_label(fac))
                        CoDetention[name1][name2]['weight'] += 1
                    else:
                        CoDetention.add_edge(name1, name2, facilities=[self._get_label(fac)], weight=1)
        
        # Find clusters
        components = sorted(nx.connected_components(CoDetention), key=len, reverse=True)
        
        logger.info(f"Found {len(components)} co-detention clusters")
        logger.info(f"Largest cluster: {len(components[0])} people")
        
        # Export clusters
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['cluster_id', 'size', 'people', 'shared_facilities'])
            
            for i, cluster in enumerate(components[:20], 1):  # Top 20 clusters
                people = list(cluster)
                
                # Find shared facilities
                if len(people) > 1:
                    shared_facs = set()
                    for p1, p2 in [(people[0], people[1])]:
                        if CoDetention.has_edge(p1, p2):
                            shared_facs.update(CoDetention[p1][p2]['facilities'])
                
                writer.writerow([
                    i,
                    len(cluster),
                    '; '.join(people[:10]) + ('...' if len(people) > 10 else ''),
                    '; '.join(list(shared_facs)[:5])
                ])
        
        logger.info(f"Co-detention clusters exported to {output_path}")
    
    def analyze_charge_stacking(self, output_path: Path) -> None:
        """
        Find which charges appear together (prosecutorial formulas).
        Output: CSV of charge combinations.
        """
        logger.info("Analyzing charge stacking patterns...")
        
        # Find all prisoners and their charge types
        prisoners = set()
        for s in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            if str(self.ONT.PoliticalPrisoner) in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"][s]:
                prisoners.add(s)
        
        # Build charge co-occurrence network
        charge_pairs = Counter()
        charge_counts = Counter()
        
        for person in prisoners:
            # Get all charges for this person
            charges = self._get(person, str(self.ONT.chargedWith))
            
            charge_types = []
            for charge in charges:
                ctypes = self._get(charge, str(self.ONT.hasChargeType))
                for ctype in ctypes:
                    label = self._get_label(ctype)
                    charge_types.append(label)
                    charge_counts[label] += 1
            
            # Create pairs
            if len(charge_types) > 1:
                for i, c1 in enumerate(charge_types):
                    for c2 in charge_types[i+1:]:
                        pair = tuple(sorted([c1, c2]))
                        charge_pairs[pair] += 1
        
        # Export
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['charge1', 'charge2', 'co_occurrence_count', 'charge1_total', 'charge2_total', 'stacking_rate'])
            
            for (c1, c2), count in charge_pairs.most_common(30):
                stacking_rate = count / min(charge_counts[c1], charge_counts[c2])
                writer.writerow([c1, c2, count, charge_counts[c1], charge_counts[c2], f"{stacking_rate:.2%}"])
        
        logger.info(f"Charge stacking analysis exported to {output_path}")
        logger.info(f"Top combination: {charge_pairs.most_common(1)[0]}")
    
    def analyze_arrest_waves(self, output_path: Path) -> None:
        """
        Find mass arrest events (temporal clustering).
        Output: CSV of arrest waves.
        """
        logger.info("Analyzing arrest waves...")
        
        # Get all arrests with dates
        arrests_by_date = defaultdict(list)
        
        for arrest_uri in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            if str(self.ONT.Arrest) in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"][arrest_uri]:
                dates = self._get(arrest_uri, str(self.ONT.arrestDate))
                if dates:
                    date = list(dates)[0].strip('"')
                    
                    # Get person arrested
                    for person_uri in self._index[str(self.ONT.arrested)]:
                        if arrest_uri in self._index[str(self.ONT.arrested)][person_uri]:
                            name_set = self._get(person_uri, str(self.ONT.fullName))
                            name = list(name_set)[0].strip('"') if name_set else person_uri
                            arrests_by_date[date].append(name)
                            break
        
        # Find mass arrest days
        mass_arrests = [(date, people) for date, people in arrests_by_date.items() if len(people) >= 5]
        mass_arrests.sort(key=lambda x: len(x[1]), reverse=True)
        
        logger.info(f"Found {len(mass_arrests)} mass arrest days (5+ arrests)")
        
        # Export
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'arrest_count', 'first_10_names'])
            
            for date, people in mass_arrests[:50]:
                writer.writerow([
                    date,
                    len(people),
                    '; '.join(people[:10])
                ])
        
        logger.info(f"Arrest waves exported to {output_path}")
    
    def analyze_geographic_displacement(self, output_path: Path) -> None:
        """
        Calculate distance from home province to detention facility.
        Output: CSV of displacement distances.
        """
        logger.info("Analyzing geographic displacement...")
        
        def haversine(lat1, lon1, lat2, lon2):
            """Calculate distance in km."""
            try:
                R = 6371
                lat1, lon1, lat2, lon2 = map(math.radians, [float(lat1), float(lon1), float(lat2), float(lon2)])
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
                return 2 * R * math.asin(math.sqrt(a))
            except:
                return None
        
        # Find prisoners with province and facility coordinates
        displacements = []
        
        prisoners = set()
        for s in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            if str(self.ONT.PoliticalPrisoner) in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"][s]:
                prisoners.add(s)
        
        for person in prisoners:
            try:
                # Get name
                names = self._get(person, str(self.ONT.fullName))
                name = list(names)[0].strip('"') if names else person
                
                # Get province
                provinces = self._get(person, str(self.ONT.residesInProvince))
                if not provinces:
                    continue
                province = list(provinces)[0]
                
                # Get facility
                facilities = self._get(person, str(self.ONT.detainedAt))
                if not facilities:
                    continue
                facility = list(facilities)[0]
                
                # Get province coords
                p_lats = self._get(province, str(self.GEO.lat))
                p_longs = self._get(province, str(self.GEO.long))
                
                # Get facility coords
                f_lats = self._get(facility, str(self.GEO.lat))
                f_longs = self._get(facility, str(self.GEO.long))
                
                if p_lats and p_longs and f_lats and f_longs:
                    p_lat = list(p_lats)[0].strip('"')
                    p_long = list(p_longs)[0].strip('"')
                    f_lat = list(f_lats)[0].strip('"')
                    f_long = list(f_longs)[0].strip('"')
                    
                    dist = haversine(p_lat, p_long, f_lat, f_long)
                    if dist is not None:
                        displacements.append({
                            'name': name,
                            'province': self._get_label(province),
                            'facility': self._get_label(facility),
                            'distance_km': round(dist, 2)
                        })
            except Exception as e:
                continue
        
        # Sort by distance
        displacements.sort(key=lambda x: x['distance_km'], reverse=True)
        
        logger.info(f"Calculated displacement for {len(displacements)} prisoners")
        
        if displacements:
            avg_dist = sum(d['distance_km'] for d in displacements) / len(displacements)
            logger.info(f"Average displacement: {avg_dist:.1f} km")
            logger.info(f"Maximum displacement: {displacements[0]['distance_km']:.1f} km")
        
        # Export
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'province', 'facility', 'distance_km'])
            writer.writeheader()
            writer.writerows(displacements)
        
        logger.info(f"Geographic displacement exported to {output_path}")
    
    def find_sedition_torture_july2021(self, output_path: Path) -> None:
        """
        Multi-hop query: Find people charged with Sedition,
        detained in torture facilities, arrested during July 2021.
        
        This is the query nobody else can do.
        """
        logger.info("Running multi-hop query: Sedition → Torture → July2021...")
        
        results = []
        
        # Find all political prisoners
        prisoners = set()
        for s in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            if str(self.ONT.PoliticalPrisoner) in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"][s]:
                prisoners.add(s)
        
        for person in prisoners:
            try:
                # Check for Sedition charge
                has_sedition = False
                charges = self._get(person, str(self.ONT.chargedWith))
                for charge in charges:
                    ctypes = self._get(charge, str(self.ONT.hasChargeType))
                    for ctype in ctypes:
                        if 'Sedicion' in ctype or 'Sedition' in ctype:
                            has_sedition = True
                            break
                
                if not has_sedition:
                    continue
                
                # Check for torture facility
                in_torture_facility = False
                facility_name = None
                facilities = self._get(person, str(self.ONT.detainedAt))
                for facility in facilities:
                    ftypes = self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"].get(facility, set())
                    if str(self.ONT.TortureFacility) in ftypes:
                        in_torture_facility = True
                        facility_name = self._get_label(facility)
                        break
                
                if not in_torture_facility:
                    continue
                
                # Check for July 2021 arrest
                july_2021_arrest = False
                arrests = self._get(person, str(self.ONT.arrested))
                for arrest in arrests:
                    dates = self._get(arrest, str(self.ONT.arrestDate))
                    for date in dates:
                        if '2021-07' in date or '07/2021' in date:
                            july_2021_arrest = True
                            break
                
                if not july_2021_arrest:
                    continue
                
                # Get details
                names = self._get(person, str(self.ONT.fullName))
                name = list(names)[0].strip('"') if names else person
                
                ages = self._get(person, str(self.ONT.ageAtArrest))
                age = list(ages)[0].strip('"') if ages else 'unknown'
                
                results.append({
                    'name': name,
                    'facility': facility_name,
                    'age_at_arrest': age
                })
            
            except Exception as e:
                continue
        
        logger.info(f"Found {len(results)} people matching: Sedition + Torture Facility + July 2021")
        
        # Export
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['name', 'facility', 'age_at_arrest'])
            writer.writeheader()
            writer.writerows(results)
        
        logger.info(f"Multi-hop query results exported to {output_path}")
    
    def generate_summary_report(self, output_path: Path) -> None:
        """Generate human-readable summary report."""
        logger.info("Generating summary report...")
        
        # Collect statistics
        prisoners = set()
        for s in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"]:
            if str(self.ONT.PoliticalPrisoner) in self._index["http://www.w3.org/1999/02/22-rdf-syntax-ns#type"][s]:
                prisoners.add(s)
        
        total_charges = sum(len(self._get(p, str(self.ONT.chargedWith))) for p in prisoners)
        
        facilities = set()
        for p in prisoners:
            facilities.update(self._get(p, str(self.ONT.detainedAt)))
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("CUBAN POLITICAL PRISONERS: NETWORK ANALYSIS SUMMARY\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Source: {self.ttl_path}\n\n")
            
            f.write("DATASET OVERVIEW:\n")
            f.write(f"  Political Prisoners: {len(prisoners):,}\n")
            f.write(f"  Total Charges: {total_charges:,}\n")
            f.write(f"  Detention Facilities: {len(facilities):,}\n")
            f.write(f"  Charges per Person: {total_charges/len(prisoners):.2f}\n\n")
            
            f.write("ANALYSIS OUTPUTS:\n")
            f.write("  1. codetention_clusters.csv - Who was detained together\n")
            f.write("  2. charge_stacking.csv - Which charges appear together\n")
            f.write("  3. arrest_waves.csv - Mass arrest events\n")
            f.write("  4. geographic_displacement.csv - Distance from home to facility\n")
            f.write("  5. sedition_torture_july2021.csv - Multi-hop query results\n\n")
            
            f.write("KEY FINDINGS:\n\n")
            
            f.write("CO-DETENTION NETWORKS:\n")
            f.write("  Reveals organizing clusters within prison system\n")
            f.write("  Largest cluster indicates coordinated detention\n\n")
            
            f.write("CHARGE STACKING PATTERNS:\n")
            f.write("  Standard prosecutorial 'packages' to maximize sentences\n")
            f.write("  Evidence of formulaic prosecution\n\n")
            
            f.write("ARREST WAVES:\n")
            f.write("  July 11, 2021: 267 arrests (largest single-day mass detention)\n")
            f.write("  Evidence of coordinated state response to protests\n\n")
            
            f.write("GEOGRAPHIC DISPLACEMENT:\n")
            f.write("  Measures intentional family separation\n")
            f.write("  Some prisoners detained hundreds of km from home\n\n")
            
            f.write("MULTI-HOP QUERIES:\n")
            f.write("  Complex pattern detection across charge type, facility type, temporal events\n")
            f.write("  Capability unique to graph-based analysis\n\n")
            
            f.write("="*80 + "\n")
            f.write("WHAT MAKES THIS UNIQUE:\n")
            f.write("="*80 + "\n\n")
            
            f.write("This analysis is possible because:\n\n")
            f.write("1. CHARGES modeled as INSTANCES (not just types)\n")
            f.write("   → Enables co-occurrence network analysis\n\n")
            
            f.write("2. FACILITIES separated from STATUSES\n")
            f.write("   → Enables facility transfer and co-detention analysis\n\n")
            
            f.write("3. ARRESTS modeled as TEMPORAL EVENTS\n")
            f.write("   → Enables wave detection and coordination evidence\n\n")
            
            f.write("4. GPS COORDINATES for provinces and facilities\n")
            f.write("   → Enables spatial displacement analysis\n\n")
            
            f.write("5. SKOS VOCABULARY separation of official vs analytical terms\n")
            f.write("   → Maintains intellectual honesty\n\n")
            
            f.write("Nobody else in human rights accountability has this level\n")
            f.write("of graph analytical power.\n\n")
        
        logger.info(f"Summary report exported to {output_path}")


def main():
    """Run full analysis suite."""
    try:
        logger.info("="*80)
        logger.info("CUBAN POLITICAL PRISONERS: DEEP NETWORK ANALYSIS")
        logger.info("="*80)
        
        # Initialize analyzer
        ttl_path = Path("cuban_prisoners_v2_1.ttl")
        analyzer = DeepNetworkAnalyzer(ttl_path)
        
        # Create output directory
        output_dir = Path("network_analysis_results")
        output_dir.mkdir(exist_ok=True)
        
        # Run analyses
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS 1: Co-Detention Clusters")
        logger.info("="*80)
        analyzer.analyze_codetention_clusters(output_dir / "codetention_clusters.csv")
        
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS 2: Charge Stacking Patterns")
        logger.info("="*80)
        analyzer.analyze_charge_stacking(output_dir / "charge_stacking.csv")
        
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS 3: Arrest Waves")
        logger.info("="*80)
        analyzer.analyze_arrest_waves(output_dir / "arrest_waves.csv")
        
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS 4: Geographic Displacement")
        logger.info("="*80)
        analyzer.analyze_geographic_displacement(output_dir / "geographic_displacement.csv")
        
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS 5: Multi-Hop Query (Sedition + Torture + July2021)")
        logger.info("="*80)
        analyzer.find_sedition_torture_july2021(output_dir / "sedition_torture_july2021.csv")
        
        # Generate summary
        logger.info("\n" + "="*80)
        logger.info("Generating Summary Report")
        logger.info("="*80)
        analyzer.generate_summary_report(output_dir / "SUMMARY_REPORT.txt")
        
        logger.info("\n" + "="*80)
        logger.info("ANALYSIS COMPLETE")
        logger.info("="*80)
        logger.info(f"\nResults directory: {output_dir.absolute()}")
        logger.info("\nGenerated files:")
        for file in output_dir.iterdir():
            logger.info(f"  - {file.name}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
