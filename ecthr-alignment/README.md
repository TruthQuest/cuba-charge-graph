# ecthr-alignment

A SKOS alignment graph mapping the eight canonical Cuban Penal Code
`ChargeType` URIs from the parent `cuba-charge-graph` ontology to the
corresponding articles of the European Convention on Human Rights.

Standalone ontological artifact. No code required to use it. Editable
directly by human-rights lawyers in TTL or in the CSV mirror without
touching Python.

---

## Why this exists

Cuba is not a Council of Europe member and the European Court of Human
Rights has no jurisdiction over Cuban cases. The alignment exists
because ECtHR jurisprudence is routinely cited as persuasive authority
by three bodies that *do* have jurisdiction over Cuba:

- The **UN Working Group on Arbitrary Detention** (WGAD), when
  interpreting the arbitrary-detention prohibition in customary
  international law and UDHR Articles 9-11
- The **UN Human Rights Committee**, when interpreting ICCPR articles
  analogous to Convention provisions
- The **Inter-American Commission on Human Rights** (IACHR), when
  interpreting the American Convention

Given a Cuban prisoner's charge bundle, the alignment identifies the
most doctrinally relevant Strasbourg authorities for citation in
submissions to those bodies. The dominant target for Cuban political
persecution is Article 18 of the Convention (restriction on rights
applied for an ulterior purpose): Kavala v Türkiye, Merabishvili v
Georgia, Navalnyy v Russia, Mammadov v Azerbaijan, and the associated
line. The alignment surfaces these authorities for the majority of
Cuban ChargeTypes.

---

## Files

```
ecthr-alignment/
├── README.md                       # this file
├── echr_concepts.ttl               # SKOS ConceptScheme for ECHR articles
├── cuban_echr_alignment.ttl        # 29 alignment mappings (source of truth)
└── cuban_charges_to_echr.csv       # lawyer-editable mirror of the TTL
```

### `echr_concepts.ttl`

SKOS `ConceptScheme` for the substantive articles of the European
Convention and its Protocols relevant to Cuba-analogy retrieval. Twelve
concepts: Articles 3, 5, 6, 8, 10, 11, 13, 14, 18, plus Protocol 1
Article 1, Protocol 4 Article 2, Protocol 7 Article 4. Each concept
carries `skos:prefLabel` in English and Spanish, `skos:definition`,
`skos:notation` in the HUDOC coding form (`Art. 10`, `P1-1`), and
`skos:scopeNote` explaining the Cuba-analogy rationale where relevant.

Namespace: `http://prisoners.defenders.org/echr#`

### `cuban_echr_alignment.ttl`

Twenty-nine alignment mappings covering all eight canonical Cuban
`ChargeType` instances from the parent ontology. Two representations
in the same file:

1. **Standard SKOS mapping triples** (`skos:closeMatch`,
   `skos:relatedMatch`) for standards-compliant consumers. Any SPARQL
   endpoint or SKOS-aware tool will consume these directly.

2. **Reified `align:Alignment` instances** carrying the metadata that
   standard SKOS does not express: mapping weight on `[0.0, 1.0]`,
   doctrinal basis as free text, and cited exemplar Strasbourg
   authorities. This is the machine-actionable form for retrieval and
   analysis.

Namespace: `http://prisoners.defenders.org/alignment#`

### `cuban_charges_to_echr.csv`

Flat mirror of the TTL for lawyer review in Excel or Google Sheets.
Regenerated from the TTL; **not** the source of truth. If you edit
the CSV, the change must be transcribed back into the TTL before it
takes effect. A future revision may add a round-trip serializer.

---

## The eight Cuban ChargeTypes covered

| ChargeType | Primary ECHR target(s) | Total mappings |
|---|---|---|
| `SedicionType` | Art. 10 (closeMatch) + Art. 11, 18, 6 | 4 |
| `DesacatoType` | Art. 10 (closeMatch) + Art. 6, 18 | 3 |
| `DesordenesPublicosType` | Art. 11 (closeMatch) + Art. 10, 18 | 3 |
| `AtentadoType` | Art. 6, 5 (closeMatch) + Art. 3, 18, 11 | 5 |
| `ResistenciaType` | Art. 5 (closeMatch) + Art. 6, 3, 18, 11 | 5 |
| `PropagandaEnemigaType` | Art. 10 (closeMatch) + Art. 18 | 2 |
| `PropagandaContraOrdenType` | Art. 10 (closeMatch) + Art. 18, 11 | 3 |
| `SabotajeType` | Art. 6 (closeMatch) + Art. 5, 10, 18 | 4 |

Every ChargeType has an `Art. 18` mapping. This is deliberate. Where a
Cuban charge is applied to political actors rather than to the underlying
common-crime population the statute was ostensibly written for, the
restriction is being pursued for an ulterior purpose. That is the
Article 18 scenario as defined by Merabishvili v Georgia and applied in
Kavala v Türkiye. The weights on these mappings reflect the strength of
the ulterior-purpose case per charge type.

---

## Loading and querying

Minimal example using `rdflib`:

```python
from rdflib import Graph

g = Graph()
g.parse("echr_concepts.ttl", format="turtle")
g.parse("cuban_echr_alignment.ttl", format="turtle")

# Also load the parent Cuban ontology to resolve ChargeType URIs
g.parse("../ontology/cuban_prisoners_charge_types.ttl", format="turtle")

# All alignments for one Cuban charge, with cited authorities
q = """
PREFIX pd:    <http://prisoners.defenders.org/ontology#>
PREFIX align: <http://prisoners.defenders.org/alignment#>
PREFIX echr:  <http://prisoners.defenders.org/echr#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>

SELECT ?target_notation ?weight ?basis ?authority WHERE {
  ?a a align:Alignment ;
     align:sourceCharge pd:SedicionType ;
     align:targetConcept ?tc ;
     align:weight ?weight ;
     align:doctrinalBasis ?basis .
  ?tc skos:notation ?target_notation .
  OPTIONAL { ?a align:citedAuthority ?authority }
}
"""
for row in g.query(q):
    print(row)
```

---

## Alignment vocabulary

A small OWL vocabulary is declared inline in `cuban_echr_alignment.ttl`
to reify the mappings with weight, doctrinal basis, and cited
authorities:

| Term | Type | Purpose |
|---|---|---|
| `align:Alignment` | `owl:Class` | A reified mapping instance |
| `align:sourceCharge` | `owl:ObjectProperty` | The Cuban `pd:ChargeType` |
| `align:targetConcept` | `owl:ObjectProperty` | The ECHR `skos:Concept` |
| `align:mappingRelation` | `owl:ObjectProperty` | The SKOS predicate that would be asserted |
| `align:weight` | `owl:DatatypeProperty` | Mapping strength `[0.0, 1.0]` |
| `align:doctrinalBasis` | `owl:DatatypeProperty` | Short justification text |
| `align:citedAuthority` | `owl:DatatypeProperty` | Exemplar Strasbourg case, free text |

---

## Editing the alignment

The alignment is intentionally hand-editable and doctrinally annotated.
A lawyer can adjust weights, add cited authorities, or introduce new
mappings without touching code. Two paths:

**Direct TTL editing (source of truth).** Edit
`cuban_echr_alignment.ttl`. Add new `align:Alignment` instances or
modify existing ones. Then regenerate the CSV mirror so both stay in
sync.

**CSV editing (review-friendly).** Edit
`cuban_charges_to_echr.csv` in Excel. Changes must be transcribed back
into the TTL before they take effect. The CSV is regenerated from the
TTL, not the other way around.

---

## Scope and limits

- **Not comprehensive Convention coverage.** Only twelve articles plus
  three Protocol articles, scoped to those most doctrinally relevant to
  Cuban political persecution. Article 2 (right to life), Article 9
  (freedom of religion), Article 15 (derogation), and others are absent
  by design. Extend as needed.
- **Weights are heuristic.** The `[0.0, 1.0]` weight on each mapping
  represents the analyst's read of doctrinal proximity. They are not
  derived from empirical measurement. A domain expert reviewing this
  alignment should feel free to adjust them.
- **Cited authorities are exemplary, not exhaustive.** The
  `align:citedAuthority` values on each mapping list the Strasbourg
  cases that best exemplify the doctrinal proximity. Practitioners
  will know additional authorities; adding them is welcome.

---

## What is not in this directory

The retrieval prototype that consumes this alignment (HUDOC ingestion,
conclusion parsing, violation-vector construction, cosine similarity
scoring, per-prisoner ranked output) is not published. Reasons:

- The HUDOC endpoint used by the prototype is unofficial and rate-limited.
  Public distribution of the fetcher risks the endpoint being throttled
  or blocked for everyone.
- The retrieval prototype has not yet completed human-rights lawyer
  review. Publishing it as a finished tool would imply an endorsement
  that has not yet been earned.
- The alignment TTL is the standalone intellectual contribution. It is
  useful independently of any particular retrieval implementation.

If you are building your own retrieval pipeline against this alignment,
reach out.

---

## Citation

If you use this alignment in academic, journalistic, or advocacy work,
please cite the parent repository and this directory:

> Brattin, E. (2026). *cuba-charge-graph / ecthr-alignment: A SKOS
> alignment from Cuban Penal Code charges to European Convention on
> Human Rights articles.* Trace Origin LLC.
> https://github.com/TruthQuest/cuba-charge-graph/tree/main/ecthr-alignment

---

## License

Same as parent repository. See root `LICENSE` and the top-level
`README.md`. All rights reserved (© 2026 Trace Origin LLC).
Non-commercial academic citation and journalistic quotation permitted
under standard fair use. Commercial use requires prior written permission.
