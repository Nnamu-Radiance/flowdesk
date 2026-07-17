class ServiceUser:
    def __init__(self, user_id: int, role: str = "submitter", approver_type: str = ""):
        self.id = user_id
        self.pk = user_id
        self.role = role
        self.approver_type = approver_type
        self.username = f"user-{user_id}"

    @property
    def is_authenticated(self) -> bool:
        return True
