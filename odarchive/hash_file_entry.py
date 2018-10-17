import datetime as dt
from collections import OrderedDict
from enum import Enum
import json
from mmap import mmap, ACCESS_READ
from pathlib import Path, PurePosixPath
from os import fsdecode, fsencode, getcwd, lstat, readlink, stat_result
from os.path import normpath
import time

import dill
from stat import S_ISLNK, S_ISREG

from .consts import *


from .tools import mangle_file_for_iso9660, mangle_dir_for_iso9660


class HashFileEntries(OrderedDict):
    """This is a collection of HashFileEntries
    In fact you can only create a new HashFileEntry with reference to a collecition
    """
    @classmethod
    def create(cls, iso_path_root, path):
        """ Did this to get around issue with loading pickled object that is derived from an OrderedDict"""
        result = cls()
        result.iso_path_root = iso_path_root
        result.path = path
        return result

    def entry_to_path(self, this_entry):
        """ Converts a fileEntry object to an ISO path via relative path

        To reverse use orig_root / self.relative_path
        """
        return self.iso_path_root / this_entry.relative_path

    def add_hash_file(self, this_entry, disc_num=None, catalogue_num=None):
        """If the hash file already exists then this will not create a new entry but simply
        append this file to the HashFileEntry.

        this_file is a FileEntry
        """
        #  Does it already exist
        try:
            existing_entry = self[this_entry.file_hash]  # Look up by File hash
            if existing_entry.has_file_path(
                self.entry_to_path(this_entry)
            ):  # Already is entered then ignore otherwise add to list of directories
                pass
            else:
                existing_entry.add_path(self.entry_to_path(this_entry))
        except AttributeError:  # file_hash is not yet defined
            raise odarchiveError(
                f"Adding {self.entry_to_path(this_entry)} with no file_hash - run calculate_file_hash()"
            )
        except KeyError:  # Adding a new entry to the Dictionary
            if this_entry.file_hash:
                self[this_entry.file_hash] = HashFileEntry(
                    self,
                    this_entry.file_hash,
                    self.entry_to_path(this_entry),
                    size=this_entry.size,
                    mtime=this_entry.mtime,
                    catalogue_num=catalogue_num,
                    disc_num=this_entry.disc_num,
                )
            else:  # Adding a file without a hash must be an error
                raise odarchiveError(
                    f"Adding {self.entry_to_path(this_entry)} with no Hash - probable programming error"
                )

    def AddHashFileInAnotherCatalogue(
        self, file_hash, filename, size=None, mtime=None, file_type=None, disc_num=None
    ):
        """If the hash file already exists then this will change the entry to note that it is stored
        in a prior catalogue.
        """
        pass

    def sort(self):
        """Sort dictionary so that when it is written out by a json method it all works"""
        # # dictionary sorted by length of the key string
        # >> > OrderedDict(sorted(d.items(), key=lambda t: len(t[0])))
        # OrderedDict([('pear', 1), ('apple', 4), ('orange', 2), ('banana', 3)])
        pass

    def to_json(self):
        header = "{\n"
        result = ""
        footer = "}\n"
        for i, entry in enumerate(self.values()):
            if i:
                result += " , "  # Can;t have trailing comma
            result += entry.to_json_entry() + "\n"
        return header + result + footer

    def dir_entries(self, disc_num=None):
        """Iterate over all files in the hash entry list and build a dictionary of all of them"""
        result = {}

        def update_dir_list(udf_path):
            nonlocal result
            if str(udf_path) not in result:
                # Make sure parent is in
                if len(udf_path.parts) > 2:  # Has parent
                    update_dir_list(
                        udf_path.parent
                    )  # Recursive parent traversal to make sure every
                    # level of directory is included.
                result[str(udf_path)] = ""

        for entry in self.values():
            if disc_num is None or disc_num == entry.disc_num:
                update_dir_list(
                    entry.udf_absolute_path.parent
                )  # Only add parent but do it recursively
            # else Do not add this directory to this entry
        return result


class HashFileEntry:
    """This represents a single duplicated file.  In can either be in this catalogue or
    in another catalogue.  You cannot create an entry without know the hash of the file.

    The filenames of each entry and duplicate are stored in a filenames dictionary
    """

    def __init__(
        self,
        parent,
        file_hash,
        filename,
        size=None,
        mtime=None,
        disc_num=None,
        catalogue_num=None,
    ):
        # In memory, "filename" should be a relative UDF Path
        self.parent = parent  # eg a HashFileEntries
        self.filenames = {
            str(filename): {}
        }  # a UDF absolute path which is stored on a blank catalogue
        self.size = size
        self.mtime = mtime
        self.file_hash = file_hash
        self._disc_num = None
        self.disc_num = disc_num
        self.catalogue_num = (
            catalogue_num
        )  # If None or 0 then in this catalogue otherwise in another catalogue
        #  You will need to look up the catalogue number to the GUID of the cataloge at the start of the catalogue

    @property
    def filename(self):
        """This represents the filename on disc of the hash file.  There may be many filenames eg copies, links
        but only one will be stored on disc"""
        return PurePosixPath(next(iter(self.filenames.keys())))

    @property
    def disc_num(self):
        if hasattr(self, "_disc_num"):
            return self._disc_num
        else:
            return None

    @disc_num.setter
    def disc_num(self, disc_num):
        self._disc_num = disc_num  # Rely on Archive level lock for overwriting

    def __str__(self):
        return f"{self.filename}, {self.hash}"

    @property
    def file_system_path(self):
        """Returns native files system absolute path"""
        return PurePosixPath(self.parent.path) / self.relative_filename

    @property
    def udf_absolute_path(self):
        """Given a UDF media (which might be 1..n) this then returns the absolute path on that media"""
        return self.parent.iso_path_root / self.filename

    @property
    def relative_filename(self):
        """returns the data part of the path without /DATA prefix"""
        return PurePosixPath(self.filename.relative_to(self.parent.iso_path_root))

    @property
    def iso9660_path(self):
        # Assume PlainBuild UDF ie written in one pass not incrementally ie suffix is ";1"
        # TODO do folding so that if the iso9660_path has been already used another is used.
        # Needs to be done through parent as the parent controls the restart of reusage cache
        file_start = self.parent.iso_path_root / self.filename
        mangled_dirs = [
            mangle_dir_for_iso9660(part, 3) for part in file_start.parent.parts
        ]
        mangled_dirs[0] = mangled_dirs[0][1:]  # Get rid of leading underscore
        mangled = (
            mangle_file_for_iso9660(str(file_start.stem), 1)[0]
            + "."
            + mangle_file_for_iso9660(str(file_start.suffix)[1:], 1)[0]
        )

        return "/".join(mangled_dirs) + "/" + mangled + ";1"

    def to_json_entry(self):
        """Returns a string which is the entry in an object
        """
        filename_list = ""
        for i, filename in enumerate(self.filenames):
            if i:
                filename_list += ", "
            filename_list += f'"{filename}" : null'
        if self.disc_num is not None:  # 0 is a valid disc_num
            disc_num = f'    "disc_num" : {self.disc_num},\n'
        else:
            disc_num = ""
        return (
            f'"{self.file_hash}"'
            + ": {\n"
            + '    "filenames" : {\n'
            + filename_list
            + "    },"
            + disc_num
            + f'    "size" : {self.size},\n'
            + f'    "mtime" : "{dt.datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%dT%H:%M:%S")}"\n'
            + "}\n"
        )

    def add_path(self, this_path):
        self.filenames[str(this_path)] = {}

    def has_file_path(self, this_path):
        """A has file entry has multiple paths this tests if a UDF path has been stored."""
        # TODO should probably test UDF relative path
        try:
            a = self.filenames[str(this_path)]
            return True
        except KeyError:
            return False


def iso9660_dir(this_dir):
    """
    A function to convert a UDF full path string to an ISO 9660 V3 compliant version.

    Parameters:
     this_dir - string UDF file name
    Returns:
     The truncated and translated name suitable for the ISO interchange level
     specified.
    """
    mangled_dirs = [mangle_dir_for_iso9660(part, 3) for part in Path(this_dir).parts]
    mangled_dirs[0] = mangled_dirs[0][1:]  # Get rid of leading underscore
    result = "/".join(mangled_dirs)
    if result == "":
        result = "/"
    return result
