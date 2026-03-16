class RepoNotFoundError(Exception):
    def __init__(self, owner: str, repo: str):
        super().__init__(f"Repository {owner}/{repo} not found")
