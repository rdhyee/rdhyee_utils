"""
for bike
"""

from pathlib import Path as P
from typing import Union

import applescript
from appscript import app, k, its, mactypes

import lxml
import lxml.etree as ET
from lxml.html import parse, fromstring, tostring, HtmlElement



ascript = """

"""


def _to_raw(obj):
    if isinstance(obj, BikeRow):
        return obj.rawrow
    elif isinstance(obj, BikeDocument):
        return obj.rawdoc
    elif isinstance(obj, BikeRichText):
        return obj.rawrichtext
    elif isinstance(obj, BikeWindow):
        return obj.rawwindow
    else:
        return obj


class BikeRow(object):
    def __init__(self, bike, rawrow):
        self.bike = bike
        self.rawrow = rawrow
        self.read_only = ["level", "id"]

    def __getattr__(self, name):
        if name in self.read_only:
            attr = getattr(self.rawrow, name)
            return attr()
        else:
            raise AttributeError(f"Can't set attribute {name} on BikeRow")

    @property
    def name(self):
        return self.rawrow.name()

    @name.setter
    def name(self, name):
        self.rawrow.name.set(name)

    @property
    def text_content(self):
        return self.rawrow.text_content()

    @text_content.setter
    def text_content(self, text):
        self.rawrow.text_content.set(text)

    @property
    def rows(self):
        return [BikeRow(self.bike, r) for r in self.rawrow.rows()]


class BikeRichText(object):
    def __init__(self, bike, rawrichtext):
        self.bike = bike
        self.rawrichtext = rawrichtext

    def __getattr__(self, name):
        return getattr(self.rawrichtext, name)


class BikeDocument(object):
    def __init__(self, bike=None, rawdoc=None):
        if bike is None:
            self.bike = Bike()
        else:
            self.bike = bike
        if rawdoc is None:
            self.rawdoc = self.bike.app.make(new=k.document)
        else:
            self.rawdoc = rawdoc

    def __repr__(self):
        return "<BikeDocument: {}>".format(self.name)

    @property
    def id(self):
        return self.rawdoc.id()

    @property
    def name(self):
        return self.rawdoc.name()

    @property
    def url(self):
        return self.rawdoc.URL()

    @property
    def root_row(self):
        return BikeRow(self.bike, self.rawdoc.root_row())

    @property
    def entire_contents(self):
        return self.rawdoc.entire_contents()

    @property
    def modified(self):
        return self.rawdoc.modified()

    @property
    def file(self) -> Union[P, None]:
        f = self.rawdoc.file()
        if isinstance(f, mactypes.File):
            return P(f.path)
        else:
            return None

    @property
    def rows(self):
        return [BikeRow(self.bike, r) for r in self.rawdoc.rows()]

    @property
    def selection_row(self):
        return BikeRow(self.bike, self.rawdoc.selection_row())

    @property
    def selection_rows(self):
        return [BikeRow(self.bike, r) for r in self.rawdoc.selection_rows()]

    def close(self, saving=k.yes, saving_in=None):
        self.rawdoc.close(saving=saving, saving_in=saving_in)

    def save(self, in_: P = None, as_=None):
        kwargs = {}

        if in_ is not None:
            kwargs["in_"] = mactypes.File(in_)
            file_ = in_
        else:
            file_ = self.file

        if as_ is not None:
            kwargs["as_"] = as_

        self.rawdoc.save(**kwargs)

        # search for doc to reassociate with rawdoc
        self.rawdoc = self.bike.document_by_path(file_).rawdoc

    def print_(self, print_dialog=k.yes, with_properties=None):
        self.rawdoc.print_(print_dialog=print_dialog, with_properties=with_properties)

    def export(self, as_=k.plain_text_format, from_=None, all: bool = True):
        """
        all: Export all contained rows (true) or only the given rows (false). Defaults to true
        """
        assert as_ in (k.plain_text_format, k.OPML_format, k.bike_format)
        if from_ is not None:
            assert isinstance(from_, list)
            return self.rawdoc.export(as_=as_, from_=[_to_raw(obj) for obj in from_], all=all)
        else:
            return self.rawdoc.export(as_=as_, all=all)

    def lxml_html(self, from_=None, all: bool = True) -> lxml.html.HtmlElement:
        """

        all: Export all contained rows (true) or only the given rows (false). Defaults to true
        """
        doc_bike = self.export(as_=k.bike_format, from_=from_, all=all)
        html = fromstring(doc_bike.encode("utf-8"))
        return html

    def lxml_etree(self, from_=None, all: bool = True) -> ET.ElementTree:
        """

        all: Export all contained rows (true) or only the given rows (false). Defaults to true
        """
        doc_bike = self.export(as_=k.bike_format, from_=from_, all=all)
        etree = ET.fromstring(doc_bike.encode("utf-8"), ET.XMLParser(remove_blank_text=True))
        return etree

    @property
    def ids(self):
        """
        Return a list of ids of the rows
        """
        etree = self.lxml_etree()
        return [e.attrib["id"] for e in etree.xpath("//*[@id]")]

    def sort_rows(
        self,
        r: BikeRow,
        row_func=lambda r: r.name,
        reverse: bool = False,
    ) -> None:
        """
        r: the row whose children to sort
        row_func: a function that takes a row and returns a value to sort on
        reverse: whether to sort in reverse order
        """
        sort_order = sorted(
            [(x.id, row_func(x)) for x in r.rows],
            key=lambda x: x[1],
            reverse=reverse,
        )

        for id_, name in sort_order:
            r_from = self.rawdoc.rows[its.id == id_].get()[0]
            r.rawrow.move(r_from, to=r.rawrow.rows.end)

    def swap_rows(self, r: BikeRow, i: int, j: int):
        """swap the child rows i and j of parent row r"""
        # make sure i not smaller than j
        if j < i:
            (i, j) = (j, i)

        r.rawrow.rows[j].move(to=r.rawrow.rows[i].before)
        r.rawrow.rows[i + 1].move(to=r.rawrow.rows[j + 1].before)


class BikeWindow(object):
    def __init__(self, bike, rawwindow):
        self.bike = bike
        self.rawwindow = rawwindow

    def __repr__(self):
        return "<BikeWindow: {}>".format(self.name)

    @property
    def id(self):
        return self.rawwindow.id()

    @property
    def name(self):
        try:
            return self.rawwindow.name()
        except Exception:
            return ""

    @property
    def document(self):
        return BikeDocument(self.bike, self.rawwindow.document())


class Bike(object):
    def __init__(self, app_name="Bike"):
        self.app = app(app_name)
        self.scpt = applescript.AppleScript(ascript)

    def __repr__(self):
        return "<Bike: {}>".format(self.name)

    @property
    def name(self):
        return self.app.name()

    @property
    def version(self):
        return self.app.version()

    @property
    def frontmost(self):
        return self.app.frontmost()

    @property
    def windows(self):
        windows = []
        for rawwindow in self.app.windows():
            try:
                rawwindow.get()
                windows.append(BikeWindow(self, rawwindow))
            except:
                pass
        return windows

    @property
    def documents(self):
        return [BikeDocument(self, d) for d in self.app.documents()]

    def document_by_path(self, path):
        if not path.exists():
            return None
        for doc in self.documents:
            if doc.file is not None and doc.file.samefile(path):
                return doc
        return None

    def open(self, path: P):
        self.app.open(mactypes.Alias(path))


def main():
    bike = Bike()
    print(bike.name)
    bike.app.activate()
    print(bike.app.documents())


if __name__ == "__main__":
    main()
