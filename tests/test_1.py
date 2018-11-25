"""
A series of tests that test at the CLI level
"""
import filecmp
import json
import os
from pathlib import Path
import sys
import unittest

from fabric.api import local, lcd


from odarchive import DB_FILENAME
try:
    from utils import test_1_clean, catalogue_compare
except ImportError:
    print(f"Import fail CWD = {os.getcwd()}")

class Test_Simple(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        os.chdir(Path(__file__).parents[0] / "test_1_files")
        test_1_clean()

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_iso_via_fab(self):
        self.assertFalse(
            os.path.isfile(DB_FILENAME),
            f"Failed to remove the file test_1_files/{DB_FILENAME}.",
        )
        # TODO Get rid of user specific reference  EVERYWHERE
        local(
            "C:/Users/HumphreyDrummond/Envs/odarchive/Scripts/python ../../odarchive_cli.py archive usb "
        )
        self.assertTrue(
            os.path.isfile(DB_FILENAME),
            f"Failed to create the file test_1_files/{DB_FILENAME}",
        )
        self.assertTrue(
            catalogue_compare(DB_FILENAME, 'reference_catalogue.json'),
            "Created catalogue.json does not match reference_catalogue.json.",
        )

    def test_create_iso_via_fab2(self):
        self.assertFalse(
            os.path.isfile(DB_FILENAME),
            f"Failed to remove the file test_1_files/{DB_FILENAME}.",
        )
        # init and write_iso should be same as archive
        local(
            "C:/Users/HumphreyDrummond/Envs/odarchive/Scripts/python ../../odarchive_cli.py init usb"
        )
        # TODO
        # local(
        #     "C:/Users/HumphreyDrummond/Envs/odarchive/Scripts/python ../../odarchive_cli.py write_iso"
        # )
        self.assertTrue(
            os.path.isfile(DB_FILENAME),
            f"Failed to create the file test_1_files/{DB_FILENAME}",
        )
        self.assertTrue(
            catalogue_compare(DB_FILENAME, "reference_catalogue.json"),
            "Created database does not match reference.",
        )
