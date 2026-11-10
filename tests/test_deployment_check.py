import json

from scripts.deployment_check import inspect


def project(tmp_path):
    for relative in ("site/index.html", "scripts/build_workspace.py", "phd_agents/server.py", "requirements-intelligence.txt"):
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    return tmp_path


def test_starter_fork(tmp_path):
    results = inspect(project(tmp_path), "pages", {"PHD_ATLAS_REPOSITORY": "example/phd_tracker"})
    assert not any(item.status == "error" for item in results)
    assert next(item for item in results if item.code == "data-mode").status == "ok"


def test_missing_source_is_blocked(tmp_path):
    results = inspect(project(tmp_path), "pages", {"PHD_ATLAS_DATA_MODE": "source"})
    assert next(item for item in results if item.code == "data-mode").status == "error"


def test_source_schema_is_checked(tmp_path):
    root = project(tmp_path)
    source = root / "data/user_opportunities.json"
    source.parent.mkdir(exist_ok=True)
    source.write_text(json.dumps({"schema_version": 1, "records": [{"id": "test"}]}))
    results = inspect(root, "pages", {"PHD_ATLAS_DATA_MODE": "source"})
    assert next(item for item in results if item.code == "data-mode").status == "ok"


def test_local_secrets_outside_repo(tmp_path):
    root = project(tmp_path)
    env = {"PHDAI_PRIVATE_DIR": str(root / "state"), "PHDAI_MAX_CONCURRENT_INFERENCE": "9"}
    results = inspect(root, "local-full-stack", env)
    assert {item.code for item in results if item.status == "error"} == {"private-storage", "inference-limit"}


def test_cloud_mode_fails_closed(tmp_path):
    results = inspect(project(tmp_path), "cloud-full-stack", {})
    assert next(item for item in results if item.code == "cloud-backend").status == "error"


def test_actions_does_not_disclose_credential(tmp_path):
    secret = "do-not-echo-this-credential"
    results = inspect(project(tmp_path), "actions", {"PHD_ATLAS_ENABLE_HOSTED_AI": "true", "PHD_ATLAS_AI_BASE_URL": "https://model.example/v1", "PHD_ATLAS_AI_MODEL": "example", "PHD_ATLAS_AI_API_KEY": secret})
    assert secret not in json.dumps([item.detail for item in results])
    assert next(item for item in results if item.code == "hosted-key").status == "ok"


def test_compose_project_namespace_validation(tmp_path):
    root = project(tmp_path)
    valid = inspect(root, "local-full-stack", {"PHD_ATLAS_COMPOSE_PROJECT": "atlas-fork-2"})
    invalid = inspect(root, "local-full-stack", {"PHD_ATLAS_COMPOSE_PROJECT": "Unsafe/Shared"})
    assert next(item for item in valid if item.code == "compose-project").status == "ok"
    assert next(item for item in invalid if item.code == "compose-project").status == "error"


def test_local_rate_budget_preflight_matches_server_constraints(tmp_path):
    root = project(tmp_path)
    options = {
        "PHDAI_MAX_INFERENCE_PER_MINUTE": "0",
        "PHDAI_MAX_WRITES_PER_MINUTE": "invalid",
    }
    report = inspect(root, "local-full-stack", options)
    failed = {entry.code for entry in report if entry.status == "error"}
    assert "phdai-max-inference-per-minute" in failed
    assert "phdai-max-writes-per-minute" in failed
    valid = inspect(root, "local-full-stack", {
        "PHDAI_MAX_INFERENCE_PER_MINUTE": "25",
        "PHDAI_MAX_WRITES_PER_MINUTE": "100",
    })
    assert not any(item.code in failed and item.status == "error" for item in valid)


def test_native_platform_deployment_fails_closed_when_unsupported(tmp_path):
    root = project(tmp_path)
    linux = inspect(root, "local-full-stack", {}, platform_name="linux")
    macos = inspect(root, "local-full-stack", {}, platform_name="darwin")
    windows = inspect(root, "local-full-stack", {}, platform_name="win32")
    assert next(item for item in linux if item.code == "native-platform").status == "ok"
    assert next(item for item in macos if item.code == "native-platform").status == "warning"
    assert next(item for item in windows if item.code == "native-platform").status == "error"
    browser = inspect(root, "browser-local", {}, platform_name="win32")
    assert not any(item.code == "native-platform" for item in browser)
