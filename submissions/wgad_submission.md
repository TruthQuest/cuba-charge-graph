# Submission to the UN Working Group on Arbitrary Detention

## Concerning a systemic pattern of arbitrary detention arising from bifurcated prosecutorial charging practices in the Republic of Cuba

**Submitted by:** E. Brattin, Trace Origin LLC
**Contact:** ebrattin@traceoriginresearch.com
**Date of submission:** August 2026
**Submission type:** Deliberation / thematic information under the Working Group's methods of work (paragraph 22 of the Revised Methods of Work, A/HRC/36/38)

---

## Executive summary

This submission presents quantitative evidence, drawn from a formal ontology encoding the case files of 1,258 documented Cuban political prisoners, that the Republic of Cuba maintains two entirely disjoint prosecutorial charging regimes for political cases. One regime consists of a boilerplate combination of low-severity charges (Public Disorder, Contempt, Assault, Resistance) applied to persons arrested at demonstrations. The second regime consists of high-severity standalone charges (principally Sedition) applied to selected individuals the State characterizes as threats to the constitutional order. Statistical analysis using a permutation test (n=5,000 iterations, p<0.001) demonstrates that the separation between the two regimes is not consistent with charging decisions arising from the acts alleged. The pattern is stable across the five-year observation window (2021 to 2026) and applies uniformly across all fifteen Cuban provinces.

The submitting party requests that the Working Group consider whether this bifurcated charging pattern, taken together with the structural absence of prosecutorial and judicial independence in Cuba, satisfies Category III (violations of fair trial norms so grave as to give the deprivation of liberty an arbitrary character) and Category II (detention resulting from exercise of rights guaranteed by the UDHR, including Articles 19, 20, and 21) of the Working Group's classification of arbitrary detention.

---

## I. Standing and methodology

### 1.1 Submitting party

E. Brattin is the founder of Trace Origin LLC, a structural-intelligence practice applying formal ontology, spectral graph theory, and provenance-tracked reasoning to public records in human rights and financial-crime investigations. This submission draws on a publicly documented dataset maintained by Prisoners Defenders (Madrid, Spain), with which the submitting party has no institutional affiliation.

### 1.2 Source data

The primary data source is the public political-prisoner registry maintained by Prisoners Defenders at `lista.prisonersdefenders.org`, comprising 1,258 individual case records as of May 2026. Each record includes the individual's name, arrest date, charge or charges filed, sentence, detention facility, and home province, where those data points are publicly available. Records lacking a parseable arrest date (approximately 155 individuals) are included in the person-level count but excluded from arrest-date-dependent analyses.

### 1.3 Analytical method

The dataset was encoded into a formal Resource Description Framework (RDF) ontology aligned to the Basic Formal Ontology (BFO) upper-level standard. Charges were modelled as instances of the class `:Charge`, linked by the property `:hasChargeType` to instances of the class `:ChargeType`, which is populated by a Simple Knowledge Organization System (SKOS) concept scheme corresponding to the Cuban Penal Code (both the 1987 and 2022 codes are represented). Every record carries provenance to its source URL via the `prov:wasDerivedFrom` property. The full ontology, including SHACL validation shapes and the reproducible pipeline, is available at https://github.com/TruthQuest/cuba-charge-graph.

Charge-bundling analysis was conducted by generating a null distribution through 5,000 iterations of random charge assignment. Each iteration preserved (a) the total number of charges per defendant and (b) the marginal frequency of each charge type across the corpus. Observed pair co-occurrence counts were compared against this null distribution to compute empirical p-values.

### 1.4 Ethical framework

Every named individual referenced in this submission is already publicly named by Prisoners Defenders with the consent framework of the affected persons or their families. The submitting party has attached a per-person risk classification to the underlying dataset, and no individual designated as high-risk is named in this submission beyond those already discussed in international press and prior human rights reporting.

---

## II. Structural context

### 2.1 Absence of prosecutorial and judicial independence

The Republic of Cuba is a one-party State. Article 5 of the Constitution designates the Communist Party of Cuba as the "superior driving force of the society and the State." Judges of the People's Supreme Court and the People's Provincial Courts are elected and subject to removal by the National Assembly of People's Power (Constitution, Articles 148 and 149), a body in which no political party other than the Communist Party is permitted to organize or nominate candidates. The Fiscalía General de la República (Prosecutor's Office) reports to the National Assembly under Article 156. There exists no independent bar association. There exists no independent judicial review of prosecutorial charging decisions.

The Working Group has previously recognized that the structural absence of prosecutorial and judicial independence in a State party is a relevant factor in assessing whether deprivation of liberty rises to the level of arbitrariness under Category III (see, inter alia, Opinion No. 63/2021 (Maykel Castillo Pérez) and Opinion No. 13/2024 (seventeen 11J protesters) concerning Cuba).

### 2.2 Overbroad political-offense statutes

The 2022 Cuban Penal Code (Law No. 151), which entered into force in December 2022, contains a number of provisions relevant to this submission. Article 120 criminalizes Sedition and provides for penalties of seven to fifteen years, or death in aggravated cases. Article 185 criminalizes Contempt (Desacato) of public officials, extending to speech acts including online expression. Article 272 criminalizes Public Disorder (Desórdenes Públicos), defined by reference to any gathering that "disturbs public order," a term the code does not further define. Articles 143 and 144 criminalize Propaganda against the Constitutional Order and Enemy Propaganda respectively.

These provisions, taken individually, are drafted with sufficient breadth that a single act of political expression (a Facebook post, a slogan chanted at a march, a livestream, an act of public assembly) can independently support one or several charges. The Working Group has previously found that such breadth, in combination with selective application, gives rise to arbitrary detention (see Opinion No. 63/2021 concerning Cuba, which uses "recurrent pattern" language).

### 2.3 The 11 July 2021 arrests as an observable natural experiment

On 11 July 2021, spontaneous protests occurred in more than fifty Cuban cities. The dataset records 267 arrests attributed to that single day, 117 on 12 July, and 38 on 13 July, aggregating to more than 500 arrests within one week. These arrests, and the charging decisions that followed, provide the largest single tranche of comparable cases in the dataset and are the empirical foundation for the pattern described below.

---

## III. The bifurcated charging pattern

### 3.1 Description of the pattern

Analysis of the 2,264 individual charges filed against the 1,258 individuals in the dataset reveals two entirely disjoint co-occurrence clusters:

**Regime A: The street-protest bundle.**
Charges of Public Disorder, Contempt, Assault, and Resistance appear together with high frequency. The pair Contempt + Public Disorder occurs in 288 individual cases, against a chance expectation under the null distribution of 94 (permutation-test p<0.001). Similar statistical significance is observed for Assault + Public Disorder (253 observed, 88 expected), Assault + Contempt (175 observed, 63 expected), and Public Disorder + Resistance (30 observed, 11 expected). In each pairing, the observed co-occurrence exceeds the 99.9th percentile of the null distribution.

**Regime B: The standalone regime charge.**
Charges of Sedition, and to a lesser extent Sabotage and Enemy Propaganda, occur systematically without the bundle described above. The pair Sedition + Public Disorder occurs in only 10 cases, against a chance expectation of 57. Sedition + Assault occurs in 9 cases, against a chance expectation of 38. In both instances, the observed co-occurrence falls below the 5th percentile of the null distribution.

The Sedition charge, which carries a mandatory penalty range of seven to fifteen years' imprisonment, is levied in 218 cases within the dataset. In 199 of those cases, no charge from the street-protest bundle is co-filed. This is inconsistent with a charging practice tied to the acts alleged, since Sedition under Article 120 of the Penal Code requires overt acts against the constitutional order, and such acts routinely occur in the context of public gatherings that would satisfy the elements of Public Disorder or Assault.

### 3.2 What the pattern indicates

Under a rule-of-law charging practice, the State's decision to file Sedition against a defendant would be independent of, and additive to, its decision to file Public Disorder or Assault: the presence of one does not exclude the elements of the other. Under the observed pattern, the two are mutually exclusive to a degree that is statistically incompatible with independent charging decisions. The conclusion the data supports is that the State selects the charging regime prior to, and independent of, the specific acts alleged, and applies one or the other according to how it has categorized the defendant.

### 3.3 Case illustration: Maykel Castillo Pérez

Maykel Castillo Pérez, known as Maykel Osorbo, is one of the 1,258 individuals in the dataset. He co-wrote the song "Patria y Vida," which won two Latin Grammy Awards in 2021. He was detained in May 2021, held in pretrial detention for approximately one year, and convicted in June 2022. The charges filed against him fall within Regime A (the street-protest bundle). He was sentenced to nine years' imprisonment. He remains detained as of the date of this submission.

The circumstances of his prosecution, including the evidentiary standards applied at his trial, have been documented by Human Rights Watch (*Prison or Exile: Cuba's Systematic Repression of July 2021 Demonstrators*, 2022) and by Amnesty International. His case is representative of the Regime A pattern in the dataset and is included here to illustrate that pattern with reference to an individual whose case has been the subject of prior international reporting.



### 3.4 Independent validation by unsupervised community detection

As an independent validation of the two-regime hypothesis, Louvain community detection (Blondel et al. 2008) was applied to the charge co-occurrence graph at the default resolution parameter (1.0). The algorithm was given no prior knowledge of the analyst-defined regime partition. It independently assigned Sedición to a separate community from the four Regime A charges (Desacato, Desórdenes Públicos, Atentado, Resistencia), which were placed together in a single community. This separation was perfectly stable across 100 runs with different random initializations (100/100). Per-prisoner classification agreement between the analyst-defined regimes and the algorithmically discovered partition was 97.2% for Regime A and 98.0% for Regime B (09_community_detection.py; results archived in 09_community_detection_results.json). The two-regime structure is not an artifact of the analyst's framing; it is a property of the data that an unsupervised algorithm recovers independently.

---

## IV. Legal analysis

### 4.1 Category III: violations of the right to a fair trial

Category III of the Working Group's classification concerns deprivations of liberty arising from "total or partial non-observance of the international norms relating to the right to a fair trial" that are of such gravity as to give the deprivation an arbitrary character (Fact Sheet No. 26, revised).

The bifurcated charging pattern documented in Section III, taken in the structural context described in Section II, engages Article 10 of the Universal Declaration of Human Rights (UDHR) and customary international law as articulated in WGAD Deliberation No. 9. Article 10 guarantees a fair and public hearing by a competent, independent, and impartial tribunal established by law. Where prosecutorial decisions are made without reference to the acts alleged, and where the tribunal charged with adjudicating those decisions is not structurally independent of the party that made them, the fair-trial guarantee is not merely procedurally deficient but substantively absent.

Article 11(1) of the UDHR further guarantees the presumption of innocence. A charging practice that assigns defendants to a prosecutorial regime prior to and independent of individualized assessment of the acts alleged is inconsistent with the presumption that innocence is the default status of the accused.

### 4.2 Category V: discrimination on political grounds

Category II concerns deprivations of liberty "on grounds of discrimination" including political opinion. The pattern documented here shows that Cuba does not deprive individuals of liberty for a uniform class of political conduct. It sorts them, prior to trial, into one of two regimes with materially different sentence exposures. The sorting is not disclosed in any statute. It is not subject to prior judicial review. It is not reasoned in the judgments of the People's Courts, which do not typically address why one charging regime rather than another was selected in a given case.

Article 7 of the UDHR guarantees equality before the law and equal protection of the law without discrimination on grounds including political opinion. The observed pattern of assigning defendants to differently-consequenced prosecutorial regimes according to characteristics not disclosed on the record engages this guarantee directly.

### 4.3 Referable prior Opinions of the Working Group

The Working Group has previously issued Opinions concerning individual Cuban detainees, including Opinion No. 41/2021 (Denis Solís and Robles Elizástigui), Opinion No. 63/2021 (Maykel Castillo Pérez, establishing "recurrent pattern" language), Opinion No. 52/2022 (11J protesters including Otero Alcántara), Opinion No. 51/2023 (Otero Alcántara and Lavastida), and Opinion No. 13/2024 (seventeen named 11J protesters). In each Opinion, the Working Group found the deprivation of liberty arbitrary and requested the Government of Cuba to release the individual concerned and to accord them an enforceable right to compensation. The Government has not complied with any of these Opinions. The pattern documented in this submission provides a systemic-level frame within which those individual Opinions can be understood not as anomalies but as instances of a designed prosecutorial architecture.

---

## V. Requests

The submitting party respectfully requests that the Working Group:

1. Take note of the evidence presented herein and consider issuing a Deliberation, under paragraph 33 of its Methods of Work, on the practice of bifurcated prosecutorial charging in political cases where the tribunal is not structurally independent of the prosecuting authority.

2. Consider, in the adjudication of future individual communications concerning Cuban political detainees, the systemic evidence presented in this submission as relevant background context under Category II and Category III.

3. Include reference to the pattern documented herein in the Working Group's next annual report to the Human Rights Council, insofar as that report addresses country-specific patterns of arbitrary detention.

4. Transmit this submission to the Special Rapporteur on the promotion and protection of the right to freedom of opinion and expression, the Special Rapporteur on the situation of human rights defenders, and the Special Rapporteur on the independence of judges and lawyers, for their consideration under their respective mandates.

---

## VI. Annexes

**Annex A:** Statistical tables showing observed co-occurrence, null-distribution mean, 95th percentile, and empirical p-value for all charge pairs with n≥10 observed co-occurrences.

**Annex B:** List of individuals in the dataset by regime (Regime A, Regime B, mixed, insufficient data), with source URLs to the Prisoners Defenders record for each.

**Annex C:** Formal ontology specification: T-Box, SHACL shapes, SKOS charge-type vocabulary, and DPV/ODRL policy overlay. Available at https://github.com/TruthQuest/cuba-charge-graph.

**Annex D:** Full 11 July 2021 arrest cohort: 267 individuals, arrest date, home province, charges filed, sentence where sentenced, current detention status.

**Annex E:** Reproducibility statement: five-step Python pipeline, versioned; every claim in Sections III and IV traceable to a specific SPARQL query included in the repository.

---

*This submission draws exclusively on publicly available data and is provided to the Working Group for its consideration under the Revised Methods of Work. The submitting party consents to the transmission of this submission and its annexes to the Government of Cuba, subject to the redaction of any information concerning individuals classified as high-risk in the underlying dataset. The submitting party is available to respond to requests for clarification or additional analysis at the contact address above.*
