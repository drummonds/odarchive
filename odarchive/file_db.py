"""This is a database of files.

It is centred on the file system.  Each file has a separate entry  It can be enhanced.
This is a temporary structure and although can be preserved by pickle is not intended to have a long duration.
So it does not need versioning.


Things it doesn't do:

- Segment the database.  See hash_db
"""
from pathlib import Path
from os import lstat
from scandir import walk
from sys import stderr

from .abstract_file_db import AbstractFileDatabase
from .file_entry import FileEntry

def do_hash(entry):
    """Make an easy parallel task"""
    entry.calculate_file_hash()

class FileDatabase(AbstractFileDatabase):

    def __init__(self, path: Path):
        super().__init__(path)
        self.path = path.absolute()

    def _find_changes(self):
        """
        Walks the filesystem. Identifies noteworthy files -- those
        that were added, removed, or changed (size, mtime or type).

        Returns a 3-tuple of sets of FileEntry objects:
        [0] added files
        [1] removed files
        [2] modified files

        self.entries is not modified; this method only reports changes.
        Candidate for making parallel
        """
        added = set()
        modified = set()
        existing_files = set()
        for dirpath_str, _, filenames in walk(str(self.path)):
            dirpath = Path(dirpath_str)
            for filename in filenames:
                # Make the assumption the database is never in the path
                abs_filename = (dirpath / filename).absolute()
                if abs_filename in self.entries:
                    entry = self.entries[abs_filename]
                    existing_files.add(entry)
                    st = lstat(str(abs_filename))
                    if entry != st:
                        modified.add(entry)
                else:
                    entry = FileEntry(self, abs_filename)
                    entry.update_attrs()
                    added.add(entry)
        removed = set(self.entries.values()) - existing_files
        return added, removed, modified

    def update(self, this_path=None):
        """
        Walks the filesystem, adding and removing files from
        the database as appropriate.

        Returns a 3-tuple of sets of filenames:
        [0] added files
        [1] removed files
        [2] modified files
        """
        if this_path is None:
            this_path = self.path
        added, removed, modified = self._find_changes()
        for entry in added:
            entry.update()  # Calculate hash
            self.entries[entry.filename] = entry
        for entry in removed:
            del self.entries[entry.filename]
        # Entries will appear in 'modified' if the size, mtime or type
        # change. This will not be reliable over time (you need hashes to do that)
        # I've seen a lot of spurious mtime mismatches on vfat
        # filesystems (like on USB flash drives), so only report files
        # as modified if the hash changes.
        content_modified = set()
        for entry in modified:
            old_entry = entry
            entry.update()
            if entry != old_entry:
                content_modified.add(entry)
        return (
            {entry.filename for entry in added},
            {entry.filename for entry in removed},
            {entry.filename for entry in content_modified},
        )

    def status(self):
        added, removed, modified = self._find_changes()
        return (
            {entry.filename for entry in added},
            {entry.filename for entry in removed},
            {entry.filename for entry in modified},
        )

    def verify(self, verbose_failures=False):
        """
        Calls each FileEntry's verify method to make sure that
        nothing has changed on disc.

        Returns a 2-tuple of sets of filenames:
        [0] modified files
        [1] removed files
        """
        modified = set()
        removed = set()
        count = len(self.entries)
        # TODO: Track number of bytes hashed instead of number of files
        # This will act as a more meaningful progress indicator
        i = 0
        for i, entry in enumerate(self.entries.values(), 1):
            if entry.exists():
                if entry.verify():
                    entry.update_attrs()
                else:
                    if verbose_failures:
                        stderr.write(
                            "\r{} failed hash verification\n".format(entry.filename)
                        )
                    modified.add(entry.filename)
            else:
                removed.add(entry.filename)
                if verbose_failures:
                    stderr.write("\r{} is missing\n".format(entry.filename))
            stderr.write("\rChecked {} of {} files".format(i, count))
        if i:
            stderr.write("\n")
        return modified, removed

    def file_paths(self):
        for entry in self.entries.values():
            yield str(entry.relative_path)

    def get_info(self):
        """Returns summary information on a file database. Uses introspection to collect statistics"""
        count_files = 0
        size_files = 0
        for entry in self.files():
            count_files += 1
            size_files += entry.size
        # Collect some stats on directory paths. This is useful to seeing if the data paths will be
        # truncated on a Joliet file path
        max_length = 0
        longest_dir = ""
        dirs = set()
        for this_dir in self.entries:
            dirs = dirs | {this_dir.parent}
            length = len(Path(this_dir).parts) - 2
            if length > max_length:
                longest_dir = this_dir.parent
                max_length = length
        # Format answer
        result = super().get_info()
        result += f"Data size       = {size_files:,} bytes\n"
        result += f"Number of dirs  = {len(dirs)}\n"
        result += f"Max dir depth   = {max_length} (on source file system)\n"
        result += f" Dir =: {longest_dir}\n"
        return result

    # Single Threaded version
    def calculate_file_hash(self, verbose=False):
        count = 0
        for entry in self.entries.values():
            entry.calculate_file_hash()
            count += 1
            if verbose:
                if (count % 1000) == 0:
                    print(f" {count}", flush=True)
                elif (count % 10) == 0:
                    print('.', end='', flush=True)
        if verbose and not ((count % 1000) == 0):  # Close off line if part finished
            print(f" {count}", flush=True)

