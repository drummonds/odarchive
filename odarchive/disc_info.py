import datetime as dt
import dateutil
import json

from .consts import odarchiveError


def load_disc_info_from_json(filename=None, json_data=None):
    """Load from from a catalogue.json file eg from an written CD.
       If filename is none, can load the json directly.  Note the filename takes precedence over json_data"""
    def parse_json(json_data):
        di = DiscInfo()
        d = json_data
        try:
            date_str = d['date']
            di.date = dateutil.parser.parse(date_str) # This a read only value after an archive has been
            # created
        except:
            raise odarchiveError('Date string malformed or not found in catalogue.json')
        try:
            di.disc_num = int(d['disc_num'])
        except:
            di.disc_num = 0
        try:
            di.num_discs = int(d['num_discs'])
        except:
            di.num_discs = 0
        return di
    if filename:
        with open(filename) as json_data_from_file:
            di = parse_json(json.load(json_data_from_file))
    else:
        di = parse_json(json.loads(json_data))
    return di

class DiscInfo:
    def __init__(self):
        self.disc_num = None  # Not yet defined
        self.num_discs = None

    def setup(self, disc_num, num_discs):
        self.disc_num = disc_num  # Not yet defined
        self.num_discs = num_discs

    def get_info(self):
        result = f'Disc num = {self.disc_num}'
        result = f'Number of discs = {self.num_discs}'
        return result

    def get_json(self):
        data = {
            "date": str(dt.datetime.utcnow().isoformat()),
            "disc_num": str(self.disc_num),
            "num_discs": str(self.num_discs),
        }
        return json.dumps(data)

