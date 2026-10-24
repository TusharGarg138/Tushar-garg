"""
CLI integration tests and data immutability verification.
"""

import os
import sys
import subprocess
import pytest


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "checker.py", "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Aeron Weather Network Data Quality Checker" in result.stdout


def test_cli_invalid_path():
    result = subprocess.run(
        [sys.executable, "checker.py", "non_existent_folder_xyz"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 1
    assert "does not exist" in result.stderr


def test_cli_execution_from_different_working_directory(tmp_path):
    repo_root = os.path.abspath(".")
    checker_script = os.path.join(repo_root, "checker.py")
    datapack_dir = os.path.join(repo_root, "ridgeline_data_pack")

    # Run from temporary directory
    result = subprocess.run(
        [sys.executable, checker_script, datapack_dir],
        cwd=str(tmp_path),
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    # flags.csv should be written into the temporary working directory!
    flags_file = tmp_path / "flags.csv"
    assert flags_file.exists()


def test_source_data_immutability():
    """Verify that running checker.py does not modify raw data files."""
    data_dir = os.path.join("ridgeline_data_pack", "data")
    if not os.path.exists(data_dir):
        pytest.skip("ridgeline_data_pack not present")

    # Get file sizes and timestamps before
    files_before = {
        f: (os.path.getsize(os.path.join(data_dir, f)), os.path.getmtime(os.path.join(data_dir, f)))
        for f in os.listdir(data_dir) if f.endswith(".csv")
    }

    subprocess.run([sys.executable, "checker.py", "ridgeline_data_pack"], capture_output=True)

    files_after = {
        f: (os.path.getsize(os.path.join(data_dir, f)), os.path.getmtime(os.path.join(data_dir, f)))
        for f in os.listdir(data_dir) if f.endswith(".csv")
    }

    assert files_before == files_after, "Raw data files were modified!"
