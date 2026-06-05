import csv
import json
from dataclasses import dataclass
from io import StringIO

from django.utils.dateparse import parse_datetime

from apps.approvals.models import ApprovalType

REQUIRED_HEADERS = {"name", "approval_type"}
OPTIONAL_HEADERS = {"description", "deadline", "priority", "tags", "metadata"}
ALL_HEADERS = REQUIRED_HEADERS | OPTIONAL_HEADERS


@dataclass
class CSVValidationResult:
    valid_rows: list
    errors: list

    @property
    def invalid_rows(self):
        return len(self.errors)


def parse_workflow_csv(file_content: str):
    reader = csv.DictReader(StringIO(file_content))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_HEADERS - headers
    unknown = headers - ALL_HEADERS
    errors = []

    if missing:
        errors.append({"row": 1, "error": f"Missing required columns: {', '.join(sorted(missing))}"})
    if unknown:
        errors.append({"row": 1, "error": f"Unknown columns: {', '.join(sorted(unknown))}"})
    if errors:
        return CSVValidationResult([], errors)

    approval_types = {item.name: item for item in ApprovalType.objects.all()}
    valid_rows = []

    for row_number, row in enumerate(reader, start=2):
        name = (row.get("name") or "").strip()
        approval_type_name = (row.get("approval_type") or "").strip()

        if not name:
            errors.append({"row": row_number, "error": "name is required"})
            continue
        if approval_type_name not in approval_types:
            errors.append({"row": row_number, "error": f"Unknown approval_type: {approval_type_name}"})
            continue

        deadline = None
        if row.get("deadline"):
            deadline = parse_datetime(row["deadline"])
            if deadline is None:
                errors.append({"row": row_number, "error": "deadline must be ISO-8601 datetime"})
                continue

        try:
            priority = int(row.get("priority") or 1)
        except ValueError:
            errors.append({"row": row_number, "error": "priority must be an integer"})
            continue

        try:
            metadata = json.loads(row.get("metadata") or "{}")
        except json.JSONDecodeError:
            errors.append({"row": row_number, "error": "metadata must be valid JSON"})
            continue

        valid_rows.append({
            "name": name,
            "description": row.get("description", ""),
            "approval_type": approval_types[approval_type_name],
            "deadline": deadline,
            "priority": priority,
            "tags": [tag.strip() for tag in (row.get("tags") or "").split(";") if tag.strip()],
            "metadata": metadata,
        })

    return CSVValidationResult(valid_rows, errors)