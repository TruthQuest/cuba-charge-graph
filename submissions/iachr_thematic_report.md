# Thematic Submission to the Inter-American Commission on Human Rights

## Bifurcated Prosecutorial Charging as a Systemic Practice of Arbitrary Detention in Cuba

**Prepared by:** E. Brattin, Trace Origin LLC
**Date:** August 2026
**Submitted to:** Executive Secretariat, Inter-American Commission on Human Rights, Organization of American States
**Purpose:** Consideration under the Commission's monitoring mandate for Cuba pursuant to the American Declaration of the Rights and Duties of Man

---

## Introductory note

Cuba is not a State Party to the American Convention on Human Rights and has not been a functionally participating member of the Organization of American States since 1962, although the June 2009 General Assembly resolution rescinded the exclusion. Notwithstanding, the Commission has consistently maintained jurisdiction over Cuba through the American Declaration of the Rights and Duties of Man, which binds all OAS member states, and has issued annual reports on Cuba as a country requiring special attention under Chapter IV.B of its Annual Report since 2002. This submission is offered for consideration under that same mandate. It presents statistical evidence, drawn from a formal ontology of publicly documented Cuban political prisoners, of a systemic charging pattern that the Commission has not previously had before it in quantified form.

---

## Executive summary

The Cuban state maintains two entirely disjoint prosecutorial charging regimes for political cases. The first is a boilerplate combination of low-severity offenses (Public Disorder, Contempt, Assault, Resistance) applied to persons detained in connection with public gatherings or expressive conduct. The second consists of high-severity standalone charges (Sedition, Sabotage, Enemy Propaganda) applied to individuals the state has selected to characterize as threats to the constitutional order. The two regimes do not overlap. Statistical analysis of 2,264 charges filed against 1,258 documented political prisoners, using a permutation test with 5,000 iterations, produces empirical p-values below 0.001 for both the positive co-occurrence within each regime and the near-absence of co-occurrence between them.

The separation is not disclosed in any Cuban statute. No official has acknowledged it. It is visible only in the pattern of charging decisions. Once named, however, it constitutes evidence of a practice inconsistent with Articles XVIII (right to a fair trial), XXV (protection from arbitrary arrest), and XXVI (right to due process of law) of the American Declaration.

This report asks the Commission to include reference to this pattern in its 2026 annual report on Cuba and to consider requesting a formal thematic hearing.

---

## 1. About this submission

### 1.1 Who I am

I am the founder of Trace Origin LLC, a structural-intelligence practice based in the United States. I have no institutional affiliation with any Cuban opposition group, any foreign government, or any of the human rights organizations whose prior work is cited in this submission. My professional background is in ontology engineering and applied semantic technology.

### 1.2 What I did

The analysis presented here rests on the publicly available political-prisoner registry maintained by Prisoners Defenders (Madrid), which has been the most comprehensive and continuously updated source of Cuban political-prisoner documentation since 2018. I encoded the full 1,258-person registry into a formal RDF ontology, aligned to the Basic Formal Ontology (BFO), with a SKOS vocabulary corresponding to the Cuban Penal Code (both the 1987 code and the 2022 code that superseded it in December 2022). Charges, arrests, sentences, and detention facilities are modelled as first-class entities. Every record carries provenance to the source URL.

I then ran a permutation test on the charge-pair co-occurrence structure of the corpus. The full pipeline is versioned, reproducible, and published at https://github.com/TruthQuest/cuba-charge-graph. Every quantitative claim in this submission can be verified by running the pipeline against the same source data.

### 1.3 Source acknowledgment

Prisoners Defenders is the primary source of the data underlying this analysis. Contact was made with the organization prior to submission, and this document should be read as an analytical layer on top of their documentation, not as a replacement for it or a competitor to their own reporting. The Commission is encouraged to treat Prisoners Defenders as the authoritative source on any individual case referenced herein.

---

## 2. Cuban prosecutorial structure

The bifurcated charging pattern this submission documents did not arise spontaneously. It is a consequence of specific structural features of the Cuban criminal justice system, which the Commission has documented in its prior reporting but which bear brief restatement here for the sake of a clear evidentiary chain.

Article 5 of the 2019 Cuban Constitution establishes the Communist Party as the "superior driving force" of the state. Judges of the People's Supreme Court and provincial courts are elected by the National Assembly (Articles 148, 149), in which no non-Communist political party can lawfully organize. The Fiscalía General de la República is constitutionally accountable to the National Assembly (Article 156). No independent bar association exists. No judicial mechanism exists for reviewing prosecutorial charging decisions.

The 2022 Penal Code (Law No. 151), which entered into force on 1 December 2022, retained and expanded the political-offense provisions of the 1987 code. The relevant articles for this submission are:

- **Article 120 (Sedition)**: penalty of 7 to 15 years, or death in aggravated cases
- **Article 143 (Propaganda against the Constitutional Order)**: 4 to 10 years
- **Article 144 (Enemy Propaganda)**: 1 to 8 years
- **Article 185 (Contempt / Desacato)**: 6 months to 1 year, with aggravations to 3 years
- **Article 272 (Public Disorder / Desórdenes Públicos)**: 3 months to 1 year
- **Article 274 (Resistance)**: 3 months to 1 year
- **Article 276 (Assault / Atentado)**: penalty variable by severity

These articles are drafted with sufficient breadth that a single expressive act (a slogan chanted, a Facebook post, a livestream, an act of public assembly) can independently satisfy the elements of multiple offenses. The Commission has previously noted the incompatibility of vague criminal statutes with the American Declaration in the context of Cuba (2020 Annual Report, Chapter IV.B, paragraphs 43-49).

The Cuban criminal procedure code does not require prosecutors to justify their choice of charges either at charging or at trial. Defense counsel does not receive the evidentiary basis for the state's charging decision. Trials in political cases are frequently held in restricted-access settings, with international observers routinely denied entry.

---

## 3. The bifurcated charging pattern

### 3.1 What the data shows

Of the 2,264 individual charges filed against the 1,258 individuals in the dataset, charge pairs cluster into two disjoint groups. The clustering is not consistent with charging decisions arising from the acts alleged. Under a null model that preserves per-defendant charge count and per-charge marginal frequency, the observed co-occurrences produce the following results:

**Positive clustering (Regime A, the street-protest bundle):**

| Charge pair | Observed | Expected under null | Lift | Empirical p |
|---|---|---|---|---|
| Contempt + Public Disorder | 288 | 94 | 3.0x | < 0.001 |
| Assault + Public Disorder | 253 | 88 | 2.9x | < 0.001 |
| Assault + Contempt | 175 | 63 | 2.8x | < 0.001 |
| Public Disorder + Sabotage | 71 | 31 | 2.3x | < 0.001 |
| Public Disorder + Resistance | 30 | 11 | 2.8x | < 0.001 |
| Contempt + Resistance | 26 | 8 | 3.4x | < 0.001 |

**Negative clustering (Regime B, the standalone regime charge):**

| Charge pair | Observed | Expected under null | Ratio | Empirical p |
|---|---|---|---|---|
| Sedition + Public Disorder | 10 | 57 | 0.18 | 1.000 |
| Sedition + Assault | 9 | 38 | 0.24 | 1.000 |
| Contempt + Sabotage | 14 | 22 | 0.64 | 0.985 |

The state charges Sedition in 218 cases. In 199 of those cases, no charge from the street-protest bundle appears on the same charge sheet. Given the elements of Sedition under Article 120, which requires overt acts against the constitutional order, and given that such acts almost by definition occur in the context of public gatherings that would satisfy the elements of Public Disorder or Assault, the near-total absence of co-occurrence is inconsistent with a charging practice tied to individual assessment of the acts.

### 3.2 What the pattern indicates

The state has, in effect, pre-sorted its political defendants into two categories before trial. Defendants sorted into Regime A face a boilerplate bundle whose primary function is sentence multiplication through charge stacking rather than proportional response to alleged conduct. Defendants sorted into Regime B face a single grave charge whose primary function is characterization: to establish, on the public record, that the defendant is not a disorderly citizen but an enemy of the constitutional order. The two categories carry materially different sentence exposures, materially different prospects for conditional release, and materially different implications for the individual's post-release status.

Nothing in Cuban law authorizes this pre-sorting. Nothing in the record justifies it in any specific case. It is not disclosed to defense counsel. It is not reasoned in judgments. It exists solely as a pattern of decisions, revealed here because the corpus is now large enough for the pattern to be detectable by statistical means.

### 3.3 Stability across the five-year window

The pattern holds when the corpus is subset by year (2021, 2022, 2023, 2024, 2025), by province (all fifteen provinces plus the Isla de la Juventud), and by pre- and post-2022 Penal Code. This is not an artifact of the 11 July 2021 mass-arrest cohort, though that cohort accounts for the largest single tranche of Regime A cases. The pre-11J subset (arrests before 11 July 2021) and the post-11J subset each independently produce the same two-regime clustering with p < 0.001.



Independent validation via Louvain community detection (Blondel et al. 2008) confirms the two-regime partition. An unsupervised algorithm, given only the charge co-occurrence graph and no domain knowledge, independently recovered the same structure with 100% stability across 100 random seeds and 97-98% prisoner-level classification agreement.

---

## 4. Individual cases

The pattern is best illustrated by reference to specific individuals whose cases are already the subject of prior Commission attention or documented public reporting. The individuals named below are drawn from Prisoners Defenders' registry and are already publicly identified. Their inclusion here is illustrative and additive to, not in substitution for, individualized case reporting.

### 4.1 Maykel Castillo Pérez ("Maykel Osorbo") — Regime A

Detained May 2021. Co-writer of "Patria y Vida," recipient of two Latin Grammy Awards in 2021. Held in pretrial detention for approximately one year. Convicted June 2022 on charges including Contempt, Assault, Public Disorder, and Defamation of Institutions. Sentenced to nine years' imprisonment. His charge combination is the archetypal Regime A bundle. He remains detained at the date of this submission. Human Rights Watch has documented the evidentiary conduct of his trial in *Prison or Exile: Cuba's Systematic Repression of July 2021 Demonstrators* (2022).

### 4.2 José Daniel Ferrer — Regime B pattern

Founder of the Unión Patriótica de Cuba (UNPACU). Detained multiple times over the past two decades under various political-offense charges including Public Disorder and Contempt in earlier cycles, and, in more recent detentions, framed under provisions consistent with the Regime B pattern. The Commission has issued precautionary measures on his behalf (see Resolution 39/2020). His case illustrates the way in which the state has migrated certain individuals from Regime A to Regime B over the course of repeated detentions, consistent with the pattern described in Section 3.2.

### 4.3 Luis Manuel Otero Alcántara — Regime A

Founder of the San Isidro Movement. Detained in July 2021 in connection with the 11 July protests. Convicted 2022 on charges including Contempt, Public Disorder, and outrage against national symbols. Sentenced to five years. His case is the subject of Commission Resolution 21/2020 (precautionary measures).

Additional named cases from the dataset, classified by regime, are provided in Annex B.

---

## 5. Legal framework and applicable standards

### 5.1 Under the American Declaration

**Article XVIII (Right to a Fair Trial):** guarantees resort to the courts and a hearing before an impartial tribunal. The absence of prosecutorial and judicial independence, taken together with a charging practice that assigns defendants to prosecutorial regimes prior to any individualized assessment of the acts alleged, is inconsistent with this guarantee.

**Article XXV (Protection from Arbitrary Arrest):** provides that no person shall be deprived of liberty except in cases and according to procedures established by pre-existing law. A charging practice not disclosed in law, and one that materially affects the sentence exposure of the accused, falls outside the "procedures established by pre-existing law" contemplated by this article.

**Article XXVI (Right to Due Process of Law):** provides that every person accused of an offense has the right to be presumed innocent until proven guilty. A charging practice that pre-sorts defendants into differently-consequenced prosecutorial regimes on grounds not disclosed in the record is inconsistent with the presumption of innocence at the earliest procedural stage.

### 5.2 Prior Commission jurisprudence

The Commission has previously found that overbroad political-offense statutes, when applied selectively in contexts of judicial dependence, give rise to violations of the American Declaration. Its 2020 Annual Report (Chapter IV.B, Cuba) documents in qualitative form what this submission now presents in quantified form. The Commission's precautionary measure decisions concerning Otero Alcántara (21/2020), Ferrer (39/2020), and others, taken together, describe individual instances of what this submission argues is a systemic practice.

### 5.3 Prior Inter-American Court practice on comparable patterns

The Court's judgments in *López Lone v. Honduras* (2015), *Norín Catrimán v. Chile* (2014), and *Kimel v. Argentina* (2008) each addressed, in different contexts, the incompatibility with the American Convention of criminal statutes drafted with sufficient breadth to permit selective political application. While Cuba is not party to the Convention, the reasoning of these judgments is instructive as to how the Inter-American system as a whole has approached the underlying legal question.

---

## 6. Requests to the Commission

I respectfully request that the Commission:

1. Include reference to the bifurcated charging pattern documented herein in Chapter IV.B of its 2026 Annual Report on Cuba, treating the pattern as evidence of systemic non-compliance with Articles XVIII, XXV, and XXVI of the American Declaration.

2. Consider granting a thematic hearing at its next regular session, or convening a working meeting, at which the pattern can be presented in fuller technical detail by the submitting party and by Prisoners Defenders. I would defer to Prisoners Defenders as the primary voice in any such hearing.

3. Reference this analysis in any future decision on precautionary measures concerning Cuban political detainees, insofar as the systemic pattern provides context for individual charging decisions.

4. Consider incorporating the underlying ontology and dataset into the Commission's own monitoring apparatus for Cuba, or, at minimum, taking judicial notice of its existence as a reproducible artifact that can be independently verified.

---

## 7. Coordination with other proceedings

A parallel submission has been prepared for the United Nations Working Group on Arbitrary Detention presenting the same evidence in the framework of Category II and Category III of that Working Group's jurisprudence. A stakeholder submission for Cuba's next Universal Periodic Review cycle is in preparation. The submitting party will inform the Commission of the disposition of these parallel proceedings and will make the Commission's Executive Secretariat aware of any responsive action by the Government of Cuba.

---

## Annexes

**Annex A:** Full statistical table for all charge pairs with n ≥ 10 observed co-occurrences, including expected values under the null distribution, empirical p-values, and effect sizes.

**Annex B:** List of dataset individuals classified by regime (A, B, mixed, insufficient data). Source URLs to the Prisoners Defenders record are provided for each. High-risk individuals are excluded from the public annex and are available on request under a confidentiality undertaking.

**Annex C:** Full 11 July 2021 arrest cohort: 267 individuals with arrest date, province, charges filed, sentence where sentenced, and current detention status.

**Annex D:** Ontology specification and reproducibility statement. T-Box, SHACL validation shapes, SKOS charge-type vocabulary, DPV/ODRL policy overlay, five-step Python pipeline, permutation-test source code.

**Annex E:** Documentation of prior Commission decisions concerning individual cases referenced in Section 4.

---

*The submitting party is available to respond to any request from the Executive Secretariat for clarification, additional analysis, or presentation at a working meeting or thematic hearing. Contact information above.*
