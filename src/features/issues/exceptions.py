class IssueNotFoundError(Exception):
    def __init__(self, issue_number: int):
        super().__init__(f"Issue {issue_number} not found")
