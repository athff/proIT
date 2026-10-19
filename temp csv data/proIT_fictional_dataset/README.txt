proIT Fictional Demo Dataset
=============================

All records are fictional and intended only for local testing. Email addresses use the reserved .example domain.

Record counts:
- locations.csv: 3
- departments.csv: 6
- vendors.csv: 10
- categories.csv: 8
- manufacturers.csv: 6
- asset_models.csv: 15
- employees.csv: 50
- assets.csv: 100

Recommended import order:
1. locations.csv
2. departments.csv
3. vendors.csv
4. categories.csv
5. manufacturers.csv
6. asset_models.csv
7. employees.csv
8. assets.csv

Important:
- Import each file using its matching proIT CSV import type/template.
- Relationship columns use matching names for most related records. The assets assigned_employee field uses employee IDs (EMP-0001, etc.).
- Asset status values currently use: Available, Assigned, In Repair, Retired. Verify the exact status choices accepted by your proIT Asset model/import validator before importing assets. If your app uses different choices, adjust the status values in assets.csv to match.
- Import dependencies first. If a file reports a validation error, do not repeatedly re-import it; share the error so the data can be corrected.
