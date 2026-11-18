from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from pid_provider.base_pid_provider import BasePidProvider


@patch("pid_provider.base_pid_provider.PidProviderXML.register", return_value={})
class ProvidePidForXMLWithPreCollectionTests(SimpleTestCase):
    """
    A coleção informada no XML (custom-meta) prevalece; collection_acron
    só completa a coleção ausente no XML
    """

    def provide(self, collection, collection_acron):
        xml_with_pre = Mock(collection=collection)
        BasePidProvider().provide_pid_for_xml_with_pre(
            xml_with_pre, "name", Mock(), collection_acron=collection_acron
        )
        return xml_with_pre.collection

    def test_collection_acron_completes_missing_xml_collection(self, register):
        self.assertEqual(self.provide(None, "psi"), "psi")

    def test_xml_collection_prevails(self, register):
        self.assertEqual(self.provide("scl", "psi"), "scl")

    def test_xml_collection_is_kept_without_collection_acron(self, register):
        self.assertEqual(self.provide("scl", None), "scl")
