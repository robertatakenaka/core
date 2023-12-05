from django.test import TestCase

# Create your tests here.
from django.contrib.auth import get_user_model
from institution import models
from location.models import Location, Country

User = get_user_model()


class InstitutionIdentificationStandardizeTest(TestCase):
    def setUp(self):
        self.text = "São Paulo State University (UNESP)"
        self.user, created = User.objects.get_or_create(username="adm")
        for item in User.objects.filter(username="adm").iterator():
            self.user = item
            break

    def test_create_or_update_with_declared_name_returns_object(self):
        item = models.InstitutionIdentification.create_or_update_with_declared_name(
            self.text, user=self.user)
        self.assertIsInstance(item, models.InstitutionIdentification)
        self.assertEqual("São Paulo State University", item.name)
        self.assertEqual("UNESP", item.acronym)

    def test_create_or_update_with_declared_name_returns_one_object(self):
        item = models.InstitutionIdentification.create_or_update_with_declared_name(
            self.text, self.user
        )
        self.assertIsInstance(
            item, models.InstitutionIdentification
        )
        self.assertEqual(
            "São Paulo State University",
            item.name,
        )
        self.assertEqual("UNESP", item.acronym)


class InstitutionTest(TestCase):
    def setUp(self):
        self.text = "São Paulo State University (UNESP)"
        self.user, created = User.objects.get_or_create(username="adm")
        for item in User.objects.filter(username="adm").iterator():
            self.user = item
            break

    def test_create_or_update(self):
        result = models.Institution.create_or_update(
            user=self.user,
            name=None,
            acronym=None,
            level_1=None,
            level_2=None,
            level_3=None,
            location=None,
            url=None,
            declared_name=self.text,
        )
        self.assertEqual(
            "São Paulo State University", result.institution_identification.name
        )
        self.assertEqual("UNESP", result.institution_identification.acronym)

    def test_create_or_update_with_declared_name_returns_multiple_object(self):
        self.text = "São Paulo State University (UNESP) / Universidade de São Paulo (USP)"
        locations = [
            Location.create_or_update(
                user=self.user,
                country=Country.create_or_update(
                    user=self.user, name=None, acronym="BR"
                ),
            ),
            Location.create_or_update(
                user=self.user,
                country=Country.create_or_update(
                    user=self.user, name=None, acronym="MX"
                ),
            ),
        ]
        expected_identification = [
            {"name": "São Paulo State University", "acronym": "UNESP"},
            {"name": "Universidade de São Paulo", "acronym": "USP"},
        ]

        result = models.Institution.create_or_update_with_declared_name(
            self.user,
            self.text,
            level_1=None,
            level_2=None,
            level_3=None,
            locations=locations,
            url=None,
        )

        for i, item in enumerate(result):
            with self.subTest(i):
                self.assertIsInstance(item, models.Institution)
                self.assertEqual(
                    expected_identification[i]["name"],
                    item.institution_identification.name,
                )
                self.assertEqual(
                    expected_identification[i].get("acronym"),
                    item.institution_identification.acronym,
                )
                self.assertEqual(
                    locations[i],
                    item.location,
                )
