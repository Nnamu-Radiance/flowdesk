import json

from channels.generic.websocket import AsyncWebsocketConsumer

from shared.auth.jwt_validator import validate_jwt


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        token = None
        query = self.scope.get("query_string", b"").decode("utf-8")
        for part in query.split("&"):
            if part.startswith("token="):
                token = part.split("=", 1)[1]
                break

        if not token:
            await self.close(code=4401)
            return

        try:
            payload = validate_jwt(token)
        except Exception:
            await self.close(code=4401)
            return

        self.user_id = payload.get("user_id") or payload.get("id")
        self.group_name = f"user_{self.user_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def event_message(self, event):
        await self.send(text_data=json.dumps({"type": event.get("type_key"), "payload": event.get("payload", {})}))
