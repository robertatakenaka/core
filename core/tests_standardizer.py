from django.test import TestCase

# Create your tests here.
from core.utils import standardizer


class StandardizerGetSplittedTextTest(TestCase):
    def test_get_splitted_text_returns_one_pair(self):
        expected = ["Universidade X", "X"]
        text = "Universidade X (X)"
        result = standardizer.get_splitted_text_one(
            text,
        )
        self.assertEqual(expected, result)

    def test_get_splitted_text_for_none(self):
        expected = []
        text = None
        result = standardizer.get_splitted_text_one(
            text,
        )
        self.assertEqual(expected, result)

    def test_get_splitted_text_dot_is_separator(self):
        expected = ["Universidade Jka. Programa xxxxxx"]
        text = "Universidade Jka. Programa xxxxxx"
        result = standardizer.get_splitted_text_one(
            text,
        )
        self.assertEqual(expected, result)

    def test_get_splitted_text_for_dot_is_not_separator(self):
        expected = ["Ab.c", "ABC"]
        text = "Ab.c - ABC"
        result = standardizer.get_splitted_text_one(
            text,
        )
        self.assertEqual(expected, result)


class StandardizerStandardizeAcronymAndNameTest(TestCase):
    def test_standardize_acronym_and_name_for_none(self):
        expected = {"name": None}
        text = None
        for item in standardizer.standardize_acronym_and_name(
            text, possible_multiple_return=None, q_locations=None
        ):
            with self.subTest(item):
                self.assertEqual(expected, item)

    def test_standardize_acronym_and_name(self):
        expected = [{"acronym": "ABC", "name": "Abc"}]
        text = "Abc / ABC"
        result = standardizer.standardize_acronym_and_name(
            text, possible_multiple_return=None, q_locations=None
        )
        self.assertEqual(expected, list(result))

    def test_standardize_acronym_and_name_returns_levels(self):
        expected = [
            {
                "acronym": "ABC",
                "name": "Abc",
                "level_1": "Faculdade FFF",
                "level_2": "Unidade UUUU",
                "level_3": "Programa XXXX",
            }
        ]
        text = "Abc (ABC) - Faculdade FFF - Unidade UUUU - Programa XXXX"
        result = standardizer.standardize_acronym_and_name(
            text, possible_multiple_return=None, q_locations=None
        )

        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertEqual(expected[i], item)


class StandardizerStandardizeAcronymAndNameOneTest(TestCase):
    def test_standardize_acronym_and_name_one_for_none(self):
        expected = {"name": None}
        acrons = []
        names = []
        splitted_text = []
        original = None
        result = standardizer.standardize_acronym_and_name_one(acrons, names, original)
        self.assertDictEqual(expected, result)

    def test_standardize_acronym_and_name_one_with_levels(self):
        expected = {
            "acronym": "ABC",
            "name": "Abc",
            "level_1": "Faculdade FFF",
            "level_2": "Unidade UUUU",
            "level_3": "Programa XXXX",
        }
        acrons = ["ABC"]
        names = [
            "Abc",
            "Faculdade FFF",
            "Unidade UUUU",
            "Programa XXXX",
        ]
        splitted_text = [
            "ABC",
            "Abc",
            "Faculdade FFF",
            "Unidade UUUU",
            "Programa XXXX",
        ]
        original = "Abc / ABC - Faculdade FFF - Unidade UUUU - Programa XXXX"
        result = standardizer.standardize_acronym_and_name_one(acrons, names, original)
        self.assertDictEqual(expected, result)

    def test_standardize_acronym_and_name_one_pair(self):
        expected = {
            "acronym": "ABC",
            "name": "Abc",
        }
        acrons = ["ABC"]
        names = ["Abc"]
        splitted_text = [
            [
                "Abc",
                "ABC",
            ]
        ]
        original = "Abc / ABC"
        result = standardizer.standardize_acronym_and_name_one(acrons, names, original)
        self.assertDictEqual(expected, result)

    def test_standardize_acronym_and_name_names_and_acrons_qty_diverge_returns_original(
        self,
    ):
        expected = {
            "name": "Abc / ABC - Faculdade FFF - Unidade UUUU - Programa XXXX",
        }
        acrons = ["ABC", "FFF"]
        names = ["Abc", "Faculdade FFF", "Unidade UUUU", "Programa XXXX"]
        splitted_text = [
            "ABC",
            "Abc",
            "FFF",
            "Faculdade FFF",
            "Unidade UUUU",
            "Programa XXXX",
        ]
        original = "Abc / ABC - Faculdade FFF - Unidade UUUU - Programa XXXX"
        result = standardizer.standardize_acronym_and_name_one(acrons, names, original)
        self.assertDictEqual(expected, result)


class StandardizerStandardizeAcronymAndNameMultTest(TestCase):
    def test_standardize_acronym_and_name_multiple_for_none(self):
        expected = {"name": None}
        acrons = []
        names = []
        splitted_text = []
        q_locations = 2
        original = None
        result = standardizer.standardize_acronym_and_name_multiple(
            splitted_text,
            acrons,
            names,
            original,
            q_locations,
        )
        self.assertEqual([expected], list(result))

    def test_pairs_and_q_location_same_len_returns_pairs(self):
        expected = [
            {"acronym": "ABC", "name": "Abc"},
            {"acronym": "FFF", "name": "Faculdade FFF"},
        ]
        splitted_text = ["ABC", "Abc", "FFF", "Faculdade FFF"]
        q_locations = 2
        original = "Abc / ABC - FFF / Faculdade FFF"
        acrons = ["ABC", "FFF"]
        names = ["Abc", "Faculdade FFF"]
        result = standardizer.standardize_acronym_and_name_multiple(
            splitted_text,
            acrons,
            names,
            original,
            q_locations,
        )
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_pairs_qty_diverges_q_locations_returns_original(self):
        expected = [{"name": "Abc / ABC - FFF / Faculdade FFF"}]
        splitted_text = ["ABC", "Abc", "FFF", "Faculdade FFF"]
        q_locations = None
        original = "Abc / ABC - FFF / Faculdade FFF"
        acrons = ["ABC", "FFF"]
        names = ["Abc", "Faculdade FFF"]
        result = standardizer.standardize_acronym_and_name_multiple(
            splitted_text,
            acrons,
            names,
            original,
            q_locations,
        )
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_2_acrons_and_0_names_and_q_locations_2_returns_acrons(self):
        expected = [
            {"acronym": "ABC"},
            {"acronym": "FFF"},
        ]
        splitted_text = ["ABC", "FFF"]
        q_locations = 2
        original = "ABC / FFF"
        acrons = ["ABC", "FFF"]
        names = []
        result = standardizer.standardize_acronym_and_name_multiple(
            splitted_text,
            acrons,
            names,
            original,
            q_locations,
        )
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_qty_acrons_and_names_diverge_returns_original(self):
        expected = [{"name": "ABC / FFF - Universidade"}]
        splitted_text = [
            "ABC",
            "FFF",
        ]
        q_locations = None
        original = "ABC / FFF - Universidade"
        acrons = ["ABC", "FFF"]
        names = ["Universidade"]
        result = standardizer.standardize_acronym_and_name_multiple(
            splitted_text,
            acrons,
            names,
            original,
            q_locations,
        )
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)


class StandardizerNameAndDivisionsTest(TestCase):
    def test_name_and_divisions(self):
        expected = {
            "name": "Abc",
            "level_1": "Faculdade FFF",
            "level_2": "Unidade UUUU",
            "level_3": "Programa XXXX",
        }
        splitted_text = [
            "Abc",
            "Faculdade FFF",
            "Unidade UUUU",
            "Programa XXXX",
        ]
        result = standardizer.name_and_divisions(splitted_text)
        self.assertEqual(expected, result)


class StandardizerStandardizeCodeAndNameTest(TestCase):
    def test_standardize_code_and_name_returns_both(self):
        expected = [{"code": "CE", "name": "Ceará"}]
        text = "Ceará / CE"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_acronym(self):
        expected = [
            {
                "code": "CE",
            }
        ]
        text = "CE"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_name(self):
        expected = [{"name": "Ceará"}]
        text = "Ceará"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_more_than_one_both(self):
        expected = [
            {"code": "CE", "name": "Ceará"},
            {"code": "SP", "name": "São Paulo"},
        ]
        text = "Ceará / CE, São Paulo / SP"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_more_than_one_acronym(self):
        expected = [
            {
                "code": "CE",
            },
            {
                "code": "SP",
            },
        ]
        text = "CE / SP"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)

    def test_standardize_code_and_name_returns_more_than_one_name(self):
        expected = [{"name": "Ceará"}, {"name": "São Paulo"}]
        text = "Ceará - São Paulo"
        result = standardizer.standardize_code_and_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertDictEqual(expected[i], item)


class StandardizerStandardizeNameTest(TestCase):
    def test_standardize_name(self):
        expected = ["Txto 1", "Texto 2", "Texto 3"]
        text = "Txto 1,    Texto 2,    Texto   3"
        result = standardizer.standardize_name(text)
        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertEqual({"name": expected[i]}, item)
