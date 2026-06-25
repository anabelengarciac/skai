#!/usr/bin/env python3

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import requests

TOKEN_URL = "https://services.kenshoo.com/api/v1/token"
REPORTS_URL = "https://services.kenshoo.com/api/v1/reports"
DEFAULT_TIMEOUT = 120
DEFAULT_REPORT_PAGE_LIMIT = 2000
ENRICHED_META_COLUMNS = ["ImageUrl", "ImageUrlCount", "SkaiMatchStatus", "SkaiMatchedAdId"]
MAPPING_OUTPUT_COLUMNS = [
    "AdId",
    "ImageUrl",
    "ImageUrlCount",
    "profile_id",
    "CampaignId",
    "CampaignName",
    "Headline",
    "Channel",
    "source",
    "brand",
    "country",
]
DEFAULT_FIELD_CONFIG = {
    "group_by": ["ad_id"],
    "fields": [
        {
            "output": "AdId",
            "name": "AdId",
            "group": "ATTRIBUTES",
            "aliases": ["AdId", "ad_id", "Ad ID"],
        },
        {
            "output": "profile_id",
            "name": "ProfileId",
            "group": "ATTRIBUTES",
            "aliases": ["ProfileId", "profile_id", "Profile ID"],
        },
        {
            "output": "CampaignId",
            "name": "CampaignId",
            "group": "ATTRIBUTES",
            "aliases": ["CampaignId", "campaign_id", "Campaign ID"],
        },
        {
            "output": "CampaignName",
            "name": "CampaignName",
            "group": "ATTRIBUTES",
            "aliases": ["CampaignName", "campaign_name", "Campaign Name"],
        },
        {
            "output": "Headline",
            "name": "AdName",
            "group": "ATTRIBUTES",
            "aliases": ["AdName", "Headline", "headline", "Ad Name"],
        },
        {
            "output": "Channel",
            "name": "Channel",
            "group": "ATTRIBUTES",
            "aliases": ["Channel", "channel", "ChannelName"],
        },
        {
            "output": "source",
            "name": "AccountName",
            "group": "ATTRIBUTES",
            "aliases": ["AccountName", "Account Name", "source", "Source"],
        },
        {
            "output": "brand",
            "name": "Brand (Ads)",
            "group": "DIMENSIONS",
            "aliases": ["Brand (Ads)", "brand", "Brand"],
        },
        {
            "output": "ImageUrl",
            "name": "ImageUrl",
            "group": "ATTRIBUTES",
            "aliases": ["ImageUrl", "image_url", "Image URL"],
        },
        {
            "output": "Country",
            "name": "Country",
            "group": "DIMENSIONS",
            "aliases": ["Country", "country"],
        },
        {
            "output": "AdTypeName",
            "name": "AdTypeName",
            "group": "ATTRIBUTES",
            "aliases": ["AdTypeName", "ad_type_name", "Ad Type Name"],
        },
    ],
}
VIDEO_HINTS = ("video", "mp4", "mov", "webm", "youtube", "vimeo")
EXCLUDED_BRAND_TEXT_FIELDS = ("CampaignName", "brand", "Headline", "source")
EXCLUDED_BRAND_PATTERNS = (
    re.compile(r"(^|[^A-Z0-9])EXCLUDED_BRAND([^A-Z0-9]|$)"),
    re.compile(r"EXCLUDED BRAND"),
)
DEFAULT_INPUT_AD_ID_ALIASES = ["AdId", "ad_id", "adId", "L1_UNIQUE_AD_ID"]
DEFAULT_INPUT_COUNTRY_ALIASES = ["country", "Country", "L1_SKAI_COUNTRY_CODE_ISO2"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Usa Skai solo para mapear ImageUrl por AdId y enriquecer un dataset base "
            "externo, por ejemplo uno exportado desde BigQuery."
        ),
    )
    parser.add_argument(
        "--input-dataset",
        required=True,
        help="Ruta al dataset base en CSV o JSON que quieres enriquecer con ImageUrl",
    )
    parser.add_argument(
        "--input-format",
        choices=("auto", "csv", "json"),
        default="auto",
        help="Formato del dataset base. Si no se indica, se infiere por extension",
    )
    parser.add_argument(
        "--input-ad-id-column",
        help=(
            "Nombre de la columna del dataset base que contiene el AdId. "
            "Si no se indica, intenta detectar AdId/ad_id/L1_UNIQUE_AD_ID"
        ),
    )
    parser.add_argument(
        "--input-country-column",
        help=(
            "Nombre de la columna de pais del dataset base. "
            "Si no se indica, intenta detectar Country/country/L1_SKAI_COUNTRY_CODE_ISO2"
        ),
    )
    parser.add_argument(
        "--country",
        help="Pais a consultar en Skai. Si no se especifica, usa SKAI_COUNTRY del .env o USA",
    )
    parser.add_argument("--start-date", required=True, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--output-dir", required=True, help="Directorio donde guardar resultados")
    parser.add_argument(
        "--format",
        choices=("csv", "json", "both"),
        default="both",
        help="Formato de salida",
    )
    parser.add_argument(
        "--field-config",
        help="Ruta a un JSON de configuracion si tu cuenta usa otros nombres de campos",
    )
    parser.add_argument(
        "--profile-ids",
        help="Lista separada por comas de profile_id a incluir, por ejemplo 775,776",
    )
    parser.add_argument(
        "--env-file",
        help="Ruta al .env. Si se omite, intenta cargar .env del skill o del directorio actual",
    )
    parser.add_argument(
        "--input-json",
        help="Ruta a una respuesta JSON ya descargada de Skai para probar el flujo sin llamar al API",
    )
    parser.add_argument("--client-id", help="Sobrescribe SKAI_CLIENT_ID")
    parser.add_argument("--refresh-token", help="Sobrescribe SKAI_REFRESH_TOKEN")
    parser.add_argument("--ks", help="Sobrescribe SKAI_KS")
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Timeout en segundos para llamadas HTTP",
    )
    parser.add_argument(
        "--save-raw-response",
        help="Guarda la respuesta original del API antes de procesarla",
    )
    parser.add_argument(
        "--exclude-brand",
        dest="exclude_brand",
        action="store_true",
        help="Excluye creatividades EXCLUDED_BRAND y Excluded Brand del mapping",
    )
    parser.add_argument(
        "--include-brand",
        dest="exclude_brand",
        action="store_false",
        help="Incluye creatividades EXCLUDED_BRAND y Excluded Brand en el mapping",
    )
    parser.set_defaults(exclude_brand=True)
    return parser.parse_args()


def load_env_file(env_file: str | None) -> None:
    candidate_paths: list[Path] = []
    if env_file:
        candidate_paths.append(Path(env_file).expanduser())
    else:
        candidate_paths.append(Path(__file__).resolve().parents[1] / ".env")
        candidate_paths.append(Path.cwd() / ".env")

    for path in candidate_paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))
        return


def load_field_config(path: str | None) -> dict[str, Any]:
    if not path:
        return DEFAULT_FIELD_CONFIG

    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if "fields" not in payload or not isinstance(payload["fields"], list):
        raise ValueError("El field config debe incluir una lista 'fields'.")

    group_by = payload.get("group_by") or DEFAULT_FIELD_CONFIG["group_by"]
    return {"group_by": group_by, "fields": payload["fields"]}


def get_required_value(cli_value: str | None, env_name: str) -> str:
    if cli_value:
        return cli_value
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    raise ValueError(f"Falta {env_name}. Define la variable de entorno o pasala por CLI.")


def get_optional_value(cli_value: str | None, env_name: str) -> str | None:
    if cli_value:
        return cli_value
    return os.getenv(env_name)


def country_env_suffix(country: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", (country or "").strip().upper()).strip("_")
    return normalized


def get_country_aware_value(
    cli_value: str | None,
    env_name: str,
    country: str,
    *,
    required: bool = False,
) -> str | None:
    if cli_value:
        return cli_value

    suffix = country_env_suffix(country)
    if suffix:
        country_env_name = f"{env_name}_{suffix}"
        if country_env_name in os.environ:
            value = os.environ.get(country_env_name)
            if required and not value:
                raise ValueError(
                    f"Falta {country_env_name}. Define la variable de entorno o pasala por CLI."
                )
            return value

    if required:
        return get_required_value(None, env_name)
    return get_optional_value(None, env_name)


def get_access_token(client_id: str, refresh_token: str, timeout: int) -> str:
    response = requests.post(
        TOKEN_URL,
        data={"refresh_token": refresh_token, "client_id": client_id},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_report(
    access_token: str,
    ks: str,
    start_date: str,
    end_date: str,
    field_config: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    requested_fields = [
        {"name": field["name"], "group": field["group"]}
        for field in field_config["fields"]
    ]
    base_payload = {
        "entity": "AD",
        "group_by": field_config["group_by"],
        "date_range": {"start_date": start_date, "end_date": end_date},
        "limit": DEFAULT_REPORT_PAGE_LIMIT,
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    merged_payload: dict[str, Any] | None = None
    total_records = 0
    page = 0

    while True:
        payload = dict(base_payload)
        payload["fields"] = requested_fields
        payload["page"] = page
        response = requests.post(
            f"{REPORTS_URL}?ks={ks}",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            invalid_field = parse_invalid_field_error(response)
            if invalid_field and remove_requested_field(requested_fields, invalid_field):
                continue
            raise

        page_payload = response.json()
        entities = page_payload.get("entities", [])

        if merged_payload is None:
            merged_payload = page_payload
        else:
            merged_entities = merged_payload.setdefault("entities", [])
            for index, entity in enumerate(entities):
                if index >= len(merged_entities):
                    merged_entities.append(entity)
                    continue
                merged_entities[index].setdefault("records", [])
                merged_entities[index]["records"].extend(entity.get("records", []))

        page_record_count = 0
        for index, entity in enumerate(entities):
            page_record_count += len(entity.get("records", []))
            if index < len((merged_payload or {}).get("entities", [])):
                merged_payload["entities"][index]["total"] = entity.get("total")

        total_records += page_record_count
        expected_total = (
            max((entity.get("total") or 0) for entity in (merged_payload or {}).get("entities", []))
            if merged_payload
            else 0
        )
        if page_record_count == 0 or (expected_total and total_records >= expected_total):
            break
        page += 1

    return merged_payload or {"entities": []}


def parse_invalid_field_error(response: requests.Response) -> tuple[str, str | None] | None:
    try:
        payload = response.json()
    except ValueError:
        return None

    message = str(payload.get("error_message") or "")
    match = re.search(r"Column name (.+?) doesn't exist in group ([A-Za-z0-9_ ()-]+)", message)
    if not match:
        return None
    return match.group(1).strip(), match.group(2).strip()


def remove_requested_field(
    requested_fields: list[dict[str, Any]],
    invalid_field: tuple[str, str | None],
) -> bool:
    invalid_name, invalid_group = invalid_field
    for index, field in enumerate(requested_fields):
        same_name = str(field.get("name") or "").strip() == invalid_name
        same_group = invalid_group is None or str(field.get("group") or "").strip() == invalid_group
        if same_name and same_group:
            requested_fields.pop(index)
            return True
    return False


def load_input_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_scalar(value: Any) -> Any:
    if isinstance(value, list):
        if not value:
            return None
        extracted = [extract_scalar(item) for item in value]
        extracted = [item for item in extracted if item not in (None, "")]
        if not extracted:
            return None
        if len(extracted) == 1:
            return extracted[0]
        return " | ".join(str(item) for item in extracted)

    if isinstance(value, dict):
        if "value" in value:
            return extract_scalar(value["value"])
        if "display_value" in value:
            return extract_scalar(value["display_value"])

    return value


def normalize_records(report_payload: dict[str, Any], field_config: dict[str, Any]) -> list[dict[str, Any]]:
    entities = report_payload.get("entities", [])
    records: list[dict[str, Any]] = []

    for entity in entities:
        for record in entity.get("records", []):
            raw_values = record.get("record_values", {})
            normalized: dict[str, Any] = {}
            for field in field_config["fields"]:
                value = None
                for key in [field["name"], *field.get("aliases", [])]:
                    if key in raw_values:
                        value = extract_scalar(raw_values[key])
                        break
                normalized[field["output"]] = value
            records.append(normalized)

    return records


def parse_profile_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def normalize_country_value(value: Any) -> str:
    text = str(value or "").strip().upper()
    aliases = {
        "USA": "US",
        "UNITED STATES": "US",
        "UNITED STATES OF AMERICA": "US",
        "ESPAÑA": "ES",
        "SPAIN": "ES",
    }
    return aliases.get(text, text)


def filter_image_records(
    records: list[dict[str, Any]],
    country: str,
    profile_ids: list[str],
    exclude_brand: bool,
) -> tuple[list[dict[str, Any]], bool, bool, int]:
    normalized_country = normalize_country_value(country)
    country_present = any(record.get("Country") not in (None, "") for record in records)
    profile_filter_applied = bool(profile_ids)
    allowed_profile_ids = set(profile_ids)
    filtered: list[dict[str, Any]] = []
    excluded_brand_rows = 0

    for record in records:
        record_profile_id = str(record.get("profile_id") or "").strip()
        if allowed_profile_ids and record_profile_id not in allowed_profile_ids:
            continue

        record_country = normalize_country_value(record.get("Country"))
        if not allowed_profile_ids and country_present and record_country != normalized_country:
            continue

        image_url = str(record.get("ImageUrl") or "").strip()
        if not image_url:
            continue

        ad_type = str(record.get("AdTypeName") or "").strip().lower()
        if any(token in ad_type for token in VIDEO_HINTS):
            continue

        image_url_lower = image_url.lower()
        if any(token in image_url_lower for token in VIDEO_HINTS):
            continue

        if exclude_brand and is_excluded_brand_record(record):
            excluded_brand_rows += 1
            continue

        filtered.append(record)

    return filtered, country_present and not allowed_profile_ids, profile_filter_applied, excluded_brand_rows


def is_excluded_brand_record(record: dict[str, Any]) -> bool:
    for field_name in EXCLUDED_BRAND_TEXT_FIELDS:
        value = str(record.get(field_name) or "").strip().upper()
        if not value:
            continue
        if any(pattern.search(value) for pattern in EXCLUDED_BRAND_PATTERNS):
            return True
    return False


def detect_dataset_format(path: Path, input_format: str) -> str:
    if input_format != "auto":
        return input_format
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".json":
        return "json"
    raise ValueError("No se pudo inferir el formato del dataset base. Usa --input-format.")


def load_input_dataset(path: str, input_format: str) -> tuple[list[dict[str, Any]], list[str]]:
    dataset_path = Path(path).expanduser().resolve()
    resolved_format = detect_dataset_format(dataset_path, input_format)

    if resolved_format == "csv":
        with open(dataset_path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = [dict(row) for row in reader]
            return rows, list(reader.fieldnames or [])

    with open(dataset_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        rows = [dict(item) for item in payload]
    elif isinstance(payload, dict) and isinstance(payload.get("records"), list):
        rows = [dict(item) for item in payload["records"]]
    else:
        raise ValueError("El JSON del dataset base debe ser una lista de objetos o incluir una clave 'records'.")

    columns = collect_columns(rows)
    return rows, columns


def collect_columns(rows: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def resolve_column_name(rows: list[dict[str, Any]], explicit: str | None, aliases: list[str]) -> str | None:
    if explicit:
        return explicit
    if not rows:
        return None
    available = rows[0].keys()
    for candidate in aliases:
        if candidate in available:
            return candidate
    lowered_map = {key.lower(): key for key in available}
    for candidate in aliases:
        if candidate.lower() in lowered_map:
            return lowered_map[candidate.lower()]
    return None


def extract_ad_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if "_" in text:
        return text.split("_", 1)[0].strip()
    return text


def filter_input_rows_by_country(
    rows: list[dict[str, Any]],
    country: str,
    country_column: str | None,
) -> tuple[list[dict[str, Any]], bool]:
    if not country_column:
        return rows, False

    rows_with_country = [
        row for row in rows if str(row.get(country_column) or "").strip()
    ]
    if not rows_with_country:
        return rows, False

    target = normalize_country_value(country)
    filtered = [
        row
        for row in rows
        if normalize_country_value(row.get(country_column)) == target
    ]
    return filtered, True


def choose_preferred_row(records: list[dict[str, Any]]) -> dict[str, Any]:
    return sorted(
        records,
        key=lambda item: (
            str(item.get("profile_id") or ""),
            str(item.get("CampaignId") or ""),
            str(item.get("ImageUrl") or ""),
        ),
    )[0]


def build_mapping_by_ad_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        ad_id = extract_ad_id(record.get("AdId"))
        if not ad_id:
            continue
        grouped.setdefault(ad_id, []).append(record)

    mapping: dict[str, dict[str, Any]] = {}
    for ad_id, items in grouped.items():
        preferred = choose_preferred_row(items)
        unique_image_urls = unique_non_empty_values(items, "ImageUrl")
        mapping[ad_id] = {
            "AdId": ad_id,
            "ImageUrl": " | ".join(unique_image_urls),
            "ImageUrlCount": len(unique_image_urls),
            "profile_id": str(preferred.get("profile_id") or ""),
            "CampaignId": str(preferred.get("CampaignId") or ""),
            "CampaignName": str(preferred.get("CampaignName") or ""),
            "Headline": str(preferred.get("Headline") or ""),
            "Channel": str(preferred.get("Channel") or ""),
            "source": str(preferred.get("source") or ""),
            "brand": str(preferred.get("brand") or ""),
            "country": str(preferred.get("Country") or ""),
        }
    return mapping


def unique_non_empty_values(records: list[dict[str, Any]], field_name: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for record in records:
        value = str(record.get(field_name) or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def enrich_rows(
    rows: list[dict[str, Any]],
    ad_id_column: str,
    mapping: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    enriched: list[dict[str, Any]] = []
    matched_rows = 0
    multi_image_matches = 0

    for row in rows:
        enriched_row = dict(row)
        input_ad_id = extract_ad_id(row.get(ad_id_column))
        match = mapping.get(input_ad_id)
        if match:
            matched_rows += 1
            if (match.get("ImageUrlCount") or 0) > 1:
                multi_image_matches += 1
            enriched_row["ImageUrl"] = match.get("ImageUrl", "")
            enriched_row["ImageUrlCount"] = match.get("ImageUrlCount", 0)
            enriched_row["SkaiMatchStatus"] = "matched"
        else:
            enriched_row["ImageUrl"] = ""
            enriched_row["ImageUrlCount"] = 0
            enriched_row["SkaiMatchStatus"] = "unmatched"
        enriched_row["SkaiMatchedAdId"] = input_ad_id
        enriched.append(enriched_row)

    return enriched, matched_rows, multi_image_matches


def count_unique_non_empty_rows(rows: list[dict[str, Any]], field_name: str) -> int:
    values = {
        str(row.get(field_name) or "").strip()
        for row in rows
        if str(row.get(field_name) or "").strip()
    }
    return len(values)


def write_exports(records: list[dict[str, Any]], destination: Path, file_format: str, columns: list[str]) -> None:
    if file_format in ("csv", "both"):
        write_csv(records, destination.with_suffix(".csv"), columns)
    if file_format in ("json", "both"):
        write_json(records, destination.with_suffix(".json"))


def write_csv(records: list[dict[str, Any]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in columns})


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def save_raw_response(raw_payload: dict[str, Any], path: str) -> None:
    write_json(raw_payload, Path(path))


def build_export_manifest(base_path: Path, file_format: str) -> dict[str, str]:
    manifest: dict[str, str] = {}
    if file_format in ("csv", "both"):
        manifest["csv"] = str(base_path.with_suffix(".csv"))
    if file_format in ("json", "both"):
        manifest["json"] = str(base_path.with_suffix(".json"))
    return manifest


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)
    if not args.country:
        args.country = os.getenv("SKAI_COUNTRY") or "USA"

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        input_rows, input_columns = load_input_dataset(args.input_dataset, args.input_format)
        ad_id_column = resolve_column_name(
            input_rows,
            args.input_ad_id_column,
            DEFAULT_INPUT_AD_ID_ALIASES,
        )
        if not ad_id_column:
            raise ValueError(
                "No pude detectar la columna de AdId en el dataset base. Usa --input-ad-id-column."
            )

        country_column = resolve_column_name(
            input_rows,
            args.input_country_column,
            DEFAULT_INPUT_COUNTRY_ALIASES,
        )
        filtered_input_rows, input_country_filter_applied = filter_input_rows_by_country(
            input_rows,
            args.country,
            country_column,
        )

        field_config = load_field_config(args.field_config)
        profile_ids = parse_profile_ids(
            get_country_aware_value(args.profile_ids, "SKAI_PROFILE_IDS", args.country) or ""
        )

        if args.input_json:
            report_payload = load_input_json(args.input_json)
        else:
            client_id = get_required_value(args.client_id, "SKAI_CLIENT_ID")
            refresh_token = get_country_aware_value(
                args.refresh_token,
                "SKAI_REFRESH_TOKEN",
                args.country,
                required=True,
            )
            ks = get_country_aware_value(args.ks, "SKAI_KS", args.country, required=True)
            access_token = get_access_token(client_id, refresh_token, args.request_timeout)
            report_payload = fetch_report(
                access_token=access_token,
                ks=ks,
                start_date=args.start_date,
                end_date=args.end_date,
                field_config=field_config,
                timeout=args.request_timeout,
            )

        if args.save_raw_response:
            save_raw_response(report_payload, args.save_raw_response)

        skai_records = normalize_records(report_payload, field_config)
        filtered_skai_records, country_filter_applied, profile_filter_applied, excluded_brand_rows = filter_image_records(
            skai_records,
            args.country,
            profile_ids,
            args.exclude_brand,
        )
        mapping = build_mapping_by_ad_id(filtered_skai_records)
        mapping_rows = list(mapping.values())
        enriched_rows, matched_rows, multi_image_matches = enrich_rows(
            filtered_input_rows,
            ad_id_column,
            mapping,
        )

        enriched_columns = list(input_columns)
        for column in ENRICHED_META_COLUMNS:
            if column not in enriched_columns:
                enriched_columns.append(column)

        write_exports(
            mapping_rows,
            output_dir / "skai_image_mapping",
            args.format,
            MAPPING_OUTPUT_COLUMNS,
        )
        write_exports(
            enriched_rows,
            output_dir / "enriched_ad_records",
            args.format,
            enriched_columns,
        )

        summary = {
            "country": args.country,
            "requested_profile_ids": profile_ids,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "input_dataset": str(Path(args.input_dataset).expanduser().resolve()),
            "input_ad_id_column": ad_id_column,
            "input_country_column": country_column,
            "input_rows_received": len(input_rows),
            "input_rows_after_country_filter": len(filtered_input_rows),
            "input_country_filter_applied": input_country_filter_applied,
            "input_unique_ad_ids": len({extract_ad_id(row.get(ad_id_column)) for row in filtered_input_rows if extract_ad_id(row.get(ad_id_column))}),
            "skai_records_received": len(skai_records),
            "skai_records_with_image": len(filtered_skai_records),
            "skai_unique_ad_ids": count_unique_non_empty_rows(mapping_rows, "AdId"),
            "matched_rows": matched_rows,
            "unmatched_rows": len(enriched_rows) - matched_rows,
            "matched_rows_with_multiple_image_urls": multi_image_matches,
            "matched_unique_ad_ids": len({
                str(row.get("SkaiMatchedAdId") or "").strip()
                for row in enriched_rows
                if row.get("SkaiMatchStatus") == "matched"
            }),
            "unique_image_urls": count_unique_non_empty_rows(mapping_rows, "ImageUrl"),
            "country_filter_applied_to_skai": country_filter_applied,
            "profile_filter_applied": profile_filter_applied,
            "excluded_brand_filter_applied": args.exclude_brand,
            "excluded_brand_rows": excluded_brand_rows,
            "output_dir": str(output_dir),
            "files": {
                "skai_image_mapping": build_export_manifest(output_dir / "skai_image_mapping", args.format),
                "enriched_ad_records": build_export_manifest(output_dir / "enriched_ad_records", args.format),
            },
        }
        write_json(summary, output_dir / "summary.json")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(exc.response.text, file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
