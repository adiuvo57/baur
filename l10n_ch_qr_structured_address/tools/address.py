# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
"""Pure-Python helpers for Swiss QR-bill structured addresses.

Kept free of any Odoo import so that they can be unit-tested standalone and
reused by the audit script.

References
----------
* SIX, Swiss Implementation Guidelines QR-bill, version 2.3, section 4
  (data structure) and annex (permitted character set).
* Odoo 16+ ``odoo.tools.street_split`` / ``ADDRESS_REGEX`` – reference
  implementation for the split; extended here for the Swiss notation
  "Bahnhofstrasse 20 A" (building number followed by a space and a letter),
  which the upstream expression does not recognise.
"""
import re
from itertools import chain

# ---------------------------------------------------------------------------
# SIX limits for structured address elements (type "S")
# ---------------------------------------------------------------------------
MAX_NAME = 70
MAX_STREET = 70
MAX_BUILDING_NUMBER = 16
MAX_POSTAL_CODE = 16
MAX_TOWN = 35
MAX_UNSTRUCTURED_MESSAGE = 140
MAX_PAYLOAD = 997  # characters, separators included
PAYLOAD_LINES = 31  # lines produced by Odoo 15 l10n_ch (no AltPmt / StrdBkgInf)

# Positions (0-based) of the address blocks inside the payload list
CREDITOR_BLOCK = slice(4, 10)          # lines 5-10
ULTIMATE_DEBTOR_BLOCK = slice(20, 26)  # lines 21-26
UNSTRUCTURED_MESSAGE_INDEX = 29        # line 30

# ---------------------------------------------------------------------------
# Character set permitted by SIX (IG 2.3, annex "Character set")
#   Basic Latin U+0020-U+007E, Latin-1 Supplement U+00A0-U+00FF,
#   Latin Extended-A U+0100-U+017F, Romanian S/T with comma U+0218-U+021B,
#   Euro sign U+20AC
# ---------------------------------------------------------------------------
UNICODE_ALLOWED = frozenset(
    chr(code) for code in chain(range(0x20, 0x7F), range(0xA0, 0x180), range(0x218, 0x21C), (0x20AC,))
)

# Characters that are not permitted but have an obvious permitted equivalent.
# They are translated instead of dropped so that "Müller–Meier" stays readable.
_TRANSLATE = str.maketrans({
    '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-', '\u2014': '-', '\u2015': '-',  # dashes
    '\u2018': "'", '\u2019': "'", '\u201a': "'", '\u201b': "'",                                  # single quotes
    '\u201c': '"', '\u201d': '"', '\u201e': '"', '\u201f': '"',                                  # double quotes
    '\u2026': '...',                                                                              # ellipsis
    '\u00a0': ' ', '\u2007': ' ', '\u2009': ' ', '\u202f': ' ',                                  # nb / narrow spaces
    '\u2022': '-',                                                                                # bullet
})

# ---------------------------------------------------------------------------
# Street / building number split
# ---------------------------------------------------------------------------
# Upstream (Odoo 16+):  ^(.*?)(\s[0-9][0-9\S]*)?(?: - (.+))?$
# Extension:            an optional single letter after a space becomes part of
#                       the building number ("20 A", "8 b").
ADDRESS_REGEX = re.compile(r'^(.*?)(\s[0-9][0-9\S]*(?:\s[A-Za-z])?)?(?: - (.+))?$', flags=re.DOTALL)

# A second address line that is nothing but a building number: "12", "12a", "20 A"
_BARE_NUMBER = re.compile(r'^[0-9][0-9\S]*(?:\s[A-Za-z])?$')

# "CH-3628", "CH 3628", "CH3628", "LI-9490", "FL-9490" → "3628", "3628", "3628", "9490", "9490"
_POSTAL_PREFIX = re.compile(r'^(?:CH|LI|FL)[\s\-]*(?=\d)', flags=re.IGNORECASE)

# Swiss / Liechtenstein postal codes are exactly four digits
SWISS_POSTAL_CODE = re.compile(r'^\d{4}$')


def sanitize_text(value):
    """Return ``value`` reduced to the SIX character set.

    * ``None`` / ``False`` become the empty string,
    * whitespace (including line breaks, which would shift the payload) is
      collapsed to single spaces,
    * typographic dashes, quotes and non-breaking spaces are replaced by
      their ASCII equivalent,
    * every remaining character outside the permitted set is dropped.
    """
    if not value:
        return ''
    value = ' '.join(str(value).translate(_TRANSLATE).split())
    if value.isascii() and value.isprintable():
        return value  # fast path
    return ' '.join(''.join(ch for ch in value if ch in UNICODE_ALLOWED).split())


def street_split(street):
    """Split ``street`` into ``street_name``, ``street_number`` and ``street_number2``.

    >>> street_split('Bahnhofstrasse 12')
    {'street_name': 'Bahnhofstrasse', 'street_number': '12', 'street_number2': ''}
    >>> street_split('Oberdorfstrasse 20 A')['street_number']
    '20 A'
    >>> street_split('Seestrasse 7 - Gebäude B')['street_number2']
    'Gebäude B'
    """
    street = ' '.join((street or '').split())  # collapse whitespace / line breaks
    match = ADDRESS_REGEX.match(street)
    results = match.groups('') if match else ('', '', '')
    return {
        'street_name': results[0].strip(),
        'street_number': ' '.join(results[1].split()),
        'street_number2': results[2].strip(),
    }


def clean_postal_code(value):
    """Postal code without country prefix, as required by SIX (IG 2.3: "The postal
    code must be provided without a country")."""
    return _POSTAL_PREFIX.sub('', sanitize_text(value)).strip()


def is_valid_swiss_postal_code(value):
    """True when the cleaned postal code is a four-digit CH/LI code."""
    return bool(SWISS_POSTAL_CODE.match(clean_postal_code(value)))


def structured_address(street, street2, zip_code, city, street_name=None, street_number=None, street_number2=None):
    """Build the four structured address elements from raw partner data.

    Returns a dict with ``street``, ``number``, ``zip``, ``city`` already
    sanitised and truncated to the SIX maxima, plus ``source`` describing
    which rule produced the split (useful for the audit report):

    ``fields``   stored split fields (base_address_extended) were used,
    ``street``   number found in ``street``,
    ``street2``  number found in ``street2`` (Baur "c/o" pattern: the real
                 postal street is on the second line),
    ``none``     no building number could be determined.
    """
    street2_txt = sanitize_text(street2)

    if street_number:  # 1) stored split fields win (base_address_extended / custom)
        name = sanitize_text(street_name)
        number = sanitize_text(' '.join(filter(None, (street_number, street_number2))))
        source = 'fields'
    else:
        s1 = street_split(sanitize_text(street))
        name = s1['street_name']
        number = ' '.join(filter(None, (s1['street_number'], s1['street_number2'])))
        if number:
            source = 'street'
            # street2 ("c/o ...", "Postfach", department, floor) is deliberately NOT
            # appended to the building number: SIX has no slot for it and it remains
            # on the printed invoice.  (Odoo 16+ would append it when it fits in 16 chars.)
        else:
            s2 = street_split(street2_txt)
            number2 = ' '.join(filter(None, (s2['street_number'], s2['street_number2'])))
            if number2:
                # Baur pattern "c/o Firma AG" / "Auweg 41": street2 is the postal street.
                # The c/o line stays on the printed invoice; the payee is identified by Name.
                name, number, source = s2['street_name'], number2, 'street2'
            elif _BARE_NUMBER.match(street2_txt):
                # "Bahnhofstrasse" / "12": the building number alone on the second line
                number, source = street2_txt, 'street2'
            else:
                source = 'none'
                if not name:
                    name = street2_txt  # "Postfach" alone on line 2

    return {
        'street': name[:MAX_STREET],
        'number': number[:MAX_BUILDING_NUMBER],
        'zip': clean_postal_code(zip_code)[:MAX_POSTAL_CODE],
        'city': sanitize_text(city)[:MAX_TOWN],
        'source': source,
    }
