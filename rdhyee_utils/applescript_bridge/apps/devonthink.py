"""
DEVONthink - Python bindings for DEVONthink 4 via appscript.

Provides Pythonic access to DEVONthink's AppleScript dictionary for
searching, reading records, managing databases, tags, custom metadata,
and DT4's AI features (chat, summarize, transcribe, classify).

The adapter checks whether DEVONthink is running before attempting to
launch it, preserving the user's session state.

Key classes:
- DEVONthink: Top-level app (databases, global search, chat, state)
- DTDatabase: A database (records, groups, search within)
- DTRecord: A record (content, tags, metadata, children)

Example:
    >>> from rdhyee_utils.applescript_bridge.apps.devonthink import DEVONthink
    >>> dt = DEVONthink()
    >>> dt.is_running
    True
    >>> for db in dt.databases:
    ...     print(db.name, db.uuid)
    >>> results = dt.search("python tutorial")
    >>> for rec in results[:5]:
    ...     print(rec.name, rec.kind, rec.tags)
    >>> rec = dt.get_record_by_uuid("SOME-UUID-HERE")
    >>> print(rec.plain_text[:200])
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

try:
    from appscript import app as appscript_app, k, its

    HAS_APPSCRIPT = True
except ImportError:
    HAS_APPSCRIPT = False


# ---------------------------------------------------------------------------
# Enum mappings (AppleScript enum names → appscript k.* constants)
# ---------------------------------------------------------------------------

# Chat engines (ChEg)
CHAT_ENGINES = {
    "apple": "AppleIntelligence",
    "chatgpt": "ChatGPT",
    "openai": "ChatGPT",
    "claude": "Claude",
    "anthropic": "Claude",
    "gemini": "Gemini",
    "google": "Gemini",
    "mistral": "Mistral",
    "perplexity": "Perplexity",
    "openrouter": "OpenRouter",
    "openai-compatible": "OpenAI_Compatible",
    "lmstudio": "LM_Studio",
    "ollama": "Ollama",
    "remote-ollama": "Remote_Ollama",
}

# Update modes (Umod)
UPDATE_MODES = {
    "set": "replacing",
    "replace": "replacing",
    "append": "appending",
    "insert": "inserting",
}

# Summary styles (Ssty)
SUMMARY_STYLES = {
    "list": "list_summary",
    "key_points": "key_points_summary",
    "table": "table_summary",
    "text": "text_summary",
    "custom": "custom_summary",
}


def _resolve_enum(name: str, mapping: dict, label: str = "value"):
    """Resolve a friendly name to an appscript k.* enum constant."""
    if not HAS_APPSCRIPT:
        return name
    canonical = mapping.get(name.lower(), name)
    enum_val = getattr(k, canonical, None)
    if enum_val is None:
        raise ValueError(
            f"Unknown {label} {name!r}. Valid: {list(mapping.keys())}"
        )
    return enum_val


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_running(app_name: str = "DEVONthink") -> bool:
    """Check if the app is running without launching it."""
    result = subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to (name of processes) contains "{app_name}"'],
        capture_output=True, text=True,
    )
    return result.stdout.strip() == "true"


def _osascript(script: str, timeout: int = 30) -> str:
    """Run an AppleScript snippet and return stdout."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"AppleScript error: {result.stderr.strip()}")
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# DTRecord
# ---------------------------------------------------------------------------

class DTRecord:
    """A DEVONthink record (document, group, tag, etc.).

    Wraps an appscript record reference. Properties are fetched lazily.
    """

    def __init__(self, raw, database: Optional[DTDatabase] = None):
        self._raw = raw
        self._database = database
        self._props: Optional[dict] = None

    def _get_props(self) -> dict:
        if self._props is None:
            self._props = self._raw.properties()
        return self._props

    def _prop(self, key, default=None):
        try:
            return self._get_props().get(key, default)
        except Exception:
            return default

    # --- Identity ---

    @property
    def id(self) -> int:
        return self._raw.id()

    @property
    def uuid(self) -> str:
        return self._raw.uuid()

    @property
    def name(self) -> str:
        return self._raw.name()

    @name.setter
    def name(self, value: str) -> None:
        self._raw.name.set(value)
        self._props = None

    # --- Type & kind ---

    @property
    def kind(self) -> str:
        """Human-readable type string (e.g. 'Markdown', 'PDF Document')."""
        return self._raw.kind()

    @property
    def record_type(self) -> str:
        """AppleScript type enum value."""
        return str(self._raw.record_type())

    # --- Content ---

    @property
    def plain_text(self) -> str:
        """Plain text content of the record."""
        return self._raw.plain_text()

    @plain_text.setter
    def plain_text(self, value: str) -> None:
        self._raw.plain_text.set(value)

    @property
    def rich_text(self) -> str:
        """Rich text content."""
        return self._raw.rich_text()

    @property
    def source(self) -> str:
        """HTML/source content."""
        return self._raw.source()

    @property
    def markdown_source(self) -> str:
        """Markdown source (DT4-specific, read-only)."""
        try:
            return self._raw.markdown_source()
        except Exception:
            return ""

    @property
    def url(self) -> str:
        return self._raw.URL() or ""

    @url.setter
    def url(self, value: str) -> None:
        self._raw.URL.set(value)

    @property
    def reference_url(self) -> str:
        """DEVONthink x-devonthink-item:// URL."""
        return self._raw.reference_URL() or ""

    # --- Metadata ---

    @property
    def comment(self) -> str:
        return self._raw.comment() or ""

    @comment.setter
    def comment(self, value: str) -> None:
        self._raw.comment.set(value)

    @property
    def aliases(self) -> str:
        return self._raw.aliases() or ""

    @aliases.setter
    def aliases(self, value: str) -> None:
        self._raw.aliases.set(value)

    @property
    def tags(self) -> List[str]:
        return self._raw.tags() or []

    @tags.setter
    def tags(self, value: List[str]) -> None:
        self._raw.tags.set(value)

    @property
    def label(self) -> int:
        return self._raw.label()

    @label.setter
    def label(self, value: int) -> None:
        self._raw.label.set(value)

    @property
    def flag(self) -> bool:
        try:
            return self._raw.flag()
        except Exception:
            return False

    @flag.setter
    def flag(self, value: bool) -> None:
        self._raw.flag.set(value)

    @property
    def rating(self) -> int:
        return self._raw.rating()

    @rating.setter
    def rating(self, value: int) -> None:
        self._raw.rating.set(value)

    @property
    def unread(self) -> bool:
        return self._raw.unread()

    @unread.setter
    def unread(self, value: bool) -> None:
        self._raw.unread.set(value)

    @property
    def locking(self) -> bool:
        return self._raw.locking()

    @locking.setter
    def locking(self, value: bool) -> None:
        self._raw.locking.set(value)

    # --- Custom metadata ---

    @property
    def custom_meta_data(self) -> dict:
        """All custom metadata as a dict."""
        try:
            return self._raw.custom_meta_data() or {}
        except Exception:
            return {}

    @custom_meta_data.setter
    def custom_meta_data(self, value: dict) -> None:
        self._raw.custom_meta_data.set(value)

    # --- Dates ---

    @property
    def creation_date(self) -> Optional[datetime]:
        try:
            return self._raw.creation_date()
        except Exception:
            return None

    @property
    def modification_date(self) -> Optional[datetime]:
        try:
            return self._raw.modification_date()
        except Exception:
            return None

    @property
    def addition_date(self) -> Optional[datetime]:
        try:
            return self._raw.addition_date()
        except Exception:
            return None

    # --- File info ---

    @property
    def filename(self) -> str:
        return self._raw.filename() or ""

    @property
    def path(self) -> str:
        return self._raw.path() or ""

    @property
    def size(self) -> int:
        return self._raw.size()

    @property
    def location(self) -> str:
        """Location (POSIX-like path within the database)."""
        return self._raw.location() or ""

    @property
    def mime_type(self) -> str:
        return self._raw.MIME_type() or ""

    @property
    def indexed(self) -> bool:
        return self._raw.indexed()

    @property
    def page_count(self) -> int:
        try:
            return self._raw.page_count()
        except Exception:
            return 0

    @property
    def word_count(self) -> int:
        try:
            return self._raw.word_count()
        except Exception:
            return 0

    @property
    def character_count(self) -> int:
        try:
            return self._raw.character_count()
        except Exception:
            return 0

    # --- Relationships ---

    @property
    def children(self) -> List[DTRecord]:
        """Child records (for groups)."""
        try:
            return [DTRecord(c, self._database) for c in self._raw.children()]
        except Exception:
            return []

    @property
    def parents(self) -> List[DTRecord]:
        """Parent groups."""
        try:
            return [DTRecord(p, self._database) for p in self._raw.parents()]
        except Exception:
            return []

    @property
    def duplicates(self) -> List[DTRecord]:
        try:
            return [DTRecord(d, self._database) for d in self._raw.duplicates()]
        except Exception:
            return []

    @property
    def annotation(self) -> Optional[DTRecord]:
        try:
            ann = self._raw.annotation()
            return DTRecord(ann, self._database) if ann else None
        except Exception:
            return None

    @property
    def score(self) -> float:
        """Search relevance score (set after search operations)."""
        try:
            return self._raw.score()
        except Exception:
            return 0.0

    @property
    def database(self) -> Optional[DTDatabase]:
        """The database this record belongs to."""
        if self._database:
            return self._database
        try:
            return DTDatabase(self._raw.database())
        except Exception:
            return None

    # --- Convenience ---

    def summary(self) -> dict:
        """Return a lightweight dict summary of this record."""
        return {
            "name": self.name,
            "uuid": self.uuid,
            "kind": self.kind,
            "tags": self.tags,
            "location": self.location,
            "size": self.size,
            "word_count": self.word_count,
            "url": self.url,
            "reference_url": self.reference_url,
        }

    def __repr__(self) -> str:
        try:
            return f"DTRecord({self.name!r}, kind={self.kind!r}, uuid={self.uuid!r})"
        except Exception:
            return "DTRecord(<unresolved>)"


# ---------------------------------------------------------------------------
# DTDatabase
# ---------------------------------------------------------------------------

class DTDatabase:
    """A DEVONthink database."""

    def __init__(self, raw, app=None):
        self._raw = raw
        self._app = app  # reference to the appscript app object

    @property
    def id(self) -> int:
        return self._raw.id()

    @property
    def uuid(self) -> str:
        return self._raw.uuid()

    @property
    def name(self) -> str:
        return self._raw.name()

    @property
    def path(self) -> str:
        return self._raw.path()

    @property
    def read_only(self) -> bool:
        return self._raw.read_only()

    @property
    def encrypted(self) -> bool:
        return self._raw.encrypted()

    @property
    def root(self) -> DTRecord:
        """Root group of the database."""
        return DTRecord(self._raw.root(), self)

    @property
    def inbox(self) -> DTRecord:
        """Inbox group."""
        return DTRecord(self._raw.incoming_group(), self)

    @property
    def trash(self) -> DTRecord:
        """Trash group."""
        return DTRecord(self._raw.trash_group(), self)

    @property
    def tags_group(self) -> DTRecord:
        """Tags group."""
        return DTRecord(self._raw.tags_group(), self)

    @property
    def current_group(self) -> DTRecord:
        """Currently selected group."""
        return DTRecord(self._raw.current_group(), self)

    def _get_app(self):
        """Get the appscript app reference."""
        if self._app:
            return self._app
        return appscript_app("DEVONthink")

    # --- Record access ---

    def get_record_at(self, location: str) -> Optional[DTRecord]:
        """Get record by POSIX-style path within the database."""
        try:
            rec = self._get_app().get_record_at(location, in_=self._raw)
            return DTRecord(rec, self)
        except Exception:
            return None

    def search(self, query: str, in_group: Optional[DTRecord] = None) -> List[DTRecord]:
        """Search within this database."""
        target = in_group._raw if in_group else self._raw.root()
        results = self._get_app().search(query, in_=target)
        return [DTRecord(r, self) for r in results]

    def create_location(self, path: str) -> DTRecord:
        """Create a hierarchy of groups if necessary."""
        rec = self._get_app().create_location(path, in_=self._raw)
        return DTRecord(rec, self)

    def top_groups(self) -> List[DTRecord]:
        """Return top-level children of the root group."""
        return self.root.children

    def summary(self) -> dict:
        return {
            "name": self.name,
            "uuid": self.uuid,
            "path": self.path,
            "read_only": self.read_only,
            "encrypted": self.encrypted,
        }

    def __repr__(self) -> str:
        try:
            return f"DTDatabase({self.name!r}, uuid={self.uuid!r})"
        except Exception:
            return "DTDatabase(<unresolved>)"


# ---------------------------------------------------------------------------
# DEVONthink (top-level)
# ---------------------------------------------------------------------------

class DEVONthink:
    """Python interface to DEVONthink (v4+) via appscript.

    Checks if DEVONthink is running before connecting, to avoid
    unintentionally launching the application.
    """

    # Try both names — "DEVONthink" (v4) and "DEVONthink 3"
    APP_NAME = "DEVONthink"
    PROCESS_NAME = "DEVONthink"

    def __init__(self, app_name: str = APP_NAME, require_running: bool = True):
        if not HAS_APPSCRIPT:
            raise ImportError(
                "appscript is required: pip install appscript"
            )
        if require_running and not _is_running(self.PROCESS_NAME):
            raise RuntimeError(
                f"{self.PROCESS_NAME} is not running. "
                "Launch it first or pass require_running=False."
            )
        self._app_name = app_name
        self._app = appscript_app(app_name)

    # --- App state ---

    @property
    def is_running(self) -> bool:
        return _is_running(self.PROCESS_NAME)

    @property
    def version(self) -> str:
        return self._app.version()

    @property
    def name(self) -> str:
        return self._app.name()

    # --- Databases ---

    @property
    def databases(self) -> List[DTDatabase]:
        """All open databases."""
        return [DTDatabase(db, self._app) for db in self._app.databases()]

    def database(self, name: str) -> Optional[DTDatabase]:
        """Get a database by name."""
        for db in self.databases:
            if db.name == name:
                return db
        return None

    @property
    def current_database(self) -> Optional[DTDatabase]:
        try:
            return DTDatabase(self._app.current_database(), self._app)
        except Exception:
            return None

    @property
    def inbox(self) -> Optional[DTDatabase]:
        try:
            return DTDatabase(self._app.inbox(), self._app)
        except Exception:
            return None

    def open_database(self, path: str) -> Optional[DTDatabase]:
        """Open a database by POSIX path."""
        try:
            db = self._app.open_database(path)
            return DTDatabase(db, self._app) if db else None
        except Exception as e:
            raise RuntimeError(f"Failed to open database at {path}: {e}")

    # --- Global record access ---

    def get_record_by_uuid(self, uuid: str) -> Optional[DTRecord]:
        """Get any record by UUID (searches all open databases)."""
        try:
            rec = self._app.get_record_with_uuid(uuid)
            return DTRecord(rec)
        except Exception:
            return None

    def get_record_by_id(self, id: int) -> Optional[DTRecord]:
        """Get any record by internal ID."""
        try:
            rec = self._app.get_record_with_id(id)
            return DTRecord(rec)
        except Exception:
            return None

    # --- Search ---

    def search(self, query: str, in_group: Optional[DTRecord] = None,
               database: Optional[DTDatabase] = None) -> List[DTRecord]:
        """Search across all databases or within a specific group/database.

        Args:
            query: DEVONthink search string (supports operators and wildcards).
            in_group: Optional group to limit search to.
            database: Optional database to limit search to (uses its root).
        """
        kwargs = {}
        if in_group:
            kwargs["in_"] = in_group._raw
        elif database:
            kwargs["in_"] = database._raw.root()
        results = self._app.search(query, **kwargs)
        return [DTRecord(r) for r in results]

    # --- Lookup ---

    def lookup_by_tags(self, tags: List[str], any_tag: bool = False,
                       database: Optional[DTDatabase] = None) -> List[DTRecord]:
        """Find records matching tags."""
        kwargs = {}
        if any_tag:
            kwargs["any"] = True
        if database:
            kwargs["in_"] = database._raw
        results = self._app.lookup_records_with_tags(tags, **kwargs)
        return [DTRecord(r) for r in results]

    def lookup_by_url(self, url: str,
                      database: Optional[DTDatabase] = None) -> List[DTRecord]:
        kwargs = {}
        if database:
            kwargs["in_"] = database._raw
        results = self._app.lookup_records_with_URL(url, **kwargs)
        return [DTRecord(r) for r in results]

    def lookup_by_comment(self, comment: str,
                          database: Optional[DTDatabase] = None) -> List[DTRecord]:
        kwargs = {}
        if database:
            kwargs["in_"] = database._raw
        results = self._app.lookup_records_with_comment(comment, **kwargs)
        return [DTRecord(r) for r in results]

    def lookup_by_path(self, path: str,
                       database: Optional[DTDatabase] = None) -> List[DTRecord]:
        kwargs = {}
        if database:
            kwargs["in_"] = database._raw
        results = self._app.lookup_records_with_path(path, **kwargs)
        return [DTRecord(r) for r in results]

    # --- Record creation ---

    def create_record(self, properties: dict,
                      in_group: Optional[DTRecord] = None) -> DTRecord:
        """Create a new record.

        Args:
            properties: Dict with keys like 'name', 'type', 'plain text',
                'URL', 'tags', 'comment', etc.
            in_group: Destination group (uses incoming group if not specified).
        """
        kwargs = {}
        if in_group:
            kwargs["in_"] = in_group._raw
        rec = self._app.create_record_with(properties, **kwargs)
        return DTRecord(rec)

    def create_markdown(self, name: str, text: str,
                        in_group: Optional[DTRecord] = None,
                        tags: Optional[List[str]] = None) -> DTRecord:
        """Convenience: create a Markdown record."""
        props = {"name": name, "type": "markdown", "plain text": text}
        if tags:
            props["tags"] = tags
        return self.create_record(props, in_group)

    def import_path(self, path: str,
                    to_group: Optional[DTRecord] = None) -> DTRecord:
        """Import a file or folder."""
        kwargs = {}
        if to_group:
            kwargs["to"] = to_group._raw
        rec = self._app.import_path(path, **kwargs)
        return DTRecord(rec)

    def index_path(self, path: str,
                   to_group: Optional[DTRecord] = None) -> DTRecord:
        """Index a file or folder (keeps external, doesn't copy into DB)."""
        kwargs = {}
        if to_group:
            kwargs["to"] = to_group._raw
        rec = self._app.index_path(path, **kwargs)
        return DTRecord(rec)

    # --- Custom metadata (app-level commands) ---

    def get_custom_meta(self, key: str, record: DTRecord,
                        default: Any = None) -> Any:
        """Get a custom metadata value from a record."""
        kwargs = {"for_": key, "from_": record._raw}
        if default is not None:
            kwargs["default_value"] = default
        return self._app.get_custom_meta_data(**kwargs)

    def set_custom_meta(self, key: str, value: Any,
                        record: DTRecord) -> bool:
        """Set a custom metadata value on a record."""
        return self._app.add_custom_meta_data(value, for_=key, to=record._raw)

    # --- AI / Chat (DT4 features) ---

    def chat(self, prompt: str, *,
             record: Optional[Union[DTRecord, List[DTRecord]]] = None,
             engine: Optional[str] = None,
             model: Optional[str] = None,
             temperature: Optional[float] = None,
             response_format: str = "text") -> str:
        """Send a chat prompt to DT4's built-in AI.

        Args:
            prompt: The message to send.
            record: Optional record(s) to use as context.
            engine: Friendly name ('claude', 'chatgpt', 'gemini', 'ollama', etc.).
            model: Model name string.
            temperature: 0-2, controls randomness.
            response_format: 'text', 'JSON', 'HTML', 'PDF', 'message', 'raw'.
        """
        kwargs = {}
        if record:
            if isinstance(record, list):
                kwargs["record"] = [r._raw for r in record]
            else:
                kwargs["record"] = record._raw
        if engine:
            kwargs["engine"] = _resolve_enum(engine, CHAT_ENGINES, "chat engine")
        if model:
            kwargs["model"] = model
        if temperature is not None:
            kwargs["temperature"] = temperature
        if response_format != "text":
            kwargs["as_"] = response_format
        return self._app.get_chat_response_for_message(prompt, **kwargs)

    def chat_models(self, engine: str) -> list:
        """Get available models for a chat engine.

        Args:
            engine: Friendly name ('claude', 'chatgpt', 'gemini', 'ollama', etc.).
        """
        engine_enum = _resolve_enum(engine, CHAT_ENGINES, "chat engine")
        return self._app.get_chat_models_for_engine(engine_enum)

    def chat_research(self, query: str, sources: List[str],
                      max_results: int = 10) -> Any:
        """AI-enhanced research across local and online sources.

        Args:
            query: Search string.
            sources: List from ['databases', 'arXiv', 'PubMed', 'web', 'Wikipedia'].
            max_results: Maximum number of results.
        """
        return self._app.perform_chat_research(
            query, sources=sources, maximum_results=max_results
        )

    # --- Summarize ---

    def summarize_text(self, text: str, style: Optional[str] = None) -> str:
        """Summarize text using DT4's AI."""
        kwargs = {}
        if style:
            kwargs["as_"] = style
        return self._app.summarize_text(text, **kwargs)

    def summarize_records(self, records: List[DTRecord],
                          format: str = "markdown",
                          in_group: Optional[DTRecord] = None) -> Any:
        """Summarize contents of records."""
        kwargs = {"records": [r._raw for r in records], "to": format}
        if in_group:
            kwargs["in_"] = in_group._raw
        return self._app.summarize_contents_of(**kwargs)

    # --- Transcribe ---

    def transcribe(self, record: DTRecord, *,
                   language: Optional[str] = None,
                   timestamps: Optional[bool] = None) -> str:
        """Transcribe audio/video/PDF/image."""
        kwargs = {"record": record._raw}
        if language is not None:
            kwargs["language"] = language
        if timestamps is not None:
            kwargs["timestamps"] = timestamps
        return self._app.transcribe(**kwargs)

    # --- Classify & Compare ---

    def classify(self, record: DTRecord,
                 database: Optional[DTDatabase] = None) -> List[DTRecord]:
        """Get classification proposals for a record."""
        kwargs = {"record": record._raw}
        if database:
            kwargs["in_"] = database._raw
        results = self._app.classify(**kwargs)
        return [DTRecord(r) for r in results]

    def compare(self, record: Optional[DTRecord] = None,
                content: Optional[str] = None,
                database: Optional[DTDatabase] = None) -> List[DTRecord]:
        """Find similar records (See Also)."""
        kwargs = {}
        if record:
            kwargs["record"] = record._raw
        if content:
            kwargs["content"] = content
        if database:
            kwargs["to"] = database._raw
        results = self._app.compare(**kwargs)
        return [DTRecord(r) for r in results]

    def extract_keywords(self, record: DTRecord, *,
                         hash_tags: bool = False,
                         existing_tags: bool = False,
                         image_tags: bool = False) -> list:
        """Extract keywords from a record."""
        kwargs = {"record": record._raw}
        if hash_tags:
            kwargs["hash_tags"] = True
        if existing_tags:
            kwargs["existing_tags"] = True
        if image_tags:
            kwargs["image_tags"] = True
        return self._app.extract_keywords_from(**kwargs)

    # --- Versioning (DT4) ---

    def save_version(self, record: DTRecord) -> Any:
        """Save a version of a record (call before editing)."""
        return self._app.save_version_of(record=record._raw)

    def get_versions(self, record: DTRecord) -> list:
        """Get saved versions of a record."""
        return self._app.get_versions_of(record=record._raw)

    # --- Update (DT4) ---

    def update_record(self, record: DTRecord, text: str,
                      mode: str = "set") -> Any:
        """Update text of a text/Markdown/HTML record.

        Args:
            record: The record to update.
            text: The text content.
            mode: 'set' (replace), 'append', or 'insert'.
        """
        mode_enum = _resolve_enum(mode, UPDATE_MODES, "update mode")
        return self._app.update(record=record._raw, with_text=text, mode=mode_enum)

    # --- Selection ---

    @property
    def selection(self) -> List[DTRecord]:
        """Currently selected records in the frontmost window."""
        try:
            return [DTRecord(r) for r in self._app.selection()]
        except Exception:
            return []

    @property
    def content_record(self) -> Optional[DTRecord]:
        """Currently displayed record."""
        try:
            return DTRecord(self._app.content_record())
        except Exception:
            return None

    # --- Convenience ---

    def __repr__(self) -> str:
        running = self.is_running
        db_count = len(self.databases) if running else 0
        return f"DEVONthink(v{self.version}, databases={db_count})"
