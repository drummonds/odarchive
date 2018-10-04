"""
A series of tests that test by calling the code directly.
It is meant to look only at the abstract_file_db parts

This should make for easier debugging
"""
import os
from pathlib import Path
import unittest

from odarchive.abstract_file_db import AbstractFileDatabase


class TestAbstractFileDB(unittest.TestCase):

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
        db = AbstractFileDatabase(Path("usb"))
        self.assertEqual(0, len(db), "Test empty length")
        db.print_files()
        self.assertEqual("Number of entries = 0", db.get_info().strip())

