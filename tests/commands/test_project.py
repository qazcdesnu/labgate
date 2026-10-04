"""lg draft·commit·verify·upgrade가 공통으로 하는 프로젝트 확인 (설계 문서 §18.3): 위치, spec_version, hook 계약."""
import subprocess

import pytest
import yaml

from support.cli import lg


@pytest.fixture
def proj(project, monkeypatch):
    """프로젝트 폴더에서 lg를 실행한다."""
    monkeypatch.chdir(project.root)
    return project


def test_outside_git_repo(tmp_path, git_sandbox, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "Git 저장소가 아닙니다" in result.output


def test_not_a_labgate_project(tmp_path, git_sandbox, monkeypatch):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "labgate 프로젝트가 아닙니다" in result.output


def test_spec_version_1_project_is_refused(proj):
    path = proj / ".lg/project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["generated"]["spec_version"] = 1
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "spec_version 1" in result.output


def test_hook_without_contract_names_is_refused(proj):
    hook = proj / ".lg/hooks/commit-msg"
    hook.write_text(hook.read_text(encoding="utf-8").replace("def check(", "def _check("), encoding="utf-8")
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "형식이 아닙니다" in result.output and "check" in result.output


def test_types_come_from_project_hook(proj, keys):
    """§18.3: 규칙의 원본은 프로젝트의 hook이다. hook을 바꾸면 lg의 판단도 따라 바뀐다."""
    hook = proj / ".lg/hooks/commit-msg"
    text = hook.read_text(encoding="utf-8").replace('"exp", "run", "result"', '"run", "result"')
    hook.write_text(text.replace('AGENT_TYPES = {"task"', 'AGENT_TYPES = {"exp", "task"'), encoding="utf-8")
    proj.write("a.py")
    result = lg("draft", "--type", "exp", "--summary", "x", "a.py")
    assert result.exit_code == 2 and "사람 커밋에 쓸 수 없는 타입입니다: exp" in result.output
