import re


def parse_yaml_front_matter(text: str):
    text = text.strip()

    # case 1: Proper YAML front matter exists
    if text.startswith("---"):
        parts = text.split("---", 2)

        if len(parts) >= 3:
            yaml_block = parts[1].strip()
            markdown_body = parts[2].strip()

            short_summary = ""
            for line in yaml_block.splitlines():
                if line.startswith("short_summary:"):
                    short_summary = line.split(":", 1)[1].strip()

            return short_summary, markdown_body

    # try to extract summary from text
    summary_match = re.search(r"short_summary:\s*(.+)", text)
    if summary_match:
        short_summary = summary_match.group(1).strip()
    else:
        # fallback: first sentence or first line
        first_line = text.splitlines()[0].strip()
        short_summary = (
            first_line
            if first_line
            else "Not explicitly defined in the provided content."
        )

    markdown_body = text

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
