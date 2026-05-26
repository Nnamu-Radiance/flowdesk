from celery import shared_task


@shared_task(queue="default")
def generate_daily_reports():
    return {"status": "queued"}
