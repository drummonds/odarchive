import hashlib
import re

# 1: 'version' field added
# 2: entry 'file_type' field added; symlinks now treated correctly
DATABASE_VERSION = 1
DB_FILENAME = "catalogue.json"

HASH_FUNCTION = hashlib.sha512
# Mostly used for importing from saved hash files
EMPTY_FILE_HASH = (
    "cf83e1357eefb8bdf1542850d66d8007d620e4050b5715dc83f4a921d36ce9ce"
    "47d0d13c5d85f2b0ff8318d2877eec2f63b931bd47417a81a538327af927da3e"
)

SHA512_HASH_PATTERN = re.compile(r"^[0-9a-fA-F]{128}$")

HASH_FILENAME = "SHA512SUM"


class odarchiveError(Exception):
    pass

def interpret_disc_capacity(size):
    """
    Converts a size parameter into a number of bytes
    :param size: either text or an int representing a number of bytes
    :return:
    """

    def p(comma_num):
        return int(comma_num.replace(",", ""))

    size_as_text = str(size).lower()
    if size_as_text == "cd":
        return p("737,280,000")
    elif size_as_text == "dvd":  # DVD-R SL DVD+R is slightly bigger
        return p("4,707,319,808")
    elif size_as_text == "bluray" or size_as_text == "bd":
        # return p("25,025,314,816   ")  # Theoretical maximum but ISO's are create slightly bigger
        return p("23,000,000,000   ")  # Try < 99% 99% still too large
    elif size_as_text == "bd-dl":
        return p("50,050,629,632")
    elif size_as_text == "bd-xl":
        return p("100,103,356,416")
    elif size_as_text == "bd - xx":
        return p("128,001,769,472")
    else:
        return size
