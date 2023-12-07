import lxml.etree as ET
from lxml.etree import Element
from lxml.html import parse, fromstring, tostring, HtmlElement
from lxml import etree

from pathlib import Path as P

from typing import List, Union

import random
import string

from rdhyee_utils.bike import Bike

# import json
import panflute as pf
from panflute import (
    Doc,
    Header,
    Str,
    Para,
    Div,
    Span,
    BulletList,
    ListItem,
    Plain,
    Space,
    OrderedList,
    HorizontalRule,
    BlockQuote,
    Note,
    CodeBlock,
    Code,
    Link,
    Emph,
    Strikeout,
    Strong,
)
import pypandoc

# import pandoc

# import pytest

BALLOT_BOX = "\u2610"
BALLOT_BOX_WITH_X = "\u2612"

namespaces = {"ns": "http://www.w3.org/1999/xhtml"}
NS = f"{{{namespaces['ns']}}}"

OVERALL_PATH = P.home() / "obsidian" / "MainRY" / "bike" / "overall.bike"
ONLY_DOC_CHILDREN = True


def convert_text(
    source,
    to_="json",
    from_="markdown",
    extra_args=("--wrap=none",),
    encoding="UTF-8",
    outputfile=None,
    filters=None,
    verify_format=True,
    sandbox=False,
    cworkdir=None,
) -> str:
    # https://github.com/JessicaTegner/pypandoc/blob/5848968bda24335b4bf3dbf4a56eafa1bf88e0cd/pypandoc/__init__.py#L54
    doc = pypandoc.convert_text(
        source,
        to=to_,
        format=from_,
        extra_args=extra_args,
        encoding=encoding,
        outputfile=outputfile,
        filters=filters,
        verify_format=verify_format,
        sandbox=sandbox,
        cworkdir=cworkdir,
    )
    return doc


# write out string representation of bike document


def text_content(element, include_tail=True, strip=False):
    parts = []
    if element.text:
        if strip:
            parts.append(element.text.strip())
        else:
            parts.append(element.text)
    for e in element:
        parts.append(text_content(e))
    if include_tail and element.tail is not None:
        if strip:
            parts.append(element.tail.strip())
        else:
            parts.append(element.tail)
    return "".join(parts)


def walk_element(e, level=0):
    print("  " * level, e.tag)
    try:
        for c in e.content:
            walk_element(c, level + 1)
    except AttributeError:
        pass


# search for all tasks, done and otherwise
# <li id="R37" data-done="2023-08-01T22:39:45Z" data-type="task">


def innerhtml(element):
    parts = []
    if element.text:
        parts.append(element.text)
    for e in element:
        parts.append(etree.tostring(e).decode("utf-8"))
        if e.tail:
            parts.append(e.tail)
    return "".join(parts)


# html can be lxml.etree.Element or lxml.html.HtmlElement
def get_task_list_items(html: Union[Element, HtmlElement]) -> List[Element]:
    if isinstance(html, HtmlElement):
        return html.xpath("//li[@data-type='task']")
    elif isinstance(html, etree._Element):
        return html.xpath("//ns:li[@data-type='task']", namespaces=namespaces)


def generate_id_attribute(length):
    if length < 1:
        raise ValueError("Length must be a positive integer")

    # Start with a random letter (A-Za-z)
    first_char = random.choice(string.ascii_letters)

    # Generate the remaining characters (A-Za-z0-9-_)
    valid_chars = string.ascii_letters + string.digits + "-_"
    remaining_chars = "".join(random.choice(valid_chars) for _ in range(length - 1))

    return first_char + remaining_chars


def generate_unique_id_attribute(length, existing_ids, max_tries=100):
    try_count = 0
    while try_count < max_tries:
        id_ = generate_id_attribute(length)
        if id_ not in existing_ids:
            return id_
        try_count += 1


def cluster_runs(lst, key_func=lambda x: x):
    """
    Cluster runs of consecutive elements in a list based on a key function.

    Args:
    - lst (list): The list to cluster.
    - key_func (function): A function to transform each element for comparison.

    Returns:
    - list: A list of clustered elements.
    """
    current_cluster = []
    clusters = []

    for elem in lst:
        if not current_cluster:
            current_cluster.append(elem)
        elif key_func(elem) == key_func(current_cluster[0]):
            current_cluster.append(elem)
        else:
            clusters.append(current_cluster)
            current_cluster = [elem]

    if current_cluster:
        clusters.append(current_cluster)

    return clusters


def keep_clusters(clusters, filter_func=lambda x: True):
    """
    Filters clusters based on a filter function. Break up the other clusters in length 1 lists.

    Args:
    - clusters (list): A list of clusters.
    - filter_func (function): A function to filter each cluster.

    Returns:
    - list: A filtered list of clusters.
    """
    filtered_clusters = []

    for cluster in clusters:
        if filter_func(cluster):
            filtered_clusters.append(cluster)
        else:
            for elem in cluster:
                filtered_clusters.append([elem])

    return filtered_clusters


def wrap_in_list_item(lst):
    return [e if isinstance(e, ListItem) else ListItem(e) for e in lst]


def rich_text(xhtml, flatten=False, wrap_para=False) -> list["panflute.Element"]:
    # p, a, span, code, strong, em

    if flatten:
        xhtml_text = text_content(xhtml)
        xhtml_elem = Span(Str(xhtml_text), attributes=xhtml.attrib)
        parts = [xhtml_elem]
    else:
        # TO DO: figure out where to stick in id attribute of parent li
        parts = []
        if xhtml.text:
            parts.append(Str(xhtml.text))
        for e in xhtml:
            parts.extend(rich_text(e, flatten=flatten))
        if xhtml.tail is not None:
            parts.append(Str(xhtml.tail))

    if xhtml.tag == f"{NS}p":
        if wrap_para:
            return [Para(*parts)]
        else:
            return parts
    elif xhtml.tag == f"{NS}a":
        return [Link(*parts, url=xhtml.attrib["href"])]
    elif xhtml.tag == f"{NS}span":
        return [Span(*parts, attributes=xhtml.attrib)]
    elif xhtml.tag == f"{NS}code":
        # TO DO: think this part through more carefully -- am I flattening too much here?
        return [Code(text_content(xhtml))]
    elif xhtml.tag == f"{NS}strong":
        return [Strong(*parts)]
    elif xhtml.tag == f"{NS}em":
        return [Emph(*parts)]
    elif xhtml.tag == f"{NS}mark":
        return [Span(*parts, attributes={"class": "mark"})]
    elif xhtml.tag == f"{NS}s":
        return [Strikeout(*parts)]
    else:
        return [(Str(text_content(xhtml)))]


def bike_etree_list_to_panflute(xhtml_list, heading_level=1, meta=None):
    if meta is None:
        meta = {}
    content = []
    for xhtml in xhtml_list:
        content.extend(bike_etree_to_panflute(xhtml, heading_level, meta=meta))
    return content


def bike_etree_to_panflute(xhtml, heading_level=1, meta=None):
    if xhtml.tag == f"{NS}html":
        body = xhtml.find(f"{NS}body")
        if meta is None:
            meta = {}
        content = bike_etree_to_panflute(body, heading_level, meta=meta)
        return Doc(*content, metadata=meta, format="html")
    elif xhtml.tag == f"{NS}body":
        id_ = xhtml.find(f"{NS}ul").attrib["id"]
        return [
            Div(*bike_etree_to_panflute(xhtml.find(f"{NS}ul")), attributes={"id": id_})
        ]
        # return bike_etree_to_panflute(xhtml.find(f'{NS}ul'))
    elif xhtml.tag == f"{NS}ul":
        li_elements = xhtml.findall(f"{NS}li")

        clusters = cluster_runs(
            li_elements, lambda e: e.attrib.get("data-type", "body")
        )
        clusters = keep_clusters(
            clusters,
            lambda c: c[0].attrib.get("data-type")
            in ["ordered", "unordered", "quote", "task"],
        )

        contents = []
        for cluster in clusters:
            data_type = cluster[0].attrib.get("data-type", "body")
            if data_type in ("unordered", "task"):
                _content = []
                for c in cluster:
                    _content.extend(bike_etree_to_panflute(c, heading_level))
                content = [BulletList(*wrap_in_list_item(_content))]
            elif data_type == "ordered":
                _content = []
                for c in cluster:
                    _content.extend(bike_etree_to_panflute(c, heading_level))
                content = [OrderedList(*wrap_in_list_item(_content))]
            elif data_type == "quote":
                _content = []
                for c in cluster:
                    _content.extend(bike_etree_to_panflute(c, heading_level))
                content = [BlockQuote(*_content)]
            # elif data_type == "code":
            #     _content = []
            #     for c in cluster:
            #         _content.extend(bike_etree_to_panflute(c, heading_level))
            #     content = [CodeBlock("".join(_content))]
            else:
                content = bike_etree_to_panflute(cluster[0], heading_level)

            contents.extend(content)

        return contents
    elif xhtml.tag == f"{NS}li":
        contents = []
        data_type = xhtml.attrib.get("data-type", "body")
        id_ = xhtml.attrib.get("id")

        # for now just grab text of p
        # TODO: handle rich text
        p_text = text_content(xhtml.find(f"{NS}p", namespaces=namespaces))
        # p_elem = Span(Str(p_text), attributes=xhtml.attrib)
        wrap_para = True if data_type == "body" else False

        rich_text_elements = rich_text(
            xhtml.find(f"{NS}p", namespaces=namespaces),
            flatten=False,
            wrap_para=wrap_para,
        )

        # integrate rich_text_elements and replace p_text, p_elem

        if data_type == "body":
            # contents.append(Para(p_elem))
            contents.extend(rich_text_elements)
        elif data_type == "heading":
            if heading_level <= 6:
                contents.append(Header(*rich_text_elements, level=heading_level))
            else:
                contents.append(Para(*rich_text_elements))

            if heading_level < 6:
                heading_level += 1

        elif data_type == "hr":
            contents.append(HorizontalRule())
        elif data_type == "note":
            # TODO: handle span
            # contents.append( Para(Note(Plain(Str(p_text)))))
            contents.append(Para(Note(Plain(*rich_text_elements))))
        elif data_type == "quote":
            # contents.append((BlockQuote(Para(*rich_text_elements))))
            contents.append(((Para(*rich_text_elements))))
        elif data_type == "task":
            task_done = xhtml.attrib.get("data-done", False)
            task_marker = BALLOT_BOX if not task_done else BALLOT_BOX_WITH_X
            contents.append(
                ListItem(Plain(Str(task_marker), Space, *rich_text_elements))
            )
        elif data_type == "code":
            contents.append(CodeBlock(p_text))
            # contents.append(p_text)
        elif data_type in ("ordered", "unordered"):
            # contents.append(ListItem(Plain(p_elem)))
            contents.append(ListItem(Plain(*rich_text_elements)))
        else:
            raise ValueError(f"unknown data-type {data_type}")

        # now handle ul
        if True and xhtml.find(f"{NS}ul") is not None:
            contents.extend(
                bike_etree_to_panflute(xhtml.find(f"{NS}ul"), heading_level)
            )
            # contents.append(ListItem(*bike_etree_to_panflute(xhtml.find(f'{NS}ul'), heading_level)))

        return contents

    else:
        raise ValueError(f"unknown tag {xhtml.tag}")


def get_bike_doc(path=OVERALL_PATH):

    for d in Bike().documents:
        f = d.file
        if f is not None and f.samefile(path):
            return d


def ids(etree:ET.Element) -> List[str]:
    """
    Return a list of ids of the rows
    """
    return [e.attrib["id"] for e in etree.xpath("//*[@id]")]


def panflute_to_bike_etree(pfdoc) -> Element:
    """
    At this point: generate an empty etree
    """

    etree = ET.Element("html", nsmap=namespaces)

    # add a head
    head = ET.SubElement(etree, "head")
    meta = ET.SubElement(head, "meta", attrib={"charset": "utf-8"})

    # add a body
    body = ET.SubElement(etree, "body")

    # add a root ul to body
    root_ul = ET.SubElement(
        body, "ul", attrib={"id": generate_unique_id_attribute(8, ids(etree))}
    )

    return etree
    # print(ET.tostring(etree, pretty_print=True, encoding="utf-8", xml_declaration=True).decode('utf-8'))


# https://www.perplexity.ai/search/Write-me-a-MFQekCRfQSyjfylvmBlUng?s=c
def merge_consecutive_codeblocks(elem, doc):
    """Merge consecutive code blocks"""
    if (
        isinstance(elem, pf.CodeBlock)
        and doc.prev_elem
        and isinstance(doc.prev_elem, pf.CodeBlock)
    ):
        doc.prev_elem.text += "\n" + elem.text
        return []
    doc.prev_elem = elem


def etree_to_panflute(etree, only_doc_children=ONLY_DOC_CHILDREN):
    if only_doc_children:
        etree2 = etree.findall("ns:body/ns:ul/*", namespaces=namespaces)
        pfd = bike_etree_list_to_panflute(etree2)
        # TO DO: fancier wrapping of items -- for example, there might be ListItems that are not wrapped in a List type of some sort
        pfd = pf.Doc(*pfd)
    else:
        pfd = bike_etree_to_panflute(etree)

    pf.run_filter(merge_consecutive_codeblocks, doc=pfd)
    return pfd



# pytest tests
def test_cluster_runs():
    assert cluster_runs([1, 1, 2, 3, 2, 3, 3, 5]) == [
        [1, 1],
        [2],
        [3],
        [2],
        [3, 3],
        [5],
    ]
    assert cluster_runs(["a", "a", "b", "a"]) == [["a", "a"], ["b"], ["a"]]
    assert cluster_runs([], lambda x: x) == []


def test_keep_clusters():
    assert keep_clusters([[1, 1, 1], [2], [3, 3], [1, 1]]) == [
        [1, 1, 1],
        [2],
        [3, 3],
        [1, 1],
    ]
    assert keep_clusters([[1, 1, 1], [2], [3, 3], [1, 1]], lambda x: x[0] in (1,)) == [
        [1, 1, 1],
        [2],
        [3],
        [3],
        [1, 1],
    ]
    assert keep_clusters([], lambda x: True) == []
