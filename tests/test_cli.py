import os
import shutil
import uuid
from pathlib import Path

from click.testing import CliRunner

from messaging_sdk.cli import cli


def test_cli_init_creates_basic_scaffold():
    runner = CliRunner()
    base_dir = Path.cwd() / ".test-artifacts" / f"cli-{uuid.uuid4().hex}"
    base_dir.mkdir(parents=True, exist_ok=True)
    original_cwd = Path.cwd()

    try:
        os.chdir(base_dir)
        result = runner.invoke(cli, ["init", "--project-name", "demo-app"])

        assert result.exit_code == 0, result.output
        assert "Project scaffold created successfully." in result.output
        assert (base_dir / "demo-app" / "main.py").exists()
        assert (base_dir / "demo-app" / ".env.example").exists()
        assert (base_dir / "demo-app" / "app" / "__init__.py").exists()
        assert (base_dir / "demo-app" / "app" / "email_hooks.py").exists()
        assert (base_dir / "demo-app" / "app" / "email_theme.py").exists()
        assert (base_dir / "demo-app" / "app" / "email_templates" / "base.html").exists()
        assert (base_dir / "demo-app" / "app" / "email_templates" / "verify_email.html").exists()
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(base_dir, ignore_errors=True)
