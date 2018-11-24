import os
from pathlib import Path, PurePosixPath
import unittest

from odarchive.file_entry import FileEntry, FileEntryType


class TestFileEntry(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        os.chdir(Path(__file__).parents[0])
        # Required for HashEntry as parent
        self.path = Path(os.getcwd()) / Path("test_1_files/usb")

    def tearDown(self):
        os.chdir(self.start_dir)

    def test_create_simple_file_entry(self):
        my_path = Path(os.getcwd())
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        self.assertEqual(
            Path(PurePosixPath("./test_1_files/usb/first.html")).absolute(),
            entry.filename,
            "Making sure absolute path ok",
        )
        self.assertEqual(
            PurePosixPath("first.html"),
            entry.relative_path,
            "Making sure path relative to root of USB drive is ok",
        )

    def test_entry_with_dir(self):
        my_path = self.path / Path("testDir/fourthé.txt")
        entry = FileEntry(self, my_path.absolute())
        entry.update_attrs()
        entry.update_type()
        # Make sure path still works
        self.assertEqual(
            Path(PurePosixPath("./test_1_files/usb/testDir/fourthé.txt")).absolute(),
            entry.filename,
            "Making sure absolute path ok",
        )

    def test_entry_disc_num(self):
        my_path = Path(os.getcwd())
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        entry.update_attrs()
        entry.update_type()
        self.assertIsNone(entry.disc_num, "Should start out null")
        entry.disc_num = 2
        self.assertEqual(2, entry.disc_num, "disc num should be two")
        # disc num should be imutable - should not make mistakes
        entry.disc_num = 1
        self.assertNotEqual(1, entry.disc_num, "disc num should not be one")
        self.assertEqual(2, entry.disc_num, "disc num should be still be two")
        # Make sure path still works
        self.assertEqual(
            Path(PurePosixPath("./test_1_files/usb/first.html")).absolute(),
            entry.filename,
            "Making sure absolute path ok",
        )

    def test_str(self):
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        self.assertEqual(
            str((self.path / Path("first.html")).absolute()),
            str(entry),
            "make sure string conversion is ok",
        )

    def test_exists(self):
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        self.assertTrue(entry.exists(), "Make sure file exists")

    def test_equality(self):
        # FileEntry requires update
        # It is seperate to allow to be done in parallel
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        same_entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        other_entry = FileEntry(self, (self.path / Path("second.txt")).absolute())
        other_copy_entry = FileEntry(
            self, (self.path / Path("second copy.txt")).absolute()
        )
        self.assertTrue(entry == entry, "Test a == a even though not updated")
        self.assertTrue(entry == other_entry, "Test for a == b when not updated")
        for e in (entry, same_entry, other_copy_entry, other_copy_entry):
            e.update()
        self.assertTrue(entry == entry, "Test a == a real test")
        self.assertTrue(entry == same_entry, "Test a == b if b the same file as a")
        self.assertFalse(entry == other_entry, "Test for a != b")
        self.assertFalse(entry == other_copy_entry, "Test for in equality")
        self.assertFalse(
            other_entry == other_copy_entry,
            "Test that two files which are the same with different names test different",
        )
        # Try nonsense
        self.assertFalse(
            entry == "first.html", "Should not test same for filename only"
        )

    def test_verify(self):
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        self.assertTrue(entry.verify(), "Make sure file verifies")

    def test_hashable(self):
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        a_set = set()
        a_set.add(entry)  # Requires entry to be hashable
        self.assertEqual(1, len(a_set), "Make sure it has been added to set")

    def test_file_hash(self):
        entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        entry.calculate_file_hash()
        self.assertEqual(
            "99f4486018bf930287842c52c1b7331e488a7848002d4426ff1a338587be85327edda57c60f15bd8f3ab6cc480a39690e498585d1f742162e4954784ec761319",
            entry.file_hash,
            "Check file hash",
        )
