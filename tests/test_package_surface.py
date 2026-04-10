from importlib import resources

from messaging_sdk import __version__


def test_package_version_is_exposed():
    assert __version__ == "1.0.0"


def test_packaged_email_templates_exist():
    template_path = resources.files("messaging_sdk").joinpath(
        "email_templates/verify_email.html"
    )
    assert template_path.is_file()
