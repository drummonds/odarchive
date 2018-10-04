"""This is an database of files.

It is based on a list of entries.

It is centred on the file system.  Each file has a separate entry  It can be enhanced.
This is a temporary structure and although can be preserved by pickle is not intended to have a long duration.
So it does not need versioning.

Things it doesn't do:

- Segment the database.  See hash_db
"""
from collections import OrderedDict


def do_hash(entry):
    """Make an easy parallel task"""
    entry.calculate_file_hash()

class AbstractFileDatabaseError(Exception):
    pass


class AbstractFileDatabase:
    """This is an abstract file database which is built from a source
    However doesn't actually have the mechanics to do the building."""

    def __init__(self, source):
        super().__init__()
        self.entries = OrderedDict()  # of FileEntry
        # from source build a list of files

    def files(self):
        for entry in self.entries.values():
            yield entry

    def print_files(self):
        for entry in self.files():
            print(entry)

    def __len__(self):
        return len(self.entries)

    def get_info(self):
        """Returns summary information on a file database. Uses introspection to collect statistics"""
        result = f"Number of entries = {len(self):,}\n"
        return result
