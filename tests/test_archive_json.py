"""
A series of tests that test by calling the code directly.
This is meant to test create an archive from json file."""
import filecmp
from io import BytesIO
import os
from pathlib import Path
import platform
import shutil
import unittest

from fabric.api import local, lcd
from jinja2 import Template
import pycdlib
import subprocess

from odarchive import Archiver, odarchiveError, load_archiver_from_json, load_disc_info_from_json, DISC_INFO_FILENAME

from utils import test_1_clean


def get_drive_letters():
    result = subprocess.run(['PowerShell', "Get-Volume"], stdout=subprocess.PIPE)
    r1 = result.stdout.decode('utf-8').strip()
    r2 = r1.split('\n')[2:]
    r9 = set([x[0] for x in r2 if x[0] != ' '])
    print(f'Num lines = {len(r9)}')
    print(r9)
    return r9


get_info = Template("""Number of entries = 3
Data size       = 158 bytes
Is segmented    = True
>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<
  Disc segment size = bd, 25,000,000,000 bytes
  Catalogue size = {{ size }} bytes
  Number of discs = 1
Number of files = 6
  Largest file  = 33
Number of dirs  = 2
Max dir depth   = 1 (on source file system)
 Dir =: /DATA
Database Version = 2
guid = {{ guid }}
""")


class Test_Archive_File_DB(unittest.TestCase):

    def setUp(self):
        """Delete files on setup so that can review at end"""
        self.start_dir = os.getcwd()
        os.chdir(Path(__file__).parents[0] / "test_1_files")
        test_1_clean()
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.save()  # To get estimate of catalogue.json, unsegmented
        ar.segment("cd")
        ar.save()  # To get final version of cataloge.json


    def tearDown(self):
        os.chdir(self.start_dir)

    def test_read_from_json(self):
        self.assertTrue(
            os.path.isfile("catalogue.json"),
            "Failed to create catalogue.json.",
        )
        ar = load_archiver_from_json("catalogue.json")
        self.assertEqual(get_info.render(size='1,480', guid = ar.guid),
                         ar.get_info().strip())

    def make_iso(self):
        ar = Archiver()
        ar.create_file_database(Path("usb"))
        ar.convert_to_hash_database()
        ar.segment('cd')
        ar.save()  # Creates catalogue.json
        ar.file_db.print_files()
        ar.write_iso(disc_num=0)

    def test_read_from_iso_without_mounting(self):
        """Can we read the catalogue from an ISO drive?"""
        self.make_iso()
        self.assertTrue(
            os.path.isfile("new_0000.iso"),
            "Failed to create new_0000.iso.",
        )
        # Now, let's open up the ISO and read the catalogue
        iso = pycdlib.PyCdlib()
        iso.open("new_0000.iso")
        extracted = BytesIO()
        # Use the get_file_from_iso_fp() API to extract the named filename into the file
        # descriptor.
        iso.get_file_from_iso_fp(extracted, iso_path='/CATALOGUE.JSON;1')
        iso.close()
        file_data = extracted.getvalue().decode('utf-8')
        self.assertEqual(
            '{\r\n    "client_n',
            file_data[:16],
            "Failed to read from ISO",
        )
        ar = load_archiver_from_json(None, json_data=file_data)
        self.assertEqual(get_info.render(size='1,479', guid = ar.guid),
                         ar.get_info().strip())

    def test_read_from_iso(self):
        """Can we read the catalogue from an ISO drive when it is mounted"""
        self.make_iso()
        self.assertTrue(
            os.path.isfile("new_0000.iso"),
            "Failed to create new_0000.iso.",
        )
        # Now, let's open up the ISO and read the catalogue
        if (platform.system() == "Windows"):
            iso_path = f'{Path(os.getcwd()) / Path("new_0000.iso")}'
            drive_letters_before = get_drive_letters()
            os.system(f'PowerShell Mount-DiskImage {iso_path}')
            try:
                drive_letters_after = get_drive_letters()
                new_drive_letter = list(drive_letters_after - drive_letters_before)[0]
                print(f'New drive letter is {new_drive_letter}')
                ar = load_archiver_from_json(f'{new_drive_letter}:\catalogue.json')
                self.assertEqual(get_info.render(size='1,480', guid=ar.guid),
                                 ar.get_info().strip())
            finally:
                os.system(f'PowerShell DisMount-DiskImage {iso_path}')
        elif (platform.system() == "Linux"):
            os.system("mount /dev/dvdrom /mount-point")  # TODO

    def test_read_disc_info(self):
        """disc info is the information about this disc eg which disc-num is it.
        Hash of catalogue.json"""
        self.make_iso()
        # Now, let's open up the ISO and read the disc info
        if (platform.system() == "Windows"):
            iso_path = f'{Path(os.getcwd()) / Path("new_0000.iso")}'
            print(f'Path = |{iso_path}|')
            drive_letters_before = get_drive_letters()
            os.system(f'PowerShell Mount-DiskImage {iso_path}')
            try:
                drive_letters_after = get_drive_letters()
                new_drive_letter = list(drive_letters_after - drive_letters_before)[0]
                print(f'New drive letter is {new_drive_letter}')
                di = load_disc_info_from_json(Path(f'{new_drive_letter}:') / f'{DISC_INFO_FILENAME}')
                self.assertTrue(di.disc_num > -1, 'Problem with disc info')
            finally:
                os.system(f'PowerShell DisMount-DiskImage {iso_path}')
        elif (platform.system() == "Linux"):
            os.system("mount /dev/dvdrom /mount-point")  # TODO
#

