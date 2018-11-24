import json
import os
from pathlib import Path, PurePosixPath
import unittest

import dill

from odarchive.file_entry import FileEntry
from odarchive.hash_file_entry import HashFileEntries, iso9660_dir
from odarchive.consts import odarchiveError

def test_hash_file_entry_clean():
    """Delete files produced in test_1_files"""
    test_1_root = Path(__file__).parents[0] / 'test_1_files'
    for this_file in (
        "test_pickling.dill",
    ):
        try:
            os.remove(test_1_root / Path(this_file))
        except FileNotFoundError:
            pass


class TestHashFileEntry(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        os.chdir(Path(__file__).parents[0])
        test_hash_file_entry_clean()
        # Required for HashEntry as parent
        self.path = Path(os.getcwd()) / Path("test_1_files/usb")
        self.iso_path_root = PurePosixPath(
            "/DATA"
        )  # Both ISO and UDF root directory for archive files.

    def tearDown(self):
        os.chdir(self.start_dir)

    def jsonEqual(self, a, b):
        a2 = json.loads(a)
        a1 = json.dumps(a2)
        b2 = json.loads(b)
        b1 = json.dumps(b2)
        self.assertEqual(a1, b1)

    def test_create_hash_db(self):
        FIRST_JSON = """
{
    "99f4486018bf930287842c52c1b7331e488a7848002d4426ff1a338587be85327edda57c60f15bd8f3ab6cc480a39690e498585d1f742162e4954784ec761319": 
        {
            "filenames": {
                "/DATA/first.html" : null
            }, 
            "size": 22, 
            "mtime": "2018-05-24T09:32:31"
        }
}
"""
        SECOND_JSON = """
{
    "99f4486018bf930287842c52c1b7331e488a7848002d4426ff1a338587be85327edda57c60f15bd8f3ab6cc480a39690e498585d1f742162e4954784ec761319": 
        {
            "filenames": {
                "/DATA/first.html" : null
            }, 
            "size": 22, 
            "mtime": "2018-05-24T09:32:31"
        },
    "390da1c000ce0c69257de9cda5255b4cd2a4a899415a017fc83be7a4d1670702054a9e1ca9e40ad15e20d403596f7c1feb001b4c1cfa459b06c7b0da4ffc583b": 
        {
            "filenames": {
                "/DATA/second.txt" : null
            }, 
            "size": 24, 
            "mtime": "2018-05-24T09:32:31"
        }
}
"""
        THIRD_JSON = """
{
    "99f4486018bf930287842c52c1b7331e488a7848002d4426ff1a338587be85327edda57c60f15bd8f3ab6cc480a39690e498585d1f742162e4954784ec761319": 
        {
            "filenames": {
                "/DATA/first.html" : null
            }, 
            "size": 22, 
            "mtime": "2018-05-24T09:32:31"
        },
    "390da1c000ce0c69257de9cda5255b4cd2a4a899415a017fc83be7a4d1670702054a9e1ca9e40ad15e20d403596f7c1feb001b4c1cfa459b06c7b0da4ffc583b": 
        {
            "filenames": {
                "/DATA/second.txt" : null,
                "/DATA/second copy.txt" : null
            }, 
            "size": 24, 
            "mtime": "2018-05-24T09:32:31"
        }
}
"""
        test_database = HashFileEntries.create(PurePosixPath("/DATA"), self.path)
        # Can add a file
        file_entry = FileEntry(self, (self.path / Path("first.html")).absolute())
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        self.assertEqual(1, len(test_database))
        self.jsonEqual(FIRST_JSON, test_database.to_json())
        # but only once
        test_database.add_hash_file(file_entry)
        self.assertEqual(1, len(test_database))
        self.jsonEqual(FIRST_JSON, test_database.to_json())
        # add non existent file
        file_entry = FileEntry(
            self, (self.path / Path("does_not_exist.txt")).absolute()
        )
        # Without update so the add hash file should fail
        with self.assertRaises(odarchiveError):
            test_database.add_hash_file(file_entry)
        # Existing database unchanged.
        self.assertEqual(1, len(test_database))
        self.jsonEqual(FIRST_JSON, test_database.to_json())
        # add non existent file
        file_entry = FileEntry(
            self, (self.path / Path("does_not_exist.txt")).absolute()
        )
        with self.assertRaises(FileNotFoundError):
            file_entry.update()  # Self update
        self.assertEqual(1, len(test_database))
        self.jsonEqual(FIRST_JSON, test_database.to_json())
        # Can add a second file
        file_entry = FileEntry(self, (self.path / Path("second.txt")).absolute())
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        self.assertEqual(2, len(test_database))
        self.jsonEqual(SECOND_JSON, test_database.to_json())
        # Can add a second file copy
        file_entry = FileEntry(
            self, (self.path / Path("second copy.txt")).absolute()
        )  # Same hash but different dir
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        self.assertEqual({"/DATA": ""}, test_database.dir_entries())
        self.assertEqual(2, len(test_database))
        self.jsonEqual(THIRD_JSON, test_database.to_json())

    # Redo tests taking into account disc_num

    def test_create_simple_file_entry(self):
        test_database = HashFileEntries.create(PurePosixPath("/DATA"), self.path)
        self.assertEqual({}, test_database.dir_entries())
        # Can add a file
        file_entry = FileEntry(
            self, (self.path / Path("first.html")).absolute(), disc_num=2
        )
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        entry = next(iter(test_database.values()))
        self.assertEqual(
            "/DATA/first.html", str(entry.udf_absolute_path), "Making sure UDF path ok"
        )
        self.assertEqual(
            "/DATA/FIRST.HTML;1", entry.iso9660_path, "Making sure ISO path ok"
        )
        self.assertEqual(2, entry.disc_num)
        self.assertEqual({"/DATA": ""}, test_database.dir_entries())

    def test_unicode(self):
        test_database = HashFileEntries.create(PurePosixPath("/DATA"), self.path)
        # Can add a unicode file
        file_entry = FileEntry(
            self, (self.path / Path("testDir/fourthé.txt")).absolute(), disc_num=2
        )
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        entry = next(iter(test_database.values()))
        self.assertEqual(
            "/DATA/testDir/fourthé.txt",
            str(entry.udf_absolute_path),
            "Making sure UDF path ok",
        )
        self.assertEqual(
            "/DATA/TESTDIR/FOURTH_.TXT;1", entry.iso9660_path, "Making sure ISO path ok"
        )
        self.assertEqual(
            "testDir/fourthé.txt",
            str(entry.relative_filename),
            "Making sure relative path ok",
        )
        self.assertEqual(
            {"/DATA": "", "/DATA/testDir": ""},
            test_database.dir_entries(),
            "Testing multiple directories",
        )

    def test_iso_dir(self):
        self.assertEqual("/", iso9660_dir("/"), "Test root dir match")
        self.assertEqual(
            "/TEST_1_FILES", iso9660_dir("/test_1_files"), "Test one level dir match"
        )
        self.assertEqual(
            "/TEST_1_FILES/USB/TESTDIR",
            iso9660_dir("/test_1_files/usb/testDir"),
            "Test three level dir match",
        )

    def test_file_system_paths(self):
        test_database = HashFileEntries.create(PurePosixPath("/DATA"), self.path)
        # Can add a unicode file
        file_entry = FileEntry(
            self, (self.path / Path("testDir/fourthé.txt")).absolute(), disc_num=2
        )
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        entry = next(iter(test_database.values()))
        self.assertEqual(
            f"{PurePosixPath(Path(os.getcwd()) / Path('test_1_files/usb/testDir/fourthé.txt'))}",
            str(entry.file_system_path),
            "Making sure File System path ok",
        )


    def test_pickling(self):
        test_database = HashFileEntries.create(PurePosixPath("/DATA"), self.path)
        file_entry = FileEntry(
            self, (self.path / Path("testDir/fourthé.txt")).absolute(), disc_num=2
        )
        file_entry.update()  # Self update
        file_entry.calculate_file_hash()
        test_database.add_hash_file(file_entry)
        with open("test_pickling.dill", "wb") as f:
            dill.dump(test_database, f, dill.HIGHEST_PROTOCOL)
        with open("test_pickling.dill", "rb") as f:
            test_load = dill.load(f)
        self.assertEqual(
            str(next(iter(test_database.values())).file_system_path),
            str(next(iter(test_load.values())).file_system_path),
            "Making pickled path same as start")
