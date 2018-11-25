import click
from pathlib import Path

from .archive import Archiver, load_archiver_from_dill


@click.group()
def cli():
    pass


@click.command()
@click.argument("usb_path")  # , help='Path to USB drive which is to be backed up')
def init(usb_path):
    ar = Archiver()
    ar.create_file_database(Path(usb_path))
    ar.convert_to_hash_database()
    ar.save()  # Creates catalogue.json
    ar.print_files()
    ar.save()


@click.command()
@click.argument("size")  # , help='Max size in Bytes for segment')
def segment(size):
    """Converts an archive into a segmented archive."""
    # Todo if an archive is modified eg adding new files then will need to be resegmented
    # However size parameter can't change
    ar = load_archiver_from_dill()
    ar.create_catalogue()
    ar.segment(size)


@click.command()
@click.option("--pretend", default=False, help="Won't create database if --pretend")
def write_iso(pretend):
    ar = load_archiver_from_dill()
    ar.print_files()
    ar.write_iso(pretend)
    ar.save()


@click.command()
@click.option("--pretend", default=False, help="Won't create database if --pretend")
@click.argument("usb_path")  # , help='Path to USB drive which is to be backed up')
def archive(pretend, usb_path):
    ar = Archiver()
    ar.create_file_database(Path(usb_path))
    ar.convert_to_hash_database()
    ar.save()  # Creates catalogue.json
    ar.print_files()
    ar.write_iso(pretend)
    ar.save()
