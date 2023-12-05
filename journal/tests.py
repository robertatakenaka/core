from django.test import TestCase
from django.contrib.auth import get_user_model

from institution.models import Publisher
from journal.models import PublisherHistory, Journal
# Create your tests here.


User = get_user_model()


class PublisherTest(TestCase):

    def setUp(self):
        self.user = User.objects.first()
        self.journal = Journal.objects.first()

    def test_publisher(self):
        publisher_name = "Nome do publicador"
        publisher = Publisher.create_or_update(
            user=self.user,
            name=publisher_name,
            acronym=None,
            level_1=None,
            level_2=None,
            level_3=None,
            location=None,
            url=None,
            declared_name=None,
        )
        publisher_history = PublisherHistory.get_or_create(
            institution=publisher,
            user=self.user,
        )
        publisher_history.journal = self.journal
        publisher_history.save()
        self.assertEqual(
            publisher_name,
            publisher.institution_identification.name
        )
