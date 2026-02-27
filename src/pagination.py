from fastapi import Query


def pagination_params(page: int = Query(1, ge=1), size: int = Query(10, ge=1, le=100)):
    return {"page": page, "size": size}


def cursor_pagination_params(
    limit: int = Query(20, ge=1, le=100),
    cursor: int | None = Query(None),
):
    result: dict[str, int | None] = {"limit": limit, "cursor": cursor}
    return result
