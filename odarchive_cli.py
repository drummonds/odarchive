from odarchive import *

if __name__ == "__main__":
    cli.add_command(archive)
    cli.add_command(init)
    cli.add_command(write_iso)
    cli()
