# Configuracion

## Credenciales

Esta skill puede leer un `.env` automaticamente desde la raiz de la skill.
El fichero esperado es `.env` in the skill root y puede incluir:

- `SKAI_CLIENT_ID`
- `SKAI_REFRESH_TOKEN`
- `SKAI_KS`
- `SKAI_PROFILE_IDS`
- `SKAI_COUNTRY`

Si no se especifica `--country`, el script usa `SKAI_COUNTRY`; si tampoco existe, usa `USA`.

## Objetivo de esta skill

El objetivo ya no es usar Skai como base completa de analisis. El objetivo es:

1. partir de un dataset base externo, normalmente exportado desde BigQuery
2. consultar Skai para sacar el mapping `AdId -> ImageUrl`
3. enriquecer cada fila del dataset base con la `ImageUrl` correspondiente

La fuente de verdad para metricas debe seguir siendo la base externa.

## Comando base

```bash
python3 scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --output-dir /tmp/spirits-image-enriched-usa
```

Si el dataset base usa nombres distintos para `AdId` o pais, pasalos por CLI:

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

Por defecto el script excluye `EXCLUDED_BRAND` y `Excluded Brand`; si alguna vez quieres incluirlos, usa `--include-brand`.

## Dataset base

La skill admite:

- CSV
- JSON con una lista de objetos
- JSON con una clave `records`

La clave de join puede detectarse automaticamente si existe alguna de estas columnas:

- `AdId`
- `ad_id`
- `L1_UNIQUE_AD_ID`

Si el dataset trae `L1_UNIQUE_AD_ID`, la skill usa el primer segmento antes del `_` para hacer match, pero no modifica la columna original.

Para el pais, intenta detectar:

- `country`
- `Country`
- `L1_SKAI_COUNTRY_CODE_ISO2`

## Salidas

El script genera:

- `enriched_ad_records.csv` y/o `.json`
- `skai_image_mapping.csv` y/o `.json`
- `summary.json`

`enriched_ad_records` conserva una fila por fila del dataset base y añade:

- `ImageUrl`
- `ImageUrlCount`
- `SkaiMatchStatus`
- `SkaiMatchedAdId`

`skai_image_mapping` contiene una fila por `AdId` encontrado en Skai, con metadata minima:

- `AdId`
- `ImageUrl`
- `ImageUrlCount`
- `profile_id`
- `CampaignId`
- `CampaignName`
- `Headline`
- `Channel`
- `source`
- `brand`
- `country`

## Matching

La skill hace lo siguiente:

- consulta Skai en el rango indicado
- filtra por pais o `profile_id`
- conserva solo filas con `ImageUrl`
- excluye video
- excluye por defecto `EXCLUDED_BRAND`
- construye un mapping por `AdId`
- hace join de ese mapping contra tu dataset base

Si un `AdId` tiene varias imágenes en Skai, `ImageUrl` se exporta como una lista separada por ` | ` y `ImageUrlCount` indica cuantas son.

## Ajuste de campos

El API de Skai puede devolver nombres de campo distintos segun cuenta o conector.
Si alguna llamada falla por un nombre de campo invalido, copia `references/field-config.example.json`,
ajusta `group_by`, `name`, `group` o `aliases`, y vuelve a ejecutar con `--field-config`.

En esta cuenta concreta, el mapeo que ha funcionado es:

- `Headline` -> `AdName`
- `source` -> `AccountName`

## Prueba local sin API

```bash
python3 scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --output-dir /tmp/skai-sample \
  --input-json scripts/fixtures/sample_report.json
```
