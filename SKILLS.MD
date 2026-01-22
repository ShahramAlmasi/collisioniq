# Skills and Domain Knowledge

This repository contains a QGIS plugin for analysing selected collision records
and producing charts and graphical summaries. Modifying this codebase safely
requires the following skills and awareness.

## Core Technical Skills
- Working knowledge of PyQGIS, including vector layers, feature selections,
  attribute access, and the QGIS plugin lifecycle.
- Familiarity with Qt / PyQt signal–slot patterns used in QGIS plugins.
- Ability to reason about GIS state (active layers, selections, project context)
  rather than assuming stateless function calls.

## Data and Analysis Awareness
- Understanding that the `clns` layer represents collision records and that
  selections are intentional analytical filters, not arbitrary subsets.
- Awareness that aggregation logic (counts, rates, distributions) reflects
  analytical choices and should not be altered without understanding impacts.
- Caution when modifying chart logic, as visual outputs may inform safety
  decisions or reporting.

## Domain Sensitivity
- Collision data is domain-specific; field meanings and coding schemes may follow
  traffic safety conventions rather than generic data science assumptions.
- Avoid renaming fields, layers, or categories unless the full analytical and
  downstream impact is understood.

## Change Discipline
- Prefer minimal, explicit changes over broad refactors.
- Do not generalize or abstract domain logic without clear justification.
- Treat visual clarity and interpretability as functional requirements, not
  cosmetic concerns.
