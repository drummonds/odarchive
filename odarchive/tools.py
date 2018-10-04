#!/usr/bin/python3

# Copyright (C) 2017-2018  Chris Lalancette <clalancette@gmail.com>

# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation;
# version 2.1 of the License.

# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""
A drop-in replacement program for the 'genisoimage' executable that uses
PyCdlib under the hood.
"""

from __future__ import print_function

import argparse
import collections
import fileinput
import fnmatch
import os
import re
import sys
import time

try:
    from cStringIO import StringIO as BytesIO
except ImportError:
    from io import BytesIO

import pycdlib

################################ MURMER3 HASH FUNCTIONS ##############################

if sys.version_info > (3, 0):

    def xrange(a, b, c):
        """
        An xrange that works for Python 3.
        """
        return range(a, b, c)

    def xencode(x):
        """
        A version of encode that works for bytes, bytearrays, or strings.
        """
        if isinstance(x, (bytearray, bytes)):
            return x
        return x.encode()


else:

    def xencode(x):
        """
        The identity version of xencode for Python 2.
        """
        return x


def mm3hash(key, seed=0x0):
    """ Implements 32bit murmur3 hash. """

    key = bytearray(xencode(key))

    def fmix(h):
        """
        A function to mix h.
        """
        h ^= h >> 16
        h = (h * 0x85ebca6b) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0xc2b2ae35) & 0xFFFFFFFF
        h ^= h >> 16
        return h

    length = len(key)
    nblocks = int(length / 4)

    h1 = seed

    c1 = 0xcc9e2d51
    c2 = 0x1b873593

    # body
    for block_start in xrange(0, nblocks * 4, 4):
        # ??? big endian?
        k1 = (
            key[block_start + 3] << 24
            | key[block_start + 2] << 16
            | key[block_start + 1] << 8
            | key[block_start + 0]
        )

        k1 = (c1 * k1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        k1 = (c2 * k1) & 0xFFFFFFFF

        h1 ^= k1
        h1 = (h1 << 13 | h1 >> 19) & 0xFFFFFFFF  # inlined ROTL32
        h1 = (h1 * 5 + 0xe6546b64) & 0xFFFFFFFF

    # tail
    tail_index = nblocks * 4
    k1 = 0
    tail_size = length & 3

    if tail_size >= 3:
        k1 ^= key[tail_index + 2] << 16
    if tail_size >= 2:
        k1 ^= key[tail_index + 1] << 8
    if tail_size >= 1:
        k1 ^= key[tail_index + 0]

    if tail_size > 0:
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    # finalization
    unsigned_val = fmix(h1 ^ length)
    if unsigned_val & 0x80000000 == 0:
        return unsigned_val

    return -((unsigned_val ^ 0xFFFFFFFF) + 1)


def mm3hashfromfile(filename):
    """
    A function to generate a Murmur3 hash given a filename.
    """
    with open(filename, "rb") as infp:
        done = False
        seed = 0
        while not done:
            data = infp.read(32 * 1024)
            if len(data) < 32 * 1024:
                # EOF
                done = True
            seed = mm3hash(data, seed)

    return seed


################################ HELPER FUNCTIONS ##############################


def truncate_basename(basename, iso_level, is_dir):
    """
    A function to truncate a basename and make it conformant to the passed-in
    ISO interchange level.

    Parameters:
     basename - The initial basename to truncate and translate
     iso_level - The ISO interchange level to follow when truncating/translating
     is_dir - Whether this is a directory or a file
    Returns:
     The truncated and translated name suitable for the ISO interchange level
     specified.
    """
    if iso_level == 4:
        # ISO level 4 allows "anything", so just return the original.
        return basename

    if iso_level == 1:
        maxlen = 8
    else:
        maxlen = 31 if is_dir else 30

    # For performance reasons, we first truncate the string to the length
    # allowed.  Second, ISO9660 Levels 1, 2, and 3 require all uppercase names,
    # so we uppercase it.
    valid_base = basename[:maxlen].upper()

    # Finally, ISO9660 requires only uppercase letters, 0-9, and underscore.
    # Translate any non-compliant characters to underscore and return that.
    return re.sub("[^A-Z0-9_]{1}", r"_", valid_base)


def mangle_file_for_iso9660(orig, iso_level):
    """
    A function to take a regular Unix-style filename (including extension) and
    produce a tuple consisting of an ISO9660-valid basename and an ISO9660-valid
    extension.

    Parameters:
     orig - The original filename
     iso_level - The ISO interchange level to conform to
    Returns:
     A tuple where the first entry is the ISO9660-compliant basename and where
     the second entry is the ISO9660-compliant extension.
    """
    # ISO9660 has a lot of restrictions on what valid names are.  Here, we mangle
    # the names to conform to those rules.  In particular, the rules for filenames are:
    # 1.  Filenames can only consist of d-characters or d1-characters; these are defined
    #     in the Appendix as: 0-9A-Z_
    # 2.  Filenames look like:
    #     - zero or more d-characters (filename)
    #     - separator 1 (.)
    #     - zero or more d-characters (extension)
    #     - separate 2 (;)
    #     - version, between 0 and 32767
    # If the filename contains zero characters, then the extension must contain at least
    # one character, and vice versa.
    # 3.  If this is iso level one, then the length of the filename cannot exceed 8 and
    #     the length of the extension cannot exceed 3.  In levels 2 and 3, the length of
    #     the filename+extension cannot exceed 30.
    #
    # This function takes any valid Unix filename and converts it into one that is allowed
    # by the above rules.  It does this by substituting _ for any invalid characters in
    # the filename, and by shortening the name to a form of aaa_xxxx.eee;1 (if necessary).
    # The aaa is always the first three characters of the original filename; the xxxx is
    # the next number in a sequence starting from 0.

    valid_ext = ""
    splitter = orig.split(".")
    if iso_level == 4:
        # A level 4 ISO allows 'anything', so just return the original.
        if len(splitter) == 1:
            return orig, valid_ext

        ext = splitter[-1]
        return orig[: len(orig) - len(ext) - 1], ext

    if len(splitter) == 1:
        # No extension specified, leave ext empty
        basename = orig
    else:
        ext = splitter[-1]
        basename = orig[: len(orig) - len(ext) - 1]

        # If the extension is empty, too long (> 3), or contains any illegal characters,
        # we treat it as part of the basename instead
        extlen = len(ext)
        if extlen == 0 or extlen > 3:
            valid_ext = ""
            basename = orig
        else:
            tmpext = ext.upper()
            valid_ext, numsub = re.subn("[^A-Z0-9_]{1}", r"_", tmpext)
            if numsub > 0:
                valid_ext = ""
                basename = orig

    # All right, now we have the basename of the file, and (optionally) an extension.
    return truncate_basename(basename, iso_level, False), valid_ext + ";1"


def mangle_dir_for_iso9660(orig, iso_level):
    """
    A function to take a regular Unix-style directory name and produce an
    ISO9660-valid directory name.

    Parameters:
     orig - The original filename
     iso_level - The ISO interchange level to conform to
    Returns:
     An ISO9660-compliant directory name.
    """
    # ISO9660 has a lot of restrictions on what valid directory names are.  Here, we mangle
    # the names to conform to those rules.  In particular, the rules for dirnames are:
    # 1.  Filenames can only consist of d-characters or d1-characters; these are defined
    #     in the Appendix as: 0-9A-Z_
    # 2.  If this is ISO level one, then directory names consist of no more than 8 characters
    # This function takes any valid Unix directory name and converts it into one that is
    # allowed by the above rules.  It does this by substituting _ for any invalid character
    # in the directory name, and by shortening the name to a form of aaaaxxx (if necessary).
    # The aaa is always the first three characters of the original filename; the xxxx is
    # the next number in a sequence starting from 0.

    return truncate_basename(orig, iso_level, True)


def match_entry_to_list(pattern_list, entry):
    """
    A function to match a string to a list of filename patterns.  If any of them
    match, returns True, otherwise, returns False.

    Parameters:
     pattern_list - The list of filename patterns to check against
     entry - The string to check
    Returns:
     True if the string matches any of the filename patterns, False otherwise.
    """
    for pattern in pattern_list:
        if fnmatch.fnmatch(entry, pattern):
            return True

    return False


def parse_file_list(thelist):
    """
    A function to take a list of filenames, open each one for reading, and
    yield each of the lines in the file.

    Parameters:
     thelist - The list of files to open
    Returns:
     Nothing.
    """
    for f in thelist:
        with open(f, "r") as infp:
            for line in infp.xreadlines():
                yield line.rstrip()


def build_joliet_path(root, name):
    """
    A function to build a complete, valid Joliet path based on a root directory
    and a name.

    Parameters:
     root - The root directory name
     name - The name for the Joliet entry
    Returns:
     A valid, absolute Joliet filename.
    """
    if root and root[0] == "/":
        root = root[1:]
    intermediate = ""
    for intdir in root.split("/"):
        if not intdir:
            continue

        intermediate += "/" + intdir[:64]

    return intermediate + "/" + name[:64]


def build_udf_path(root, name):
    """
    A function to build a complete, valid UDF path based on a root directory
    and a name.

    Parameters:
     root - The root directory name.
     name - The name for the UDF entry.
    Returns:
     A valid, absolute UDF filename.
    """
    if root and root[0] == "/":
        root = root[1:]
    intermediate = ""
    for intdir in root.split("/"):
        if not intdir:
            continue

        intermediate += "/" + intdir

    return intermediate + "/" + name


class EltoritoEntry(object):
    """
    A class that represents a single El Torito entry on the ISO.  There may be
    more than one of these per-ISO, so each one is tracked separately.
    """

    __slots__ = (
        "bootfile_orig",
        "bootfile_parts",
        "mediatype",
        "boot",
        "load_size",
        "load_seg",
        "boot_info_table",
        "bootfile_iso_path",
        "dirlevel",
    )

    def __init__(self):
        self.bootfile_orig = ""
        self.bootfile_parts = []
        self.mediatype = "floppy"
        self.boot = True
        self.load_size = 0
        self.load_seg = 0
        self.boot_info_table = False
        self.bootfile_iso_path = ""
        self.dirlevel = None

    def set_bootfile(self, bootfile):
        """
        A method to set the bootfile for this El Torito entry.

        Parameters:
         bootfile - The bootfile to set for this El Torito entry
        Returns:
         Nothing.
        """
        self.bootfile_orig = bootfile
        self.bootfile_parts = bootfile.split("/")


def parse_arguments():
    """
    A function to parse all of the arguments passed to the executable.  Note
    that the set of arguments accepted is intentionally compatible with
    genisoimage.  Also note that this executable does not support all flags
    below, and will silently ignore ones it doesn't understand.  This is to
    keep maximum compatibility with genisoimage.

    Parameters:
     None.
    Returns:
     An ArgumentParser object with the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-nobak", "-no-bak", help="Do not include backup files", action="store_true"
    )
    parser.add_argument(
        "-abstract", help="Set Abstract filename", action="store", default=""
    )
    parser.add_argument(
        "-appid", "-A", help="Set Application ID", action="store", default=""
    )
    parser.add_argument(
        "-biblio", help="Set Bibliographic filename", action="store", default=""
    )
    parser.add_argument(
        "-cache-inodes",
        help="Cache inodes (needed to detect hard links)",
        action="store_true",
    )
    parser.add_argument(
        "-no-cache-inodes",
        help="Do not cache inodes (if filesystem has no unique unides)",
        action="store_true",
    )
    parser.add_argument(
        "-check-oldnames",
        help="Check all imported ISO9660 names from old session",
        action="store_true",
    )
    parser.add_argument(
        "-check-session",
        help="Check all ISO9660 names from previous session",
        action="store",
    )
    parser.add_argument(
        "-copyright", help="Set Copyright filename", action="store", default=""
    )
    parser.add_argument("-debug", help="Set debug flag", action="store_true")
    parser.add_argument(
        "-eltorito-boot", "-b", help="Set El Torito boot image name", action="store"
    )
    parser.add_argument(
        "-efi-boot", "-e", help="Set EFI boot image name", action="append"
    )
    parser.add_argument(
        "-eltorito-alt-boot",
        help="Start specifying alternative El Torito boot parameters",
        action="append_const",
        const=True,
    )
    parser.add_argument(
        "-sparc-boot", "-B", help="Set sparc boot image names", action="store"
    )
    parser.add_argument(
        "-sunx86-boot", help="Set sunx86 boot image names", action="store"
    )
    parser.add_argument(
        "-generic-boot", "-G", help="Set generic boot image name", action="store"
    )
    parser.add_argument(
        "-sparc-label", help="Set sparc boot disk label", action="store", nargs=2
    )
    parser.add_argument(
        "-sunx86-label", help="Set sunx86 boot disk label", action="store", nargs=2
    )
    parser.add_argument(
        "-eltorito-catalog",
        "-c",
        help="Set El Torito boot catalog name",
        action="store",
        default=None,
    )
    parser.add_argument(
        "-cdrecord-params", "-C", help="Magic parameters from cdrecord", action="store"
    )
    parser.add_argument(
        "-omit-period",
        "-d",
        help="Omit trailing periods from filenames (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-dir-mode", help="Make the mode of all directories this mode", action="store"
    )
    parser.add_argument(
        "-disable-deep-relocation",
        "-D",
        help="Disable deep directory relocation (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-file-mode", help="Make the mode of all plain files this mode", action="store"
    )
    parser.add_argument(
        "-follow-links", "-f", help="Follow symbolic links", action="store_true"
    )
    parser.add_argument(
        "-gid", help="Make the group owner of all files this gid", action="store"
    )
    parser.add_argument(
        "-graft-points",
        help="Allow to use graft points for filenames",
        action="store_true",
    )
    parser.add_argument(
        "-root",
        help="Set root directory for all new files and directories",
        action="store",
    )
    parser.add_argument(
        "-old-root",
        help="Set root directory in previous session this is searched for files",
        action="store",
    )
    parser.add_argument("-help", help="Print option help", action="help")
    parser.add_argument(
        "-hide", help="Hide ISO9660/RR file", action="append", default=[]
    )
    parser.add_argument(
        "-hide-list",
        help="File with list of ISO9660/RR files to hide",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-hidden",
        help="Set hidden attribute on ISO9660 file",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-hidden-list",
        help="File with list of ISO9660 files with hidden attribute",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-hide-joliet", help="Hide Joliet file", action="append", default=[]
    )
    parser.add_argument(
        "-hide-joliet-list",
        help="File with list of Joliet files to hide",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-hide-joliet-trans-tbl",
        help="Hide TRANS.TBL from Joliet tree",
        action="store_true",
    )
    parser.add_argument(
        "-hide-rr-moved",
        help="Rename RR_MOVED to .rr_moved in Rock Ridge tree",
        action="store_true",
    )
    parser.add_argument("-gui", help="Switch behavior for GUI", action="store_true")
    parser.add_argument("-i", help="No longer supported", action="store")
    parser.add_argument(
        "-input-charset",
        help="Local input charset for file name conversion",
        action="store",
    )
    parser.add_argument(
        "-output-charset",
        help="Output charset for file name conversion",
        action="store",
    )
    parser.add_argument(
        "-iso-level",
        help="Set ISO9660 conformance level (1..3) or 4 for ISO9660 version 2",
        action="store",
        default=1,
        type=int,
        choices=range(1, 5),
    )
    parser.add_argument(
        "-joliet",
        "-J",
        help="Generate Joliet directory information",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-joliet-long",
        help="Allow Joliet file names to be 103 Unicode characters",
        action="store_true",
    )
    parser.add_argument(
        "-jcharset",
        help="Local charset for Joliet directory information",
        action="store",
    )
    parser.add_argument(
        "-full-iso9660-filenames",
        "-l",
        help="Allow full 31 character filenames for ISO9660 names",
        action="store_true",
    )
    parser.add_argument(
        "-max-iso9660-filenames",
        help="Allow 37 character filenames for ISO9660 names (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-allow-limited-size",
        help="Allow different file sizes in ISO9660/UDF on large files",
        action="store_true",
    )
    parser.add_argument(
        "-allow-leading-dots",
        "-ldots",
        "-L",
        help="Allow ISO9660 filenames to start with '.' (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-log-file", help="Re-direct messages to LOG_FILE", action="store"
    )
    parser.add_argument(
        "-exclude", "-m", help="Exclude file name", action="append", default=[]
    )
    parser.add_argument(
        "-exclude-list",
        help="File with list of file names to exclude",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-pad", help="Pad output to a multiple of 32k (default)", action="store_true"
    )
    parser.add_argument(
        "-no-pad", help="Do not pad output to a multiple of 32k", action="store_true"
    )
    parser.add_argument(
        "-prev-session",
        "-M",
        help="Set path to previous session to merge",
        action="store",
    )
    parser.add_argument("-dev", help="Device", action="store")
    parser.add_argument(
        "-omit-version-number",
        "-N",
        help="Omit version number from ISO9660 filename (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-new-dir-mode", help="Mode used when creating new directories", action="store"
    )
    parser.add_argument(
        "-force-rr",
        help="Inhibit automatic Rock Ridge detection for previous session",
        action="store_true",
    )
    parser.add_argument(
        "-no-rr",
        help="Inhibit reading of Rock Ridge attributes from previous session",
        action="store_true",
    )
    parser.add_argument(
        "-no-split-symlink-components",
        help="Inhibit splitting symlink components",
        action="store_true",
    )
    parser.add_argument(
        "-no-split-symlink-fields",
        help="Inhibit splitting symlink fields",
        action="store_true",
    )
    parser.add_argument("-output", "-o", help="Set output file name", action="store")
    parser.add_argument(
        "-path-list", help="File with list of pathnames to process", action="store"
    )
    parser.add_argument(
        "-preparer", "-p", help="Set Volume preparer", action="store", default=""
    )
    parser.add_argument(
        "-print-size",
        help="Print estimated filesystem size and exit",
        action="store_true",
    )
    parser.add_argument(
        "-publisher", "-P", help="Set Volume publisher", action="store", default=""
    )
    parser.add_argument("-quiet", help="Run quietly", action="store_true")
    parser.add_argument(
        "-rational-rock",
        "-r",
        help="Generate rationalized Rock Ridge directory information",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-rock",
        "-R",
        help="Generate Rock Ridge directory information",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-sectype",
        "-s",
        help="Set output sector type to e.g. data/xa1/raw",
        action="store",
    )
    parser.add_argument(
        "-alpha-boot",
        help="Set alpha boot image name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-hppa-cmdline",
        help="Set hppa boot command line (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-hppa-kernel-32",
        help="Set hppa 32-bit image name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-hppa-kernel-64",
        help="Set hppa 64-bit image name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-hppa-bootloader",
        help="Set hppa boot loader file name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-hppa-ramdisk",
        help="Set hppa ramdisk file name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-mips-boot",
        help="Set mips boot image name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-mipsel-boot",
        help="Set mipsel boot image name (relative to image root)",
        action="store",
    )
    parser.add_argument(
        "-jigdo-jigdo",
        help="Produce a jigdo .jigdo file as well as the .iso",
        action="store",
    )
    parser.add_argument(
        "-jigdo-template",
        help="Produce a jigdo .template file as well as the .iso",
        action="store",
    )
    parser.add_argument(
        "-jigdo-min-file-size",
        help="Minimum size for a file to be listed in the jigdo file",
        action="store",
    )
    parser.add_argument(
        "-jigdo-force-md5",
        help="Pattern(s) where files MUST match an externally-supplied MD5Sum",
        action="store",
    )
    parser.add_argument(
        "-jigdo-exclude",
        help="Pattern(s) to exclude from the jigdo file",
        action="store",
    )
    parser.add_argument(
        "-jigdo-map",
        help="Pattern(s) to map paths (e.g. Debian=/mirror/debian)",
        action="store",
    )
    parser.add_argument(
        "-md5-list",
        help="File containing MD5 sums of the files that should be checked",
        action="store",
    )
    parser.add_argument(
        "-jigdo-template-compress",
        help="Choose to use gzip or bzip2 compression for template data; default is gzip",
        action="store",
    )
    parser.add_argument(
        "-checksum_algorithm_iso",
        help="Specify the checksum types desired for the output image",
        action="store",
    )
    parser.add_argument(
        "-checksum_algorithm_template",
        help="Specify the checksum types desired for the output jigdo template",
        action="store",
    )
    parser.add_argument(
        "-sort",
        help="Sort file content locations according to rules in FILE",
        action="store",
    )
    parser.add_argument(
        "-split-output",
        help="Split output into files of approx. 1GB size",
        action="store_true",
    )
    parser.add_argument(
        "-stream-file-name",
        help="Set the stream file ISO9660 name (incl. version)",
        action="store",
    )
    parser.add_argument(
        "-stream-media-size",
        help="Set the size of your CD media in sectors",
        action="store",
    )
    parser.add_argument("-sysid", help="Set System ID", action="store", default="")
    parser.add_argument(
        "-translation-table",
        "-T",
        help="Generate translation tables for systems that don't understand long filenames",
        action="store_true",
    )
    parser.add_argument(
        "-table-name", help="Translation table file name", action="store"
    )
    parser.add_argument(
        "-ucs-level", help="Set Joliet UCS level (1..3)", action="store"
    )
    parser.add_argument("-udf", help="Generate UDF file system", action="store_true")
    parser.add_argument(
        "-dvd-video",
        help="Generate DVD-Video compliant UDF file system",
        action="store_true",
    )
    parser.add_argument(
        "-uid", help="Make the owner of all files this uid", action="store"
    )
    parser.add_argument(
        "-untranslated-filenames",
        "-U",
        help="Allow Untranslated filenames (for HPUX & AIX - violates ISO9660).  Forces -l, -d, -N, -allow-leading-dots, -relaxed-filenames, -allow-lowercase, -allow-multidot",
        action="store_true",
    )
    parser.add_argument(
        "-relaxed-filenames",
        help="Allow 7 bit ASCII except lower case characters (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-no-iso-translate",
        help="Do not translate illegal ISO characters '~', '-', and '#' (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-allow-lowercase",
        help="Allow lower case characters in addition to the current character set (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-allow-multidot",
        help="Allow more than one dot in filenames (e.g. .tar.gz) (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-use-fileversion", help="Use fileversion # from filesystem", action="store"
    )
    parser.add_argument("-verbose", "-v", help="Verbose", action="store_true")
    parser.add_argument(
        "-version", help="Print the current version", action="store_true"
    )
    parser.add_argument(
        "-volid", "-V", help="Set Volume ID", action="store", default=""
    )
    parser.add_argument("-volset", help="Set Volume set ID", action="store", default="")
    parser.add_argument(
        "-volset-size", help="Set Volume set size", action="store", default=1
    )
    parser.add_argument(
        "-volset-seqno",
        help="Set Volume set sequence number",
        action="store",
        default=1,
    )
    parser.add_argument(
        "-old-exclude",
        "-x",
        help="Exclude file name (deprecated)",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-hard-disk-boot",
        help="Boot image is a hard disk image",
        action="append_const",
        const=True,
    )
    parser.add_argument(
        "-no-emul-boot",
        help="Boot image is a 'no emulation' image",
        action="append_const",
        const=True,
    )
    parser.add_argument(
        "-no-boot", help="Boot image is not bootable", action="append_const", const=True
    )
    parser.add_argument(
        "-boot-load-seg", help="Set load segment for boot image", action="append"
    )
    parser.add_argument(
        "-boot-load-size", help="Set number of load sectors", action="append"
    )
    parser.add_argument(
        "-boot-info-table",
        help="Patch boot image with info table",
        action="append_const",
        const=True,
    )
    parser.add_argument(
        "-XA", help="Generate XA directory attributes", action="store_true"
    )
    parser.add_argument(
        "-xa", help="Generate rationalized XA directory attributes", action="store_true"
    )
    parser.add_argument(
        "-transparent-compression",
        "-z",
        help="Enable transparent compression of files",
        action="store_true",
    )
    parser.add_argument("-hfs-type", help="Set HFS default TYPE", action="store")
    parser.add_argument("-hfs-creator", help="Set HFS default CREATOR", action="store")
    parser.add_argument(
        "-apple", "-g", help="Add Apple ISO9660 extensions", action="store_true"
    )
    parser.add_argument(
        "-hfs", "-h", help="Create ISO9660/HFS hybrid", action="store_true"
    )
    parser.add_argument(
        "-map", "-H", help="Map file extensions to HFS TYPE/CREATOR", action="store"
    )
    parser.add_argument(
        "-magic", help="Magic file for HFS TYPE/CREATOR", action="store"
    )
    parser.add_argument(
        "-probe", help="Probe all files for Apple/Unix file types", action="store_true"
    )
    parser.add_argument(
        "-mac-name",
        help="Use Macintosh name for ISO9660/Joliet/RockRidge file name",
        action="store_true",
    )
    parser.add_argument(
        "-no-mac-files",
        help="Do not look for Unix/Mac files (deprecated)",
        action="store_true",
    )
    parser.add_argument(
        "-boot-hfs-file", help="Set HFS boot image name", action="store"
    )
    parser.add_argument(
        "-part", help="Generate HFS partition table", action="store_true"
    )
    parser.add_argument(
        "-cluster-size",
        help="Cluster size for PC Exchange Macintosh files",
        action="store",
    )
    parser.add_argument("-auto", help="Set HFS AutoStart file name", action="store")
    parser.add_argument(
        "-no-desktop",
        help="Do not create the HFS (empty) Desktop files",
        action="store_true",
    )
    parser.add_argument("-hide-hfs", help="Hide HFS file", action="append", default=[])
    parser.add_argument(
        "-hide-hfs-list", help="List of HFS files to hide", action="append", default=[]
    )
    parser.add_argument(
        "-hfs-volid", help="Volume name for the HFS partition", action="store"
    )
    parser.add_argument(
        "-icon-position", help="Keep HFS icon position", action="store_true"
    )
    parser.add_argument("-root-info", help="finderinfo for root folder", action="store")
    parser.add_argument(
        "-input-hfs-charset",
        help="Local input charset for HFS file name conversion",
        action="store",
    )
    parser.add_argument(
        "-output-hfs-charset",
        help="Output charset for HFS file name conversion",
        action="store",
    )
    parser.add_argument(
        "-hfs-unlock", help="Leave HFS volume unlocked", action="store_true"
    )
    parser.add_argument(
        "-hfs-bless", help="Name of Folder to be blessed", action="store"
    )
    parser.add_argument(
        "-hfs-parms", help="Comma separated list of HFS parameters", action="store"
    )
    parser.add_argument(
        "-prep-boot", help="PReP boot image file -- up to 4 are allowed", action="store"
    )  # FIXME: we need to allow between 1 and 4 arguments
    parser.add_argument("-chrp-boot", help="Add CHRP boot header", action="store_true")
    parser.add_argument(
        "--cap", help="Look for AUFS CAP Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--netatalk", help="Look for NETATALK Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--double", help="Look for AppleDouble Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--ethershare",
        help="Look for Helios EtherShare Macintosh files",
        action="store_true",
    )
    parser.add_argument(
        "--exchange", help="Look for PC Exchange Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--sgi", help="Look for SGI Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--macbin", help="Look for MacBinary Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--single", help="Look for AppleSingle Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--ushare", help="Look for IPT UShare Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--xinet", help="Look for XINET Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--dave", help="Look for DAVE Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--sfm", help="Look for SFM Macintosh files", action="store_true"
    )
    parser.add_argument(
        "--osx-double",
        help="Look for MacOS X AppleDouble Macintosh files",
        action="store_true",
    )
    parser.add_argument(
        "--osx-hfs", help="Look for MacOS X HFS Macintosh files", action="store_true"
    )
    parser.add_argument(
        "-find",
        help="Option separator: Use find command line to the right",
        action="store",
    )
    parser.add_argument(
        "-posix-H",
        help="Follow symbolic links encountered on command line",
        action="store_true",
    )
    parser.add_argument(
        "-posix-L", help="Follow all symbolic links", action="store_true"
    )
    parser.add_argument(
        "-posix-P", help="Do not follow symbolic links (default)", action="store_true"
    )
    parser.add_argument(
        "-rrip110", help="Create old Rock Ridge V 1.10", action="store_true"
    )
    parser.add_argument(
        "-rrip112", help="Create new Rock Ridge V 1.12 (default)", action="store_true"
    )
    parser.add_argument("-ignore-error", help="Ignore errors", action="store_true")
    parser.add_argument(
        "-eltorito-platform",
        help="Set El Torito platform id for the next boot entry",
        action="store",
    )
    parser.add_argument(
        "-data-change-warn",
        help="Treat data/size changes as warning only",
        action="store_true",
    )
    parser.add_argument(
        "-errctl", help="Read error control defs from file or inline.", action="store"
    )
    parser.add_argument("-hide-udf", help="Hide UDF file", action="append", default=[])
    parser.add_argument(
        "-hide-udf-list",
        help="File with list of UDF files to hide",
        action="append",
        default=[],
    )
    parser.add_argument(
        "-long-rr-time", help="Use long Rock Ridge time format", action="store_true"
    )
    parser.add_argument(
        "-modification-date",
        help="Set the modification date field of the PVD",
        action="store",
    )
    parser.add_argument(
        "-no-limit-pathtables",
        help="Allow more than 65535 parent directories (violates ISO9660)",
        action="store_true",
    )
    parser.add_argument(
        "-no-long-rr-time",
        "-short-rr-time",
        help="Use short Rock Ridge time format",
        action="store_true",
    )
    parser.add_argument("-UDF", help="Generate UDF file system", action="store_true")
    parser.add_argument(
        "-udf-symlinks",
        help="Create symbolic links on UDF image (default)",
        action="store_true",
    )
    parser.add_argument(
        "-no-udf-symlinks",
        help="Do not create symbolic links on UDF image",
        action="store_true",
    )
    parser.add_argument(
        "-no-hfs", help="Do not create ISO9660/HFS hybrid", action="store_true"
    )
    parser.add_argument(
        "-scan-for-duplicates",
        help="Aggressively try to find duplicate files to reduce size (very slow!)",
        action="store_true",
    )
    parser.add_argument(
        "paths", help="Paths to get data from", action="store", nargs=argparse.REMAINDER
    )
    return parser.parse_args()


def determine_eltorito_entries(args):
    """
    A function to build up the list of EltoritoEntry objects for this ISO.

    Parameters:
     args - The ArgumentParser object returned from parse_arguments()
    Returns:
     A list of EltoritoEntry objects for this ISO (which may be empty).
    """
    eltorito_entries = []
    efi_boot_index = 0
    load_seg_index = 0
    load_size_index = 0

    for arg in sys.argv[1:]:
        if arg == "-eltorito-alt-boot":
            eltorito_entries.append(EltoritoEntry())
            continue

        if arg not in (
            "-b",
            "-eltorito-boot",
            "-e",
            "-efi-boot",
            "-no-emul-boot",
            "-hard-disk-boot",
            "-no-boot",
            "-boot-load-seg",
            "-boot-load-size",
            "-boot-info-table",
        ):
            continue

        if not eltorito_entries:
            entry = EltoritoEntry()
            eltorito_entries.append(entry)
        else:
            entry = eltorito_entries[-1]

        if arg in ("-b", "-eltorito-boot"):
            entry.set_bootfile(args.eltorito_boot)
        elif arg in ("-e", "-efi-boot"):
            entry.set_bootfile(args.efi_boot[efi_boot_index])
            efi_boot_index += 1
        elif arg == "-no-emul-boot":
            entry.mediatype = "noemul"
        elif arg == "-hard-disk-boot":
            entry.mediatype = "hdemul"
        elif arg == "-no-boot":
            entry.boot = False
        elif arg == "-boot-load-seg":
            entry.load_seg = int(args.boot_load_seg[load_seg_index])
            load_seg_index += 1
        elif arg == "-boot-load-size":
            entry.load_size = int(args.boot_load_size[load_size_index])
            load_size_index += 1
        elif arg == "-boot-info-table":
            entry.boot_info_table = True

    return eltorito_entries


class DirLevel(object):
    """
    A class to hold information about one directory level of the directory
    hierarchy.  Each level has an iso_path, a joliet_path, and a set of
    mangled maps for mangling filenames as appropriate.
    """

    __slots__ = ("iso_path", "joliet_path", "udf_path", "mangled_children")

    def __init__(self, iso_path, joliet_path, udf_path):
        self.iso_path = iso_path
        self.joliet_path = joliet_path
        self.udf_path = udf_path
        self.mangled_children = {}


def build_iso_path(parent_dirlevel, nameonly, iso_level, is_dir):
    """
    A function to build an absolute ISO path from a DirLevel object, a name,
    an ISO interchange level, and whether this is a directory or not.

    Parameters:
     parent_dirlevel - The DirLevel object representing the parent.
     nameonly - The basename of the ISO path.
     iso_level - The ISO interchange level to use.
     is_dir - Whether this is a directory or not.
    Returns:
     A string representing the ISO absolute path.
    """

    # Mangling the name and keeping track is a complicated affair.  First off,
    # we mangle the incoming dirname so it conforms to ISO9660 rules (see
    # mangle_dir_for_iso9660() for more info on that).  Once we have the
    # mangled name, we see if that name has been used at this directory level
    # yet.  If it has not been used, we mark it as now used, and return it
    # unmolested (beyond the ISO9660 mangle).  If it has been used, then we
    # need to strip it down to its prefix (the first 4 characters), add a
    # 3-digit number starting at zero, then iterate until we find a free one.
    # Once we have found a free one, we mark it as now used, and return what
    # we figured out.

    if is_dir:
        filemangle = mangle_dir_for_iso9660(nameonly, iso_level)
    else:
        filename, ext = mangle_file_for_iso9660(nameonly, iso_level)
        if ext == "":
            filemangle = filename
        else:
            filemangle = ".".join([filename, ext])

    if filemangle in parent_dirlevel.mangled_children:
        currnum = 0
        prefix = filemangle[:5]
        while True:
            if is_dir:
                tmp = "%s%.03d" % (prefix, currnum)
            else:
                tmp = "%s%.03d.%s" % (prefix, currnum, ext)
            if tmp not in parent_dirlevel.mangled_children:
                filemangle = tmp
                break
            currnum += 1
            if currnum == 1000:
                return None

    parent_dirlevel.mangled_children[filemangle] = True

    parent_iso_path = parent_dirlevel.iso_path
    if parent_dirlevel.iso_path == "/":
        parent_iso_path = parent_dirlevel.iso_path[1:]
    return parent_iso_path + "/" + filemangle


################################### MAIN #######################################


def main():
    """
    The main function for this executable that does the main work of generating
    an ISO given the parameters specified by the user.
    """
    args = parse_arguments()

    eltorito_entries = determine_eltorito_entries(args)

    if args.quiet:
        logfp = open(os.devnull, "w")
    else:
        if args.log_file is not None:
            print("re-directing all messages to %s" % (args.log_file))
            logfp = open(args.log_file, "w")
        else:
            logfp = sys.stdout

    print("pycdlib-genisoimage 1.0.0", file=logfp)

    # Check out all of the arguments we can here.
    if args.version:
        sys.exit(0)

    rock_version = None
    if args.rational_rock or args.rock:
        rock_version = "1.09"
    if args.rrip112:
        rock_version = "1.12"

    udf_version = None
    if args.udf or args.UDF:
        udf_version = "2.60"

    if args.joliet and rock_version is None:
        print(
            "Warning: creating filesystem with Joliet extensions but without Rock Ridge",
            file=logfp,
        )
        print(
            "         extensions. It is highly recommended to add Rock Ridge.",
            file=logfp,
        )

    if args.eltorito_catalog is not None and not eltorito_entries:
        print("genisoimage: No boot image specified.", file=logfp)
        sys.exit(255)

    if args.i is not None:
        print("genisoimage: -i option no longer supported.", file=logfp)
        sys.exit(255)

    hidden_patterns = args.hidden
    for pattern in parse_file_list(args.hidden_list):
        hidden_patterns.append(pattern)

    exclude_patterns = args.exclude + args.old_exclude
    for pattern in parse_file_list(args.exclude_list):
        exclude_patterns.append(pattern)

    hide_patterns = args.hide
    for pattern in parse_file_list(args.hide_list):
        hide_patterns.append(pattern)

    hide_joliet_patterns = args.hide_joliet
    for pattern in parse_file_list(args.hide_joliet_list):
        hide_joliet_patterns.append(pattern)

    hide_udf_patterns = args.hide_udf
    for pattern in parse_file_list(args.hide_udf_list):
        hide_udf_patterns.append(pattern)

    ignore_patterns = []
    if args.nobak:
        ignore_patterns.extend(("*~*", "*#*", "*.bak"))

    if args.print_size:
        fp = BytesIO()
    else:
        if args.output is None:
            print("Output file must be specified (use -o)", file=logfp)
            sys.exit(1)

        fp = open(args.output, "wb")

    # Figure out Joliet flag, which is the combination of args.joliet
    # and args.ucs_level.
    joliet_level = None
    if args.joliet:
        joliet_level = 3
        if args.ucs_level is not None:
            joliet_level = int(args.ucs_level)

    eltorito_catalog_path = ""
    eltorito_catalog_parts = []
    if args.eltorito_catalog is not None:
        eltorito_catalog_parts = args.eltorito_catalog.split("/")

    # Create a new PyCdlib object.
    iso = pycdlib.PyCdlib()

    if args.hide_rr_moved:
        iso.set_relocated_name("_RR_MOVE", ".rr_moved")

    # Create a new ISO.
    iso.new(
        interchange_level=args.iso_level,
        sys_ident=args.sysid,
        vol_ident=args.volid,
        set_size=args.volset_size,
        seqnum=args.volset_seqno,
        vol_set_ident=args.volset,
        pub_ident_str=args.publisher,
        preparer_ident_str=args.preparer,
        app_ident_str=args.appid,
        copyright_file=args.copyright,
        abstract_file=args.abstract,
        bibli_file=args.biblio,
        joliet=joliet_level,
        rock_ridge=rock_version,
        xa=(args.XA or args.xa),
        udf=udf_version,
    )

    path_list = args.paths

    if args.path_list is not None:
        for line in fileinput.input(args.path_list):
            path_list.append(line.strip())

    seen_hashes = {}
    for path in path_list:
        check_eltorito_catalog = len(eltorito_catalog_parts) > 0
        root_level = DirLevel("/", "/", "/")
        for eltorito_entry in eltorito_entries:
            eltorito_entry.dirlevel = root_level
        entries = collections.deque(
            [(os.path.normpath(path), root_level, False, check_eltorito_catalog)]
        )
        while entries:
            localpath, parent_level, add_dir, check_eltorito_catalog = entries.popleft()
            basename = os.path.basename(localpath)

            if check_eltorito_catalog and len(eltorito_catalog_parts) == 1:
                filename, ext = mangle_file_for_iso9660(
                    eltorito_catalog_parts.pop(), args.iso_level
                )
                eltorito_catalog_path += "/" + filename + "." + ext

            for eltorito_entry in eltorito_entries:
                if (
                    eltorito_entry.dirlevel == parent_level
                    and len(eltorito_entry.bootfile_parts) == 1
                ):
                    filename, ext = mangle_file_for_iso9660(
                        eltorito_entry.bootfile_parts.pop(), args.iso_level
                    )
                    tail = "." + ext
                    if ext == "":
                        tail = ""
                    eltorito_entry.bootfile_iso_path += "/" + filename + tail

            rr_name = None
            if args.rational_rock or args.rock:
                rr_name = basename

            joliet_path = None
            if args.joliet:
                joliet_path = build_joliet_path(parent_level.joliet_path, basename)

            udf_path = None
            if args.udf or args.UDF:
                udf_path = build_udf_path(parent_level.udf_path, basename)

            if os.path.islink(localpath):
                if (not args.rational_rock or args.rock) and (not args.udf or args.UDF):
                    print("Symlink %s ignored - continuing." % (localpath), file=logfp)
                else:
                    iso_path = build_iso_path(
                        parent_level, basename, args.iso_level, False
                    )
                    if iso_path is None:
                        print(
                            "Could not find free ISO9660 name for path %s; skipping"
                            % (localpath),
                            file=logfp,
                        )

                    rr_target = None
                    if args.rational_rock or args.rock:
                        rr_target = os.readlink(localpath)

                    udf_target = None
                    if args.udf or args.UDF:
                        udf_target = os.readlink(localpath)

                    iso.add_symlink(
                        iso_path,
                        rr_symlink_name=rr_name,
                        rr_path=rr_target,
                        udf_symlink_path=udf_path,
                        udf_target=udf_target,
                        joliet_path=joliet_path,
                    )

            elif os.path.isdir(localpath):
                if add_dir:
                    iso_path = build_iso_path(
                        parent_level, basename, args.iso_level, True
                    )
                    if iso_path is None:
                        print(
                            "Could not find free ISO9660 name for path %s; skipping"
                            % (localpath),
                            file=logfp,
                        )
                    depth = iso_path.count("/")
                    if rr_name is None and depth > 7:
                        print(
                            "Directories too deep for '%s' (%d) max is 7; ignored - continuing."
                            % (localpath, depth),
                            file=logfp,
                        )
                        continue
                    iso.add_directory(
                        iso_path,
                        rr_name=rr_name,
                        joliet_path=joliet_path,
                        udf_path=udf_path,
                    )
                else:
                    iso_path = parent_level.iso_path
                    joliet_path = parent_level.joliet_path
                    udf_path = parent_level.udf_path

                on_eltorito_catalog_path = False
                eltorito_duplicate_check = ""
                if (
                    check_eltorito_catalog
                    and len(eltorito_catalog_parts) > 1
                    and eltorito_catalog_parts[0] == basename
                ):
                    eltorito_catalog_path += "/" + mangle_dir_for_iso9660(
                        basename, args.iso_level
                    )
                    eltorito_catalog_parts.pop(0)
                    on_eltorito_catalog_path = True
                    if len(eltorito_catalog_parts) == 1:
                        eltorito_duplicate_check = eltorito_catalog_parts[0]

                parent = DirLevel(iso_path, joliet_path, udf_path)
                for eltorito_entry in eltorito_entries:
                    if (
                        parent_level == eltorito_entry.dirlevel
                        and len(eltorito_entry.bootfile_parts) > 1
                        and eltorito_entry.bootfile_parts[0] == basename
                    ):
                        eltorito_entry.bootfile_iso_path += (
                            "/" + mangle_dir_for_iso9660(basename, args.iso_level)
                        )
                        eltorito_entry.bootfile_parts.pop(0)
                        eltorito_entry.dirlevel = parent

                for f in os.listdir(localpath):
                    fullpath = os.path.join(localpath, f)

                    if (
                        match_entry_to_list(exclude_patterns, f)
                        or eltorito_duplicate_check == f
                    ):
                        print("Excluded by match: %s" % (fullpath), file=logfp)
                        continue

                    if match_entry_to_list(ignore_patterns, f):
                        print("Ignoring file %s" % (fullpath), file=logfp)
                        continue

                    if args.verbose:
                        print("Scanning %s" % (fullpath), file=logfp)

                    entries.append((fullpath, parent, True, on_eltorito_catalog_path))
            else:
                iso_path = build_iso_path(parent_level, basename, args.iso_level, False)
                if iso_path is None:
                    print(
                        "Could not find free ISO9660 name for path %s; skipping"
                        % (localpath),
                        file=logfp,
                    )

                thishash = 0
                if args.scan_for_duplicates:
                    thishash = mm3hashfromfile(localpath)

                if thishash in seen_hashes:
                    iso.add_hard_link(
                        iso_old_path=seen_hashes[thishash],
                        iso_new_path=iso_path,
                        rr_name=rr_name,
                    )
                    if joliet_path is not None:
                        iso.add_hard_link(
                            iso_old_path=seen_hashes[thishash],
                            joliet_new_path=joliet_path,
                        )
                    if udf_path is not None:
                        iso.add_hard_link(
                            iso_old_path=seen_hashes[thishash], udf_new_path=udf_path
                        )
                else:
                    iso.add_file(
                        localpath,
                        iso_path,
                        rr_name=rr_name,
                        joliet_path=joliet_path,
                        udf_path=udf_path,
                    )
                    if match_entry_to_list(hide_patterns, basename):
                        iso.rm_hard_link(iso_path=iso_path)

                    if args.joliet and match_entry_to_list(
                        hide_joliet_patterns, basename
                    ):
                        iso.rm_hard_link(joliet_path=joliet_path)

                    if args.udf and match_entry_to_list(hide_udf_patterns, basename):
                        iso.rm_hard_link(udf_path=udf_path)

                    if args.scan_for_duplicates:
                        seen_hashes[thishash] = iso_path

            if match_entry_to_list(hidden_patterns, basename):
                iso.set_hidden(iso_path)
                print("Hidden ISO9660 attribute: %s" % (localpath), file=logfp)

    # Add in El Torito if it was requested
    for entry in eltorito_entries:
        try:
            iso.add_eltorito(
                entry.bootfile_iso_path,
                bootcatfile=eltorito_catalog_path,
                bootable=entry.boot,
                boot_load_size=entry.load_size,
                boot_info_table=entry.boot_info_table,
                media_name=entry.mediatype,
                boot_load_seg=entry.load_seg,
            )
        except pycdlib.pycdlibexception.PyCdlibInvalidInput as e:
            if "Could not find path" in str(e):
                print(
                    "Uh oh, I cant find the boot image '%s' !" % (entry.bootfile_orig),
                    file=logfp,
                )
                sys.exit(255)
            else:
                raise

    class ProgressData(object):
        """
        A private class to hold onto the data from the last progress call.
        """

        __slots__ = ("last_percent", "logfp", "begun")

        def __init__(self, logfp):
            self.last_percent = ""
            self.logfp = logfp
            self.begun = time.time()

    def progress_cb(done, total, progress_data):
        """
        A private function that will be passed into the write_fp method of the
        PyCdlib object, and prints out the current progress of the mastering.

        Parameters (as prescribe by PyCdlib):
         done - The amount of data written so far
         total - The total amount of data to write
         progress_data - An object of type ProgressData to track progress
        Returns:
         Nothing.
        """
        frac = float(done) / float(total)
        percent = "%.2f%%" % (frac * 100)
        if percent != progress_data.last_percent:
            the_end = time.time()
            if frac > 0:
                the_end = progress_data.begun + (the_end - progress_data.begun) / frac
            print(
                "%s done, estimate finish %s" % (percent, time.ctime(the_end)),
                file=progress_data.logfp,
            )
            progress_data.last_percent = percent

    iso.write_fp(fp, progress_cb=progress_cb, progress_opaque=ProgressData(logfp))

    if args.print_size:
        print(
            "Total extents scheduled to be written = %d" % (len(fp.getvalue()) / 2048),
            file=logfp,
        )

    iso.close()


if __name__ == "__main__":
    main()
