"""마크다운 문서 읽기."""
import yaml


def frontmatter(text):
    """맨 앞 `---` 블록의 YAML. 없으면 None."""
    if not text.startswith("---\n"):
        return None
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def section(text, heading):
    """`## heading` 아래부터 다음 `## ` 전까지."""
    start = text.index(f"\n## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start: end if end != -1 else len(text)]


def table_column(block, column=0):
    """Markdown 표의 본문 행에서 한 열의 값 (머리·구분선 제외)."""
    rows = [l for l in block.splitlines() if l.startswith("|")]
    return [[c.strip() for c in r.strip("|").split("|")][column] for r in rows[2:]]
