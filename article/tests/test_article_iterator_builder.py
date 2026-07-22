"""
Testes para ArticleIteratorBuilder (versão com __init__ guardando filtros
comuns e métodos from_pid_provider / from_article / from_harvest /
from_article_source explícitos e mutuamente excludentes).

Usa apenas a biblioteca padrão (unittest + unittest.mock) — sem pytest.

IMPORTANTE: ajuste MODULE_PATH abaixo para o caminho real do módulo onde
ArticleIteratorBuilder está definida (article/tasks.py, segundo o contexto
do projeto).
"""
import logging
import unittest
from unittest.mock import MagicMock, patch

MODULE_PATH = "article.controller"
from article.controller import ArticleIteratorBuilder  # noqa: E402


def setUpModule():
    """
    Desliga o logging (abaixo de CRITICAL) para todo o módulo de testes.

    Sem isso, os logging.info/logging.error chamados dentro de
    ArticleIteratorBuilder alcançam os handlers reais configurados no
    settings.LOGGING do Django (ex.: um handler que despacha para o
    OpenSearch de forma assíncrona) — em ambiente de teste, esse host
    normalmente não existe/não está acessível, gerando o ruído de
    "NameResolutionError" / "--- Logging error ---" no output dos testes.
    logging.disable() impede que os registros sequer cheguem aos
    handlers, então não é necessário conhecer/mockar o handler específico.
    """
    logging.disable(logging.CRITICAL)


def tearDownModule():
    logging.disable(logging.NOTSET)


# =======================================================================
# Helpers
# =======================================================================
def make_builder(**kwargs):
    defaults = dict(
        user=MagicMock(name="user"),
        collection_acron_list=None,
        journal_acron_list=None,
        from_pub_year=None,
        until_pub_year=None,
        from_date=None,
        until_date=None,
        force_update=None,
        limit=None,
        timeout=None,
        opac_url=None,
    )
    defaults.update(kwargs)
    return ArticleIteratorBuilder(**defaults)


class FakeValuesQuerySet:
    """
    Simula o resultado de .values(...)/.values(...=F(...)) — os itens já
    são os dicts finais, e .iterator() apenas os devolve.
    """

    def __init__(self, items):
        self.items = list(items)

    def values(self, *args, **kwargs):
        return self

    def iterator(self):
        return iter(self.items)


class FakeObjectQuerySet:
    """
    Simula uma queryset de objetos "cheios" (instâncias reais), cujo
    .iterator() devolve os próprios objetos (não dicts).
    """

    def __init__(self, items):
        self.items = list(items)

    def iterator(self):
        return iter(self.items)


class FakeArticleBaseQuerySet:
    """
    Simula o `base_qs` de from_article: .distinct() retorna a si mesma, e
    .filter(pp_xml__isnull=...) direciona para o grupo certo — permitindo
    diferenciar o comportamento dos dois sub-filtros (que na vida real
    produziriam querysets diferentes a partir do mesmo base_qs).
    """

    def __init__(self, with_pp_xml=None, without_pp_xml=None):
        self._with_pp_xml = list(with_pp_xml or [])
        self._without_pp_xml = list(without_pp_xml or [])

    def distinct(self):
        return self

    def filter(self, **kwargs):
        if kwargs.get("pp_xml__isnull") is False:
            return FakeValuesQuerySet(self._with_pp_xml)
        if kwargs.get("pp_xml__isnull") is True:
            return FakeObjectQuerySet(self._without_pp_xml)
        return self


# =======================================================================
# __init__
# =======================================================================
class TestInit(unittest.TestCase):
    def test_stores_common_attributes(self):
        user = MagicMock(name="user")
        builder = ArticleIteratorBuilder(
            user=user,
            collection_acron_list=["scl"],
            journal_acron_list=["abc"],
            from_pub_year=2020,
            until_pub_year=2022,
            from_date="2020-01-01",
            until_date="2022-12-31",
            force_update=True,
            limit=10,
            timeout=30,
            opac_url="www.custom.br",
        )
        self.assertIs(builder.user, user)
        self.assertEqual(builder.collection_acron_list, ["scl"])
        self.assertEqual(builder.journal_acron_list, ["abc"])
        self.assertEqual(builder.from_pub_year, 2020)
        self.assertEqual(builder.until_pub_year, 2022)
        self.assertEqual(builder.from_date, "2020-01-01")
        self.assertEqual(builder.until_date, "2022-12-31")
        self.assertTrue(builder.force_update)
        self.assertEqual(builder.limit, 10)
        self.assertEqual(builder.timeout, 30)
        self.assertEqual(builder.opac_url, "www.custom.br")

    def test_defaults_are_none(self):
        builder = ArticleIteratorBuilder(user=MagicMock())
        self.assertIsNone(builder.collection_acron_list)
        self.assertIsNone(builder.journal_acron_list)
        self.assertIsNone(builder.from_pub_year)
        self.assertIsNone(builder.until_pub_year)
        self.assertIsNone(builder.from_date)
        self.assertIsNone(builder.until_date)
        self.assertIsNone(builder.force_update)
        self.assertIsNone(builder.limit)
        self.assertIsNone(builder.timeout)
        self.assertIsNone(builder.opac_url)

    def test_proc_status_list_and_similar_are_not_instance_attributes(self):
        """
        proc_status_list / data_status_list / article_source_status_list
        são exclusivos de cada fonte e não devem existir como atributo de
        instância (ficam só como parâmetro do método correspondente).
        """
        builder = make_builder()
        self.assertFalse(hasattr(builder, "proc_status_list"))
        self.assertFalse(hasattr(builder, "data_status_list"))
        self.assertFalse(hasattr(builder, "article_source_status_list"))


# =======================================================================
# from_pid_provider
# =======================================================================
class TestFromPidProvider(unittest.TestCase):
    def test_yields_dicts_directly_from_queryset(self):
        builder = make_builder()
        items = [{"pp_xml_id": 1}, {"pp_xml_id": 2}]

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX:
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet(items)
            )
            result = list(builder.from_pid_provider())

        self.assertEqual(result, items)

    def test_default_proc_status_used_when_not_provided(self):
        builder = make_builder()

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.PPXML_STATUS_TODO", "todo"), \
             patch(f"{MODULE_PATH}.PPXML_STATUS_INVALID", "invalid"):
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([])
            )
            list(builder.from_pid_provider())

            _, kwargs = MockPPX.objects.filter.call_args
            self.assertEqual(kwargs["proc_status__in"], ["todo", "invalid"])

    def test_custom_proc_status_list_used_when_provided(self):
        builder = make_builder()

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX:
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([])
            )
            list(builder.from_pid_provider(proc_status_list=["custom"]))

            _, kwargs = MockPPX.objects.filter.call_args
            self.assertEqual(kwargs["proc_status__in"], ["custom"])

    def test_date_and_year_filters_applied(self):
        builder = make_builder(
            from_pub_year=2020,
            until_pub_year=2022,
            from_date="2020-01-01",
            until_date="2022-12-31",
        )

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX:
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([])
            )
            list(builder.from_pid_provider())

            _, kwargs = MockPPX.objects.filter.call_args
            self.assertEqual(kwargs["pub_date_year__gte"], 2020)
            self.assertEqual(kwargs["pub_date_year__lte"], 2022)
            self.assertEqual(kwargs["updated__gte"], "2020-01-01")
            self.assertEqual(kwargs["updated__lte"], "2022-12-31")

    def test_collection_filter_does_not_query_journal(self):
        """
        Só com collection_acron_list, nenhuma consulta a Journal deve
        acontecer (o filtro vai direto via collections__acron3__in).
        """
        builder = make_builder(collection_acron_list=["scl"])

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.Journal") as MockJournal:
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([])
            )
            list(builder.from_pid_provider())

            MockJournal.objects.filter.assert_not_called()
            (q_arg,), _ = MockPPX.objects.filter.call_args
            self.assertIn("collections__acron3__in", str(q_arg))

    def test_journal_acron_list_queries_journal_for_issns(self):
        builder = make_builder(journal_acron_list=["abc"])

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.Journal") as MockJournal:
            journal_mock = MockJournal.objects.filter.return_value
            journal_mock.filter.return_value = journal_mock
            journal_mock.values_list.return_value.distinct.return_value = [
                ("1234-5678", "8765-4321"),
            ]
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([{"pp_xml_id": 1}])
            )

            result = list(builder.from_pid_provider())

        MockJournal.objects.filter.assert_called_once_with(
            scielojournal__journal_acron__in=["abc"]
        )
        self.assertEqual(result, [{"pp_xml_id": 1}])

    def test_journal_acron_list_combined_with_collection_acron_list(self):
        builder = make_builder(
            journal_acron_list=["abc"], collection_acron_list=["scl"]
        )

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.Journal") as MockJournal:
            journal_mock = MockJournal.objects.filter.return_value
            journal_mock.filter.return_value = journal_mock
            journal_mock.values_list.return_value.distinct.return_value = [
                ("1234-5678", None),
            ]
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([])
            )

            list(builder.from_pid_provider())

        journal_mock.filter.assert_called_once_with(
            scielojournal__collection__acron3__in=["scl"]
        )

    def test_returns_empty_without_querying_pid_provider_when_no_issn_found(self):
        """
        Se journal_acron_list não casar com nenhum ISSN, o método deve
        parar (return) sem consultar PidProviderXML.
        """
        builder = make_builder(journal_acron_list=["nao-existe"])

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.Journal") as MockJournal:
            journal_mock = MockJournal.objects.filter.return_value
            journal_mock.filter.return_value = journal_mock
            journal_mock.values_list.return_value.distinct.return_value = []

            result = list(builder.from_pid_provider())

        self.assertEqual(result, [])
        MockPPX.objects.filter.assert_not_called()

    def test_issn_list_filters_out_falsy_values(self):
        builder = make_builder(journal_acron_list=["abc"])

        with patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.Journal") as MockJournal:
            journal_mock = MockJournal.objects.filter.return_value
            journal_mock.filter.return_value = journal_mock
            # Um periódico só com issn_print, outro só com issn_electronic,
            # outro com ambos nulos (deve ser ignorado).
            journal_mock.values_list.return_value.distinct.return_value = [
                ("1111-1111", None),
                (None, "2222-2222"),
                (None, None),
            ]
            MockPPX.objects.filter.return_value.values.return_value.distinct.return_value = (
                FakeValuesQuerySet([])
            )

            list(builder.from_pid_provider())

            (q_arg,), _ = MockPPX.objects.filter.call_args
            q_str = str(q_arg)
            self.assertIn("1111-1111", q_str)
            self.assertIn("2222-2222", q_str)


# =======================================================================
# from_article
# =======================================================================
class TestFromArticle(unittest.TestCase):
    def test_articles_with_pp_xml_use_values_shortcut(self):
        builder = make_builder()
        base_qs = FakeArticleBaseQuerySet(
            with_pp_xml=[{"pp_xml_id": 10}, {"pp_xml_id": 20}],
            without_pp_xml=[],
        )

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.choices") as MockChoices:
            MockChoices.DATA_STATUS_PENDING = "pending"
            MockChoices.DATA_STATUS_UNDEF = "undef"
            MockChoices.DATA_STATUS_INVALID = "invalid"
            MockArticle.objects.filter.return_value = base_qs

            result = list(builder.from_article())

        self.assertEqual(result, [{"pp_xml_id": 10}, {"pp_xml_id": 20}])

    def test_articles_without_pp_xml_fetch_and_save(self):
        builder = make_builder()
        article = MagicMock(pp_xml=None, pid_v3="abc123", id=1)
        found_pp_xml = MagicMock(id=55)
        base_qs = FakeArticleBaseQuerySet(
            with_pp_xml=[], without_pp_xml=[article]
        )

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs
            MockPPX.get_by_pid_v3.return_value = found_pp_xml

            result = list(builder.from_article())

        MockPPX.get_by_pid_v3.assert_called_once_with(pid_v3="abc123")
        article.save.assert_called_once_with(update_fields=["pp_xml"])
        self.assertEqual(result, [{"pp_xml_id": 55}])

    def test_yields_none_when_pp_xml_lookup_fails(self):
        builder = make_builder()
        article = MagicMock(pp_xml=None, pid_v3="not-found", id=2)
        base_qs = FakeArticleBaseQuerySet(
            with_pp_xml=[], without_pp_xml=[article]
        )

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs
            MockPPX.get_by_pid_v3.side_effect = Exception("not found")

            result = list(builder.from_article())

        self.assertEqual(result, [])
        article.save.assert_not_called()

    def test_mixes_with_and_without_pp_xml_groups(self):
        builder = make_builder()
        good_article = MagicMock(pp_xml=None, pid_v3="ok", id=3)
        found_pp_xml = MagicMock(id=77)
        base_qs = FakeArticleBaseQuerySet(
            with_pp_xml=[{"pp_xml_id": 1}],
            without_pp_xml=[good_article],
        )

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.PidProviderXML") as MockPPX, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs
            MockPPX.get_by_pid_v3.return_value = found_pp_xml

            result = list(builder.from_article())

        # grupo "com pp_xml" vem primeiro, depois o grupo "sem pp_xml"
        self.assertEqual(result, [{"pp_xml_id": 1}, {"pp_xml_id": 77}])

    def test_default_data_status_list_used_when_not_provided(self):
        builder = make_builder()
        base_qs = FakeArticleBaseQuerySet()

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.choices") as MockChoices:
            MockChoices.DATA_STATUS_PENDING = "pending"
            MockChoices.DATA_STATUS_UNDEF = "undef"
            MockChoices.DATA_STATUS_INVALID = "invalid"
            MockArticle.objects.filter.return_value = base_qs

            list(builder.from_article())

            _, kwargs = MockArticle.objects.filter.call_args
            self.assertEqual(kwargs["data_status__in"], ["pending", "undef", "invalid"])

    def test_custom_data_status_list_used_when_provided(self):
        builder = make_builder()
        base_qs = FakeArticleBaseQuerySet()

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs

            list(builder.from_article(data_status_list=["custom"]))

            _, kwargs = MockArticle.objects.filter.call_args
            self.assertEqual(kwargs["data_status__in"], ["custom"])

    def test_collection_and_journal_filters_traverse_scielojournal(self):
        builder = make_builder(
            collection_acron_list=["scl"], journal_acron_list=["abc"]
        )
        base_qs = FakeArticleBaseQuerySet()

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs

            list(builder.from_article())

            _, kwargs = MockArticle.objects.filter.call_args
            self.assertEqual(
                kwargs["journal__scielojournal__collection__acron3__in"], ["scl"]
            )
            self.assertEqual(
                kwargs["journal__scielojournal__journal_acron__in"], ["abc"]
            )

    def test_no_journal_query_is_made_directly_by_from_article(self):
        """
        Journal não deve ser consultado por from_article — os filtros de
        coleção/periódico vão direto no Article via joins.
        """
        builder = make_builder(collection_acron_list=["scl"])
        base_qs = FakeArticleBaseQuerySet()

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.Journal") as MockJournal, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs

            list(builder.from_article())

            MockJournal.get_ids.assert_not_called()
            MockJournal.objects.filter.assert_not_called()

    def test_pub_year_and_date_filters_applied(self):
        builder = make_builder(
            from_pub_year=2019,
            until_pub_year=2021,
            from_date="2019-01-01",
            until_date="2021-12-31",
        )
        base_qs = FakeArticleBaseQuerySet()

        with patch(f"{MODULE_PATH}.Article") as MockArticle, \
             patch(f"{MODULE_PATH}.choices"):
            MockArticle.objects.filter.return_value = base_qs

            list(builder.from_article())

            _, kwargs = MockArticle.objects.filter.call_args
            self.assertEqual(kwargs["pub_year__gte"], 2019)
            self.assertEqual(kwargs["pub_year__lte"], 2021)
            self.assertEqual(kwargs["updated__gte"], "2019-01-01")
            self.assertEqual(kwargs["updated__lte"], "2021-12-31")


# =======================================================================
# from_harvest
# =======================================================================
class TestFromHarvest(unittest.TestCase):
    def test_loads_collection_when_empty(self):
        builder = make_builder(collection_acron_list=["scl"])

        with patch(f"{MODULE_PATH}.Collection") as MockCollection:
            MockCollection.objects.count.return_value = 0
            fake_harvester = MagicMock()
            fake_harvester.harvest_documents.return_value = []
            with patch.object(builder, "_build_harvester", return_value=fake_harvester):
                list(builder.from_harvest())

        MockCollection.load.assert_called_once_with(builder.user)

    def test_does_not_load_collection_when_not_empty(self):
        builder = make_builder(collection_acron_list=["scl"])

        with patch(f"{MODULE_PATH}.Collection") as MockCollection:
            MockCollection.objects.count.return_value = 5
            fake_harvester = MagicMock()
            fake_harvester.harvest_documents.return_value = []
            with patch.object(builder, "_build_harvester", return_value=fake_harvester):
                list(builder.from_harvest())

        MockCollection.load.assert_not_called()

    def test_falls_back_to_all_collection_acronyms_when_none_given(self):
        builder = make_builder(collection_acron_list=None)

        with patch(f"{MODULE_PATH}.Collection") as MockCollection:
            MockCollection.objects.count.return_value = 5
            MockCollection.get_acronyms.return_value = ["scl", "mex"]
            fake_harvester = MagicMock()
            fake_harvester.harvest_documents.return_value = []

            with patch.object(builder, "_build_harvester", return_value=fake_harvester) as mock_build:
                list(builder.from_harvest())

            self.assertEqual(
                mock_build.call_args_list,
                [(("scl",),), (("mex",),)],
            )

    def test_yields_expected_dict_from_documents(self):
        builder = make_builder(collection_acron_list=["scl"])
        doc = {
            "url": "http://x/y.xml",
            "pid_v2": "S123",
            "processing_date": "2024-01-01",
            "is_public": True,
        }

        with patch(f"{MODULE_PATH}.Collection") as MockCollection:
            MockCollection.objects.count.return_value = 5
            fake_harvester = MagicMock()
            fake_harvester.harvest_documents.return_value = [doc]

            with patch.object(builder, "_build_harvester", return_value=fake_harvester):
                result = list(builder.from_harvest())

        self.assertEqual(result, [{
            "xml_url": "http://x/y.xml",
            "collection_acron": "scl",
            "pid": "S123",
            "source_date": "2024-01-01",
            "is_public": True,
        }])

    def test_uses_origin_date_when_processing_date_absent(self):
        builder = make_builder(collection_acron_list=["scl"])
        doc = {
            "url": "http://x/y.xml",
            "pid_v2": "S123",
            "origin_date": "2023-05-05",
            "is_public": False,
        }

        with patch(f"{MODULE_PATH}.Collection") as MockCollection:
            MockCollection.objects.count.return_value = 5
            fake_harvester = MagicMock()
            fake_harvester.harvest_documents.return_value = [doc]

            with patch.object(builder, "_build_harvester", return_value=fake_harvester):
                result = list(builder.from_harvest())

        self.assertEqual(result[0]["source_date"], "2023-05-05")


# =======================================================================
# from_article_source
# =======================================================================
class TestFromArticleSource(unittest.TestCase):
    def test_yields_dicts_directly_from_queryset(self):
        builder = make_builder(
            from_date="d1", until_date="d2", force_update=True
        )
        items = [{"article_source_id": 10}, {"article_source_id": 20}]

        with patch(f"{MODULE_PATH}.ArticleSource") as MockArticleSource:
            MockArticleSource.get_queryset_to_complete_data.return_value.values.return_value = (
                FakeValuesQuerySet(items)
            )

            result = list(
                builder.from_article_source(article_source_status_list=["pending"])
            )

        MockArticleSource.get_queryset_to_complete_data.assert_called_once_with(
            "d1", "d2", True, ["pending"]
        )
        self.assertEqual(result, items)


# =======================================================================
# _build_harvester
# =======================================================================
class TestBuildHarvester(unittest.TestCase):
    def test_scl_collection_uses_opac_harvester_with_default_url(self):
        builder = make_builder(opac_url=None, from_date="a", until_date="b", limit=10, timeout=30)

        with patch(f"{MODULE_PATH}.OPACHarvester") as MockOPACHarvester:
            builder._build_harvester("scl")

        MockOPACHarvester.assert_called_once_with(
            "www.scielo.br", "scl", from_date="a", until_date="b", limit=10, timeout=30
        )

    def test_scl_collection_uses_provided_opac_url(self):
        builder = make_builder(opac_url="www.custom.br")

        with patch(f"{MODULE_PATH}.OPACHarvester") as MockOPACHarvester:
            builder._build_harvester("scl")

        args, _ = MockOPACHarvester.call_args
        self.assertEqual(args[0], "www.custom.br")

    def test_non_scl_collection_uses_am_harvester(self):
        builder = make_builder(from_date="a", until_date="b", limit=5, timeout=15)

        with patch(f"{MODULE_PATH}.AMHarvester") as MockAMHarvester:
            builder._build_harvester("mex")

        MockAMHarvester.assert_called_once_with(
            "article", "mex", from_date="a", until_date="b", limit=5, timeout=15
        )


if __name__ == "__main__":
    unittest.main()