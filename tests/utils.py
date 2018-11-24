import json
import os
from pathlib import Path

def test_1_clean():
    """Delete files produced in test_1, assume in directory ./test_1_files"""
    for this_file in (
        "usb.iso",
        "usb.db",
        "catalogue.json",
        "new.iso",
        "new_0000.iso",
        "new_0001.iso",
        "new_0002.iso",
        "archiver.pickle",
        "archiver.dill",
        "archiver.json",
    ):
        try:
            os.remove(Path(this_file))
        except FileNotFoundError:
            pass


def catalogue_compare(filename1, filename2):
    with open(filename1) as json_data:
        a = json.load(json_data)
        a['guid'] = ''
        a['date'] = ''
    with open(filename2) as json_data:
        b = json.load(json_data)
        b['guid'] = ''
        b['date'] = ''
    return a == b,

