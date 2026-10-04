"""`lg spec adopt`의 합치기 규칙 (설계 문서 §24.8)."""
import pytest

from labgate.errors import Fail
from labgate.render import base_context, render, stub_context
from labgate.spec import merge, sections
from labgate.stubs import STUBS


@pytest.fixture
def stub(config):
    catalog = next(s for s in STUBS if s.name == "catalog")
    return render("specs/doc-types/_stub.spec.md.j2", stub_context(base_context(config, "2026-10-01"), catalog))


def body(*numbers):
    return "".join(f"## {n}. 아무 제목\n\n내용 {n}\n\n" for n in numbers)


def test_replaces_only_drafted_sections(stub):
    out, replaced = merge(stub, "# 초안 제목은 버린다\n\n" + body(3, 4, 5, 6, 7))
    assert replaced == [3, 4, 5, 6, 7]
    head, secs = sections(out)
    assert [n for n, _, _ in secs] == [1, 2, 3, 4, 5, 6, 7]
    assert secs[2][1] == "## 3. Frontmatter" and secs[2][2].strip() == "내용 3"
    assert secs[0][2] == sections(stub)[1][0][2]  # §1은 그대로
    assert "status: complete" in head and "(stub)" not in head and "> 이 사양은" not in head
    assert out.endswith("내용 7\n") and "\n\n\n" not in out


def test_draft_frontmatter_is_ignored(stub):
    out, _ = merge(stub, "---\nid: catalog\nstatus: draft\n---\n" + body(3, 4, 5, 6, 7))
    assert "status: complete" in out and "status: draft" not in out


@pytest.mark.parametrize("draft, message", [
    (body(3), "§4, §5, §6, §7"),
    (body(3, 4, 5, 6, 7) + "## 메모\n\nx\n", "## 메모"),
    (body(3, 4, 5, 6, 7, 9), "§9"),
    ("# 제목만\n", "번호 붙은 절"),
])
def test_refusals(stub, draft, message):
    with pytest.raises(Fail) as e:
        merge(stub, draft)
    assert message in str(e.value)
