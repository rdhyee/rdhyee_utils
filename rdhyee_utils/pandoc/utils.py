import subprocess
from pathlib import Path as P


def run_cmd(*args, shell=True, cwd=None):
    r = subprocess.run(*args, shell=shell, capture_output=True, cwd=cwd)
    return r


def pandoc_formats():
    cmd = "pandoc --list-input-formats"
    r = run_cmd(cmd, shell=True, cwd=P.cwd())
    input_formats = set([f for f in r.stdout.decode("utf-8").split("\n") if f != ""])

    cmd = "pandoc --list-output-formats"
    r = run_cmd(cmd, shell=True, cwd=P.cwd())
    output_formats = set([f for f in r.stdout.decode("utf-8").split("\n") if f != ""])

    return {"input": input_formats, "output": output_formats}


def extensions_for_format(fmt):
    cmd = f"pandoc --list-extensions {fmt}"
    r = run_cmd(cmd, shell=True, cwd=P.cwd())
    # partition the extensions into two sets based by default enabling or disabling
    enabled = set()
    disabled = set()
    for e in r.stdout.decode("utf-8").split("\n"):
        if e.startswith("+"):
            enabled.add(e[1:])
        elif e.startswith("-"):
            disabled.add(e[1:])
    return {"enabled": enabled, "disabled": disabled, "all": enabled.union(disabled)}


class PFormatExtensionCombo:
    def __init__(self, fmt=None, enabled=None, disabled=None, by_str=None):
        """either fmt or by_str must be specified"""
        if fmt is None and by_str is None:
            raise ValueError("either fmt or by_str must be specified")
        if by_str is not None:
            self.fmt, self.enabled, self.disabled = self._parse_by_str(by_str)
        else:
            self.fmt = fmt
            self.enabled = enabled
            self.disabled = disabled

    def __str__(self):
        """return a string like 'markdown+footnotes+pipe_tables'"""
        return f'{self.fmt}{"".join(["+"+l for l in self.enabled])}{"".join(["-"+l for l in self.disabled])}'

    def __repr__(self):
        return self.__str__()

    def canonicalize(self):
        """return a new PFormatExtensionCombo with canonicalized enabled and disabled extensions"""
        extensions = extensions_for_format(self.fmt)

        # return enabled that is not in the default enabled

        enabled = self.enabled - extensions["enabled"]
        disabled = self.disabled - extensions["disabled"]

        return PFormatExtensionCombo(fmt=self.fmt, enabled=enabled, disabled=disabled)

    def expand(self):
        """layer enabled, disabled on top of defaults"""
        extensions = extensions_for_format(self.fmt)

        # return enabled that is not in the default enabled
        enabled = extensions["enabled"].union(self.enabled) - self.disabled
        disabled = extensions["disabled"].union(self.disabled) - self.enabled

        return PFormatExtensionCombo(fmt=self.fmt, enabled=enabled, disabled=disabled)

    def _parse_by_str(self, by_str):
        fmt = ""
        enabled = set()
        disabled = set()

        # Extract the format specifier (everything before the first '+' or '-')
        fmt, sep, remainder = (
            by_str.partition("+") if "+" in by_str else by_str.partition("-")
        )

        # Initialize variables to hold the current mode ('+' or '-') and extension name
        mode = None
        ext = ""

        # Parse the remaining string to identify enabled and disabled extensions
        for k in sep + remainder:  # Include the separator
            if k in ["+", "-"]:
                if mode:
                    # Add the current extension to the appropriate set
                    (enabled if mode == "+" else disabled).add(ext)
                mode = k
                ext = ""
            else:
                ext += k

        # Handle the last extension
        if mode:
            (enabled if mode == "+" else disabled).add(ext)

        return fmt, enabled, disabled
