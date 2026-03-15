class IssueNotFoundError(Exception):
    def __init__(self, issue_id: int):
        super().__init__(f"Issue {issue_id} not found")
