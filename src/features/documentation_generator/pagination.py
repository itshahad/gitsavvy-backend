from fastapi import Query


def children_pagination_params(
    limit: int | None = Query(default=20, ge=1, le=100),
    module_cursor: int | None = None,
    file_cursor: int | None = None,
):
    return {
        "limit": limit,
        "module_cursor": module_cursor,
        "file_cursor": file_cursor,
    }
