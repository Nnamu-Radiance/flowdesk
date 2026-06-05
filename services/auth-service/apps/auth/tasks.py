from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(queue="auth")
def send_magic_link_email(email: str, link: str, ttl_minutes: int):
    send_mail(
        "Your FlowDesk sign-in link",
        f"Use this link to sign in to FlowDesk:\n\n{link}\n\nThis link expires in {ttl_minutes} minutes.",
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )
    return {"email": email}
