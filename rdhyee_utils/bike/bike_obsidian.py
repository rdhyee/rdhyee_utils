"""
Bike <-> Obsidian Integration

Helper functions for moving content between Bike and Obsidian.
Designed for use by Claude Code and automation workflows.
"""

from pathlib import Path
from typing import List, Optional, Union, Dict, Any
import json
from datetime import datetime

from lxml import etree as ET
import panflute as pf
import pypandoc

from rdhyee_utils.bike import Bike, BikeDocument, BikeRow
from rdhyee_utils.bike import mdimport
from rdhyee_utils.bike.bikeformat import (
    namespaces,
    bike_etree_to_panflute,
    bike_etree_list_to_panflute,
    panflute_to_bike_etree,
    merge_consecutive_codeblocks,
    markdown_to_bike_p_element,
    generate_unique_id_attribute,
    ONLY_DOC_CHILDREN
)


# Default paths
DEFAULT_BIKE_FILE = Path.home() / "obsidian/Main/bike/overall.bike"
DEFAULT_OBSIDIAN_VAULT = Path.home() / "obsidian/Main"
DEFAULT_SCRATCHPAD = DEFAULT_OBSIDIAN_VAULT / "ScratchPad.md"

# Markdown formats
SOURCE_MARKDOWN_FORMAT = (
    "markdown+lists_without_preceding_blankline+wikilinks_title_after_pipe+mark"
)
DEST_MARKDOWN_FORMAT = (
    "markdown+lists_without_preceding_blankline+wikilinks_title_after_pipe+mark"
    "-native_divs-native_spans-header_attributes-link_attributes"
)


class BikeObsidianBridge:
    """Bridge for moving content between Bike and Obsidian."""

    def __init__(
        self,
        bike_file: Path = DEFAULT_BIKE_FILE,
        obsidian_vault: Path = DEFAULT_OBSIDIAN_VAULT
    ):
        """
        Initialize the bridge.

        Args:
            bike_file: Path to the main bike file (usually overall.bike)
            obsidian_vault: Path to Obsidian vault root
        """
        self.bike_file = bike_file
        self.obsidian_vault = obsidian_vault
        self.bike = Bike()

    def get_overall_document(self) -> Optional[BikeDocument]:
        """
        Get the overall.bike document if it's open in Bike.app.

        Returns:
            BikeDocument if found, None otherwise
        """
        return self.bike.document_by_path(self.bike_file)

    def ensure_overall_open(self) -> BikeDocument:
        """
        Ensure overall.bike is open, open it if not.

        Returns:
            BikeDocument for overall.bike
        """
        doc = self.get_overall_document()
        if doc is None:
            # Open the file
            self.bike.app.open(str(self.bike_file))
            doc = self.get_overall_document()
            if doc is None:
                raise RuntimeError(f"Could not open {self.bike_file}")
        return doc

    def get_document_structure(self, max_depth: int = 2) -> Dict[str, Any]:
        """
        Get the hierarchical structure of overall.bike.

        Args:
            max_depth: Maximum depth to traverse

        Returns:
            Dict with document structure
        """
        doc = self.ensure_overall_open()

        def row_to_dict(row: BikeRow, depth: int = 0) -> Dict[str, Any]:
            """Convert a row and its children to a dict."""
            result = {
                'id': row.id,
                'name': row.name,
                'level': row.level,
                'text': row.text_content[:100] if len(row.text_content) > 100 else row.text_content
            }

            if depth < max_depth:
                children = row.rows
                if children:
                    result['children'] = [
                        row_to_dict(child, depth + 1)
                        for child in children
                    ]
                    result['child_count'] = len(children)

            return result

        root = doc.root_row
        return {
            'file': str(self.bike_file),
            'id': doc.id,
            'name': doc.name,
            'modified': doc.modified,
            'root': row_to_dict(root, depth=0),
            'total_rows': len(doc.rows)
        }

    def find_row_by_id(self, row_id: str) -> Optional[BikeRow]:
        """
        Find a row by its ID.

        Args:
            row_id: The row ID to find

        Returns:
            BikeRow if found, None otherwise
        """
        doc = self.ensure_overall_open()
        for row in doc.rows:
            if row.id == row_id:
                return row
        return None

    def find_rows_by_name(self, name: str, exact: bool = True) -> List[BikeRow]:
        """
        Find rows by name/text content.

        Args:
            name: Text to search for
            exact: If True, match exactly; if False, match substring

        Returns:
            List of matching BikeRows
        """
        doc = self.ensure_overall_open()
        results = []

        for row in doc.rows:
            if exact:
                if row.name == name:
                    results.append(row)
            else:
                if name.lower() in row.name.lower():
                    results.append(row)

        return results

    def export_row_to_markdown(
        self,
        row: Union[BikeRow, str],
        include_children: bool = True,
        only_doc_children: bool = True
    ) -> str:
        """
        Export a row (and optionally its children) to markdown.

        Args:
            row: BikeRow or row ID
            include_children: Whether to include child rows
            only_doc_children: If True, export only document children (cleaner)

        Returns:
            Markdown string
        """
        if isinstance(row, str):
            row = self.find_row_by_id(row)
            if row is None:
                raise ValueError(f"Row with id '{row}' not found")

        doc = self.ensure_overall_open()

        # Export the row to bike format
        etree = doc.lxml_etree(from_=[row], all=include_children)

        # Convert to panflute
        if only_doc_children:
            etree2 = etree.findall('body/ul/*')
            pfd = bike_etree_list_to_panflute(etree2)
            pfd = pf.Doc(*pfd)
        else:
            pfd = bike_etree_to_panflute(etree)

        # Merge consecutive code blocks
        pf.run_filter(merge_consecutive_codeblocks, doc=pfd)

        # Convert to markdown
        pandoc_json = pfd.to_json()
        output_md = pypandoc.convert_text(
            json.dumps(pandoc_json),
            to=DEST_MARKDOWN_FORMAT,
            format='json',
            extra_args=['--wrap=none']
        )

        return output_md

    def export_selection_to_markdown(self) -> str:
        """
        Export currently selected rows in Bike to markdown.

        Returns:
            Markdown string
        """
        doc = self.ensure_overall_open()
        etree = doc.lxml_etree(from_=doc.selection_rows)

        # Convert to panflute
        etree2 = etree.findall('body/ul/*')
        pfd = bike_etree_list_to_panflute(etree2)
        pfd = pf.Doc(*pfd)

        # Merge consecutive code blocks
        pf.run_filter(merge_consecutive_codeblocks, doc=pfd)

        # Convert to markdown
        pandoc_json = pfd.to_json()
        output_md = pypandoc.convert_text(
            json.dumps(pandoc_json),
            to=DEST_MARKDOWN_FORMAT,
            format='json',
            extra_args=['--wrap=none']
        )

        return output_md

    def export_to_obsidian(
        self,
        row: Union[BikeRow, str],
        obsidian_file: Optional[Path] = None,
        append: bool = False
    ) -> Path:
        """
        Export a Bike row to an Obsidian markdown file.

        Args:
            row: BikeRow or row ID
            obsidian_file: Target file path (defaults to ScratchPad.md)
            append: If True, append to file; if False, overwrite

        Returns:
            Path to the created/updated file
        """
        if obsidian_file is None:
            obsidian_file = DEFAULT_SCRATCHPAD

        # Make path relative to vault if not absolute
        if not obsidian_file.is_absolute():
            obsidian_file = self.obsidian_vault / obsidian_file

        # Export to markdown
        markdown = self.export_row_to_markdown(row)

        # Write to file
        mode = 'a' if append else 'w'
        with open(obsidian_file, mode, encoding='utf-8') as f:
            if append:
                f.write('\n\n---\n\n')  # Add separator
            f.write(markdown)

        return obsidian_file

    def export_selection_to_obsidian(
        self,
        obsidian_file: Optional[Path] = None,
        append: bool = False
    ) -> Path:
        """
        Export currently selected Bike rows to Obsidian.

        Args:
            obsidian_file: Target file path (defaults to ScratchPad.md)
            append: If True, append to file; if False, overwrite

        Returns:
            Path to the created/updated file
        """
        if obsidian_file is None:
            obsidian_file = DEFAULT_SCRATCHPAD

        # Make path relative to vault if not absolute
        if not obsidian_file.is_absolute():
            obsidian_file = self.obsidian_vault / obsidian_file

        # Export to markdown
        markdown = self.export_selection_to_markdown()

        # Write to file
        mode = 'a' if append else 'w'
        with open(obsidian_file, mode, encoding='utf-8') as f:
            if append:
                f.write('\n\n---\n\n')  # Add separator
            f.write(markdown)

        return obsidian_file

    def import_markdown_to_bike(
        self,
        markdown: str,
        parent_row: Optional[Union[BikeRow, str]] = None,
        position: str = "append",
        output_path: Optional[Union[str, Path]] = None,
    ) -> List[str]:
        """
        Import markdown into Bike as new rows, on the file-level tree model
        (this closes the "???" step named in the 2025-11-21 dev-journal
        gap: ``Markdown -> panflute -> Bike XML -> ??? -> Bike.app``).

        This delegates to the tested, model-based grafting in
        ``rdhyee_utils.bike.mdimport`` (``markdown -> pandoc(-t
        bike_writer.lua) -> BikeDoc rows -> insert_rows()`` with
        collision-free id re-keying) rather than driving Bike.app live via
        AppleScript. That's a deliberate, honest scope decision: the
        AppleScript object model here (``Bike``/``BikeDocument``/``BikeRow``
        in ``rdhyee_utils/bike/__init__.py``) has no verb to create new rows
        or to force a reload from disk, so a live-AppleScript-insertion
        implementation is a different, larger feature and is NOT what this
        method does. (A separate, uncommitted 2025-11 working-tree draft
        takes the panflute route to a similar end; this is the committed,
        tested equivalent — see ``rdhyee_utils/bike/mdimport.py`` and
        ``BIKE_PANDOC_DESIGN.md`` for the full relationship.)

        Because there is no AppleScript "revert"/reload verb, overwriting
        ``self.bike_file`` on disk while Bike.app has it open with unsaved
        edits would risk losing those edits when the human later saves from
        the GUI. This method refuses to write in that situation unless an
        explicit ``output_path`` is given (writing elsewhere is always
        safe). When the target file *is* open in Bike.app (with no unsaved
        changes, or via ``output_path``), Bike.app will show "File Changed
        on Disk" and the human uses File > Revert to Saved to pick up the
        change — this method does not attempt to automate that.

        Args:
            markdown: Markdown text to import
            parent_row: Parent row to graft under (None = document root);
                a ``BikeRow`` (its ``.id`` is used) or a raw row id string
            position: "append" (default) or "prepend" among the parent's
                existing children
            output_path: explicit write target; defaults to ``self.bike_file``
                (in place). Required (and always honored) if the file is
                open in Bike.app with unsaved changes.

        Returns:
            ids of the newly inserted top-level rows

        Raises:
            RuntimeError: if ``self.bike_file`` is open in Bike.app with
                unsaved changes and no ``output_path`` was given
        """
        parent_id = parent_row.id if isinstance(parent_row, BikeRow) else parent_row
        target_path = Path(output_path) if output_path is not None else self.bike_file

        same_file = (
            Path(target_path).expanduser().resolve()
            == Path(self.bike_file).expanduser().resolve()
        )
        if same_file:
            open_doc = self.get_overall_document()
            if open_doc is not None and open_doc.modified:
                raise RuntimeError(
                    f"{self.bike_file} is open in Bike.app with unsaved "
                    "changes; save or close it in Bike.app first, or pass "
                    "output_path= to write the import elsewhere."
                )

        return mdimport.import_markdown_into_file(
            self.bike_file,
            markdown,
            output_path=target_path,
            parent_id=parent_id,
            position=position,
        )

    def get_row_context(
        self,
        row: Union[BikeRow, str],
        ancestors: bool = True,
        siblings: bool = True,
        children: bool = True
    ) -> Dict[str, Any]:
        """
        Get contextual information about a row.

        Args:
            row: BikeRow or row ID
            ancestors: Include parent/ancestor rows
            siblings: Include sibling rows
            children: Include child rows

        Returns:
            Dict with contextual information
        """
        if isinstance(row, str):
            row = self.find_row_by_id(row)
            if row is None:
                raise ValueError(f"Row with id '{row}' not found")

        result = {
            'id': row.id,
            'name': row.name,
            'level': row.level,
            'text': row.text_content
        }

        # TODO: Implement ancestor/sibling finding
        # This requires more sophisticated tree traversal

        if children:
            result['children'] = [
                {
                    'id': child.id,
                    'name': child.name,
                    'level': child.level
                }
                for child in row.rows
            ]

        return result

    def list_top_level_items(self, max_items: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List top-level items in overall.bike.

        Args:
            max_items: Maximum number of items to return (None = all)

        Returns:
            List of dicts with item information
        """
        doc = self.ensure_overall_open()
        root = doc.root_row
        items = []

        for i, row in enumerate(root.rows):
            if max_items is not None and i >= max_items:
                break

            items.append({
                'id': row.id,
                'name': row.name,
                'level': row.level,
                'text_preview': row.text_content[:100],
                'has_children': len(row.rows) > 0
            })

        return items

    def search_content(self, query: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
        """
        Search for text in all rows.

        Args:
            query: Text to search for
            case_sensitive: Whether search is case-sensitive

        Returns:
            List of matching rows with context
        """
        doc = self.ensure_overall_open()
        results = []

        if not case_sensitive:
            query = query.lower()

        for row in doc.rows:
            text = row.text_content
            if not case_sensitive:
                text = text.lower()

            if query in text:
                results.append({
                    'id': row.id,
                    'name': row.name,
                    'level': row.level,
                    'text': row.text_content,
                    'match_preview': self._get_match_preview(row.text_content, query, case_sensitive)
                })

        return results

    def _get_match_preview(self, text: str, query: str, case_sensitive: bool) -> str:
        """Get a preview of text around the match."""
        search_text = text if case_sensitive else text.lower()
        search_query = query if case_sensitive else query.lower()

        idx = search_text.find(search_query)
        if idx == -1:
            return text[:100]

        # Get context around match
        start = max(0, idx - 50)
        end = min(len(text), idx + len(query) + 50)

        preview = text[start:end]
        if start > 0:
            preview = '...' + preview
        if end < len(text):
            preview = preview + '...'

        return preview


# Convenience functions for direct use

def get_bridge(
    bike_file: Path = DEFAULT_BIKE_FILE,
    obsidian_vault: Path = DEFAULT_OBSIDIAN_VAULT
) -> BikeObsidianBridge:
    """Get a BikeObsidianBridge instance with default paths."""
    return BikeObsidianBridge(bike_file, obsidian_vault)


def export_selection_to_scratchpad(append: bool = False) -> Path:
    """
    Quick function: Export Bike selection to Obsidian ScratchPad.

    Args:
        append: If True, append to file; if False, overwrite

    Returns:
        Path to ScratchPad.md
    """
    bridge = get_bridge()
    return bridge.export_selection_to_obsidian(append=append)


def get_overall_structure(max_depth: int = 2) -> Dict[str, Any]:
    """
    Quick function: Get structure of overall.bike.

    Args:
        max_depth: How deep to traverse

    Returns:
        Dict with document structure
    """
    bridge = get_bridge()
    return bridge.get_document_structure(max_depth)


def search_overall(query: str) -> List[Dict[str, Any]]:
    """
    Quick function: Search overall.bike for text.

    Args:
        query: Text to search for

    Returns:
        List of matching rows
    """
    bridge = get_bridge()
    return bridge.search_content(query)


def list_top_items(max_items: int = 20) -> List[Dict[str, Any]]:
    """
    Quick function: List top-level items in overall.bike.

    Args:
        max_items: Maximum number to return

    Returns:
        List of top-level items
    """
    bridge = get_bridge()
    return bridge.list_top_level_items(max_items)


# ============================================================================
# Daily Note Functions
# ============================================================================

def format_date_for_bike(date: datetime) -> str:
    """
    Format a date in the format used in Bike daily notes.

    Args:
        date: datetime object

    Returns:
        Date string in format: YYYY.MM.DD
    """
    return date.strftime("%Y.%m.%d")


def parse_bike_date(date_str: str) -> Optional[datetime]:
    """
    Parse a Bike date string into a datetime object.

    Args:
        date_str: Date string in format YYYY.MM.DD

    Returns:
        datetime object or None if parsing fails
    """
    try:
        return datetime.strptime(date_str, "%Y.%m.%d")
    except ValueError:
        return None


def get_daily_note(date: Optional[Union[datetime, str]] = None) -> Optional[Dict[str, Any]]:
    """
    Get a daily note by date.

    Args:
        date: datetime object, date string (YYYY.MM.DD), or None for today

    Returns:
        Dict with daily note info or None if not found
    """
    bridge = get_bridge()

    # Handle date parameter
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        parsed = parse_bike_date(date)
        if parsed is None:
            raise ValueError(f"Invalid date format: {date}. Use YYYY.MM.DD")
        date = parsed

    date_str = format_date_for_bike(date)

    # Find the daily note
    rows = bridge.find_rows_by_name(date_str, exact=True)

    if not rows:
        return None

    # Get the first match (should be only one)
    row = rows[0]

    # Get children
    children = row.rows

    return {
        'id': row.id,
        'date': date_str,
        'name': row.name,
        'level': row.level,
        'text': row.text_content,
        'children': [
            {
                'id': child.id,
                'name': child.name,
                'level': child.level,
                'text_preview': child.text_content[:100],
                'has_children': len(child.rows) > 0,
                'child_count': len(child.rows)
            }
            for child in children
        ],
        'item_count': len(children)
    }


def get_daily_note_content(date: Optional[Union[datetime, str]] = None) -> Optional[str]:
    """
    Get the full markdown content of a daily note.

    Args:
        date: datetime object, date string (YYYY.MM.DD), or None for today

    Returns:
        Markdown string or None if not found
    """
    bridge = get_bridge()

    # Handle date parameter
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        parsed = parse_bike_date(date)
        if parsed is None:
            raise ValueError(f"Invalid date format: {date}. Use YYYY.MM.DD")
        date = parsed

    date_str = format_date_for_bike(date)

    # Find the daily note
    rows = bridge.find_rows_by_name(date_str, exact=True)

    if not rows:
        return None

    row = rows[0]

    # Export to markdown
    return bridge.export_row_to_markdown(row, include_children=True)


def get_recent_daily_notes(days: int = 7) -> List[Dict[str, Any]]:
    """
    Get recent daily notes.

    Args:
        days: Number of days to look back

    Returns:
        List of daily note info dicts, newest first
    """
    from datetime import timedelta

    results = []
    today = datetime.now()

    for i in range(days):
        date = today - timedelta(days=i)
        note = get_daily_note(date)
        if note:
            results.append(note)

    return results


def export_daily_note_to_obsidian(
    date: Optional[Union[datetime, str]] = None,
    obsidian_file: Optional[Path] = None,
    append: bool = False
) -> Optional[Path]:
    """
    Export a daily note to Obsidian.

    Args:
        date: datetime object, date string (YYYY.MM.DD), or None for today
        obsidian_file: Target file path (defaults to daily-note-YYYY-MM-DD.md)
        append: If True, append to file; if False, overwrite

    Returns:
        Path to the created file or None if note not found
    """
    bridge = get_bridge()

    # Handle date parameter
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        parsed = parse_bike_date(date)
        if parsed is None:
            raise ValueError(f"Invalid date format: {date}. Use YYYY.MM.DD")
        date = parsed

    date_str = format_date_for_bike(date)

    # Find the daily note
    rows = bridge.find_rows_by_name(date_str, exact=True)

    if not rows:
        return None

    row = rows[0]

    # Default output file
    if obsidian_file is None:
        filename = f"daily-note-{date.strftime('%Y-%m-%d')}.md"
        obsidian_file = Path(filename)

    # Export
    return bridge.export_to_obsidian(row, obsidian_file, append)


def add_to_daily_note(
    content: str,
    date: Optional[Union[datetime, str]] = None,
    parent_id: Optional[str] = None,
    markdown: bool = False
) -> BikeRow:
    """
    Add content to a daily note.

    Args:
        content: Content to add (plain text for now)
        date: Date of daily note (None = today)
        parent_id: ID of parent item (None = add to root of daily note)
        markdown: Reserved for future use (currently ignored)

    Returns:
        The created BikeRow

    Example:
        # Add plain text to today
        add_to_daily_note("hello from CC")

        # Add to specific date
        add_to_daily_note("New item", date="2025.11.11")

    Note:
        Rich text formatting (bold, italic, etc.) requires using the
        pandoc/panflute pipeline. See add_formatted_to_daily_note() for that.
    """
    bridge = get_bridge()

    # Handle date parameter
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        parsed = parse_bike_date(date)
        if parsed is None:
            raise ValueError(f"Invalid date format: {date}. Use YYYY.MM.DD")
        date = parsed

    date_str = format_date_for_bike(date)

    # Find or create the daily note
    rows = bridge.find_rows_by_name(date_str, exact=True)

    if not rows:
        # Daily note doesn't exist, create it
        daily_note_row = create_daily_note(date)
    else:
        daily_note_row = rows[0]

    # NOTE: Bike's AppleScript k.name property only accepts plain text
    # HTML tags will render as literal text, not formatting
    # For rich text, we need to use Bike's import mechanism (TODO)

    # Determine where to add the new row
    if parent_id:
        parent = bridge.find_row_by_id(parent_id)
        if parent is None:
            raise ValueError(f"Parent row {parent_id} not found")
        at_location = parent.rawrow
    else:
        # Add to the daily note itself
        at_location = daily_note_row.rawrow

    # Create the new row with plain text
    from appscript import k
    bike = bridge.bike
    new_rawrow = bike.app.make(
        new=k.row,
        with_properties={k.name: content},
        at=at_location
    )

    return BikeRow(bike, new_rawrow)


def create_daily_note(date: Optional[Union[datetime, str]] = None) -> BikeRow:
    """
    Create a daily note if it doesn't exist.

    Args:
        date: Date for the note (None = today)

    Returns:
        The daily note BikeRow
    """
    bridge = get_bridge()

    # Handle date parameter
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        parsed = parse_bike_date(date)
        if parsed is None:
            raise ValueError(f"Invalid date format: {date}. Use YYYY.MM.DD")
        date = parsed

    date_str = format_date_for_bike(date)

    # Check if it already exists
    rows = bridge.find_rows_by_name(date_str, exact=True)
    if rows:
        return rows[0]

    # Find the Daily Notes section
    daily_notes_rows = bridge.find_rows_by_name("Daily Notes", exact=True)

    if not daily_notes_rows:
        raise RuntimeError("Daily Notes section not found in overall.bike")

    daily_notes = daily_notes_rows[0]

    # Create new daily note at the beginning of Daily Notes
    from appscript import k
    bike = bridge.bike

    # Add as first child (or use .before on first existing child)
    children = daily_notes.rows
    if children:
        # Add before first child
        at_location = children[0].rawrow.before
    else:
        # Add as child of Daily Notes
        at_location = daily_notes.rawrow

    new_rawrow = bike.app.make(
        new=k.row,
        with_properties={k.name: date_str},
        at=at_location
    )

    return BikeRow(bike, new_rawrow)


def add_formatted_to_daily_note(
    content: str,
    date: Optional[Union[datetime, str]] = None,
    parent_id: Optional[str] = None,
    bike_file: Path = DEFAULT_BIKE_FILE
) -> BikeRow:
    """
    Add formatted content to a daily note by directly modifying the Bike file.

    This function supports markdown formatting (bold, italic, code, links, etc.)
    by converting markdown to Bike XML and directly writing to the file.

    **IMPORTANT**: Bike must have the file open. After modification, Bike will detect
    the change and prompt you to reload the file. Choose "Revert to Saved" to see
    the new content.

    Args:
        content: Markdown-formatted text (e.g., "This is **bold**")
        date: Date of daily note (None = today)
        parent_id: ID of parent row (None = add to root of daily note)
        bike_file: Path to the Bike file (defaults to overall.bike)

    Returns:
        A BikeRow proxy object (may need refresh after Bike reloads the file)

    Example:
        # Add formatted content to today's note
        row = add_formatted_to_daily_note("This is **bold** and *italic*")

        # Add to specific date
        row = add_formatted_to_daily_note("New item", date="2025.11.11")

    Note:
        This modifies the file directly while Bike has it open. Bike will
        detect the change and offer to reload. This is safe but requires
        manual reload confirmation.
    """
    # Handle date parameter
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        parsed = parse_bike_date(date)
        if parsed is None:
            raise ValueError(f"Invalid date format: {date}. Use YYYY.MM.DD")
        date = parsed

    date_str = format_date_for_bike(date)

    # Parse the Bike file
    parser = ET.XMLParser(remove_blank_text=True)
    tree = ET.parse(str(bike_file), parser)
    root = tree.getroot()

    # Find the daily note by date string
    daily_note_elems = root.xpath(
        f"//ns:li[ns:p/text()='{date_str}']",
        namespaces=namespaces
    )

    if not daily_note_elems:
        # Daily note doesn't exist - create it
        # Find Daily Notes section
        daily_notes_elems = root.xpath(
            f"//ns:li[ns:p/text()='Daily Notes']",
            namespaces=namespaces
        )

        if not daily_notes_elems:
            raise RuntimeError("Daily Notes section not found in Bike file")

        daily_notes_elem = daily_notes_elems[0]

        # Create nested <ul> if needed
        ul_elem = daily_notes_elem.find(f"{{{namespaces['ns']}}}ul")
        if ul_elem is None:
            ul_elem = ET.SubElement(daily_notes_elem, f"{{{namespaces['ns']}}}ul")

        # Create new daily note <li>
        new_daily_note = ET.Element(
            f"{{{namespaces['ns']}}}li",
            attrib={
                "id": generate_unique_id_attribute(5, [e.get('id') for e in root.xpath("//*[@id]")]),
                "data-type": "body"
            }
        )
        p_elem = ET.SubElement(new_daily_note, f"{{{namespaces['ns']}}}p")
        p_elem.text = date_str

        # Add at beginning
        ul_elem.insert(0, new_daily_note)
        daily_note_elem = new_daily_note
    else:
        daily_note_elem = daily_note_elems[0]

    # Determine parent element (daily note or specific parent_id)
    if parent_id:
        parent_elems = root.xpath(f"//ns:li[@id='{parent_id}']", namespaces=namespaces)
        if not parent_elems:
            raise ValueError(f"Parent row {parent_id} not found")
        parent_elem = parent_elems[0]
    else:
        parent_elem = daily_note_elem

    # Create nested <ul> for children if needed
    ul_elem = parent_elem.find(f"{{{namespaces['ns']}}}ul")
    if ul_elem is None:
        ul_elem = ET.SubElement(parent_elem, f"{{{namespaces['ns']}}}ul")

    # Create new row with formatted content
    new_id = generate_unique_id_attribute(5, [e.get('id') for e in root.xpath("//*[@id]")])
    new_li = ET.SubElement(
        ul_elem,
        f"{{{namespaces['ns']}}}li",
        attrib={"id": new_id, "data-type": "body"}
    )

    # Convert markdown to Bike XML <p> element
    p_with_formatting = markdown_to_bike_p_element(content)

    # Add the <p> element to the new <li>
    new_li.append(p_with_formatting)

    # Write back to file
    tree.write(
        str(bike_file),
        encoding='utf-8',
        xml_declaration=True,
        pretty_print=True
    )

    # Create a proxy BikeRow (won't be accurate until Bike reloads)
    # We return a minimal representation
    class TempRow:
        def __init__(self, row_id):
            self.id = row_id
            self.text_content = content  # Approximate

    return TempRow(new_id)


def _markdown_to_bike_html(text: str) -> str:
    """
    Convert simple markdown formatting to Bike HTML.

    Supports:
    - **bold** -> <strong>bold</strong>
    - *italic* -> <em>italic</em>
    - `code` -> <code>code</code>
    - ==highlight== -> <mark>highlight</mark>

    Args:
        text: Markdown text

    Returns:
        HTML text for Bike
    """
    import re

    # Bold: **text** -> <strong>text</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # Italic: *text* -> <em>text</em>
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)

    # Code: `text` -> <code>text</code>
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # Highlight: ==text== -> <mark>text</mark>
    text = re.sub(r'==(.+?)==', r'<mark>\1</mark>', text)

    return text
