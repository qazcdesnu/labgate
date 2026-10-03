"""릴리즈된 spec_version의 해시표와 동결 (설계 문서 §22.2.2, §22.4.3).

해시표 `src/labgate/hashes/<n>.json`은 `lg upgrade`가 "그 버전 그대로인가"를 판별하는 기준이다.
"""
import subprocess
import sys

import pytest

from labgate import SPEC_VERSION, kinds
from labgate.upgrade import MIGRATIONS, load_hashes

from support.env import ROOT
from support.releases import TAGS, current_files, has_tag


@pytest.mark.parametrize("spec", sorted(TAGS))
def test_hash_tables_match_release_tags(spec):
    """§22.4.3: 저장된 해시표가 그 tag의 템플릿에서 다시 만든 것과 같다."""
    if not has_tag(TAGS[spec]):
        pytest.skip(f"tag {TAGS[spec]} 없음")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/hash-templates.py"), TAGS[spec], str(spec), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_current_templates_frozen_if_released():
    """§22.2.2 규칙 2: 현재 spec_version이 릴리즈됐으면(해시표가 있으면) 템플릿이 그와 같다."""
    table = load_hashes(SPEC_VERSION)
    if table is None:
        pytest.skip(f"spec_version {SPEC_VERSION}는 아직 릴리즈 전 (해시표 없음)")
    for claude in (True, False):
        var = kinds.variant(claude)
        for path, (content, _) in current_files(claude).items():
            if kinds.classify(path) in (kinds.MANAGED, kinds.EDITABLE):
                assert kinds.digest(path, content) == table["files"][path][var], path


def test_every_generated_file_is_classified_and_none_lost():
    """모든 생성 파일에 분류가 있고, 지난 버전의 관리 문서가 소리 없이 사라지지 않는다."""
    current = set()
    for claude in (True, False):
        for path in current_files(claude):
            kind = kinds.classify(path)
            assert kind in (kinds.MANAGED, kinds.EDITABLE, kinds.GITIGNORE, kinds.RESEARCH, kinds.RECORD, kinds.OTHER)
            if kind in (kinds.MANAGED, kinds.EDITABLE):
                current.add(path)
    for spec in MIGRATIONS:
        assert set(load_hashes(spec)["files"]) <= current, spec
