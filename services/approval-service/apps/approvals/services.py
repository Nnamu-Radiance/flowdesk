import logging

from django.core.cache import cache
from django.db import transaction
from django.utils import dateparse, timezone
from apps.approvals.events import notify_event
from apps.approvals.models import ApprovalChain, ApprovalRecord, ApprovalStep

logger = logging.getLogger(__name__)


def normalize_role(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("/", "_")


def display_role(value: str) -> str:
    return " ".join(part for part in (value or "").replace("_", " ").split()).title()


def cached_assignee_for(role: str, payload: dict) -> tuple[int | None, str]:
    normalized = normalize_role(role)
    form_data = payload.get("form_data") or {}
    if normalized == "supervisor" and form_data.get("supervisor_id"):
        return int(form_data["supervisor_id"]), form_data.get("supervisor_name", "")

    assignees = payload.get("assignees") or {}
    configured = assignees.get(role) or assignees.get(normalized)
    if configured:
        if isinstance(configured, dict):
            return int(configured["id"]), configured.get("name", "")
        return int(configured), ""

    cached = cache.get(f"approval:role_assignees:{normalized}") or []
    if cached:
        first = cached[0]
        if isinstance(first, dict):
            return int(first["id"]), first.get("name", "")
        return int(first), ""
    return None, ""

# services/approval-service/apps/approvals/services.py

def resolve_approver(stop_role: str, supervisor_id: int = None, department: str = None, faculty: str = None) -> int:
    """
    Given a stop label from the CSV, return the user ID of the approver
    by calling the auth-service internal API.
    """
    import requests
    from django.conf import settings

    normalized = (stop_role or "").strip().lower()

    if normalized == "supervisor":
        if not supervisor_id:
            raise ValueError("Supervisor stop requires supervisor_id from the workflow form.")
        return supervisor_id

    type_map = {
        "hod": "hod",
        "head of department": "hod",
        "program coordinator / hod": "hod",
        "program coordinator": "hod",
        "dean": "dean",
        "registrar": "registrar",
        "library": "registrar",
        "finance office": "registrar",
        "admin assistant": "admin_assistant",
        "administrative assistant": "admin_assistant",
        "faculty scientific council": "faculty_council",
        "faculty": "faculty_council",
        "faculty council": "faculty_council",
        "dvc": "dvc",
        "deputy vice chancellor": "dvc",
        "deputy vice chancellor (dvc)": "dvc",
    }

    approver_type = type_map.get(normalized)
    if not approver_type:
        raise ValueError(f"Unknown approver role in CSV: '{stop_role}'")

    department_scoped = {"hod", "admin_assistant"}

    params = {
        "role": "approver",
        "approver_type": approver_type,
        "is_active": "true",
    }

    if approver_type in department_scoped:
        if faculty:
            params["faculty"] = faculty

    try:
        response = requests.get(
            f"{settings.AUTH_SERVICE_URL}/api/auth/users/",
            params=params,
            headers={"X-Internal-Service": "approval-service"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
    except Exception as exc:
        raise ValueError(f"Auth service unreachable when resolving '{stop_role}': {exc}") from exc

    if not results:
        scope = ""
        if department:
            scope = f" for department '{department}'"
        elif faculty:
            scope = f" for faculty '{faculty}'"
        raise ValueError(
            f"No active approver with type '{approver_type}'{scope} found. "
            f"Admin must assign this role before workflows of this type can be submitted."
        )

    return int(results[0]["id"])

class ApprovalService:
    @staticmethod
    @transaction.atomic
    def handle_workflow_created(event: dict):
        payload = event.get("payload", {})
        workflow_id = payload["workflow_id"]
        approval_chain = payload.get("approval_chain") or []
        if not approval_chain:
            raise ValueError("workflow.created payload must include approval_chain")

        form_data = payload.get("form_data") or {}
        student_department = payload.get("student_department") or form_data.get("department", "")
        student_faculty = payload.get("student_faculty") or form_data.get("faculty", "")
        supervisor_id = form_data.get("supervisor_id")

        deadline = dateparse.parse_datetime(payload["deadline"]) if payload.get("deadline") else None
        chain, _ = ApprovalChain.objects.update_or_create(
            workflow_id=workflow_id,
            defaults={
                "workflow_type_name": payload.get("workflow_type_name", ""),
                "student_id": payload.get("student_id") or payload.get("created_by_id"),
                "student_name": payload.get("student_name", ""),
                "student_matricule": payload.get("student_matricule", ""),
                "student_faculty": payload.get("student_faculty", ""),
                "total_steps": len(approval_chain),
                "current_step_number": 1,
                "status": ApprovalChain.Status.ACTIVE,
                "deadline": deadline,
                "documents": payload.get("documents") or [],
                "appeal_round": payload.get("appeal_round", 0),
                "appeal_reason": payload.get("appeal_reason", ""),
                "original_rejection_reason": payload.get("original_rejection_reason", ""),
            },
        )
        chain.steps.all().delete()

        first_step = None
        for index, role in enumerate(approval_chain, start=1):
            assignee_id = None
            assignee_name = ""
            try:
                assignee_id = resolve_approver(
                    stop_role=role,
                    supervisor_id=int(supervisor_id) if supervisor_id else None,
                    department=student_department,
                    faculty=student_faculty,
                )
            except Exception as exc:
                logger.warning(
                    "resolve_approver failed for role '%s': %s; step will have no assignee",
                    role,
                    exc,
                )
                assignee_id, assignee_name = cached_assignee_for(role, payload)

            step = ApprovalStep.objects.create(
                chain=chain,
                step_number=index,
                role_required=normalize_role(role),
                role_display_name=display_role(role),
                assignee_id=assignee_id,
                assignee_name=assignee_name,
                status=ApprovalStep.Status.ACTIVE if index == 1 else ApprovalStep.Status.PENDING,
            )
            if index == 1:
                first_step = step
        if first_step and first_step.assignee_id:
            ApprovalService.publish_requested(chain, first_step, event.get("correlation_id"))
        return chain

    @staticmethod
    def publish_requested(chain: ApprovalChain, step: ApprovalStep, correlation_id: str | None = None):
        return notify_event(
            "approval.requested",
            {
                "workflow_id": chain.workflow_id,
                "step_number": step.step_number,
                "total_steps": chain.total_steps,
                "assignee_id": step.assignee_id,
                "approver_id": step.assignee_id,
                "student_id": chain.student_id,
                "role_display_name": step.role_display_name,
                "student_name": chain.student_name,
                "student_matricule": chain.student_matricule,
                "student_faculty": chain.student_faculty,
                "workflow_type_name": chain.workflow_type_name,
                "deadline": chain.deadline.isoformat() if chain.deadline else None,
                "documents": chain.documents,
            },
            correlation_id=correlation_id,
        )

    @staticmethod
    @transaction.atomic
    def decision(
        chain: ApprovalChain,
        approver_id: int,
        action: str,
        comments: str,
        annotated_document=None,
        send_feedback_to_student: bool = False,
        correlation_id: str | None = None,
    ):
        action_map = {
            "approve": ApprovalRecord.Action.APPROVED,
            "approved": ApprovalRecord.Action.APPROVED,
            "reject": ApprovalRecord.Action.REJECTED,
            "rejected": ApprovalRecord.Action.REJECTED,
            "return": ApprovalRecord.Action.RETURNED,
            "returned": ApprovalRecord.Action.RETURNED,
        }
        record_action = action_map.get(action)
        if not record_action:
            raise ValueError("Invalid approval action")

        current = chain.steps.select_for_update().filter(
            assignee_id=approver_id,
            status=ApprovalStep.Status.ACTIVE,
            step_number=chain.current_step_number,
        ).first()
        if not current:
            raise PermissionError("Only the active assignee can decide this step")

        record = ApprovalRecord.objects.create(
            workflow_id=chain.workflow_id,
            step_number=current.step_number,
            actor_id=approver_id,
            actor_name=current.assignee_name,
            action=record_action,
            comments=comments,
            annotated_document=annotated_document,
            send_feedback_to_student=send_feedback_to_student,
        )
        if annotated_document:
            record.annotated_document = annotated_document
        if send_feedback_to_student:
            record.send_to_submitter = True
        record.approver_comments = comments
        record.save(update_fields=["annotated_document", "send_to_submitter", "approver_comments"])

        current.comments = comments
        current.decision_at = timezone.now()
        current.has_annotated_document = bool(annotated_document)

        if record_action == ApprovalRecord.Action.APPROVED:
            current.status = ApprovalStep.Status.APPROVED
            current.save(update_fields=["status", "comments", "decision_at", "has_annotated_document"])
            next_step = chain.steps.filter(status=ApprovalStep.Status.PENDING).order_by("step_number").first()
            if next_step:
                next_step.status = ApprovalStep.Status.ACTIVE
                next_step.save(update_fields=["status"])
                chain.current_step_number = next_step.step_number
                chain.save(update_fields=["current_step_number"])
                notify_event(
                    "approval.step_completed",
                    {
                        "workflow_id": chain.workflow_id,
                        "student_id": chain.student_id,
                        "workflow_type_name": chain.workflow_type_name,
                        "role_display_name": current.role_display_name,
                        "next_role_display_name": next_step.role_display_name,
                        "step_number": next_step.step_number,
                        "total_steps": chain.total_steps,
                    },
                    correlation_id=correlation_id,
                )
                if next_step.assignee_id:
                    ApprovalService.publish_requested(chain, next_step, correlation_id)
                return "in_approval"

            chain.status = ApprovalChain.Status.APPROVED
            chain.save(update_fields=["status"])
            notify_event(
                "approval.decision",
                {
                    "workflow_id": chain.workflow_id,
                    "student_id": chain.student_id,
                    "workflow_type_name": chain.workflow_type_name,
                    "status": "approved",
                    "final_comments": comments,
                    "send_feedback_to_student": send_feedback_to_student,
                },
                correlation_id=correlation_id,
            )
            notify_event(
                "approval.approved",
                {
                    "workflow_id": chain.workflow_id,
                    "student_id": chain.student_id,
                    "workflow_type_name": chain.workflow_type_name,
                    "comments": comments,
                },
                correlation_id=correlation_id,
            )
            return "approved"

        if record_action == ApprovalRecord.Action.REJECTED:
            current.status = ApprovalStep.Status.REJECTED
            current.save(update_fields=["status", "comments", "decision_at", "has_annotated_document"])
            chain.steps.filter(status=ApprovalStep.Status.PENDING).update(status=ApprovalStep.Status.VOID)
            chain.status = ApprovalChain.Status.REJECTED
            chain.save(update_fields=["status"])
            notify_event(
                "approval.decision",
                {
                    "workflow_id": chain.workflow_id,
                    "student_id": chain.student_id,
                    "workflow_type_name": chain.workflow_type_name,
                    "status": "rejected",
                    "final_comments": comments,
                    "send_feedback_to_student": send_feedback_to_student,
                },
                correlation_id=correlation_id,
            )
            notify_event(
                "approval.rejected",
                {
                    "workflow_id": chain.workflow_id,
                    "student_id": chain.student_id,
                    "workflow_type_name": chain.workflow_type_name,
                    "comments": comments,
                },
                correlation_id=correlation_id,
            )
            return "rejected"

        current.status = ApprovalStep.Status.RETURNED
        current.save(update_fields=["status", "comments", "decision_at", "has_annotated_document"])
        chain.steps.filter(status=ApprovalStep.Status.PENDING).update(status=ApprovalStep.Status.VOID)
        chain.status = ApprovalChain.Status.RETURNED
        chain.save(update_fields=["status"])
        notify_event(
            "approval.returned",
            {
                "workflow_id": chain.workflow_id,
                "student_id": chain.student_id,
                "workflow_type_name": chain.workflow_type_name,
                "step_number": current.step_number,
                "comments": comments,
                "annotated_document_url": record.annotated_document.url if record.annotated_document else "",
                "send_feedback_to_student": send_feedback_to_student,
            },
            correlation_id=correlation_id,
        )
        return "returned"

    @staticmethod
    @transaction.atomic
    def reassign(chain: ApprovalChain, approver_id: int, new_assignee_id: int, reason: str, correlation_id: str | None = None):
        step = chain.steps.select_for_update().filter(
            assignee_id=approver_id,
            status=ApprovalStep.Status.ACTIVE,
            step_number=chain.current_step_number,
        ).first()
        if not step:
            raise PermissionError("Only the active assignee can reassign this step")
        old_assignee_id = step.assignee_id
        step.assignee_id = new_assignee_id
        step.save(update_fields=["assignee_id"])
        ApprovalRecord.objects.create(
            workflow_id=chain.workflow_id,
            step_number=step.step_number,
            actor_id=approver_id,
            actor_name=step.assignee_name,
            action=ApprovalRecord.Action.REASSIGNED,
            comments=reason,
        )
        ApprovalService.publish_requested(chain, step, correlation_id)
        return {"old_assignee_id": old_assignee_id, "new_assignee_id": new_assignee_id}

