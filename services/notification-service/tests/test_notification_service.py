import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from rest_framework import exceptions
from rest_framework.test import APIClient, APIRequestFactory

from apps.notifications.authentication import JWTLocalAuthentication, ServiceUser
from apps.notifications.consumers import NotificationConsumer
from apps.notifications.events import (
    handle_approval_decision,
    handle_approval_escalated,
    handle_approval_requested,
    handle_sla_warning,
)
from apps.notifications.models import Notification
from apps.notifications.routing import websocket_urlpatterns
from apps.notifications.tasks import handle_event


@pytest.mark.django_db
def test_health_endpoint():
    client = APIClient()
    response = client.get("/health/")
    assert response.status_code in {200, 503}


@pytest.mark.django_db
def test_handle_event_task_creates_notification_and_dispatches():
    event = {"event_type": "workflow.created", "payload": {"submitter_id": 42, "workflow_id": 1}}
    layer = SimpleNamespace(group_send=AsyncMock())

    with patch("apps.notifications.tasks.get_channel_layer", return_value=layer) as mock_layer, patch(
        "apps.notifications.tasks.send_email_task.delay"
    ) as mock_email:
        result = handle_event.run(event)

    saved = Notification.objects.get(recipient_id=42)
    assert result == {"handled": "workflow.created"}
    assert saved.type == "workflow.created"
    assert saved.title == "Workflow Created"
    assert saved.read is False
    mock_layer.assert_called_once()
    layer.group_send.assert_awaited_once_with(
        "user_42",
        {"type": "event_message", "type_key": "workflow.created", "payload": {"submitter_id": 42, "workflow_id": 1}},
    )
    mock_email.assert_called_once_with(42, template="workflow.created", context={"submitter_id": 42, "workflow_id": 1})


@pytest.mark.django_db
def test_handle_event_task_without_recipient_is_noop():
    event = {"event_type": "workflow.created", "payload": {"workflow_id": 99}}
    with patch("apps.notifications.tasks.get_channel_layer") as mock_layer, patch(
        "apps.notifications.tasks.send_email_task.delay"
    ) as mock_email:
        result = handle_event.run(event)

    assert result == {"handled": "workflow.created"}
    assert Notification.objects.count() == 0
    mock_layer.assert_not_called()
    mock_email.assert_not_called()


def test_event_handlers_delegate_to_task_delay():
    event = {"event_type": "x", "payload": {"a": 1}}
    with patch("apps.notifications.events.handle_event.delay") as mock_delay:
        handle_approval_requested(event)
        handle_approval_decision(event)
        handle_sla_warning(event)
        handle_approval_escalated(event)

    assert mock_delay.call_count == 4


def test_jwt_authentication_missing_header_returns_none():
    auth = JWTLocalAuthentication()
    request = APIRequestFactory().get("/")
    assert auth.authenticate(request) is None


def test_jwt_authentication_valid_token():
    auth = JWTLocalAuthentication()
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer good-token")

    with patch("apps.notifications.authentication.validate_jwt", return_value={"user_id": 7, "role": "approver"}) as mock_validate:
        user, payload = auth.authenticate(request)

    mock_validate.assert_called_once_with("good-token")
    assert isinstance(user, ServiceUser)
    assert user.id == 7
    assert user.role == "approver"
    assert payload["user_id"] == 7


def test_jwt_authentication_invalid_token_raises():
    auth = JWTLocalAuthentication()
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer bad-token")
    with patch("apps.notifications.authentication.validate_jwt", side_effect=Exception("bad")):
        with pytest.raises(exceptions.AuthenticationFailed):
            auth.authenticate(request)


def test_service_user_is_authenticated_property():
    assert ServiceUser(user_id=5).is_authenticated is True


def test_websocket_routing_contains_notifications_endpoint():
    assert len(websocket_urlpatterns) == 1
    assert "ws/notifications/" in str(websocket_urlpatterns[0].pattern)


def test_notification_consumer_connect_without_token_closes():
    consumer = NotificationConsumer()
    consumer.scope = {"query_string": b""}
    consumer.close = AsyncMock()
    consumer.accept = AsyncMock()

    asyncio.run(consumer.connect())

    consumer.close.assert_awaited_once_with(code=4401)
    consumer.accept.assert_not_awaited()


def test_notification_consumer_connect_with_invalid_token_closes():
    consumer = NotificationConsumer()
    consumer.scope = {"query_string": b"token=bad"}
    consumer.close = AsyncMock()
    consumer.accept = AsyncMock()

    with patch("apps.notifications.consumers.validate_jwt", side_effect=Exception("invalid")):
        asyncio.run(consumer.connect())

    consumer.close.assert_awaited_once_with(code=4401)
    consumer.accept.assert_not_awaited()


def test_notification_consumer_connect_success_disconnect_and_event_message():
    consumer = NotificationConsumer()
    consumer.scope = {"query_string": b"token=good"}
    consumer.channel_name = "chan-1"
    consumer.channel_layer = SimpleNamespace(group_add=AsyncMock(), group_discard=AsyncMock())
    consumer.accept = AsyncMock()
    consumer.send = AsyncMock()
    consumer.close = AsyncMock()

    with patch("apps.notifications.consumers.validate_jwt", return_value={"user_id": 12}):
        asyncio.run(consumer.connect())

    assert consumer.user_id == 12
    assert consumer.group_name == "user_12"
    consumer.channel_layer.group_add.assert_awaited_once_with("user_12", "chan-1")
    consumer.accept.assert_awaited_once()

    asyncio.run(consumer.event_message({"type_key": "approval.requested", "payload": {"workflow_id": 77}}))
    consumer.send.assert_awaited_once_with(
        text_data=json.dumps({"type": "approval.requested", "payload": {"workflow_id": 77}})
    )

    asyncio.run(consumer.disconnect(1000))
    consumer.channel_layer.group_discard.assert_awaited_once_with("user_12", "chan-1")
