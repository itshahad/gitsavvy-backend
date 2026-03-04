def parse_yaml_front_matter(text: str):
    print(text)
    if not text.strip().startswith("---"):
        raise ValueError("Missing YAML front matter")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Invalid YAML structure")

    yaml_block = parts[1].strip()
    markdown_body = parts[2].strip()

    short_summary = ""
    for line in yaml_block.splitlines():
        if line.startswith("short_summary:"):
            short_summary = line.split(":", 1)[1].strip()

    return short_summary, markdown_body


def split_huge_text(chunk_content: str, max_bytes: int = 6_000) -> list[str]:
    lines = chunk_content.splitlines(keepends=True)

    texts: list[str] = []
    text = ""
    text_bytes = 0

    for line in lines:
        line_bytes = len(line.encode("utf-8"))

        if text_bytes + line_bytes <= max_bytes:
            text += line
            text_bytes += line_bytes
            continue
        else:
            if text:
                texts.append(text)
            text = line
            text_bytes = line_bytes

    if text:
        texts.append(text)
    return texts
