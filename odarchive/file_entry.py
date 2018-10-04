from enum import Enum
from mmap import mmap, ACCESS_READ
from pathlib import Path, PurePosixPath
from os import fsencode, lstat, readlink, stat_result

from stat import S_ISLNK, S_ISREG

from .consts import *


class FileEntryType(Enum):
    TYPE_FILE = 0
    TYPE_SYMLINK = 1


class FileEntry:
    """This represents each file stored.
    It is also meant to deal with:
        - both symlinks and files
        - Building a catalogue before you have the hashes for each file
    """

    def __init__(
        self, parent, filename, size=None, mtime=None, type=None, disc_num=None
    ):
        # In memory, "filename" should be an absolute Path
        self.parent = parent
        self.filename = filename
        self.size = size
        self.mtime = mtime
        self.type = type
        self._disc_num = None
        self.disc_num = disc_num

    @property
    def disc_num(self):
        if hasattr(self, "_disc_num"):
            return self._disc_num
        else:
            return None

    @disc_num.setter
    def disc_num(self, disc_num):
        if self.disc_num is None:
            self._disc_num = disc_num  # Can set it the first time

    def exists(self):
        return self.filename.is_file() or self.filename.is_symlink()

    def verify(self):
        current = FileEntry(self.parent, self.filename)
        return self == current

    def __eq__(self, other):
        """Weak would be stronger with hashes"""
        if isinstance(other, FileEntry):
            return (
                self.size == other.size
                and self.mtime == other.mtime
                and (self.type == other.type)
            )
        return super().__eq__(other)

    def update_attrs(self):
        s = lstat(str(self.filename))
        self.size, self.mtime = s.st_size, s.st_mtime

    def update_type(self):
        if self.filename.is_symlink():
            self.type = FileEntryType.TYPE_SYMLINK
        else:
            # Treat it as a file even if it's missing.
            self.type = FileEntryType.TYPE_FILE

    def update(self):
        self.update_attrs()
        self.update_type()

    def __str__(self):
        return str(self.filename)

    def __hash__(self):
        return hash(self.filename)

    @property
    def relative_path(self):
        """Returns relative path to parent directory"""
        return PurePosixPath(self.filename.relative_to(self.parent.path))

    def calculate_file_hash(self):
        if self.filename.is_file():
            if lstat(str(self.filename)).st_size > 0:
                with self.filename.open("rb") as f:
                    with mmap(f.fileno(), 0, access=ACCESS_READ) as m:
                        self.file_hash = HASH_FUNCTION(m).hexdigest()
            else:
                self.file_hash = EMPTY_FILE_HASH
        elif self.filename.is_symlink():
            # The link target will suffice as the "contents"
            target = readlink(str(self.filename))
            self.file_hash = HASH_FUNCTION(fsencode(target)).hexdigest()
