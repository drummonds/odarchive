# -*- encoding: utf-8 -*-
import datetime as dt

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO
import logging
import os
from os import lstat
import dill

import click
import pycdlib

from .consts import *
from .file_db import FileDatabase
from .hash_db import *
from .hash_file_entry import iso9660_dir, HashFileEntry


# import tarfile
# import tempfile
# from datetime import datetime
# from getpass import getpass
# import hashlib
# import uuid
# import socket
# import re
# import fnmatch
# import mimetypes
# import calendar
# import functools
# from contextlib import closing  # for Python2.6 compatibility
# from gzip import GzipFile
#
# import yaml
# from beefish import decrypt, encrypt_file
# import grandfatherson
# from byteformat import ByteFormatter
#
# from bakthat.backends import GlacierBackend, S3Backend, RotationConfig, SwiftBackend
# from bakthat.conf import config, events, load_config, DEFAULT_DESTINATION, DEFAULT_LOCATION, CONFIG_FILE, EXCLUDE_FILES
# from bakthat.utils import _interval_string_to_seconds
# from bakthat.models import Backups
# from bakthat.sync import BakSyncer, bakmanager_hook, bakmanager_periodic_backups
# from bakthat.plugin import setup_plugins, plugin_setup
#
# __version__ = "0.6.0"
#
#
log = logging.getLogger("odarchive")


def archive():
    pass


class odarchiveFilter(logging.Filter):

    def filter(self, rec):
        if rec.name.startswith("odarchive") or rec.name == "root":
            return True
        else:
            return rec.levelno >= logging.WARNING


#!/usr/bin/env python3
from argparse import ArgumentParser
from fnmatch import fnmatch
from os import fsdecode, fsencode, getcwd, lstat, readlink, stat_result
from pathlib import Path
import re


# fnmatch patterns, specifically:
IMPORT_FILENAME_PATTERNS = [
    DB_FILENAME,
    HASH_FILENAME,
    HASH_FILENAME + ".asc",
    "*.sha512sum",
    "*.sha512sum.asc",
    "DIGESTS",
    "DIGESTS.asc",
]
SURROGATE_ESCAPES = re.compile(r"([\udc80-\udcff])")

ADDED_COLOR = "\033[01;32m"
REMOVED_COLOR = "\033[01;34m"
MODIFIED_COLOR = "\033[01;31m"
NO_COLOR = "\033[00m"


def find_external_hash_files(path: Path):
    for dirpath_str, _, filenames in walk(str(path)):
        dirpath = Path(dirpath_str).absolute()
        for filename in filenames:
            if any(fnmatch(filename, pattern) for pattern in IMPORT_FILENAME_PATTERNS):
                yield dirpath / filename


def print_file_list(files):
    for filename in sorted(files):
        printable_filename = SURROGATE_ESCAPES.sub("\ufffd", str(filename))
        print(printable_filename)
    print()

def print_file_lists(added, removed, modified):
    if added:
        print(ADDED_COLOR + "Added files:" + NO_COLOR)
        print_file_list(added)
    if removed:
        print(REMOVED_COLOR + "Removed files:" + NO_COLOR)
        print_file_list(removed)
    if modified:
        print(MODIFIED_COLOR + "Modified files:" + NO_COLOR)
        print_file_list(modified)


def list_dirs(files):
    for filename in sorted(files):
        printable_filename = SURROGATE_ESCAPES.sub("\ufffd", str(filename))
        print(printable_filename)
    print()


def load_archiver_from_json(filename="archiver.dill"):
    with open(filename, "rb") as f:
        # The protocol version used is detected automatically, so we do not
        # have to specify it.
        archiver = dill.load(f)
    return archiver


class Archiver:
    """This holds the information on the archiving project - potentially should keep state over multiple
    invocations.  This means that you do not have to hold in memory a temporary copy of all discs but
    can do them one by one.  For a 10TB archiving to 25GB drives this is a big saving."""

    def __init__(self):
        self.iso_path_root = PurePosixPath("/DATA")

    def save(self, filename="archiver.dill"):
        with open(filename, "wb") as f:
            # Pickle the 'data' dictionary using the highest protocol available.
            dill.dump(self, f, dill.HIGHEST_PROTOCOL)

    def create_file_database(self, usb_path, job_name="new"):
        # Create database
        self.file_db = FileDatabase(usb_path)
        self.job_name = job_name
        # Check to make sure not overwriting database
        click.echo("Initializing file database")
        self.file_db.update(
            usb_path
        )  # Scan directory to add files
        # Need to load the hash files into the Has list

    def convert_to_hash_database(self, verbose=False):
        if not self.is_locked:
            self.file_db.calculate_file_hash(verbose)
            # Create database
            self.hash_db = HashDatabase(self.file_db, self.iso_path_root)
        else:
            raise odarchiveError('Archive locked so cannot calculate hashes')

    def create_catalogue(self, verbose=False):
        """Creates a catalogue file catalogue.json on disk."""
        self.hash_db.save()  # Creates catalogue.json
        self.save()


    def write_iso(self, pretend=False, disc_num=None, job_name="new"):
        """No ISO file will be created if there are not files in it.  Eg using a disc num that is
        not being used."""
        try:
            if disc_num is None and self.hash_db.last_disc_number is not None:
                raise odarchiveError("disc_num is None but archive has been segmented")
            elif self.hash_db.last_disc_number is None and disc_num is not None:
                raise odarchiveError(
                    f"disc_num is {disc_num} but archive has not been segmented"
                )
            else:
                # Create ISO file
                iso = pycdlib.PyCdlib()
                if disc_num is None:  # Assuming standard is one based.
                    seqnum = 0
                else:
                    seqnum = disc_num
                if self.last_disc_num is None:  # Has not been segmented
                    set_size = 1
                else:
                    set_size = self.last_disc_num
                print(f'Disc num = |{disc_num}|')
                iso.new(
                    interchange_level=3,
                    udf="2.60",
                    app_ident_str="odarchive (C) 2018 drummonds.net",
                    abstract_file="README.MKD",
                    set_size=set_size,  # This is the size of the set of discs ie the number of disck
                    # eg 2 of set_size
                    seqnum=seqnum,
                )
        except AttributeError:
            raise odarchiveError(
                f"Probably have not yet created hash db"
            )

        # The readme file is created fresh for each disc created.  It should consist of specific information about
        # this disc and also information about the archive process
        readme = f"""# Archive File created by www.drummonds.net
This archive was created {dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}

The data for this archive is stored in the directory /DATA.
There is a catalogue of this archive stored in catalouge.json.  This catalogue has a list of all the files
archived in this run and on which disc they are stored.  The same catalogue is written to each disc in the 
archive series."""
        readme_bytes = readme.encode("utf-8")
        iso.add_fp(
            BytesIO(readme_bytes),
            len(readme_bytes),
            "/README.MKD;1",
            udf_path="/README.MKD",
        )
        iso.add_file(
            str("catalogue.json"),
            "/CATALOGUE.JSON;1",
            udf_path="/catalogue.json"  # Same catalogue for each disc
            # So that you can go to single disc and then find where to go next - which disc to read rather than
            # having to read all the files.
        )
        # Todo add_file which says which disc this is in which catalogue

        # iso.add_directory(str(self.iso_path_root), udf_path=str(self.iso_path_root))
        # iso.add_directory(
        #     str(self.iso_path_root) + "/TESTDIR",
        #     udf_path=str(self.iso_path_root) + "/testDir",
        # )
        dir_count = 0
        for this_dir in self.hash_db.entries.dir_entries(disc_num=disc_num):
            # Todo add Bridge format and iso9660
            # iso.add_directory(iso9660_dir(this_dir), udf_path=this_dir)
            # After 10^8 directories (which breaks a standard ISO 9660 the formatting will vary
            if this_dir == "/DATA":
                iso.add_directory(
                    "/DATA", udf_path="/DATA"
                )  # Add root data directory to both ISO and UDF
            else:
                iso.add_directory(
                    f"/DATA/{dir_count:08}", udf_path=this_dir
                )  # Note can't use "/" as ISO 9660 root as we are adding
                # a directory and this would only be the root
            dir_count += 1
        any_files = False
        file_count = 0
        for this_file in self.hash_db.files(disc_num=disc_num):
            # Todo add Bridge format and iso9660
            # iso.add_file(
            #     str(this_file.filename),
            #     this_file.iso9660_path,
            #     udf_path=str(this_file.udf_absolute_path),
            # )
            iso.add_file(
                str(this_file.file_system_path),
                f"/DATA/{file_count:08}",  # All data files in same directory and anonymise names :(
                udf_path=str(this_file.udf_absolute_path),
            )
            any_files = True
            file_count += 1
        if (
            not pretend and any_files
        ):  # Will not write out a cataloge with no files in it
            if disc_num is None:
                filename = f"{job_name}.iso"
            else:
                filename = f"{job_name}_{disc_num:04}.iso"
            # If file exists then iso.write will just overwrite part of it so need to delete it first.
            try:
                os.remove(filename)
            except FileNotFoundError:
                pass
            iso.write(filename)
            iso.close()

    @property
    def is_locked(self):
        """Once you have successfully written the first ISO then you should lock the archive.
        This should prevent operations such as segmenting if the archive is locked."""
        try:
            return self.locked
        except AttributeError:  # NO hash db so not segmented
            return False

    def segment(self, size):
        """Segment an archive.  This is mainly"""
        if not self.is_locked:
            catalogue_size = (
                (2048 + lstat(str(str("catalogue.json"))).st_size) // 2048
            ) * 2048  # Account for sector size
            self.hash_db.segment(size, catalogue_size)
        else:
            raise odarchiveError('Archive is locked so cannot resegment')

    @property
    def is_segmented(self):
        try:
            return self.hash_db.is_segmented
        except AttributeError:  # NO hash db so not segmented
            return False

    def get_info(self):
        """Returns summary information on archive"""
        try:
            return self.hash_db.get_info()
        except:
            return self.file_db.get_info()

    def print_files(self):
        self.file_db.print_files()

    @property
    def last_disc_num(self):
        return self.hash_db.last_disc_number

    def get_disc_info(self, disc_num):
        """Returns summary information on a single disc"""
        return self.hash_db.get_info(disc_num)


    def get_all_disc_info(self):
        """Returns summary information on all discs"""
        result = ''
        for i in range(self.last_disc_num):
            result += self.get_disc_info(i)
        return result
