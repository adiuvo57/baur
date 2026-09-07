# -*- coding: utf-8 -*-
# Powered by Mindphin Technologies.
"""Pure-Python tests of the address helpers (no database needed)."""
from odoo.tests.common import BaseCase, tagged

from ..tools.address import clean_postal_code, is_valid_swiss_postal_code, sanitize_text, street_split, structured_address


@tagged('standard', 'at_install', 'l10n_ch_qr')
class TestStreetSplit(BaseCase):

    def _split(self, street):
        result = street_split(street)
        return result['street_name'], result['street_number']

    def test_standard_cases(self):
        self.assertEqual(self._split('Bahnhofstrasse 12'), ('Bahnhofstrasse', '12'))
        self.assertEqual(self._split('Rue de la Gare 12a'), ('Rue de la Gare', '12a'))
        self.assertEqual(self._split('Via Nassa 12-14'), ('Via Nassa', '12-14'))
        self.assertEqual(self._split('Postfach 250'), ('Postfach', '250'))
        self.assertEqual(self._split('Route de Lausanne 12b'), ('Route de Lausanne', '12b'))

    def test_baur_letter_suffix_with_space(self):
        """'20 A' notation used by ~550 Baur customers (not handled upstream)."""
        self.assertEqual(self._split('Oberdorfstrasse 20 A'), ('Oberdorfstrasse', '20 A'))
        self.assertEqual(self._split('Höheweg 8 B'), ('Höheweg', '8 B'))
        self.assertEqual(self._split('Wyssbach 16 a'), ('Wyssbach', '16 a'))
        self.assertEqual(self._split('Alte Bernstr. 160 B'), ('Alte Bernstr.', '160 B'))
        self.assertEqual(self._split('Engehaldenstrasse  202   A'), ('Engehaldenstrasse', '202 A'))

    def test_digits_inside_street_name(self):
        self.assertEqual(self._split('Chemin des 3 Sapins 4'), ('Chemin des 3 Sapins', '4'))

    def test_no_number(self):
        self.assertEqual(self._split('Industriestrasse'), ('Industriestrasse', ''))
        self.assertEqual(self._split('Dorf'), ('Dorf', ''))
        self.assertEqual(self._split(''), ('', ''))
        self.assertEqual(self._split(None), ('', ''))
        self.assertEqual(self._split(False), ('', ''))

    def test_unparseable_stays_untouched(self):
        # real Baur records that must land in the audit report, not be guessed
        self.assertEqual(self._split('Talackerstrasse 43 I ,K, L'), ('Talackerstrasse 43 I ,K, L', ''))
        self.assertEqual(self._split('12, rue du Marché'), ('12, rue du Marché', ''))
        self.assertEqual(self._split('Hauptstrasse 5 c/o Meier'), ('Hauptstrasse 5 c/o Meier', ''))

    def test_secondary_number(self):
        result = street_split('Seestrasse 7 - Gebäude B')
        self.assertEqual(result, {'street_name': 'Seestrasse', 'street_number': '7', 'street_number2': 'Gebäude B'})


@tagged('standard', 'at_install', 'l10n_ch_qr')
class TestSanitize(BaseCase):

    def test_whitespace_and_newlines(self):
        self.assertEqual(sanitize_text('Muster\nAG'), 'Muster AG')
        self.assertEqual(sanitize_text('  Muster \t AG \r\n'), 'Muster AG')
        self.assertEqual(sanitize_text('Muster AG'), 'Muster AG')

    def test_typographic_characters_translated(self):
        self.assertEqual(sanitize_text('Müller–Meier'), 'Müller-Meier')
        self.assertEqual(sanitize_text('“Villa” d’Or'), '"Villa" d\'Or')

    def test_forbidden_characters_dropped(self):
        self.assertEqual(sanitize_text('Zürich ☺ AG'), 'Zürich AG')
        self.assertEqual(sanitize_text('Café 5€'), 'Café 5€')      # Latin-1 + Euro are allowed
        self.assertEqual(sanitize_text('Łódź'), 'Łódź')            # Latin Extended-A allowed

    def test_empty(self):
        self.assertEqual(sanitize_text(None), '')
        self.assertEqual(sanitize_text(False), '')
        self.assertEqual(sanitize_text(''), '')

    def test_postal_code_prefix(self):
        self.assertEqual(clean_postal_code('CH-3628'), '3628')
        self.assertEqual(clean_postal_code('ch - 3628'), '3628')
        self.assertEqual(clean_postal_code('FL-9490'), '9490')
        self.assertEqual(clean_postal_code('3628'), '3628')
        self.assertEqual(clean_postal_code('CH3628'), '3628')
        self.assertEqual(clean_postal_code('CH 3628'), '3628')
        self.assertEqual(clean_postal_code('CH \u2013 3628'), '3628')   # en dash

    def test_swiss_postal_code_validity(self):
        for ok in ('3628', 'CH-3628', 'CH3628', ' 8001 ', 'FL-9490'):
            self.assertTrue(is_valid_swiss_postal_code(ok), ok)
        for bad in ('362', '36280', 'CH', 'Bern', '', None, '3628 Uttigen'):
            self.assertFalse(is_valid_swiss_postal_code(bad), bad)


@tagged('standard', 'at_install', 'l10n_ch_qr')
class TestStructuredAddress(BaseCase):

    def _addr(self, street, street2=None, zip_code='3628', city='Uttigen', **kw):
        return structured_address(street, street2, zip_code, city, **kw)

    def test_number_in_street(self):
        addr = self._addr('Eichenweg 11')
        self.assertEqual((addr['street'], addr['number'], addr['zip'], addr['city'], addr['source']),
                         ('Eichenweg', '11', '3628', 'Uttigen', 'street'))

    def test_street2_not_appended_to_number(self):
        addr = self._addr('Bahnhofstrasse 12', 'c/o Meier')
        self.assertEqual((addr['street'], addr['number']), ('Bahnhofstrasse', '12'))
        addr = self._addr('Grenzstrasse 20 A', 'Postfach 112')
        self.assertEqual((addr['street'], addr['number']), ('Grenzstrasse', '20 A'))

    def test_care_of_pattern_uses_street2(self):
        """Baur pattern: c/o line in Street, real street in Street 2."""
        addr = self._addr('c/o Ruchti Partner AG', 'Auweg 41')
        self.assertEqual((addr['street'], addr['number'], addr['source']), ('Auweg', '41', 'street2'))
        addr = self._addr('Fabienne Griessen', 'Muristrasse 21')
        self.assertEqual((addr['street'], addr['number']), ('Muristrasse', '21'))

    def test_bare_number_on_line_two(self):
        addr = self._addr('Bahnhofstrasse', '12')
        self.assertEqual((addr['street'], addr['number'], addr['source']), ('Bahnhofstrasse', '12', 'street2'))
        addr = self._addr('Bahnhofstrasse', '20 A')
        self.assertEqual((addr['street'], addr['number']), ('Bahnhofstrasse', '20 A'))

    def test_no_number_anywhere(self):
        addr = self._addr('Dorf')
        self.assertEqual((addr['street'], addr['number'], addr['source']), ('Dorf', '', 'none'))
        addr = self._addr('Bahnhofstrasse', 'c/o Meier')
        self.assertEqual((addr['street'], addr['number'], addr['source']), ('Bahnhofstrasse', '', 'none'))
        addr = self._addr(None, 'Postfach')
        self.assertEqual((addr['street'], addr['number'], addr['source']), ('Postfach', '', 'none'))

    def test_stored_split_fields_take_precedence(self):
        addr = self._addr('Whatever 99', None, street_name='Eichenweg', street_number='11', street_number2='b')
        self.assertEqual((addr['street'], addr['number'], addr['source']), ('Eichenweg', '11 b', 'fields'))

    def test_truncation_to_six_maxima(self):
        addr = self._addr('S' * 80 + ' 1234567890123456789', None, 'Z' * 20, 'C' * 40)
        self.assertEqual(len(addr['street']), 70)
        self.assertEqual(len(addr['number']), 16)
        self.assertEqual(len(addr['zip']), 16)
        self.assertEqual(len(addr['city']), 35)

    def test_postal_code_country_prefix_removed(self):
        addr = self._addr('Eichenweg 11', None, 'CH-3628', 'Uttigen')
        self.assertEqual(addr['zip'], '3628')
