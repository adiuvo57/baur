# -*- coding: utf-8 -*-
import re


_NUMBER_RE = re.compile(r'\d+(?:[.,]\d+)?')
# Expected sale line size format, e.g. 1100x500mm or 1100 x 500 mm
GROSSE_FORMAT_RE = re.compile(
    r'^\s*(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*mm\s*$',
    re.IGNORECASE,
)
GROSSE_FORMAT_HELP = '1100x500mm'


def _to_float(value):
    return float(str(value).replace(',', '.'))


def is_valid_grosse_format(size_text):
    """Blank is valid; any other value must match WIDTHxHEIGHTmm."""
    text = (size_text or '').strip()
    if not text:
        return True
    return bool(GROSSE_FORMAT_RE.match(text))


def grosse_format_warning_message():
    return (
        'Grösse must be in the format %(example)s (width and height in millimeters). '
        'Leave the field empty if no size applies.'
    ) % {'example': GROSSE_FORMAT_HELP}


def parse_square_meter(size_text):
    text = (size_text or '').strip()
    if not text:
        return 0.0

    match = GROSSE_FORMAT_RE.match(text)
    if not match:
        return 0.0

    width = _to_float(match.group(1)) * 0.001
    height = _to_float(match.group(2)) * 0.001
    return width * height


def parse_size_lower_bound(size_label):
    text = (size_label or '').strip().lower()
    if not text:
        return None

    matches = _NUMBER_RE.findall(text)
    if not matches:
        return None

    if text.startswith('<'):
        return 0.0
    return _to_float(matches[0])
