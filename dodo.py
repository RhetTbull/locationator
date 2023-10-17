"""doit build script for locationator; run with `doit` or `doit list` to see available tasks"""

import pathlib


def get_app_files() -> list[pathlib.Path]:
    """Get list of all files in the app bundle for dependency checking"""
    if not pathlib.Path("dist/Locationator.app").exists():
        return ["dist/Locationator.app"]
    return [
        p for p in pathlib.Path("dist/Locationator.app").glob("**/*") if p.is_file()
    ]


DOIT_CONFIG = {"default_tasks": ["build_cli", "build_app", "create_dmg"]}


def task_build_cli():
    """Build the CLI"""
    return {
        "actions": [
            "rm -rf dist/",
            "rm -rf build/",
            "pyinstaller locationator.spec",
        ],
        "file_dep": ["locationator.spec", "locationator/cli.py"],
        "targets": ["dist/locationator"],
    }


def task_build_app():
    """Build the app"""
    file_deps = list(pathlib.Path("locationator").glob("*.py"))
    targets = get_app_files()
    return {
        "actions": ["python3 setup.py py2app"],
        "file_dep": file_deps,
        "targets": targets,
    }


def task_create_dmg():
    """Create the DMG for release"""
    file_deps = get_app_files()
    return {
        "actions": ["./create_dmg.sh"],
        "file_dep": [*file_deps, "create_dmg.sh"],
        "targets": ["dist/Locationator-Installer.dmg"],
    }


def task_tests():
    """Run tests"""
    return {"actions": ["python3 -m pytest tests/"]}
