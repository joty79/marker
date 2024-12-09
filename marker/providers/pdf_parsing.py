from __future__ import annotations

import math
import statistics
from ctypes import byref, c_int, create_string_buffer
from typing import Any, Dict, List, TypedDict, Union

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


class Bbox:
    def __init__(self, bbox: List[float]):
        self.bbox = bbox

    @property
    def height(self):
        return self.bbox[3] - self.bbox[1]

    @property
    def width(self):
        return self.bbox[2] - self.bbox[0]

    @property
    def area(self):
        return self.width * self.height

    @property
    def center(self):
        return [(self.bbox[0] + self.bbox[2]) / 2, (self.bbox[1] + self.bbox[3]) / 2]

    @property
    def size(self):
        return [self.width, self.height]

    @property
    def x_start(self):
        return self.bbox[0]

    @property
    def y_start(self):
        return self.bbox[1]

    @property
    def x_end(self):
        return self.bbox[2]

    @property
    def y_end(self):
        return self.bbox[3]

    def merge(self, other: Bbox) -> Bbox:
        x_start = self.x_start if self.x_start < other.x_start else other.x_start
        y_start = self.y_start if self.y_start < other.y_start else other.y_start
        x_end = self.x_end if self.x_end > other.x_end else other.x_end
        y_end = self.y_end if self.y_end > other.y_end else other.y_end

        return Bbox([x_start, y_start, x_end, y_end])

    def overlap_x(self, other: Bbox):
        return max(0, min(self.bbox[2], other.bbox[2]) - max(self.bbox[0], other.bbox[0]))

    def overlap_y(self, other: Bbox):
        return max(0, min(self.bbox[3], other.bbox[3]) - max(self.bbox[1], other.bbox[1]))

    def intersection_area(self, other: Bbox):
        return self.overlap_x(other) * self.overlap_y(other)

    def intersection_pct(self, other: Bbox):
        if self.area == 0:
            return 0

        intersection = self.intersection_area(other)
        return intersection / self.area


class Char(TypedDict):
    bbox: Bbox
    text: str
    rotation: float
    font: Dict[str, Union[Any, str]]
    char_idx: int
    char_start_idx: int
    char_end_idx: int


class Span(TypedDict):
    bbox: Bbox
    text: str
    font: Dict[str, Union[Any, str]]
    font_weight: float
    font_size: float
    chars: List[Char]


class Line(TypedDict):
    spans: List[Span]
    bbox: Bbox


class Block(TypedDict):
    lines: List[Line]
    bbox: Bbox


class Page(TypedDict):
    page: int
    bbox: Bbox
    width: int
    height: int
    blocks: List[Block]


Chars = List[Char]
Spans = List[Span]
Lines = List[Line]
Blocks = List[Block]
Pages = List[Page]


def flatten(page, flag=pdfium_c.FLAT_NORMALDISPLAY):
    rc = pdfium_c.FPDFPage_Flatten(page, flag)
    if rc == pdfium_c.FLATTEN_FAIL:
        raise pdfium.PdfiumError("Failed to flatten annotations / form fields.")


def get_fontname(textpage, i):
    font_name_str = ""
    flags = 0
    try:
        buffer_size = 256
        font_name = create_string_buffer(buffer_size)
        font_flags = c_int()

        length = pdfium_c.FPDFText_GetFontInfo(textpage, i, font_name, buffer_size, byref(font_flags))
        if length > buffer_size:
            font_name = create_string_buffer(length)
            pdfium_c.FPDFText_GetFontInfo(textpage, i, font_name, length, byref(font_flags))

        if length > 0:
            font_name_str = font_name.value.decode('utf-8')
            flags = font_flags.value
    except:
        pass
    return font_name_str, flags


def get_chars(page, textpage, loose=True) -> Chars:
    chars: Chars = []
    start_idx = 0
    end_idx = 1

    x_start, y_start, x_end, y_end = page.get_bbox()
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    for i in range(textpage.count_chars()):
        fontname, fontflag = get_fontname(textpage, i)
        text = chr(pdfium_c.FPDFText_GetUnicode(textpage, i))
        end_idx = start_idx + len(text)
        
        rotation = pdfium_c.FPDFText_GetCharAngle(textpage, i)

        loosebox = loose
        if text in ["'"] or rotation != 0:
            loosebox = False

        char_box = textpage.get_charbox(i, loose=loosebox)
        cx_start, cy_start, cx_end, cy_end = char_box

        cx_start -= x_start
        cx_end -= x_start
        cy_start -= y_start
        cy_end -= y_start

        ty_start = page_height - cy_start
        ty_end = page_height - cy_end

        bbox = [cx_start, min(ty_start, ty_end), cx_end, max(ty_start, ty_end)]
        bbox = Bbox(bbox)

        chars.append({
            "bbox": bbox,
            "text": text,
            "rotation": rotation,
            "font": {
                "name": fontname,
                "flags": fontflag,
                "size": pdfium_c.FPDFText_GetFontSize(textpage, i),
                "weight": pdfium_c.FPDFText_GetFontWeight(textpage, i),
            },
            "char_idx": i,
            "char_start_idx": start_idx,
            "char_end_idx": end_idx
        })
        start_idx = end_idx
    return chars


def get_spans(chars: Chars) -> Spans:
    spans: Spans = []
    span: Span = None

    for char in chars:
        if spans:
            span = spans[-1]

        if not span:
            spans.append({key: char[key] for key in char.keys() if key != 'char_idx'} | {"chars": [char]})
        elif (
            any(char['font'][k] != span['font'][k] for k in ['name', 'flags', 'size', 'weight'])
            or span['text'].endswith("\x02")
        ):
            spans.append({key: char[key] for key in char.keys() if key != 'char_idx'} | {"chars": [char]})
        else:
            span['text'] += char['text']
            span['char_end_idx'] = char['char_end_idx']
            span['bbox'] = span['bbox'].merge(char['bbox'])
            span['chars'].append(char)

    return spans


def get_lines(spans: Spans) -> Lines:
    lines: Lines = []
    line: Line = None

    for span in spans:
        if lines:
            line = lines[-1]

        if not line:
            lines.append({
                "spans": [span],
                "bbox": span["bbox"],
            })
        elif any(line["spans"][-1]["text"].endswith(suffix) for suffix in ["\r\n", "\x02"]):
            line["spans"][-1]["text"] = line["spans"][-1]["text"].replace("\x02", "-")
            lines.append({
                "spans": [span],
                "bbox": span["bbox"],
            })
        elif span["bbox"].y_start > line["bbox"].y_end:
            lines.append({
                "spans": [span],
                "bbox": span["bbox"],
            })
        else:
            line["spans"].append(span)
            line["bbox"] = line["bbox"].merge(span["bbox"])

    return lines


def get_blocks(lines: Lines) -> Blocks:
    if not lines:
        return []

    x_diffs = []
    y_diffs = []
    for i in range(len(lines) - 1):
        prev_center = lines[i]["bbox"].center
        curr_center = lines[i + 1]["bbox"].center
        x_diffs.append(abs(curr_center[0] - prev_center[0]))
        y_diffs.append(abs(curr_center[1] - prev_center[1]))

    median_x_gap = statistics.median(x_diffs) or 0.1
    median_y_gap = statistics.median(y_diffs) or 0.1

    tolerance_factor = 1.5
    allowed_x_gap = median_x_gap * tolerance_factor
    allowed_y_gap = median_y_gap * tolerance_factor

    blocks: Blocks = []
    for line in lines:
        if not blocks:
            # First block
            blocks.append({"lines": [line], "bbox": line["bbox"]})
            continue

        block = blocks[-1]
        last_line = block["lines"][-1]

        last_center = last_line["bbox"].center
        current_center = line["bbox"].center

        x_diff = abs(current_center[0] - last_center[0])
        y_diff = abs(current_center[1] - last_center[1])

        if x_diff <= allowed_x_gap and y_diff <= allowed_y_gap:
            block["lines"].append(line)
            block["bbox"] = block["bbox"].merge(line["bbox"])
            continue

        line_x_indented_start = last_line["bbox"].x_start > line["bbox"].x_start
        if len(block["lines"]) == 1 and line_x_indented_start and y_diff <= allowed_y_gap:
            block["lines"].append(line)
            block["bbox"] = block["bbox"].merge(line["bbox"])
            continue

        line_x_indented_end = last_line["bbox"].x_end > line["bbox"].x_end
        if line_x_indented_end and y_diff <= allowed_y_gap:
            block["lines"].append(line)
            block["bbox"] = block["bbox"].merge(line["bbox"])
            continue

        if y_diff < allowed_y_gap * 0.2 and last_line["bbox"].x_end > line["bbox"].x_start:
            block["lines"].append(line)
            block["bbox"] = block["bbox"].merge(line["bbox"])
            continue

        if block["bbox"].intersection_pct(line["bbox"]) > 0:
            block["lines"].append(line)
            block["bbox"] = block["bbox"].merge(line["bbox"])
            continue

        blocks.append({"lines": [line], "bbox": line["bbox"]})

    merged_blocks = []
    for i in range(len(blocks)):
        if not merged_blocks:
            merged_blocks.append(blocks[i])
            continue

        prev_block = merged_blocks[-1]
        curr_block = blocks[i]

        if prev_block["bbox"].intersection_pct(curr_block["bbox"]) > 0:
            merged_blocks[-1] = {
                "lines": prev_block["lines"] + curr_block["lines"],
                "bbox": prev_block["bbox"].merge(curr_block["bbox"])
            }
        else:
            merged_blocks.append(curr_block)

    return merged_blocks


def get_pages(pdf: pdfium.PdfDocument, page_range: range, flatten_pdf: bool = True) -> Pages:
    pages: Pages = []

    for page_idx in page_range:
        page = pdf.get_page(page_idx)
        if flatten_pdf:
            flatten(page)
            page = pdf.get_page(page_idx)

        textpage = page.get_textpage()

        page_bbox: List[float] = page.get_bbox()
        page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
        page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

        chars = get_chars(page, textpage)
        spans = get_spans(chars)
        lines = get_lines(spans)
        blocks = get_blocks(lines)

        pages.append({
            "page": page_idx,
            "bbox": page_bbox,
            "width": page_width,
            "height": page_height,
            "blocks": blocks
        })
    return pages


if __name__ == "__main__":
    import cProfile

    pdf_path = '/home/ubuntu/surya-test/pdfs/chinese_progit.pdf'
    pdf = pdfium.PdfDocument(pdf_path)

    cProfile.run('get_pages(pdf, range(len(pdf)))', filename='pdf_parsing_bbox.prof')

    # for page in get_pages(pdf, [481]):
    #     for block in page["blocks"]:
    #         for line_idx, line in enumerate(block["lines"]):
    #             text = ""
    #             for span_idx, span in enumerate(line["spans"]):
    #                 text += span["text"]
    #             print(text, [span["text"] for span in line["spans"]])
