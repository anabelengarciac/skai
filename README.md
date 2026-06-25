---
name: skai
description: Enriquecer un dataset base con `ImageUrl` desde Skai usando `AdId` como clave de mapping. Usar cuando Codex necesite tomar una base externa, normalmente exportada desde BigQuery, y anadir la URL de imagen correspondiente a cada fila sin usar Skai como fuente principal de metricas de performance. Si no se especifica pais, asumir USA por defecto.
---

# Skai

## Overview

Usar esta skill para tomar un dataset base ya preparado fuera de Skai y enriquecerlo con `ImageUrl`. La fuente de verdad para impresiones, clicks, conversiones, CTR y demas metricas debe seguir siendo el dataset externo, por ejemplo BigQuery. Skai se usa solo para construir el mapping `AdId -> ImageUrl` y anadirlo a cada fila.

El flujo correcto es:

1. partir de una base externa con las columnas de negocio y metricas ya definidas
2. consultar Skai para obtener `AdId`, `ImageUrl` y metadata minima
3. filtrar en Skai solo creatividades con imagen y excluir video
4. excluir `EXCLUDED_BRAND` y `Excluded Brand` por defecto, salvo que el usuario pida incluirlos
5. hacer el join por `AdId`
6. exportar una base final enriquecida lista para analisis posterior

Si la misma imagen aparece en muchas filas, eso no es un error: significa que la creatividad se reutiliza en multiples ads o contextos. Esta skill no agrega ni deduplica por imagen en la salida final enriquecida; conserva una fila por fila del dataset base.

## Workflow

1. Confirmar el dataset base, el rango de fechas y el pais. Si no se especifica pais, asumir `USA`.
2. Revisar [configuration.md](./skai/references/configuration.md) si faltan credenciales o si hay dudas con el nombre de la columna de `AdId`.
3. Ejecutar [skai_image_ctr_report.py](./skai/scripts/skai_image_ctr_report.py) con el dataset base y el rango pedido.
4. Entregar:
   - `enriched_ad_records`
   - `skai_image_mapping`
   - `summary.json`
5. Explicar el resultado como una base enriquecida:
   - metricas desde la fuente externa
   - `ImageUrl` desde Skai
6. Si el usuario quiere luego una vista agregada por imagen, construirla despues a partir de `enriched_ad_records`, no durante el mapping.

## Command Pattern

```bash
python3 ./skai/scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --start-date 2025-04-01 \
  --end-date 2025-04-30 \
  --output-dir /tmp/skai-enriched-usa
```

Si el dataset base usa nombres de BigQuery sin transformar, normalmente basta con dejar que la skill detecte:

- `L1_UNIQUE_AD_ID` como clave base para extraer `AdId`
- `L1_SKAI_COUNTRY_CODE_ISO2` como columna de pais

Si tu base usa otros nombres, pasalos de forma explicita:

```bash
python3 ./skai/scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --input-ad-id-column my_ad_id \
  --input-country-column my_country \
  --country ES \
  --start-date 2025-04-01 \
  --end-date 2025-04-30 \
  --output-dir /tmp/skai-enriched-es
```

Si quieres incluir `EXCLUDED_BRAND`, anadir `--include-brand`.

## Inputs

El dataset base puede ser CSV o JSON y debe incluir al menos una columna con `AdId` o un identificador del que se pueda extraer, por ejemplo:

- `AdId`
- `ad_id`
- `L1_UNIQUE_AD_ID`

Si el dataset base contiene `L1_UNIQUE_AD_ID`, la skill extrae automaticamente el `AdId` como el primer segmento antes del primer `_`, pero deja la columna original intacta.

## Outputs

- `enriched_ad_records.csv/json`: dataset base original mas columnas anadidas desde Skai
- `skai_image_mapping.csv/json`: tabla de mapping por `AdId` con `ImageUrl` y metadata minima de Skai
- `summary.json`: contadores de cobertura y matching

Las columnas anadidas en `enriched_ad_records` son:

- `ImageUrl`
- `ImageUrlCount`
- `SkaiMatchStatus`
- `SkaiMatchedAdId`

`ImageUrl` puede contener varias URLs separadas por ` | ` si un mismo `AdId` en Skai aparece asociado a mas de una imagen distinta en el rango consultado.

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

Si tu cuenta de Skai usa otros nombres de campo para `ImageUrl` o `AdId`, copiar y ajustar [field-config.example.json](./skai/references/field-config.example.json) y ejecutar con `--field-config`.

## Testing

Para probar el pipeline sin llamar al API, usar el fixture `scripts/fixtures/sample_report.json` junto con un CSV o JSON pequeño como dataset base.

```bash
python3 ./skai/scripts/skai_image_ctr_report.py \
  --input-dataset /tmp/base_bq.csv \
  --start-date 2026-03-01 \
  --end-date 2026-03-31 \
  --output-dir /tmp/skai-sample \
  --input-json ./skai/scripts/fixtures/sample_report.json
```

## Notes

- No usar Skai como fuente principal de performance si ya existe una tabla curada en BigQuery.
- Usar Skai para el mapping `AdId -> ImageUrl`.
- Si hay filas sin match, revisar primero el rango de fechas y luego la columna usada como `AdId`.
- Si el API devuelve error por nombres de campo, ajustar el `field-config`.
