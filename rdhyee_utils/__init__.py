"""
general utility functions
"""
__all__ = [
    "grouper",
    "singleton",
    "nowish_tz"
]

from typing import Union, Tuple

import subprocess
import shlex
import datetime
import pytz



# http://stackoverflow.com/questions/2348317/how-to-write-a-pager-for-python-iterators/2350904#2350904
def grouper(iterable, page_size):
    """grouper('ABCDEFG', 3) --> ABC DEF G"""
    page = []
    for item in iterable:
        page.append(item)
        if len(page) == page_size:
            yield page
            page = []
    if len(page) > 0:
        yield page


# http://stackoverflow.com/questions/42558/python-and-the-singleton-pattern/2752280#2752280
def singleton(cls):
    """Decorator that makes a class a singleton."""
    instances = {}

    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance


def nowish_tz(tzname="US/Pacific"):
    """
    Return the current time in a given timezone. Default is US/Pacific."""
    # put in Pacific time
    tz = pytz.timezone(tzname)
    return (
        datetime.datetime(*datetime.datetime.utcnow().timetuple()[:6])
        .replace(tzinfo=pytz.utc)
        .astimezone(tz)
    )


def execute_command(
    command: Union[str, list], use_shell: bool = False, check: bool = False
) -> Tuple[str, str]:
    """
    Execute a shell command and return its output and error messages."""
    if isinstance(command, str) and not use_shell:
        command = shlex.split(command)

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=use_shell,
        check=check,
    )

    return result.stdout, result.stderr
