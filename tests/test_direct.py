"""
A series of tests that test by calling the code directly.

This should make for easier debugging
"""
import filecmp
import os
from pathlib import Path
import shutil
import unittest

from fabric.api import local, lcd
from pycdlib.pycdlibexception import PyCdlibInvalidInput
from odarchive import Archiver, odarchiveError

try:
    from utils import test_1_clean, catalogue_compare
except ImportError:
    print(f"Import fail CWD = {os.getcwd()}")


class Test_Direct(unittest.TestCase):

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

    def test_create_iso_direct(self):
        self.assertFalse(
            os.path.isfile("catalogue.json"),
            "Failed to remove the file test_1_files/catalogue.json.",
        )
        self.assertFalse(os.path.isfile("new.iso"), "Failed to remove new.iso.")
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.save()  # Creates archiver.dill
        ar.hash_db.save()  #  Creates catalogue.json
        ar.file_db.print_files()
        ar.write_iso(True)
        self.assertFalse(
            os.path.isfile("new.iso"),
            "new.iso should not exist at this point as pretending to create.",
        )
        ar.write_iso()
        self.assertTrue(
            os.path.isfile("new.iso"), "Create new.iso but was not created."
        )
        ar.save()
        self.assertTrue(
            os.path.isfile("catalogue.json"),
            "Failed to create the file test_1_files/catalogue.json",
        )
        self.assertTrue(
            catalogue_compare("catalogue.json", "reference_catalogue.json"),
            "Created file catalogue does not match reference.",
        )

    def test_create_iso_disc_num(self):
        GET_INFO_BEFORE_SEGMENTATION = (
            """Number of entries = 3
Data size       = 158 bytes
Is segmented    = False
>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<
Number of files = 6
  Largest file  = 33
Number of dirs  = 2
Max dir depth   = 1 (on source file system)
 Dir =: /DATA"""
        )
        GET_INFO_AFTER_SEGMENTATION = (
            """Number of entries = 3
Data size       = 158 bytes
Is segmented    = True
>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<
  Disc segment size = cd, 737,280,000 bytes
  Catalogue size = 2,048 bytes
  Number of discs = 1
Number of files = 6
  Largest file  = 33
Number of dirs  = 2
Max dir depth   = 1 (on source file system)
 Dir =: /DATA
Database Version = 1"""
        )
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.hash_db.save()  #  Creates catalogue.json
        ar.file_db.print_files()
        with self.assertRaises(odarchiveError):
            ar.write_iso(disc_num=0)
        self.assertFalse(
            os.path.isfile("new_0000.iso"),
            "new_0000.iso should not be written as archive has not been segmented.",
        )
        self.assertFalse(ar.is_segmented, "Archive should not be segmented")
        test_result = GET_INFO_BEFORE_SEGMENTATION + f'\nguid = {ar.guid}'
        test_result = test_result + f'\nDatabase Version = 1'
        self.assertEqual(
            test_result,
            ar.get_info().strip(),
            "Testing get info before segmentation",
        )
        ar.convert_to_hash_database()
        ar.segment("cd")
        self.assertTrue(ar.is_segmented, "Archive should be segmented")
        self.assertEqual(
            GET_INFO_AFTER_SEGMENTATION,
            ar.get_info().strip(),
            "Testing get info after segmentation",
        )
        # TODO need to check for presence of cataloge
        # with self.assertRaises(odarchiveError):
        #     ar.write_iso(disc_num=0)
        self.assertFalse(
            os.path.isfile("new_0000.iso"),
            "new_0000.iso should not be written as have not written out catalogue.",
        )
        ar.save()
        ar.write_iso(disc_num=0)
        self.assertTrue(
            os.path.isfile("new_0000.iso"), "new_0000.iso failed to be written."
        )
        with self.assertRaises(PyCdlibInvalidInput):
            ar.write_iso(disc_num=2)
        self.assertFalse(
            os.path.isfile("new_0002.iso"),
            "Should not have created new_0002.iso as not enough files.",
        )


    def test_archive_lock(self):
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.hash_db.save()  #  Creates catalogue.json
        ar.segment("cd")
        ar.segment("bd")  # before locking can resegment
        ar.locked = True
        with self.assertRaises(odarchiveError):
            ar.segment("cd")


    def test_multi_disc(self):
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.hash_db.save()  #  Creates catalogue.json
        ar.segment(506145)
        ar.locked = True
        self.assertEqual(2, ar.last_disc_num)
        for i in range(3):
            ar.write_iso(disc_num=i)


    def test_guid(self):
        ar = Archiver()
        self.assertIsNone(ar.guid, "At creation guid should be none")
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.hash_db.save()  #  Creates catalogue.json
        self.assertIsNotNone(ar.guid, "After sving guid should exist")
