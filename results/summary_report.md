# Cuban Political Prisoners: Analysis Summary
Generated: 2026-08-23T15:55:19.981294Z

## Dataset
- Persons: 1258
- Facilities: 158
- Arrests: 1139

## Outputs
- facility_colocation.csv (state facility clustering, NOT prisoner organizing)
- charge_stacking.csv (with permutation-test p-values)
- arrest_waves.csv
- geographic_displacement.csv

## Interpretation guardrails
1. Facility co-location measures state clustering behavior. Do not infer
   pre-arrest political networks or in-prison organizing from this.
2. Charge stacking p-values below 0.001 indicate non-random co-occurrence.
   Interpret higher p-values as consistent with chance under marginal-preserving null.
3. Wave detection is duplicated: derived here from A-Box AND independently
   asserted via SPARQL CONSTRUCT in step 04. Cross-check the two.