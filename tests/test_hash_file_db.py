"""
A series of tests that test by calling the code directly.
It is meant to look only at the file_db parts and does not include the archive element of this


This should make for easier debugging
"""
import filecmp
import os
from pathlib import Path, PurePosixPath
import shutil
import unittest

from odarchive.file_db import FileDatabase
from odarchive.hash_db import HashDatabase


class TestFileDB(unittest.TestCase):

    def setUp(self):
        """Set the correct working directory"""
        self.start_dir = os.getcwd()
        if Path(self.start_dir).parts[-1] == "tests":
            os.chdir("test_1_files")
        else:  # Assume in parent directory
            os.chdir("tests/test_1_files")
        self.file_db = FileDatabase(Path("usb"))
        self.file_db.update()
        self.file_db.calculate_file_hash()
        self.iso_path_root = PurePosixPath("/DATA")

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_hash_file_db(self):
        self.assertEqual(5, len(self.file_db), "Test length after scanning directory")
        hash_db = HashDatabase(self.file_db, self.iso_path_root)
        self.assertEqual(3, len(hash_db), "Test length of hashes (quite a number of duplicates)")

    def test_create_iso_disc_num(self):
        GET_INFO_BEFORE_SEGMENTATION = (
            f"""Number of entries = 3
Data size       = 158 bytes
Is segmented    = False
>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<
Number of files = 6
  Largest file  = 33
Number of dirs  = 2
Max dir depth   = 1 (on source file system)
 Dir =: /DATA
Database Version = 1"""
        )
        GET_INFO_AFTER_SEGMENTATION = (
            f"""Number of entries = 3
Data size       = 158 bytes
Is segmented    = True
>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<
  Disc segment size = cd, 737,280,000 bytes
  Catalogue size = 0 bytes
  Number of discs = 1
Number of files = 6
  Largest file  = 33
Number of dirs  = 2
Max dir depth   = 1 (on source file system)
 Dir =: /DATA
Database Version = 1"""
        )
        hash_db = HashDatabase(self.file_db, self.iso_path_root)
        self.assertFalse(hash_db.is_segmented, "File database should not be segmented")
        self.assertEqual(
            GET_INFO_BEFORE_SEGMENTATION,
            hash_db.get_info().strip(),
            "Testing get info before segmentation",
        )
        hash_db.segment("cd", 0)
        self.assertTrue(hash_db.is_segmented, "Archive should be segmented")
        self.assertEqual(
            GET_INFO_AFTER_SEGMENTATION,
            hash_db.get_info().strip(),
            "Testing get info after segmentation",
        )
