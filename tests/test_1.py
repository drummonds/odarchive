"""
A series of tests that test at the CLI level
"""
import filecmp
import os
from pathlib import Path
import sys
import unittest

from fabric.api import local, lcd

try:
    from utils import test_1_clean
except ImportError:
    print(f"Import fail CWD = {os.getcwd()}")

class Test_Simple(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        test_1_clean()
        if Path(self.start_dir).parts[-1] == "tests":
            os.chdir("test_1_files")
        else:  # Assume in parent directory
            os.chdir("tests/test_1_files")

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_iso_via_fab(self):
        self.assertFalse(
            os.path.isfile("catalogue.json"),
            "Failed to remove the file test_1_files/catalogue.json.",
        )
        local(
            "C:/Users/HumphreyDrummond/Envs/odarchive/Scripts/python ../../odarchive_cli.py archive usb"
        )
        self.assertTrue(
            os.path.isfile("catalogue.json"),
            "Failed to create the file test_1_files/catalogue.json",
        )
        self.assertTrue(
            filecmp.cmp("catalogue.json", "reference_catalogue.json", shallow=False),
            "Created database does not match reference.",
        )

    def test_create_iso_via_fab2(self):
        self.assertFalse(
            os.path.isfile("catalogue.json"),
            "Failed to remove the file test_1_files/catalogue.json.",
        )
        # init and write_iso should be same as archive
        local(
            "C:/Users/HumphreyDrummond/Envs/odarchive/Scripts/python ../../odarchive_cli.py init usb"
        )
        local(
            "C:/Users/HumphreyDrummond/Envs/odarchive/Scripts/python ../../odarchive_cli.py write_iso"
        )
        self.assertTrue(
            os.path.isfile("catalogue.json"),
            "Failed to create the file test_1_files/catalogue.json",
        )
        self.assertTrue(
            filecmp.cmp("catalogue.json", "reference_catalogue.json", shallow=False),
            "Created database does not match reference.",
        )
