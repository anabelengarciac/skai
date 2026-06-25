---
name: spirits-creative-image-enrichment
description: Enrich a trusted performance dataset with creative image URLs from Skai using AdId as the mapping key. Use when Codex needs to prepare AI-ready creative analytics datasets, especially for spirits advertising analysis, without using Skai as the main source of performance metrics. If no country is specified, assume USA.
---

# Spirits Creative Image Enrichment

## Overview

Use this skill to take a base dataset prepared outside Skai and enrich it with `ImageUrl`. The source of truth for impressions, clicks, conversions, CTR, and other performance metrics should remain the external dataset, for example BigQuery. Skai is used only to build the `AdId -> ImageUrl` mapping and add it to each row.

The correct flow is:

1. start from an external dataset with business columns and metrics already defined
2. query Skai to obtain `AdId`, `ImageUrl`, and minimal metadata
3. keep only creatives with image assets and exclude video when needed
4. exclude `EXCLUDED_BRAND` by default unless the user asks to include it
5. join by `AdId`
6. export an enriched final dataset ready for AI-assisted creative analysis

If the same image appears in many rows, that is not an error: it means the creative is reused across multiple ads or contexts. This skill does not aggregate or deduplicate by image in the final enriched output; it preserves one row per input row.

## Workflow

1. Confirm the base dataset, date range, and country. If no country is specified, assume `USA`.
2. Read [configuration.md](references/configuration.md) if credentials are missing or if the `AdId` column is unclear.
3. Run [skai_image_ctr_report.py](scripts/skai_image_ctr_report.py) with the base dataset and requested date range.
4. Deliver:
   - `enriched_ad_records`
   - `skai_image_mapping`
   - `summary.json`
5. Explain the result as an enriched dataset:
   - metrics from the external source
   - `ImageUrl` desde Skai
6. If the user later wants an image-level aggregated view, build it from `enriched_ad_records` after the mapping step.

## Command Pattern

```bash
python3 scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --start-date 2025-04-01 \
  --end-date 2025-04-30 \
  --output-dir /tmp/spirits-image-enriched-usa
```

If the base dataset uses raw BigQuery-style names, the skill can usually auto-detect:

- `L1_UNIQUE_AD_ID` as the base key for extracting `AdId`
- `L1_SKAI_COUNTRY_CODE_ISO2` as the country column

If the base dataset uses other names, pass them explicitly:

```bash
python3 scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --input-ad-id-column my_ad_id \
  --input-country-column my_country \
  --country ES \
  --start-date 2025-04-01 \
  --end-date 2025-04-30 \
  --output-dir /tmp/spirits-image-enriched-es
```

To include `EXCLUDED_BRAND`, add `--include-brand`.

## Inputs

The base dataset can be CSV or JSON and must include at least one column with `AdId` or an identifier from which it can be extracted, for example:

- `AdId`
- `ad_id`
- `L1_UNIQUE_AD_ID`

If the base dataset contains `L1_UNIQUE_AD_ID`, the skill automatically extracts `AdId` as the first segment before `_`, while preserving the original column.

## Outputs

- `enriched_ad_records.csv/json`: original base dataset plus columns added from Skai
- `skai_image_mapping.csv/json`: mapping table by `AdId` with `ImageUrl` and minimal Skai metadata
- `summary.json`: coverage and match counters

The columns added to `enriched_ad_records` are:

- `ImageUrl`
- `ImageUrlCount`
- `SkaiMatchStatus`
- `SkaiMatchedAdId`

`ImageUrl` may contain multiple URLs separated by ` | ` if the same `AdId` is associated with more than one image in the requested date range.

## Matching Rules

- la clave principal de join es `AdId`
- si el dataset base trae un identificador compuesto como `3734766_759_USA`, se usa `3734766` para hacer match con Skai
- por defecto se filtra el dataset base al pais pedido si existe una columna de pais detectable
- Skai se filtra por pais, por `profile_id` si se define, y solo deja filas con `ImageUrl`

## Field Mapping

En Skai se consultan por defecto estos campos:

- `AdId`
- `profile_id`
- `CampaignId`
- `CampaignName`
- `Headline`
- `Channel`
- `source`
- `brand`
- `ImageUrl`
- `Country`
- `AdTypeName`

Los nombres del dataset externo no tienen que coincidir con los de Skai. El mapping relevante es:

- `L1_UNIQUE_AD_ID` -> `AdId` extraido
- `L1_SKAI_COUNTRY_CODE_ISO2` -> `country`

Si tu cuenta de Skai usa otros nombres de campo para `ImageUrl` o `AdId`, copiar y ajustar [field-config.example.json](references/field-config.example.json) y ejecutar con `--field-config`.

## Testing

Para probar el pipeline sin llamar al API, usar el fixture `scripts/fixtures/sample_report.json` junto con un CSV o JSON pequeño como dataset base.

```bash
python3 scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --output-dir /tmp/skai-sample \
  --input-json scripts/fixtures/sample_report.json
```

## Notes

- No usar Skai como fuente principal de performance si ya existe una tabla curada en BigQuery.
- Usar Skai para el mapping `AdId -> ImageUrl`.
- Si hay filas sin match, revisar primero el rango de fechas y luego la columna usada como `AdId`.
- Si el API devuelve error por nombres de campo, ajustar el `field-config`.
