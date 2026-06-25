# Spirits Creative Image Enrichment

![Status](https://img.shields.io/badge/status-showcase_ready-2ea44f)
![Built for](https://img.shields.io/badge/built_for-final_degree_project-0969da)
![Domain](https://img.shields.io/badge/domain-creative_analytics_enrichment-6f42c1)
![Stack](https://img.shields.io/badge/stack-python_%7C_skai_api_%7C_csv_json-8250df)

A data-enrichment workflow built for my Final Degree Project, **"Analysis of advertising creatives in spirits through AI"**. It connects trusted performance data with the image URLs needed to analyze advertising creatives visually.

In the thesis workflow, performance metrics such as impressions, clicks, and CTR came from a curated source. The missing piece was the visual layer: the image associated with each ad. This skill used Skai as an enrichment source, mapping `AdId -> ImageUrl` so the final dataset could be used for AI-assisted creative analysis.

## Why It Matters

Creative-performance research needs both sides of the dataset: reliable metrics and accessible creative assets. Platform exports often separate those layers, and using the ad platform as the main performance source can create inconsistencies when a curated warehouse already exists.

This skill solves that by keeping performance metrics in the trusted source and using Skai only to enrich each record with creative image metadata.

| Research need | What this skill provides |
| --- | --- |
| Connect campaign performance to actual creative images | `AdId -> ImageUrl` mapping from Skai |
| Preserve the trusted performance source | Enrichment-only design, no metric replacement |
| Prepare data for AI image classification | Valid image URLs attached to each ad/creative row |
| Handle reused creative assets | Image URL counts and match status |
| Support auditability | Mapping table, enriched output, and summary diagnostics |

## Role In My TFG

```mermaid
flowchart LR
    A["Curated performance data"] --> B["Extract AdId"]
    B --> C["Query Skai for ImageUrl"]
    C --> D["Build image mapping"]
    D --> E["Enrich performance dataset"]
    E --> F["Group by creative image"]
    F --> G["AI visual analysis"]
```

The broader thesis methodology used this enrichment step to:

- recover image URLs for ads in spirits campaigns,
- remove records without usable creative images,
- group repeated ads that shared the same image,
- support recalculation of creative-level impressions, clicks, and CTR,
- prepare datasets for Top vs Bottom creative-performance comparison,
- feed the later AI visual-classification stage.

## What It Can Do

- Read a base performance dataset from CSV or JSON.
- Detect or normalize ad identifiers from fields such as `AdId`, `ad_id`, or compound IDs.
- Query Skai for image metadata within a date range and country.
- Filter non-image or video creatives when needed.
- Join image metadata back to the original performance dataset.
- Export enriched records, mapping tables, and run summaries.

## Repository Structure

```text
.
|-- SKILL.md
|-- agents/openai.yaml
|-- references/
|   |-- configuration.md
|   `-- field-config.example.json
`-- scripts/
    |-- fixtures/sample_report.json
    `-- skai_image_ctr_report.py
```

## Example Command

```bash
python3 scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_performance.csv \
  --input-ad-id-column ad_id \
  --country US \
  --start-date 2025-04-01 \
  --end-date 2025-04-30 \
  --output-dir /tmp/spirits-image-enriched
```

## Outputs

| Output | Purpose |
| --- | --- |
| `enriched_ad_records.csv/json` | Original performance dataset plus image metadata |
| `skai_image_mapping.csv/json` | Reusable `AdId -> ImageUrl` mapping |
| `summary.json` | Match rates, filters, and run diagnostics |

## Design Principles

- Do not replace curated performance metrics with platform data.
- Keep Skai as an enrichment layer for creative assets.
- Preserve one output row per input row unless aggregation is explicitly requested.
- Make match status visible instead of silently dropping records.
- Keep field mapping configurable for account-specific schemas.
- Keep credentials and private exports outside the repository.

## Skills Demonstrated

`marketing analytics` - `creative analytics` - `Skai API` - `data enrichment` - `Python ETL` - `CSV/JSON pipelines` - `data quality checks` - `AI-ready dataset preparation`

## Security

This is a sanitized showcase repository. It contains no Skai credentials, client IDs, refresh tokens, profile IDs, private image URLs, proprietary performance exports, or thesis datasets.
