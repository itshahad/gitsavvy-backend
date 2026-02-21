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
