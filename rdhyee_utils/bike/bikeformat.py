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


def tag_matches(element_tag: str, tag_name: str) -> bool:
    """Check if element tag matches, handling both namespaced and plain tags."""
    return element_tag == tag_name or element_tag == f"{NS}{tag_name}"


def find_child(element, tag_name: str):
    """Find child element, handling both namespaced and plain tags."""
    # Try with namespace first, then without
    child = element.find(f"{NS}{tag_name}")
    if child is None:
        child = element.find(tag_name)
    return child


def find_children(element, tag_name: str):
    """Find all child elements, handling both namespaced and plain tags."""
    children = element.findall(f"{NS}{tag_name}")
    if not children:
        children = element.findall(tag_name)
    return children

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

    if tag_matches(xhtml.tag, "p"):
        if wrap_para:
            return [Para(*parts)]
        else:
            return parts
    elif tag_matches(xhtml.tag, "a"):
        return [Link(*parts, url=xhtml.attrib["href"])]
    elif tag_matches(xhtml.tag, "span"):
        return [Span(*parts, attributes=xhtml.attrib)]
    elif tag_matches(xhtml.tag, "code"):
        # TO DO: think this part through more carefully -- am I flattening too much here?
        return [Code(text_content(xhtml))]
    elif tag_matches(xhtml.tag, "strong"):
        return [Strong(*parts)]
    elif tag_matches(xhtml.tag, "em"):
        return [Emph(*parts)]
    elif tag_matches(xhtml.tag, "mark"):
        return [Span(*parts, attributes={"class": "mark"})]
    elif tag_matches(xhtml.tag, "s"):
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
    if tag_matches(xhtml.tag, "html"):
        body = find_child(xhtml, "body")
        if meta is None:
            meta = {}
        content = bike_etree_to_panflute(body, heading_level, meta=meta)
        return Doc(*content, metadata=meta, format="html")
    elif tag_matches(xhtml.tag, "body"):
        ul_elem = find_child(xhtml, "ul")
        id_ = ul_elem.attrib["id"]
        return [
            Div(*bike_etree_to_panflute(ul_elem), attributes={"id": id_})
        ]
        # return bike_etree_to_panflute(xhtml.find(f'{NS}ul'))
    elif tag_matches(xhtml.tag, "ul"):
        li_elements = find_children(xhtml, "li")

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
    elif tag_matches(xhtml.tag, "li"):
        contents = []
        data_type = xhtml.attrib.get("data-type", "body")
        id_ = xhtml.attrib.get("id")

        # for now just grab text of p
        # TODO: handle rich text
        p_elem = find_child(xhtml, "p")
        p_text = text_content(p_elem)
        # p_elem = Span(Str(p_text), attributes=xhtml.attrib)
        wrap_para = True if data_type == "body" else False

        rich_text_elements = rich_text(
            p_elem,
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
        ul_child = find_child(xhtml, "ul")
        if ul_child is not None:
            contents.extend(
                bike_etree_to_panflute(ul_child, heading_level)
            )
            # contents.append(ListItem(*bike_etree_to_panflute(ul_child, heading_level)))

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


def panflute_inline_to_bike_xml(elem, parent_elem):
    """
    Convert panflute inline elements to Bike XML elements.

    Maps panflute inline elements to their Bike XML equivalents:
    - Str → text content
    - Strong → <strong>
    - Emph → <em>
    - Code → <code>
    - Link → <a href="...">
    - Strikeout → <s>
    - Space/SoftBreak → " "
    - Span with class="mark" → <mark>

    Args:
        elem: Panflute inline element
        parent_elem: lxml Element to append to
    """
    if isinstance(elem, pf.Str):
        # Add text to parent
        if len(parent_elem) == 0:
            parent_elem.text = (parent_elem.text or "") + elem.text
        else:
            parent_elem[-1].tail = (parent_elem[-1].tail or "") + elem.text

    elif isinstance(elem, pf.Space):
        # Add space
        if len(parent_elem) == 0:
            parent_elem.text = (parent_elem.text or "") + " "
        else:
            parent_elem[-1].tail = (parent_elem[-1].tail or "") + " "

    elif isinstance(elem, (pf.SoftBreak, pf.LineBreak)):
        # Add space for softbreak
        if isinstance(elem, pf.SoftBreak):
            if len(parent_elem) == 0:
                parent_elem.text = (parent_elem.text or "") + " "
            else:
                parent_elem[-1].tail = (parent_elem[-1].tail or "") + " "

    elif isinstance(elem, pf.Strong):
        strong = ET.SubElement(parent_elem, f"{NS}strong")
        for child in elem.content:
            panflute_inline_to_bike_xml(child, strong)

    elif isinstance(elem, pf.Emph):
        em = ET.SubElement(parent_elem, f"{NS}em")
        for child in elem.content:
            panflute_inline_to_bike_xml(child, em)

    elif isinstance(elem, pf.Code):
        code = ET.SubElement(parent_elem, f"{NS}code")
        code.text = elem.text

    elif isinstance(elem, pf.Link):
        a = ET.SubElement(parent_elem, f"{NS}a", attrib={"href": elem.url})
        for child in elem.content:
            panflute_inline_to_bike_xml(child, a)

    elif isinstance(elem, pf.Strikeout):
        s = ET.SubElement(parent_elem, f"{NS}s")
        for child in elem.content:
            panflute_inline_to_bike_xml(child, s)

    elif isinstance(elem, pf.Span):
        # Check if it's a <mark> (highlighted text)
        if elem.attributes.get("class") == "mark":
            mark = ET.SubElement(parent_elem, f"{NS}mark")
            for child in elem.content:
                panflute_inline_to_bike_xml(child, mark)
        else:
            # Regular span
            span = ET.SubElement(parent_elem, f"{NS}span", attrib=dict(elem.attributes))
            for child in elem.content:
                panflute_inline_to_bike_xml(child, span)


def markdown_to_bike_p_element(markdown_text: str) -> Element:
    """
    Convert markdown text to a Bike <p> element with formatting.

    Args:
        markdown_text: Markdown-formatted text (e.g., "This is **bold**")

    Returns:
        lxml Element representing a <p> tag with formatted content

    Example:
        >>> p_elem = markdown_to_bike_p_element("Text with **bold** and *italic*")
        >>> ET.tostring(p_elem, encoding='unicode')
        '<p>Text with <strong>bold</strong> and <em>italic</em></p>'
    """
    # Convert markdown to panflute
    doc = pf.convert_text(markdown_text, input_format='markdown', output_format='panflute')

    # Create <p> element
    p = ET.Element(f"{NS}p")

    # Extract paragraph content and convert to Bike XML
    if doc and isinstance(doc[0], pf.Para):
        para = doc[0]
        for elem in para.content:
            panflute_inline_to_bike_xml(elem, p)

    return p


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
