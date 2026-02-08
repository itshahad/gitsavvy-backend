import requests
from pathlib import Path
from zipfile import ZipFile, BadZipFile, LargeZipFile
from tree_sitter_language_pack import get_parser
from src.features.indexer.constants import *
from src.features.indexer.config import *
from src.features.indexer.utils import *
from src.features.indexer.schemas import *
from src.features.indexer.models import *
from src.features.indexer.exceptions import *
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.exceptions import ExternalServiceError, StorageError
from sqlalchemy.exc import IntegrityError
from src.config import (
    MAX_LINES_NUM,
    MAX_FUNC_SPLITTING_DEPTH,
    MIN_TAIL_LINES,
    OVERLAPPING_LINES_NUM,
)
from pgvector.sqlalchemy import Vector  # type: ignore


# ==================================================================================================
# Github:
def get_repo_metadata(
    http: requests.Session, owner: str, repo_name: str, session: Session
):
    try:
        r = http.get(f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}", headers=headers())
        r.raise_for_status()
        repo_metadata = RepoCreate.model_validate(r.json())
        repo_data = Repository(
            **repo_metadata.model_dump(
                exclude={"topics", "url", "avatar_url", "language"}
            ),
            url=str(repo_metadata.url),
            avatar_url=(
                str(repo_metadata.avatar_url) if repo_metadata.avatar_url else None
            ),
        )
        session.add(repo_data)
        session.flush()  # to get an id
        session.add_all(
            [
                RepositoryTopic(repository_id=repo_data.id, topic=t)
                for t in repo_metadata.topics
            ]
        )
        # session.commit()
        session.refresh(repo_data)
        return RepoRead.model_validate(repo_data)
    except IntegrityError as e:
        session.rollback()
        stmt = select(Repository).where(
            Repository.owner == owner, Repository.name == repo_name
        )
        repo_from_db = get_item_from_db(session, stmt)
        if repo_from_db is None:
            raise
        return RepoRead.model_validate(repo_from_db)
    except Exception as e:
        raise_request_exception(e=e, owner=owner, repo_name=repo_name)


def download_repo(http: requests.Session, owner: str, repo_name: str):
    try:
        commits = http.get(
            f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/commits", headers=headers()
        )
        commits.raise_for_status()
        latest_commit = commits.json()[0]["sha"]

        file_path = get_repo_path(repo_name=repo_name)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        r = http.get(
            f"{API_URL}{REPOS_PATH}/{owner}/{repo_name}/zipball/{latest_commit}",
            headers=headers(),
        )
        r.raise_for_status()
        with open(file_path, mode="wb") as file:
            file.write(r.content)

        return str(file_path), latest_commit
    except (PermissionError, FileNotFoundError, OSError) as e:
        msg = str(e) or "Storage write failed"
        raise StorageError(message=msg) from e
    except Exception as e:
        raise_request_exception(e=e, owner=owner, repo_name=repo_name)


# ==================================================================================================
# file selection:
def select_repo_files(
    session: Session,
    repo_id: int,
    zip_file_path: str,
    repo_name: str,
    commit_sha: str,
    max_size: int = 200_000,
):  # 200KB per file
    try:
        selected_files: list[FileRead] = []
        extract_dir = Path(f"{REPOS_PATH}/{repo_name}")

        with ZipFile(zip_file_path, "r") as zip:
            for info in zip.infolist():
                if info.is_dir() or info.file_size > max_size:
                    continue

                if (
                    not is_skipped(info.filename)
                    and not is_binary(zip, info)
                    and is_selected(info.filename)
                ):
                    zip.extract(info.filename, extract_dir)
                    file = store_file_to_db(session, repo_id, commit_sha, zip, info)
                    selected_files.append(file)
            session.commit()
        return selected_files

    except (BadZipFile, LargeZipFile) as e:
        raise ExternalServiceError(service="ZIP", message="invalid zip archive") from e

    except (PermissionError, FileNotFoundError, OSError) as e:
        msg = str(e) or "Storage read failed"
        raise StorageError(message=msg) from e


def store_file_to_db(
    session: Session, repo_id: int, commit_sha: str, zip_file: ZipFile, info: ZipInfo
):
    content_hash = hash_file_content(zip_file, info)
    data: dict[str, str | int] = {
        "repository_id": repo_id,
        "commit_sha": commit_sha,
        "file_path": info.filename,
        "content_hash": content_hash,
    }
    try:
        file_data = FileCreate.model_validate(data)
        file_db = File(**file_data.model_dump())
        session.add(file_db)
        session.flush()
        return FileRead.model_validate(file_db)
    except IntegrityError:
        session.rollback()
        stmt = select(File).where(
            File.repository_id == data["repository_id"],
            File.commit_sha == data["commit_sha"],
            File.file_path == data["file_path"],
        )
        file_from_db = get_item_from_db(session, stmt)
        if file_from_db is None:
            raise
        return FileRead.model_validate(file_from_db)


# ==================================================================================================
# files chunking:
def chunk_text_files(
    session: Session,
    repo_id: int,
    file: FileRead,
    repo_name: str,
    chunk_size: int = MAX_LINES_NUM,
    overlapping: int = OVERLAPPING_LINES_NUM,
):
    try:
        if overlapping >= chunk_size:
            raise ValueError("overlapping value must be less than chunk_size")

        chunks: list[ChunkRead] = []
        file_path = get_file_complete_path(file.file_path, repo_name)

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        step = chunk_size - overlapping

        raw_chunks: list[tuple[int, int, str]] = []

        for i in range(0, len(lines), step):
            start = i
            end = min(i + chunk_size, len(lines))
            chunk = lines[i:end]
            text = "\n".join(chunk).strip()
            if text:
                raw_chunks.append((start, end, text))

        if len(raw_chunks) >= 2:
            tail_start, tail_end, tail_text = raw_chunks[-1]
            tail_lines = tail_end - tail_start
            if tail_lines <= MIN_TAIL_LINES:
                prev_start, _, prev_text = raw_chunks[-2]
                new_text = prev_text + "\n" + tail_text
                raw_chunks[-2] = (prev_start, tail_end, new_text.strip())
                raw_chunks.pop()

        for start_line, end_line, text in raw_chunks:
            db_chunk = store_chunk_in_db(
                session,
                repo_id=repo_id,
                file_id=file.id,
                file_path=file.file_path,
                type=ChunkType.TEXT.value,
                start_line=start_line,
                end_line=end_line,
                content=text,
                content_hash=hash_text(text),
            )
            chunks.append(ChunkRead.model_validate(db_chunk))
        return chunks
    except (PermissionError, FileNotFoundError, OSError) as e:
        msg = str(e) or "Storage read failed"
        raise StorageError(message=msg) from e


# --------------------------------------------------------------------------------------------------
# code files chunking:
def build_file_summary(
    src: bytes, root: Node, repo_id: int, file: FileRead, session: Session, lang: str
):
    parts: list[str] = []

    classes_and_methods: list[str] = []
    for child in root.named_children:
        if is_class(child, lang=lang) or is_function(child, lang=lang):
            classes_and_methods.append(node_signature(src, child))
            continue

        wrapped_node = unwrap_node(child, lang=lang)
        if wrapped_node:
            classes_and_methods.append(node_signature(src, wrapped_node))
            continue

        text = node_text(src, child)
        if not text:
            continue
        parts.append(text)

    if classes_and_methods:
        parts.append(
            "\nClasses/Methods in file:\n"
            + "\n".join(f"{item}" for item in classes_and_methods).strip()
        )

    text = "\n".join(parts).strip()

    stored_chunk = store_chunk_in_db(
        session,
        repo_id=repo_id,
        file_id=file.id,
        file_path=file.file_path,
        type=ChunkType.FILE_SUMMARY.value,
        content=text,
        content_hash=hash_text(text),
    )
    print(f"stored_chunk -> {stored_chunk}")
    return stored_chunk


def build_class_summary(src: bytes, node: Node, repo_id: int, lang: str | None):
    parts: list[str] = []

    body = find_body(node)

    header = (
        slice_text(src, node.start_byte, body.start_byte)
        if body
        else node_text(src, node)
    )
    parts.append(header.strip())

    simple_contents: list[str] = []
    classes_and_methods: list[str] = []

    if body:
        for child in body.named_children:
            if child.type in SKIP_NODE_TYPES:
                continue

            if is_function(child, lang=lang) or is_class(child, lang=lang):
                classes_and_methods.append(node_signature(src, child))
                continue

            wrapped_function = unwrap_node(child, lang=lang)
            if wrapped_function:
                classes_and_methods.append(node_signature(src, wrapped_function))
                continue

            # if this node is just a wrapper and has children, don't treat it as a class member itself let recursion handle its children
            if not child.is_named and child.children:
                continue

            content = node_text(src, child).strip()
            simple_contents.append(content)
    if simple_contents:
        parts.append(
            "\nMembers/Comments:\n" + "\n".join(f"{m}" for m in simple_contents)
        )
    if classes_and_methods:
        parts.append("\nMethods:\n" + "\n".join(f"{m}" for m in classes_and_methods))
    return "\n".join(parts).strip()


def visit_node(
    node: Node,
    repo_id: int,
    src: bytes,
    chunks_list: list[ChunkRead],
    file: FileRead,
    session: Session,
    lang: str | None,
    chunk_parent_id: int | None = None,
):
    is_fn = is_function(node, lang=lang)
    is_cls = is_class(node, lang=lang)

    if is_fn:
        text = node_text(src, node)
        db_chunk = store_chunk_in_db(
            session,
            repo_id=repo_id,
            file_id=file.id,
            file_path=file.file_path,
            type=ChunkType.FUNCTION.value,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            content=text,
            content_hash=hash_text(text),
            chunk_parent_id=chunk_parent_id,
        )
        chunks_list.append(ChunkRead.model_validate(db_chunk))
        # for child in node.children:
        #     visit_node(child, src, chunks_list, file, session, lang, chunk_parent_id)
        return
    elif is_cls:
        text = build_class_summary(src, node, repo_id, lang)
        db_chunk = store_chunk_in_db(
            session,
            repo_id=repo_id,
            file_id=file.id,
            file_path=file.file_path,
            type=ChunkType.CLASS_SUMMARY.value,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            content=text,
            content_hash=hash_text(text),
            chunk_parent_id=chunk_parent_id,
        )
        chunks_list.append(ChunkRead.model_validate(db_chunk))
        for child in node.children:
            visit_node(
                child, repo_id, src, chunks_list, file, session, lang, db_chunk.id
            )
        return

    for child in node.children:
        visit_node(
            child, repo_id, src, chunks_list, file, session, lang, chunk_parent_id
        )


# --------------------------------------------------------------------------------------------------
# long function block chunking:
# what im trying to do:
# I check the length of the function, if long then go into children, chunk them, check the children length, if long chunk them too
# I'm trying to keep order of statements in account
def collect_blocks(node: Node, max_lines: int = MAX_LINES_NUM):
    blocks: list[Node] = []

    body = find_body(node)
    if not body:
        return blocks

    for child in body.named_children:
        if is_block(child) and (node_line_count(child) > max_lines):
            blocks.append(child)
    return blocks


def build_parent_with_placeholders(src: bytes, node: Node, extracted_nodes: list[Node]):
    body = find_body(node)
    if not body:
        return node_text(src, node)

    blocks = sorted(extracted_nodes, key=lambda n: n.start_byte)

    out: list[str] = []

    cursor = body.start_byte
    if src[cursor : cursor + 1] == b"{":
        cursor += 1

    for block in blocks:
        out.append(slice_text(src=src, a=cursor, b=block.start_byte))
        out.append(block_placeholder(src=src, node=block))
        cursor = block.end_byte

    out.append(slice_text(src=src, a=cursor, b=body.end_byte))

    function_signature = node_signature(src, node)
    return function_signature + "\n" + "".join(out)


def func_children_chunks(
    session: Session,
    repo_id: int,
    src: bytes,
    child_node: Node,
    parent_id: int,
    file: FileRead,
    depth: int,
    max_depth: int,
    max_lines: int,
):
    blocks_data: list[Chunk] = []

    if depth + 1 <= max_depth:
        inner_blocks = collect_blocks(node=child_node, max_lines=max_lines)
        function_placeholder = build_parent_with_placeholders(
            src=src, node=child_node, extracted_nodes=inner_blocks
        )
        function_placeholder = normalize_newlines(function_placeholder)

        db_chunk = store_chunk_in_db(
            session,
            repo_id=repo_id,
            file_id=file.id,
            file_path=file.file_path,
            type=ChunkType.FUNCTION_INNER_BLOCK.value,
            start_line=child_node.start_point[0] + 1,
            end_line=child_node.end_point[0] + 1,
            content=function_placeholder,
            content_hash=hash_text(function_placeholder),
            chunk_parent_id=parent_id,
        )

        blocks_data.append(db_chunk)
        parent_id = db_chunk.id

        for child in inner_blocks:
            blocks_data.extend(
                func_children_chunks(
                    session=session,
                    repo_id=repo_id,
                    src=src,
                    child_node=child,
                    file=file,
                    parent_id=parent_id,
                    depth=depth + 1,
                    max_depth=max_depth,
                    max_lines=max_lines,
                )
            )
    else:
        text = node_text(src=src, node=child_node)
        text = normalize_newlines(text)

        db_chunk = store_chunk_in_db(
            session,
            file_id=file.id,
            repo_id=repo_id,
            file_path=file.file_path,
            type=ChunkType.FUNCTION_INNER_BLOCK.value,
            start_line=child_node.start_point[0] + 1,
            end_line=child_node.end_point[0] + 1,
            content=text,
            content_hash=hash_text(text),
            chunk_parent_id=parent_id,
        )
        blocks_data.append(db_chunk)

    return blocks_data


def split_large_func_in_chunks(
    session: Session,
    repo_id: int,
    src: bytes,
    node: Node,
    file: FileRead,
    depth: int = 0,
    max_depth: int = MAX_FUNC_SPLITTING_DEPTH,
    max_lines: int = MAX_LINES_NUM,
    chunk_parent_id: int | None = None,
):
    blocks_data: list[Chunk] = []
    body = find_body(node)
    if not body:
        return node_text(src, node)

    direct_blocks = collect_blocks(node=node, max_lines=max_lines)

    function_placeholder = build_parent_with_placeholders(
        src=src, node=node, extracted_nodes=direct_blocks
    )
    function_placeholder = normalize_newlines(function_placeholder)

    db_chunk = store_chunk_in_db(
        session,
        repo_id=repo_id,
        file_id=file.id,
        file_path=file.file_path,
        type=ChunkType.FUNCTION.value,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        content=function_placeholder,
        content_hash=hash_text(function_placeholder),
        chunk_parent_id=chunk_parent_id,
    )

    blocks_data.append(db_chunk)
    parent_id = db_chunk.id

    for block in direct_blocks:
        blocks_data.extend(
            func_children_chunks(
                session=session,
                repo_id=repo_id,
                src=src,
                child_node=block,
                file=file,
                parent_id=parent_id,
                depth=depth + 1,
                max_depth=max_depth,
                max_lines=max_lines,
            )
        )

    return blocks_data


# --------------------------------------------------------------------------------------------------


def chunk_code_files(
    file: FileRead, repo_id: int, repo_name: str, session: Session
) -> list[ChunkRead]:
    chunks: list[ChunkRead] = []
    file_path = get_file_complete_path(file.file_path, repo_name)
    file_ext = ext(file_path)
    lang = lang_from_ext(file_ext)

    if lang is None:
        return []

    file_bytes = Path(file_path).read_bytes()
    parser = get_parser(language_name=lang)

    tree = parser.parse(file_bytes)
    root = tree.root_node

    db_file_chunk = build_file_summary(file_bytes, root, repo_id, file, session, lang)
    chunks.append(ChunkRead.model_validate(db_file_chunk))
    visit_node(
        root,
        repo_id,
        file_bytes,
        chunks,
        file,
        session,
        lang,
        chunk_parent_id=db_file_chunk.id,
    )

    return chunks


# --------------------------------------------------------------------------------------------------
def store_chunk_in_db(
    session: Session,
    repo_id: int,
    file_id: int,
    file_path: str,
    type: str,
    content: str,
    content_hash: str,
    start_line: int | None = None,
    end_line: int | None = None,
    chunk_parent_id: int | None = None,
):
    data: dict[str, int | str] = {
        "repo_id": repo_id,
        "file_id": file_id,
        "file_path": file_path,
        "type": type,
        "content": content,
        "content_hash": content_hash,
    }

    if start_line is not None and end_line is not None:
        data["start_line"] = start_line
        data["end_line"] = end_line

    if chunk_parent_id is not None:
        data["chunk_parent_id"] = chunk_parent_id

    chunk_data = ChunkCreate.model_validate(data)
    chunk_db = Chunk(**chunk_data.model_dump())
    session.add(chunk_db)
    session.flush()
    return chunk_db


def chunk_repo_files(
    session: Session, zip_file_path: str, repo_id: int, commit_sha: str, repo_name: str
):
    chunks: list[ChunkRead] = []
    selected_files = select_repo_files(
        session, repo_id, zip_file_path, repo_name, commit_sha
    )

    for file in selected_files:
        e = ext(file.file_path)

        if e in AST_LANG_EXT:
            print(f"AST_LANG_EXT -> {file.file_path}")
            chunks.extend(chunk_code_files(file, repo_id, repo_name, session))
        elif e in TEXT_LANG_EXT:
            print(f"TEXT_LANG_EXT -> {file.file_path}")
            chunks.extend(chunk_text_files(session, repo_id, file, repo_name))
    # session.commit()
    return chunks


# ==================================================================================================
# embedding:
def store_embedding(session: Session, chunk_id: int, embedding_vector: Vector):
    embedding_data = ChunkEmbeddingCreate.model_validate(
        {"chunk_id": chunk_id, "embedding_vector": embedding_vector}
    )
    embedding_db = ChunkEmbedding(**embedding_data.model_dump())
    session.add(embedding_db)
    session.flush()
    return embedding_db


# def embed_chunks(embedder, session: Session, chunks: list[ChunkRead]):
#     text_chunks = [dict_to_text(chunk.model_dump()) for chunk in chunks]
#     emb = embedder.encode(
#         text_chunks, batch_size=8, show_progress_bar=True, normalize_embeddings=True
#     )

#     embeddings = []
#     for chunk, vector in zip(chunks, emb):
#         data = {"chunk_id": chunk.id, "embedding_vector": vector}
#         embedding = store_embedding(session, chunk_id: int, )
#         embeddings.append(ChunkEmbeddingRead.model_validate(embedding))
#     return embeddings
