"""릴리즈 tag의 labgate로 옛 spec_version 프로젝트를 실제로 만든다.

tag가 없는 환경(얕은 클론, 소스 배포판)에서는 그 테스트를 건너뛴다. 새 spec_version을 릴리즈하면
`TAGS`에 그 tag를 더한다 (tests/README.md "릴리즈할 때").
"""
import datetime
import subprocess
import sys
import tarfile

import pytest

from labgate.config import parse_config
from labgate.plan import build_plan

from support.configs import project_config, write_config
from support.env import ROOT
from support.project import Project

TAGS = {2: "v0.2.1", 3: "v0.3.0", 4: "v0.4.0", 5: "v0.5.0"}


def has_tag(tag):
    return subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=ROOT,
                          capture_output=True).returncode == 0


def extract_sources(tmp_path_factory):
    """{spec_version: tag의 src 폴더 또는 None}."""
    out = {}
    for spec, tag in TAGS.items():
        if not has_tag(tag):
            out[spec] = None
            continue
        dest = tmp_path_factory.mktemp(f"src{spec}")
        archive = dest / "src.tar"
        subprocess.run(["git", "archive", "-o", str(archive), tag, "src/labgate"], cwd=ROOT, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(dest, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        out[spec] = dest / "src"
    return out


def make_old(tmp_path, env, sources, spec, claude_code=True):
    """옛 labgate(그 spec_version을 처음 릴리즈한 tag)로 프로젝트를 만든다."""
    src = sources[spec]
    if src is None:
        pytest.skip(f"tag {TAGS[spec]} 없음")
    cfg = write_config(tmp_path / "cfg.yaml", project_config(claude_code))
    root = tmp_path / f"old{spec}"
    code = f"import sys; sys.path.insert(0, {str(src)!r}); from labgate.cli import app; app()"
    result = subprocess.run([sys.executable, "-c", code, "init", str(root), "--config", str(cfg)],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    p = Project(root, env)
    assert p.yaml()["generated"]["spec_version"] == spec
    return p


def current_files(claude_code=True):
    """현재 labgate가 기본 설정으로 만드는 파일 {경로: (내용, 권한)}."""
    plan = build_plan(parse_config(project_config(claude_code)), datetime.date.today().isoformat())
    return {str(f.path): (f.content, f.mode) for f in plan}
