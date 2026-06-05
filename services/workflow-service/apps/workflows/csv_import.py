import csv
import json
import re
from dataclasses import dataclass
from io import StringIO

from apps.workflows.models import label_for_document_slug

CONFIG_HEADERS = {
    "name",
    "approval_type",
    "description",
    "deadline",
    "priority",
    "tags",
    "metadata",
}

BASE_FORM_FIELDS = ["full_name", "matricule", "faculty", "department", "notes"]
STOP_PATTERN = re.compile(r"^stop_(\d+)$")


@dataclass
class CSVValidationResult:
    valid_rows: list
    errors: list

    @property
    def invalid_rows(self):
        return len(self.errors)


def split_tags(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def parse_required_documents(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw or raw.lower() == "none":
        return []
    return [item.strip() for item in raw.split("|") if item.strip()]


def parse_sla_days(value: str) -> int:
    raw = (value or "").strip()
    if not raw:
        return 3
    match = re.search(r"\d+", raw)
    return max(int(match.group(0)), 1) if match else 3


def parse_metadata(value: str, row_number: int) -> tuple[dict, list]:
    if not (value or "").strip():
        return {}, []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        return {}, [{"row": row_number, "error": f"metadata must be valid JSON: {exc.msg}"}]
    if not isinstance(parsed, dict):
        return {}, [{"row": row_number, "error": "metadata must be a JSON object"}]
    return parsed, []


def approval_chain_from_metadata(metadata: dict) -> list[str]:
    stops = []
    for key, value in metadata.items():
        match = STOP_PATTERN.match(key)
        if match and str(value).strip():
            stops.append((int(match.group(1)), str(value).strip()))
    return [value for _, value in sorted(stops, key=lambda item: item[0])]


def form_fields_for(approval_chain: list[str], required_docs: list[str]) -> list[str]:
    fields = list(BASE_FORM_FIELDS)
    needs_supervisor = "supervisor" in {doc.lower() for doc in required_docs} or any(
        role.strip().lower() == "supervisor" for role in approval_chain
    )
    if needs_supervisor:
        fields.append("supervisor")
    return fields


def parse_workflow_config_csv(csv_text: str) -> CSVValidationResult:
    reader = csv.DictReader(StringIO(csv_text))
    headers = {header.strip() for header in (reader.fieldnames or [])}
    errors = []

    missing = CONFIG_HEADERS - headers
    if missing:
        errors.append({"row": 1, "error": f"Missing required columns: {', '.join(sorted(missing))}"})
        return CSVValidationResult(valid_rows=[], errors=errors)

    valid_rows = []
    for row_number, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        if not name:
            errors.append({"row": row_number, "error": "name is required"})
            continue

        metadata, metadata_errors = parse_metadata(row.get("metadata", ""), row_number)
        if metadata_errors:
            errors.extend(metadata_errors)
            continue

        approval_chain = approval_chain_from_metadata(metadata)
        if not approval_chain:
            errors.append({"row": row_number, "error": "metadata must contain at least one stop_N field"})
            continue

        required_docs = parse_required_documents(str(metadata.get("required_documents", "")))
        all_documents_required = bool(metadata.get("all_documents_required", True))
        try:
            priority = int((row.get("priority") or "2").strip() or "2")
        except ValueError:
            errors.append({"row": row_number, "error": "priority must be an integer"})
            continue

        valid_rows.append(
            {
                "name": name,
                "approval_type": (row.get("approval_type") or "").strip(),
                "description": (row.get("description") or "").strip(),
                "department": str(metadata.get("department", "") or "").strip(),
                "priority": priority,
                "tags": split_tags(row.get("tags", "")),
                "approval_chain": approval_chain,
                "required_docs": required_docs,
                "form_fields": form_fields_for(approval_chain, required_docs),
                "all_documents_required": all_documents_required,
                "expected_output": str(metadata.get("output", "") or "").strip(),
                "sla_days": parse_sla_days(row.get("deadline", "")),
                "is_active": True,
                "metadata": metadata,
                "approval_stops": approval_chain,
                "document_requirements": [
                    {
                        "document_slug": slug,
                        "label": label_for_document_slug(slug),
                        "is_required": all_documents_required,
                    }
                    for slug in required_docs
                ],
            }
        )

    return CSVValidationResult(valid_rows=valid_rows, errors=errors)


parse_workflow_csv = parse_workflow_config_csv
