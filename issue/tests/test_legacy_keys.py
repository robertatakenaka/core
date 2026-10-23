from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from article.models import AMArticle, Article
from collection.models import Collection
from core.users.models import User
from issue.controller import _choose_am_issue_to_keep, fix_issue_legacy_keys
from issue.models import AMIssue, Issue
from issue.tasks import task_fix_issue_legacy_keys
from journal.models import Journal, SciELOJournal


class LegacyKeysTestMixin:
    ISSN = "0034-8910"

    def setUp(self):
        self.user = User.objects.create(username="legacy_keys_user", password="x")
        self.collection = Collection.objects.create(creator=self.user, acron3="scl")
        self.journal = Journal.objects.create(creator=self.user, title="Journal")
        self.scielo_journal = SciELOJournal.objects.create(
            issn_scielo=self.ISSN,
            collection=self.collection,
            journal=self.journal,
            journal_acron="rsp",
        )

    def create_issue(self, number="2", year="2018", **kwargs):
        return Issue.create(
            user=self.user,
            journal=self.journal,
            number=number,
            volume="52",
            season=None,
            year=year,
            month=None,
            supplement=None,
            **kwargs,
        )

    def create_article(self, issue, pid_v2):
        return Article.objects.create(
            pid_v2=pid_v2,
            issue=issue,
            journal=self.journal,
            creator=self.user,
        )

    def am_issues(self, issue):
        return AMIssue.objects.filter(new_record=issue, collection=self.collection)


class IssueCreateLegacyKeysTest(LegacyKeysTestMixin, TestCase):
    def test_save_creates_am_issue_for_each_scielo_journal(self):
        issue = self.create_issue()

        am_issues = self.am_issues(issue)
        self.assertEqual(am_issues.count(), 1)
        self.assertEqual(am_issues.first().pid, f"{self.ISSN}20180002")
        self.assertEqual(am_issues.first().status, "done")

    def test_save_again_does_not_duplicate_am_issue(self):
        issue = self.create_issue()

        issue.month = "6"
        issue.save()
        issue.save()

        self.assertEqual(self.am_issues(issue).count(), 1)

    def test_save_keeps_existing_migrated_am_issue_with_different_pid(self):
        issue = self.create_issue()
        self.am_issues(issue).delete()
        AMIssue.objects.create(
            pid=f"{self.ISSN}20180050",
            collection=self.collection,
            new_record=issue,
            data={"migrated": True},
            creator=self.user,
        )

        issue.save()

        self.assertEqual(
            list(self.am_issues(issue).values_list("pid", flat=True)),
            [f"{self.ISSN}20180050"],
        )

    def test_save_uses_updated_by_when_creating_am_issue(self):
        issue = self.create_issue()
        self.am_issues(issue).delete()
        other = User.objects.create(username="other_user", password="x")

        issue.updated_by = other
        issue.save()

        self.assertEqual(self.am_issues(issue).first().creator, other)

    def test_skips_scielo_journal_without_issn_scielo(self):
        other_collection = Collection.objects.create(creator=self.user, acron3="spa")
        SciELOJournal.objects.create(
            issn_scielo=None,
            collection=other_collection,
            journal=self.journal,
            journal_acron="rspspa",
        )

        issue = self.create_issue()

        self.assertFalse(
            AMIssue.objects.filter(
                new_record=issue, collection=other_collection
            ).exists()
        )
        self.assertFalse(AMIssue.objects.filter(pid__startswith="None").exists())

    def test_creates_am_issue_for_collection_added_after_issue(self):
        # duplicado na coleção existente: a contagem de AMIssue (2) iguala a
        # de SciELOJournal (2), mas falta o AMIssue da nova coleção
        issue = self.create_issue()
        AMIssue.objects.create(
            pid=f"{self.ISSN}20180050",
            collection=self.collection,
            new_record=issue,
            data={"migrated": True},
            creator=self.user,
        )
        other_collection = Collection.objects.create(creator=self.user, acron3="dom")
        SciELOJournal.objects.create(
            issn_scielo=self.ISSN,
            collection=other_collection,
            journal=self.journal,
            journal_acron="rspdom",
        )

        issue.create_legacy_keys(self.user)

        self.assertTrue(
            AMIssue.objects.filter(
                new_record=issue, collection=other_collection
            ).exists()
        )


    def test_skips_issue_without_year(self):
        issue = self.create_issue(year=None)

        self.assertFalse(AMIssue.objects.filter(new_record=issue).exists())

    def test_creates_am_issue_for_each_collection(self):
        other_collection = Collection.objects.create(creator=self.user, acron3="dom")
        SciELOJournal.objects.create(
            issn_scielo="2636-2147",
            collection=other_collection,
            journal=self.journal,
            journal_acron="rspdom",
        )

        issue = self.create_issue()

        self.assertEqual(
            AMIssue.objects.get(new_record=issue, collection=other_collection).pid,
            "2636-214720180002",
        )
        self.assertEqual(self.am_issues(issue).get().pid, f"{self.ISSN}20180002")

    def test_without_user_uses_issue_creator(self):
        issue = self.create_issue()
        self.am_issues(issue).delete()

        issue.create_legacy_keys(user=None, force_update=True)

        self.assertEqual(self.am_issues(issue).get().creator, self.user)

    def test_does_nothing_when_all_collections_have_am_issue(self):
        issue = self.create_issue()
        am_issue = self.am_issues(issue).get()

        issue.create_legacy_keys(self.user)

        self.assertEqual(list(self.am_issues(issue)), [am_issue])


class ArticleCreateLegacyKeysTest(LegacyKeysTestMixin, TestCase):
    def test_creates_am_article_when_pid_v2_matches_issue_pid(self):
        issue = self.create_issue()
        article = self.create_article(issue, f"S{self.ISSN}20180002" + "00001")

        article.create_legacy_keys(self.user)

        am_article = article.legacy_article.get()
        self.assertEqual(am_article.pid, article.pid_v2)
        self.assertEqual(am_article.collection, self.collection)

    def test_matches_any_am_issue_of_the_collection(self):
        # issue com AMIssue gerado (0002) e migrado (0050) na mesma coleção;
        # o artigo pertence ao migrado
        issue = self.create_issue()
        AMIssue.objects.create(
            pid=f"{self.ISSN}20180050",
            collection=self.collection,
            new_record=issue,
            data={"migrated": True},
            creator=self.user,
        )
        article = self.create_article(issue, f"S{self.ISSN}20180050" + "00001")

        article.create_legacy_keys(self.user, force_update=True)

        self.assertEqual(article.legacy_article.count(), 1)
        self.assertEqual(article.legacy_article.get().pid, article.pid_v2)

    def test_does_not_create_am_article_without_pid_v2(self):
        issue = self.create_issue()
        article = self.create_article(issue, None)

        article.create_legacy_keys(self.user)

        self.assertFalse(article.legacy_article.exists())

    def test_does_not_create_am_article_when_pid_v2_does_not_match(self):
        issue = self.create_issue()
        article = self.create_article(issue, f"S{self.ISSN}20189999" + "00001")

        article.create_legacy_keys(self.user)

        self.assertFalse(article.legacy_article.exists())

    def test_issue_pid_must_be_prefix_of_pid_v2(self):
        issue = self.create_issue()
        # contém o pid do issue, mas não no início
        article = self.create_article(issue, f"S99{self.ISSN}20180002" + "001")

        article.create_legacy_keys(self.user)

        self.assertFalse(article.legacy_article.exists())

    def test_creates_am_article_for_collection_added_after_issue(self):
        issue = self.create_issue()
        article = self.create_article(issue, f"S{self.ISSN}20180002" + "00001")
        article.create_legacy_keys(self.user)
        other_collection = Collection.objects.create(creator=self.user, acron3="dom")
        SciELOJournal.objects.create(
            issn_scielo=self.ISSN,
            collection=other_collection,
            journal=self.journal,
            journal_acron="rspdom",
        )

        article.create_legacy_keys(self.user)

        self.assertTrue(
            article.legacy_article.filter(collection=other_collection).exists()
        )


    def test_creates_am_article_for_each_matching_collection(self):
        other_collection = Collection.objects.create(creator=self.user, acron3="dom")
        SciELOJournal.objects.create(
            issn_scielo=self.ISSN,
            collection=other_collection,
            journal=self.journal,
            journal_acron="rspdom",
        )
        issue = self.create_issue()
        article = self.create_article(issue, f"S{self.ISSN}20180002" + "00001")

        article.create_legacy_keys(self.user)

        self.assertEqual(
            set(article.legacy_article.values_list("collection__acron3", flat=True)),
            {"scl", "dom"},
        )

    def test_does_not_create_am_article_for_collection_with_other_issn(self):
        other_collection = Collection.objects.create(creator=self.user, acron3="dom")
        SciELOJournal.objects.create(
            issn_scielo="2636-2147",
            collection=other_collection,
            journal=self.journal,
            journal_acron="rspdom",
        )
        issue = self.create_issue()
        article = self.create_article(issue, f"S{self.ISSN}20180002" + "00001")

        article.create_legacy_keys(self.user)

        self.assertEqual(article.legacy_article.get().collection, self.collection)

    def test_create_legacy_keys_again_does_not_duplicate_am_article(self):
        issue = self.create_issue()
        article = self.create_article(issue, f"S{self.ISSN}20180002" + "00001")

        article.create_legacy_keys(self.user)
        article.create_legacy_keys(self.user, force_update=True)

        self.assertEqual(article.legacy_article.count(), 1)
        self.assertEqual(
            AMArticle.objects.filter(pid=article.pid_v2).count(), 1
        )


class FixIssueLegacyKeysTest(LegacyKeysTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.issue = self.create_issue()
        # AMIssue gerado (pid ...0002) criado pelo save
        self.generated = self.am_issues(self.issue).get()
        self.migrated = AMIssue.objects.create(
            pid=f"{self.ISSN}20180050",
            collection=self.collection,
            new_record=self.issue,
            data={"migrated": True},
            creator=self.user,
        )
        self.article = self.create_article(
            self.issue, f"S{self.ISSN}20180050" + "00001"
        )

    def test_dry_run_does_not_change_anything(self):
        stats = fix_issue_legacy_keys(self.user, dry_run=True)

        self.assertTrue(stats["dry_run"])
        self.assertEqual(stats["issues_with_duplicates"], 1)
        self.assertEqual(stats["am_issues_deleted"], [str(self.generated)])
        self.assertEqual(stats["articles_without_legacy_keys"], 1)
        self.assertEqual(stats["articles_fixed"], 0)
        self.assertEqual(self.am_issues(self.issue).count(), 2)
        self.assertFalse(self.article.legacy_article.exists())

    def test_deletes_generated_duplicate_and_fixes_articles(self):
        stats = fix_issue_legacy_keys(self.user, dry_run=False)

        self.assertEqual(stats["errors"], 0)
        self.assertEqual(stats["am_issues_deleted"], [str(self.generated)])
        self.assertEqual(
            list(self.am_issues(self.issue)), [self.migrated]
        )
        self.assertEqual(stats["articles_fixed"], 1)
        self.assertEqual(stats["articles_still_without_legacy_keys"], [])
        self.assertEqual(self.article.legacy_article.get().pid, self.article.pid_v2)

    def test_keeps_generated_am_issue_that_matches_articles(self):
        # o artigo pertence ao gerado; o migrado não pode ser removido
        self.article.pid_v2 = f"S{self.ISSN}20180002" + "00001"
        self.article.save()

        stats = fix_issue_legacy_keys(self.user, dry_run=False)

        self.assertEqual(stats["am_issues_deleted"], [])
        self.assertEqual(
            stats["am_issues_kept_with_data_conflict"], [str(self.migrated)]
        )
        self.assertEqual(self.am_issues(self.issue).count(), 2)
        self.assertEqual(stats["articles_fixed"], 1)

    def test_never_deletes_migrated_am_issues(self):
        self.generated.data = {"migrated": True}
        self.generated.save()

        stats = fix_issue_legacy_keys(self.user, dry_run=False)

        self.assertEqual(stats["am_issues_deleted"], [])
        self.assertEqual(len(stats["am_issues_kept_with_data_conflict"]), 1)
        self.assertEqual(self.am_issues(self.issue).count(), 2)

    def test_reports_articles_that_remain_without_legacy_keys(self):
        orphan = self.create_article(self.issue, f"S{self.ISSN}20189999" + "00001")

        stats = fix_issue_legacy_keys(self.user, dry_run=False)

        self.assertEqual(stats["articles_without_legacy_keys"], 2)
        self.assertEqual(stats["articles_fixed"], 1)
        self.assertEqual(
            stats["articles_still_without_legacy_keys"],
            [f"{orphan.pid_v2} {self.issue}"],
        )

    def test_filters_by_collection(self):
        stats = fix_issue_legacy_keys(
            self.user, collection_acron_list=["xxx"], dry_run=False
        )

        self.assertEqual(stats["issues_with_duplicates"], 0)
        self.assertEqual(self.am_issues(self.issue).count(), 2)


class ChooseAMIssueToKeepTest(SimpleTestCase):
    def am_issue(self, pid, data=None, created=datetime(2024, 1, 1)):
        return SimpleNamespace(pid=pid, data=data, created=created)

    def test_prefers_am_issue_matching_more_articles(self):
        generated = self.am_issue("0034-891020180002")
        migrated = self.am_issue("0034-891020180050", data={"migrated": True})
        pids_v2 = [
            "S0034-89102018000200001",
            "S0034-89102018000200002",
            "S0034-89102018005000001",
        ]

        self.assertIs(_choose_am_issue_to_keep([migrated, generated], pids_v2), generated)

    def test_tie_prefers_migrated(self):
        generated = self.am_issue("0034-891020180002")
        migrated = self.am_issue("0034-891020180050", data={"migrated": True})

        self.assertIs(_choose_am_issue_to_keep([generated, migrated], []), migrated)

    def test_tie_without_data_prefers_oldest(self):
        older = self.am_issue("0034-891020180002", created=datetime(2020, 1, 1))
        newer = self.am_issue("0034-891020180050", created=datetime(2024, 1, 1))

        self.assertIs(_choose_am_issue_to_keep([newer, older], []), older)

    def test_am_issue_without_pid_matches_nothing(self):
        without_pid = self.am_issue(None, created=datetime(2020, 1, 1))
        generated = self.am_issue("0034-891020180002")

        self.assertIs(
            _choose_am_issue_to_keep(
                [without_pid, generated], ["S0034-89102018000200001"]
            ),
            generated,
        )


class TaskFixIssueLegacyKeysTest(TestCase):
    MODULE_PATH = "issue.tasks"

    def test_calls_controller_and_returns_stats(self):
        user = SimpleNamespace(username="u")
        stats = {"dry_run": False}
        with patch(f"{self.MODULE_PATH}._get_user", return_value=user), patch(
            f"{self.MODULE_PATH}.controller.fix_issue_legacy_keys",
            return_value=stats,
        ) as mock_fix:
            result = task_fix_issue_legacy_keys(
                user_id=1,
                collection_acron_list=["dom"],
                journal_acron_list=["recie"],
                publication_year="2024",
                dry_run=False,
            )

        self.assertEqual(result, stats)
        mock_fix.assert_called_once_with(
            user,
            collection_acron_list=["dom"],
            journal_acron_list=["recie"],
            publication_year="2024",
            dry_run=False,
        )

    def test_dry_run_is_default(self):
        with patch(f"{self.MODULE_PATH}._get_user"), patch(
            f"{self.MODULE_PATH}.controller.fix_issue_legacy_keys",
            return_value={},
        ) as mock_fix:
            task_fix_issue_legacy_keys(user_id=1)

        self.assertTrue(mock_fix.call_args.kwargs["dry_run"])

    def test_registers_unexpected_event_and_reraises(self):
        with patch(f"{self.MODULE_PATH}._get_user"), patch(
            f"{self.MODULE_PATH}.controller.fix_issue_legacy_keys",
            side_effect=ValueError("boom"),
        ), patch(f"{self.MODULE_PATH}.UnexpectedEvent") as mock_event:
            with self.assertRaises(ValueError):
                task_fix_issue_legacy_keys(user_id=1)

        mock_event.create.assert_called_once()
        self.assertEqual(
            mock_event.create.call_args.kwargs["action"],
            "issue.tasks.task_fix_issue_legacy_keys",
        )
