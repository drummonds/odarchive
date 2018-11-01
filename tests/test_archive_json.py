"""
A series of tests that test by calling the code directly.
This is meant to test create an archive from json file."""
import filecmp
import os
from pathlib import Path
import shutil
import unittest

from fabric.api import local, lcd

from odarchive import Archiver, odarchiveError, load_archiver_from_json
from odarchive.hash_file_entry import iso9660_dir, HashFileEntries

# Todo remove this function being duplicated couldn't get it to work importing from util
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


GET_INFO_AFTER_SEGMENTATION ="""Number of entries = 3
Data size       = 158 bytes
Is segmented    = True
>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<
  Disc segment size = bd, 25,000,000,000 bytes
  Catalogue size = 1,266 bytes
  Number of discs = 1
Number of files = 6
  Largest file  = 33
Number of dirs  = 2
Max dir depth   = 1 (on source file system)
 Dir =: /DATA"""

class Test_Archive_File_DB(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        test_archive_clean()
        if Path(self.start_dir).parts[-1] == "tests":
            os.chdir("test_1_files")
        else:  # Assume in parent directory
            os.chdir("tests/test_1_files")
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.segment("cd")
        ar.hash_db.save()  #  Creates catalogue.json


    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_db(self):
        self.assertTrue(
            os.path.isfile("catalogue.json"),
            "Failed to create catalogue.json.",
        )
        ar = load_archiver_from_json("catalogue.json")
        test_info = GET_INFO_AFTER_SEGMENTATION + f'\nguid = {ar.guid}'
        test_info = test_info + f"\nDatabase Version = 1"
        self.assertEqual(test_info, ar.get_info().strip())
