from urllib.parse import parse_qs, urlparse


def extract_next_page_from_link(link_header: str):
    if not link_header:
        return None

    for part in link_header.split(","):
        section = part.strip()

        if 'rel="next"' not in section:
            continue

        url = section.split(";", 1)[0].strip().strip("<>")
        query = parse_qs(urlparse(url).query)

        if "page" in query:
            return int(query["page"][0])

    return None
