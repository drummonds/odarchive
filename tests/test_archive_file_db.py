"""
A series of tests that test by calling the code directly.
It is meant to look only at the file_db parts inside an archive


This should make for easier debugging
"""
import filecmp
import os
from pathlib import Path
import shutil
import unittest

from fabric.api import local, lcd

from odarchive import Archiver, odarchiveError
from odarchive.hash_file_entry import iso9660_dir, HashFileEntries

# Todo remove this function being duplicated couldnt get it to work importing from util
def test_archive_clean():
    """Delete files produced in test_1"""
    home = Path(os.getcwd())
    if home.parts[-1] == "tests":
        test_1_root = home / Path("test_1_files")
    else:
        test_1_root = home / Path("tests/test_1_files")
    print(f" test1_clean CWD = {os.getcwd()}")
    for this_file in ("archiver.dill",):
        try:
            os.remove(test_1_root / Path(this_file))
        except FileNotFoundError:
            pass


class Test_Archive_File_DB(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        test_archive_clean()
        if Path(self.start_dir).parts[-1] == "tests":
            os.chdir("test_1_files")
        else:  # Assume in parent directory
            os.chdir("tests/test_1_files")

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_db(self):
        self.assertFalse(
            os.path.isfile("archiver.dill"),
            "Failed to remove the file test_1_files/archiver.dill.",
        )
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.save()
        ar.file_db.print_files()
        ar.save()
        self.assertTrue(
            os.path.isfile("archiver.dill"),
            "Failed to create the file test_1_files/archiver.dill",
        )
