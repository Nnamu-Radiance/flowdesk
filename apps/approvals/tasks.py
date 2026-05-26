from celery import shared_task


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def notify_approval_task(self, workflow_id: int):
    return {"workflow_id": workflow_id, "status": "queued"}
