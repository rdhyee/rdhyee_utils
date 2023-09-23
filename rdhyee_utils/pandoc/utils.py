import subprocess
from pathlib import Path
from typing import Dict, List, Set, Optional


def run_cmd(
    cmd: str, shell: bool = True, cwd: Optional[Path] = None
) -> subprocess.CompletedProcess:
    """
    Run a shell command and return the result.
    :param cmd: The shell command to run.
    :param shell: Whether to use shell=True for subprocess.
    :param cwd: The current working directory for the command.
    :return: subprocess.CompletedProcess object.
    """
    return subprocess.run(cmd, shell=shell, capture_output=True, cwd=cwd)


def pandoc_formats() -> Dict[str, Set[str]]:
    """
    Get available pandoc input and output formats.

    :return: A dictionary with keys 'input' and 'output' containing sets of input and output formats.
    """
    cwd = Path.cwd()  # Get the current working directory

    # Get input formats
    input_formats = set(
        _parse_pandoc_list(run_cmd("pandoc --list-input-formats", cwd=cwd).stdout)
    )

    # Get output formats
    output_formats = set(
        _parse_pandoc_list(run_cmd("pandoc --list-output-formats", cwd=cwd).stdout)
    )

    # Return the formats as a dictionary
    return {"input": input_formats, "output": output_formats}


def _parse_pandoc_list(pandoc_output: bytes) -> List[str]:
    """
    Helper function to parse the output of pandoc list commands.
    :param pandoc_output: The bytes output from a pandoc list command.
    :return: A list of available formats or extensions.
    """
    return [f for f in pandoc_output.decode("utf-8").split("\n") if f != ""]


def extensions_for_format(fmt: str) -> Dict[str, Set[str]]:
    """
    Get the enabled and disabled extensions for a given Pandoc format.

    :param fmt: The Pandoc format (e.g., 'markdown').
    :return: A dictionary with keys 'enabled', 'disabled', and 'all' containing sets of extensions.
    """
    cwd = Path.cwd()
    cmd = f"pandoc --list-extensions {fmt}"
    r = run_cmd(cmd, shell=True, cwd=cwd)
    extensions_output = r.stdout.decode("utf-8").split("\n")

    # Partition the extensions into sets based on default enabling or disabling
    enabled = {e[1:] for e in extensions_output if e.startswith("+")}
    disabled = {e[1:] for e in extensions_output if e.startswith("-")}

    return {"enabled": enabled, "disabled": disabled, "all": enabled.union(disabled)}


class PFormatExtensionCombo:
    def __init__(self, fmt: str = None, enabled=set(), disabled=set(), by_str=None):
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
