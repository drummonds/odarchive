import os
from pathlib import Path


def test_1_clean():
    """Delete files produced in test_1"""
    home = Path(os.getcwd())
    if home.parts[-1] == "tests":
        test_1_root = home / Path("test_1_files")
    else:
        test_1_root = home / Path("tests/test_1_files")
    print(f" test1_clean CWD = {os.getcwd()}")
    for this_file in (
        "usb.iso",
        "usb.db",
        "catalogue.json",
        "new.iso",
        "new_0000.iso",
        "new_0001.iso",
        "new_0002.iso",
        "archiver.pickle",
        "archiver.dill",
        "archiver.json",
    ):
        try:
            os.remove(test_1_root / Path(this_file))
        except FileNotFoundError:
            pass

