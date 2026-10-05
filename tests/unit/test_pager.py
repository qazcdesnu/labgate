"""긴 출력의 pager (`labgate.pager`): 색 코드는 해석하는 pager에만 (실사용: 옵션 없는 less에 ESC[1m이 그대로 보였다)."""
import os

import pytest

from labgate import answer, pager


@pytest.fixture
def captured(monkeypatch):
    seen = {}

    def fake(text):
        seen["text"], seen["LESS"] = text, os.environ.get("LESS")

    monkeypatch.setattr(pager.pydoc, "pager", fake)
    for key in ("PAGER", "MANPAGER", "LESS"):
        monkeypatch.delenv(key, raising=False)
    return seen


def test_default_less_gets_R(captured, monkeypatch):
    monkeypatch.setattr(pager.shutil, "which", lambda name: "/usr/bin/less")
    pager.page("\x1b[1mcolored\x1b[0m", "plain")
    assert captured == {"text": "\x1b[1mcolored\x1b[0m", "LESS": "-R"}
    assert "LESS" not in os.environ  # 되돌린다


def test_existing_less_flags_are_kept(captured, monkeypatch):
    monkeypatch.setenv("PAGER", "less")
    monkeypatch.setenv("LESS", "-FRX")
    pager.page("colored", "plain")
    assert captured["LESS"] == "-FRX"
    monkeypatch.setenv("LESS", "-F")
    pager.page("colored", "plain")
    assert captured["LESS"] == "-F -R" and os.environ["LESS"] == "-F"


def test_other_pager_gets_plain_text(captured, monkeypatch):
    monkeypatch.setenv("PAGER", "more")
    pager.page("\x1b[1mcolored\x1b[0m", "plain")
    assert captured["text"] == "plain"
    monkeypatch.delenv("PAGER")
    monkeypatch.setattr(pager.shutil, "which", lambda name: None)  # less가 없다
    pager.page("colored", "plain")
    assert captured["text"] == "plain"


def test_render_has_no_hyperlink_codes():
    text = answer._render("상세는 [결과](results/M0/r.md)\n\n**굵게**", color=True)
    assert "\x1b]8;" not in text and "\x1b[" in text   # 색은 있지만 하이퍼링크 코드는 없다
    assert "\x1b[" not in answer._render("**굵게**", color=False)
