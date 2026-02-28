class RepoNotFound(Exception):
    def __init__(self, repo_id: int) -> None:
        super().__init__(f"Repo {repo_id} not found")
        self.repo_id = repo_id


class ModuleNotFound(Exception):
    def __init__(self, module_id: int) -> None:
        super().__init__(f"Module {module_id} not found")
        self.module_id = module_id


class FileNotFound(Exception):
    def __init__(self, file_id: int) -> None:
        super().__init__(f"File {file_id} not found")
        self.file_id = file_id
