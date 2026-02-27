class RepoNotFound(Exception):
    def __init__(self, repo_id: int) -> None:
        super().__init__(f"Repo {repo_id} not found")
        self.repo_id = repo_id
