"""
A series of tests that test by calling the code directly.
It is meant to look only at the file_db parts and does not include the archive element of this


This should make for easier debugging
"""
import filecmp
import os
from pathlib import Path
import shutil
import unittest

from odarchive.file_db import FileDatabase


class TestFileDB(unittest.TestCase):

    def setUp(self):
        """Set the correct working directory"""
        self.start_dir = os.getcwd()
        if Path(self.start_dir).parts[-1] == "tests":
            os.chdir("test_1_files")
        else:  # Assume in parent directory
            os.chdir("tests/test_1_files")

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_file_db(self):
        db = FileDatabase(Path("usb"))
        self.assertEqual(0, len(db), "Test empty length")
        added, removed, modified = db.update()  # Scan directory to add files
        self.assertEqual(5, len(db), "Test length after scanning directory")
        db.print_files()  # TODO should be made a function to test result
        GET_INFO = (
            f"""Number of entries = 5
Data size       = 127 bytes
Number of dirs  = 2
Max dir depth   = {len(Path(os.getcwd()).parts)+1} (on source file system)
 Dir =: {Path(os.getcwd()) / Path("usb/testDir")}"""
        )
        self.assertEqual(
            GET_INFO,
            db.get_info().strip(),
            "Testing get info before segmentation",
        )



