import requests
from requests import HTTPError
from pathlib import Path
from zipfile import ZipFile
from tree_sitter_language_pack import get_parser
from .constants import *
from .config import *
from .utils import *
from .schemas import *
from .models import *
from .exceptions import *
from sqlalchemy.orm import Session
from sqlalchemy import select


class IndexerService:
    #==================================================================================================
    #Github:
    def get_repo_metadata(self,owner:str, repo_name:str, session: Session) -> str:
        try:
            r = requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}", headers=headers())
            r.raise_for_status()
            repo_metadata = RepoCreate.model_validate(r.json())
            repo_data = Repository(**repo_metadata.model_dump(exclude={"topics", "url", "avatar_url", "language"}), url=str(repo_metadata.url), avatar_url= str(repo_metadata.avatar_url))
            session.add(repo_data)
            session.flush() #to get an id
            session.add_all([
                RepositoryTopic(repository_id=repo_data.id, topic=t)
                for t in repo_metadata.topics
            ])
            session.commit()
            session.refresh(repo_data)
            return RepoRead.model_validate(repo_data)
        except HTTPError as e:
            if r.status_code == 404:
                raise RepoNotFoundError(owner, repo_name)

    def download_repo(self, owner, repo_name) -> dict:
        commits =  requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/commits", headers=headers())
        commits.raise_for_status()
        latest_commit = commits.json()[0]["sha"]

        file_path = Path(f"{REPOS_PATH}/{repo_name}.zip")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/zipball/{latest_commit}", headers=headers())
        r.raise_for_status()
        with open(file_path, mode="wb") as file:
            file.write(r.content)

        return{"path": str(file_path), "commit_sha": latest_commit}

    #==================================================================================================
    #file selection:
    def store_file_to_db(self, session: Session, repo_id: int, commit_sha: str, zip_file: ZipFile, info :ZipInfo):
        content_hash = hash_file_content(zip_file, info) 
        data = {
            "repository_id" : repo_id,
            "commit_sha": commit_sha,
            "file_path": info.filename,
            "content_hash": content_hash
        }
        file_data = FileCreate.model_validate(data)
        file_db = File(**file_data.model_dump())
        session.add(file_db)
        session.flush()
        return file_db

    def select_repo_files(self, session: Session, repo_id: int, zip_file_path: str, repo_name, commit_sha: str, max_size:int=200_000): # 200KB per file
        selected_files = []
        extract_dir = Path(f"{REPOS_PATH}/{repo_name}")

        with ZipFile(zip_file_path, "r") as zip:
            for info in zip.infolist():
                if info.is_dir() or info.file_size > max_size:
                    continue

                if not is_skipped(info.filename) and not is_binary(zip, info.filename) and is_selected(info.filename):
                    zip.extract(info.filename, extract_dir)
                    file = self.store_file_to_db(session, repo_id, commit_sha, zip, info)
                    selected_files.append(FileRead.model_validate(file))
            session.commit()
        return selected_files
    #==================================================================================================
    #files chunking:
    def chunk_text_files(self,file_path: str, chunk_size= 100, overlapping=20):
        if (overlapping >= chunk_size):
            raise ValueError("overlapping value must be less than chunk_size")
        
        chunks = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        
        step = chunk_size - overlapping

        for i in range(0, len(lines), step):
            chunk = lines[i: i + chunk_size]
            chunks.append({
                "file_path": file_path,
                "start_line": i + 1,
                "end_line": min(i + chunk_size, len(lines)),
                "code_text": "\n".join(chunk).strip(),
            })
        
        return chunks
    #--------------------------------------------------------------------------------------------------
    #code files chunking:
    def build_class_summary(self,src: bytes, node):
        parts = []

        body = find_body(node)

        header = slice_text(src, node.start_byte, body.start_byte) if body else node_text(src, node)
        parts.append(header.strip())

        simple_contents = []
        methods = []

        if body:
            for child in body.children:
                if is_function(child):
                    methods.append(method_signature(src, child))
                    continue

                wrapped_function = unwrap_function(child)
                if wrapped_function:
                    methods.append(method_signature(src, wrapped_function))
                    continue

                # if this node is just a wrapper and has children, don’t treat it as a class member itself let recursion handle its children
                if not child.is_named and child.children:
                    continue
                
                content = node_text(src, child).strip()
                simple_contents.append(content)
        if simple_contents:
            parts.append("\nMembers/Comments:\n+" + "\n".join(f"- {m}" for m in simple_contents))
        if methods:
            parts.append("\nMethods:\n+" + "\n".join(f"- {m}" for m in methods))
        return "\n".join(parts).strip()

    def build_file_summary(self, src: bytes, root, file_path: str):
        parts = []

        for child in root.children:
            if is_class(child) or is_function(child):
                break

            text = node_text(src, child)
            if not text:
                continue
            parts.append(text)
        return {
            "type": "file_summary",
            "path": file_path,
            "text": "\n".join(parts).strip(),
        } 


    def visit_node(self, node, src: bytes, chunks_list: list, file_path: str):
        is_fn = is_function(node)
        is_cls = is_class(node)

        if is_fn:
            chunks_list.append(
                {
                    "type": "function",
                    "file_path": file_path,
                    "start_line": node.start_point[0]+1,
                    "end_line": node.end_point[0]+1,
                    "code_text": node_text(src, node),
                    "node_type": node.type
                }
            )
        elif is_cls:
            chunks_list.append(
                {
                    "type": "class_summary",
                    "file_path": file_path,
                    "start_line": node.start_point[0]+1,
                    "end_line": node.end_point[0]+1,
                    "code_text": self.build_class_summary(src, node),
                    "node_type": node.type
                }
            )
        for child in node.children:
            self.visit_node(child, src, chunks_list, file_path)

    def chunk_code_files(self, file_path: str):
        chunks = []
        file_bytes = Path(file_path).read_bytes()
        lang = "python"
        parser = get_parser(language_name=lang)

        tree = parser.parse(file_bytes)
        root = tree.root_node

        chunks.append(self.build_file_summary(file_bytes, root, file_path))
        self.visit_node(root, file_bytes, chunks, file_path)
            
        return chunks
    #--------------------------------------------------------------------------------------------------

    def chunk_repo_files(self, session, zip_file_path:str, repo_name:str):
        chunks = []
        current_file = None
        stmt = lambda x : select(File).where(File.file_path == x)
        selected_files = self.select_repo_files(zip_file_path, repo_name)[:10]

        for file_path in selected_files:
            current_file = session.execute(stmt(file_path)).scaler_one()
            print(current_file)
            e = ext(file_path)

            if e in AST_LANG_EXT:
                print(f"AST_LANG_EXT -> {file_path}")
                chunks.append(self.chunk_code_files(file_complete_path(file_path, repo_name)))
            elif e in TEXT_LANG_EXT:
                print(f"TEXT_LANG_EXT -> {file_path}")
                chunks.append(self.chunk_text_files(file_complete_path(file_path, repo_name)) )           
        return chunks