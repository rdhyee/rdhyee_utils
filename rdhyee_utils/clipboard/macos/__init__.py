__ALL__ = ["PasteboardTypes", "Pasteboard", "PTYPES", "GeneralPasteboard"]

import plistlib
from typing import Any, Union, Optional

import AppKit
from AppKit import NSPasteboard, NSPasteboardItem, NSData


# hardcoded instead of trying to dynamically elicit the list from AppKit
PTYPES = (
    "NSPasteboardTypeColor",
    "NSPasteboardTypeFileURL",
    "NSPasteboardTypeFindPanelSearchOptionKey",
    "NSPasteboardTypeFindPanelSearchOptions",
    "NSPasteboardTypeFont",
    "NSPasteboardTypeHTML",
    "NSPasteboardTypeMultipleTextSelection",
    "NSPasteboardTypePDF",
    "NSPasteboardTypePNG",
    "NSPasteboardTypeRTF",
    "NSPasteboardTypeRTFD",
    "NSPasteboardTypeRuler",
    "NSPasteboardTypeSound",
    "NSPasteboardTypeString",
    "NSPasteboardTypeTIFF",
    "NSPasteboardTypeTabularText",
    "NSPasteboardTypeTextFinderOptionKey",
    "NSPasteboardTypeTextFinderOptions",
    "NSPasteboardTypeURL",
)

# abbreviations for UTIs for property list types

BINARY_PROPERTY_LIST = "com.apple.binary-property-list"
XML_PROPERTY_LIST = "com.apple.xml-property-list"

PLIST_UTI_FMT = {
    BINARY_PROPERTY_LIST: plistlib.FMT_BINARY,
    XML_PROPERTY_LIST: plistlib.FMT_XML,
}


def singleton(cls):
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance


@singleton
class PasteboardTypes:
    def __init__(self, import_types: bool = True):
        self.ptypes = PTYPES
        self.PASTEBOARD_TYPES = dict()
        module = AppKit

        for ptype in self.ptypes:
            v = getattr(module, ptype)
            self.PASTEBOARD_TYPES[ptype] = v
            if import_types:
                globals()[ptype] = v

        self.ABBR_TYPES = dict(
            (k[len("NSPasteboardType") :], v)
            for (k, v) in self.PASTEBOARD_TYPES.items()
            if k[len("NSPasteboardType") :]
        )
        self.REV_ABBR_TYPES = dict([(v, k) for (k, v) in self.ABBR_TYPES.items()])

        # add the abbreviations to the instance
        for k, v in self.ABBR_TYPES.items():
            setattr(self, k, v)


# global instance of PasteboardTypes
ptypes = PasteboardTypes()


class Pasteboard:
    """
    This is not meant to be instantiated directly.  Use one of the subclasses.
    """

    def name(self):
        return self.pb.name()

    def get_types(self):
        available_types = self.pb.types()
        return [
            (pasteboard_type, ptypes.REV_ABBR_TYPES.get(pasteboard_type))
            for pasteboard_type in available_types
        ]


class PasteboardItem:
    def __init__(self, content_list: list[tuple[str, str | bytes]] = None):
        self.item = NSPasteboardItem.alloc().init()
        if content_list:
            self.set_from_content_list(content_list)

    def get_string(self, t: str = ptypes.ABBR_TYPES["String"]) -> str | None:
        return self.item.stringForType_(t)

    def set_string(self, s: str, t: str = ptypes.ABBR_TYPES["String"]):
        self.item.setString_forType_(s, t)

    def get_data(self, t: str = ptypes.ABBR_TYPES["String"]) -> bytes | None:
        return self.item.dataForType_(t)

    def set_data(self, data: bytes, t: str = ptypes.ABBR_TYPES["String"]):
        data = NSData.dataWithBytes_length_(data, len(data))
        self.item.setData_forType_(data, t)

    def get_property_list(self, t: str = BINARY_PROPERTY_LIST):
        data = self.item.propertyListForType_(t)
        if t in (BINARY_PROPERTY_LIST, XML_PROPERTY_LIST):
            return PropertyList(data)
        else:
            return data

    def set_property_list(self, plist, t: str = BINARY_PROPERTY_LIST):
        if t in (BINARY_PROPERTY_LIST, XML_PROPERTY_LIST):
            data = plist.dumps(fmt=PLIST_UTI_FMT[t])
        else:
            data = plist
        self.item.setPropertyList_forType_(data, t)

    def set_from_content_list(self, content_list):
        for uti, content in content_list:
            if isinstance(content, str):
                # Set string content
                self.set_string(content, uti)
            elif isinstance(content, bytes):
                # Set binary data content
                self.set_data(content, uti)
            elif isinstance(content, PropertyList):
                # Set property list content
                self.set_property_list(content, uti)


class PropertyList:
    def __init__(self, data: Union[bytes, dict]) -> None:
        """
        Initialize a PropertyList object by loading plist data.

        :param data: plist data in bytes or a Python dict
        """
        self.loads(data)

    def loads(self, data: Union[bytes, dict]) -> Any:
        """
        Load plist data.

        :param data: plist data in bytes or a Python dict
        :return: parsed plist data
        """
        if isinstance(data, bytes):
            try:
                self.plist_data = plistlib.loads(data)
            except Exception as e:
                raise ValueError(f"Unable to parse plist data: {e}")
        elif isinstance(data, dict):
            self.plist_data = data
        else:
            raise ValueError("Invalid data type. Data should be bytes or dict.")
        return self.plist_data

    def dumps(self, fmt: Optional[Union[int, str]] = plistlib.FMT_BINARY) -> bytes:
        """
        Dump plist data to bytes.

        :param fmt: Format to use for dumping. Options are plistlib.FMT_BINARY or plistlib.FMT_XML
        :return: plist data in bytes
        """
        if fmt not in (plistlib.FMT_BINARY, plistlib.FMT_XML):
            raise ValueError(
                "Invalid format. Use plistlib.FMT_BINARY or plistlib.FMT_XML."
            )
        return plistlib.dumps(self.plist_data, fmt=fmt)


class GeneralPasteboard(Pasteboard):
    def __init__(self):
        self.pb = NSPasteboard.generalPasteboard()

    def get_string(self, t: str = ptypes.ABBR_TYPES["String"]) -> str | None:
        return self.pb.stringForType_(t)

    def get_data(self, t: str = ptypes.ABBR_TYPES["String"]) -> bytes | None:
        return self.pb.dataForType_(t)

    def get_property_list(self, t: str = BINARY_PROPERTY_LIST):
        data = self.pb.propertyListForType_(t)
        if t in (BINARY_PROPERTY_LIST, XML_PROPERTY_LIST):
            return PropertyList(data)
        else:
            return data

    def set_content(self, content_list: list[PasteboardItem]):
        # Clear existing contents
        self.pb.clearContents()

        # Create pasteboard item
        # pbitem = PasteboardItem()
        # pbitem.set_from_content_list(content_list)

        # Write the item to the pasteboard
        self.pb.writeObjects_([pbitem.item for pbitem in content_list])

    def set_string(self, s: str, t: str = ptypes.ABBR_TYPES["String"]):
        """
        set the string content of the clipboard
        """
        # self.set_content([(t, s)])
        self.set_content([PasteboardItem([(t, s)])])

    def set_data(self, data: bytes, t: str = ptypes.ABBR_TYPES["String"]):
        """
        set the binary data content of the clipboard
        """
        # self.set_content([(t, data)])
        self.set_content([PasteboardItem([(t, data)])])
