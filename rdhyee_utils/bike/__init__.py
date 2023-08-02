"""
for bike
"""

import applescript
from appscript import app, k, its

ascript = """

"""


class BikeDocument(object):
    def __init__(self, bike, rawdoc):
        self.bike = bike
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
        return self.rawdoc.root_row()

    @property
    def entire_contents(self):
        return self.rawdoc.entire_contents()

    @property
    def modified(self):
        return self.rawdoc.modified()

    @property
    def file(self):
        return self.rawdoc.file()

    def close(self, saving=k.yes, saving_in=None):
        self.rawdoc.close(saving=saving, saving_in=saving_in)

    def save(self, in_=None, as_=None):
        self.rawdoc.save(in_=in_, as_=as_)

    def print_(self, print_dialog=k.yes, with_properties=None):
        self.rawdoc.print_(print_dialog=print_dialog, with_properties=with_properties)

    def export(self, as_=k.plain_text_format, all=True):
        assert as_ in (k.plain_text_format, k.OPML_format, k.bike_format)
        return self.rawdoc.export(as_=as_, all=all)


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
        except:
            return ""


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


def main():
    bike = Bike()
    print(bike.name)
    bike.app.activate()
    print(bike.app.documents())


if __name__ == "__main__":
    main()
