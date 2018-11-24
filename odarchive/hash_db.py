"""
This is a database of unique files which may exist in different locations.
In addtiion the file entities can be segmented to fit onto multiple discs.
"""
import datetime as dt
import json
from pathlib import Path, PurePosixPath
from os import fsdecode, fsencode, getcwd, lstat, readlink, stat_result, getcwd
import uuid

try:
    from scandir import walk
except ImportError:
    from os import walk

from .consts import *
from .abstract_file_db import AbstractFileDatabase
from .file_db import FileDatabase
from .file_entry import FileEntryType, FileEntry
from .hash_file_entry import HashFileEntries, HashFileEntry


class HashDatabase(AbstractFileDatabase):
    """This consists of making a database which has as a key each hash entry with multiple
    entries for each file.
    In addition it handles segmented the database for conversion to a set of ISO files"""

    def __init__(self, file_db: FileDatabase, iso_path_root):
        self.iso_path_root = iso_path_root
        self.db_path = Path(DB_FILENAME)
        self.version = DATABASE_VERSION
        self.segment_size = None  # DB is started not segmented
        self.last_disc_number = None  # This starts as a non segmented archive
        # segmented or not is None or not
        try:
            self.entries = HashFileEntries.create(self.iso_path_root, file_db.path)
            self.update(file_db)
        except AttributeError:
            self.entries = HashFileEntries.create(self.iso_path_root, None)


    def save_disc_info(self, catalogue_name=DISC_INFO_FILENAME):
        """Save the current catalogue to file as a JSON file.
        It should be possible to reread this file later and recreate this record and a complete archive."""
        self.guid = uuid.uuid4()  # a second save will have a different guid as the structure is mutable and this
        # ensures that each saved file is uniquely identifiable.
        filename = Path(getcwd()) / catalogue_name
        data = {
            # Todo If use original path then need to create dynamically the path to match
            #"OriginalPath": str(self.path),
            "date": str(dt.datetime.utcnow().isoformat()),
            "guid": str(self.guid),
            "segment_size_str" : self.str_segment_size,
            "segment_size_int" : self.int_segment_size,
            "version": self.version,
            "files": json.loads(self.entries.to_json()),
            # List of directories are derived from file paths
            # List of catalogues as GUID, the first will be this catalogue
        }
        with filename.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=4)

    def segment(self, size, catalogue_size):
        """
        For a catalogue will place each file onto a disc.
        This will overwrite the segments if carrie out repeatedly.
        :param size:
        :return:
        """
        # Deal with differing types of segment size
        self.str_segment_size = size
        new_size = interpret_disc_capacity(size)
        self.int_segment_size = new_size
        self.segment_size = new_size
        # Store the size of the catalogue
        self.catalogue_size = catalogue_size
        OVERHEAD = (
            500000 + catalogue_size
        )  # This is the number of bytes of overhead that will be used for size of iso file
        # TODO needs a method to deal more accruately with directory sizes
        FILE_OVERHEAD = (
            2048
        )  # This is the number of bytes of overhead this is allocated for each file in addition
        # to the actual contents of the file.  Needs to cover directory entries.
        min_size = OVERHEAD + FILE_OVERHEAD + next(iter(self.files())).size
        if new_size <= min_size:
            raise odarchiveError(f"Disc too small {new_size:,}, cannot fit first file on with overhead {min_size:,}.")

        count = OVERHEAD # Count the number of bytes used
        self.last_disc_number = 0
        for entry in self.files():
            size_on_disc = (
                (2048 + entry.size) // 2048
            ) * 2048 + FILE_OVERHEAD
            if (count + size_on_disc) >= self.segment_size:
                # If too big to fit file in segment then start a new disc
                count = OVERHEAD
                self.last_disc_number += 1
            # Only add
            entry.disc_num = self.last_disc_number
            count += size_on_disc
            if count > self.segment_size:
                # if file is too big to fit on a single disc with overhad
                raise odarchiveError(f"Disc too small {new_size:,}, cannot fit file {entry.filename} on disc {self.last_disc_number} with overhead {count:,}.")

    @property
    def is_segmented(self):
        return self.last_disc_number is not None

    def update(self, file_db):
        """
        Iterates a file entry database to get each entry and add to hash database
        """
        for entry in file_db.files():
            self.entries.add_hash_file(entry)

    def files(self, disc_num=None):
        """Extend class with a disc number segemtn"""
        for entry in self.entries.values():
            if disc_num is None:  # without a disc num specification return all files
                yield entry
            elif entry.disc_num == disc_num:  # only get entries for this disc_num
                yield entry

    def get_info(self, for_disc_num = None):
        """Returns summary information on an archive. Uses introspection"""
        count_files = 0
        size_files = 0
        disc_nums = set()
        entries_no_disc = 0
        largest_file = 0
        max_dir_length = 0
        longest_dir = ""
        dirs = set()
        for entry in self.files():
            count_files += 1
            size_files += entry.size
            if for_disc_num is None or for_disc_num == entry.disc_num:
                count_files += 1
                size_files += entry.size
                if self.is_segmented:
                    if entry.disc_num is None:
                        entries_no_disc += 1
                    else:
                        disc_nums |= {entry.disc_num}
                if entry.size > largest_file:
                    largest_file = entry.size
                # Each entry may have multiple directory entries
                for this_file in entry.filenames:
                    this_dir = PurePosixPath(this_file).parent
                    dirs = dirs | {this_dir}
                    length = len(Path(this_dir).parts) - 2
                    if length > max_dir_length:
                        longest_dir = this_dir.parent
                        max_dir_length = length
        # Format answer
        result = super().get_info()
        result += f"Data size       = {size_files:,} bytes\n"
        result += f"Is segmented    = {self.is_segmented}\n"
        if for_disc_num is None:
             result += f'>>>>>>>>> For all files in all discs <<<<<<<<<<<<<<<<\n'
        else:
            if self.is_segmented:  # Add information about disc size
                result += f'>>>>>>>>> Disc {for_disc_num} <<<<<<<<<<<<<<<<\n'
            else:
                result += f'>>>>>>>>> Error asking for disc {for_disc_num} but disc not segmented  <<<<<<<<<<<<<<<<\n'
        if self.is_segmented:  # Add information about disc size
            if isinstance(self.str_segment_size, str):  # Then can interpret text
                result += (
                    f"  Disc segment size = {self.str_segment_size}, {self.int_segment_size:,} bytes\n"
                )
            else:  # Can only write size
                result += f"  Disc segment size = {self.int_segment_size:,} bytes\n"
            result += f"  Catalogue size = {self.catalogue_size:,} bytes\n"
            result += f"  Number of discs = {self.last_disc_number+1:,}\n"
        if entries_no_disc > 0 and self.is_segmented:
            result += (
                f"  ERROR: {entries_no_disc} entries have not been allocated a disc number and should have been.\n"
            )
        result += f"Number of files = {count_files:,}\n"
        result += f"  Largest file  = {largest_file:,}\n"
        result += f"Number of dirs  = {len(dirs)}\n"
        result += f"Max dir depth   = {max_dir_length} (on source file system)\n"
        result += f" Dir =: {longest_dir}\n"
        if hasattr(self,'guid'):
            result += (
                f"guid = {self.guid}\n"
            )
        result += f"Database Version = {self.version}\n"
        return result
