import uuid


class ServiceUser:
    def __init__(self, user_id: int, role: str = "submitter"):
        self.id = user_id
        self.pk = user_id
        self.role = role
        self.username = f"user-{user_id}"

    @property
    def is_authenticated(self) -> bool:
        return True
