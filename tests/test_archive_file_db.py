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
    for this_file in ("archiver.dill",):
        try:
            os.remove(Path(this_file))
        except FileNotFoundError:
            pass


class Test_Archive_File_DB(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        os.chdir(Path(__file__).parents[0] / "test_1_files")
        test_archive_clean()

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_db(self):
        self.assertFalse(
            os.path.isfile("archiver.dill"),
            "Failed to remove the file test_1_files/archiver.dill.",
        )
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        with self.assertRaises(odarchiveError):
            # 'Tried to save fileDB but should not be able to save until hashes are calculated'
            ar.save()
