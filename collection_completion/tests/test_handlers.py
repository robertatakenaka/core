"""
Core: complementação de coleções do periódico Psicologia USP, presente em
scl (PID 0103-6564, coleção principal) e psi (PID 1678-5177)
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

from article.models import AMArticle, Article
from collection_completion import choices, handlers, tasks
from collection_completion.models import CollectionCompletion
from issue.models import AMIssue, Issue
from journal.models import Journal
from pid_provider.models import CollectionPidV2, PidProviderXML
from pid_provider.tests.test_register_multi_collection import (
    PSI_V2,
    SCL_V2,
    RegisterSameArticleInDifferentCollectionsTestBase,
    scl_xml,
)

User = get_user_model()

SCL_ISSUE_PID = "0103-656420090003"
PSI_ISSUE_PID = "1678-517720090003"


class CoreCollectionCompletionTestBase(RegisterSameArticleInDifferentCollectionsTestBase):
    """
    Fascículo e artigo presentes somente em scl
    """

    def setUp(self):
        super().setUp()
        self.journal = Journal.objects.get()
        self.issue = Issue.objects.create(
            journal=self.journal,
            year="2009",
            volume="20",
            number="3",
            issue_pid_suffix="0003",
            creator=self.user,
        )
        # Issue.save cria as chaves legadas em todas as coleções do periódico
        # (Issue.create_legacy_keys); simula o fascículo que não está em psi
        # (ex.: periódico incluído em psi depois)
        AMIssue.objects.filter(new_record=self.issue).exclude(collection=self.scl).delete()
        self.assertEqual(
            list(AMIssue.objects.filter(new_record=self.issue).values_list("pid", flat=True)),
            [SCL_ISSUE_PID],
        )
        self.register(scl_xml(), "scl")
        self.pid_provider_xml = PidProviderXML.objects.get()
        self.article = Article.objects.create(
            journal=self.journal,
            issue=self.issue,
            pid_v2=SCL_V2,
            pid_v3=self.pid_provider_xml.v3,
            pp_xml=self.pid_provider_xml,
            creator=self.user,
        )
        AMArticle.create_or_update(
            SCL_V2, self.scl, None, self.user, status="done", new_record=self.article
        )

    def complete_issue(self):
        return handlers.complete_issue(
            self.user, self.journal, self.scl, self.psi, self.issue.pk
        )

    def complete_article(self):
        return handlers.complete_article(
            self.user, self.scl, self.psi, self.article.pk, self.issue.pk
        )


class GetJournalsAndIssuesTest(CoreCollectionCompletionTestBase):
    def test_journal_in_more_than_one_collection(self):
        self.assertEqual(list(handlers.get_journals_queryset()), [self.journal])
        self.assertCountEqual(
            handlers.get_journal_collections(self.journal), [self.scl, self.psi]
        )

    def test_source_issues(self):
        self.assertEqual(
            handlers.get_source_issues(self.journal, self.scl, self.psi, ["2009"]),
            [
                {
                    "id": str(self.issue.pk),
                    "label": "2009 v.20 n.3",
                    "source_pid": SCL_ISSUE_PID,
                    "target_pid": None,
                }
            ],
        )
        self.assertEqual(
            handlers.get_source_issues(self.journal, self.scl, self.psi, ["2010"]), []
        )
        # fascículo não está em psi
        self.assertEqual(
            handlers.get_source_issues(self.journal, self.psi, self.scl, ["2009"]), []
        )


class CompleteIssueTest(CoreCollectionCompletionTestBase):
    def test_issue_is_added_with_the_target_journal_pid(self):
        response = self.complete_issue()

        self.assertEqual(response["status"], choices.STATUS_ADDED)
        self.assertEqual(response["source_pid"], SCL_ISSUE_PID)
        self.assertEqual(response["target_pid"], PSI_ISSUE_PID)
        self.assertEqual(response["target_issue_id"], self.issue.pk)
        self.assertEqual(
            response["articles"],
            [{"id": str(self.article.pk), "label": self.article.pid_v3, "pid": SCL_V2}],
        )
        self.assertEqual(
            AMIssue.objects.get(collection=self.psi).new_record, self.issue
        )

    def test_issue_already_in_target_collection_is_ignored(self):
        self.complete_issue()

        response = self.complete_issue()

        self.assertEqual(response["status"], choices.STATUS_IGNORED)
        self.assertEqual(response["target_pid"], PSI_ISSUE_PID)
        # os artigos são completados
        self.assertEqual(response["target_issue_id"], self.issue.pk)
        self.assertEqual(len(response["articles"]), 1)

    def test_pid_used_by_another_issue_is_ignored(self):
        other = Issue.objects.create(journal=self.journal, year="2009", creator=self.user)
        AMIssue.create_or_update(
            PSI_ISSUE_PID, self.psi, None, self.user, status="done", new_record=other
        )

        response = self.complete_issue()

        self.assertEqual(response["status"], choices.STATUS_IGNORED)
        self.assertIsNone(response.get("target_issue_id"))
        self.assertEqual(AMIssue.objects.filter(new_record=self.issue).count(), 1)

    def test_unlinked_legacy_key_with_the_pid_is_linked(self):
        AMIssue.create_or_update(PSI_ISSUE_PID, self.psi, None, self.user, status="done")

        response = self.complete_issue()

        self.assertEqual(response["status"], choices.STATUS_ADDED)
        self.assertEqual(
            AMIssue.objects.get(collection=self.psi).new_record, self.issue
        )


class CompleteArticleTest(CoreCollectionCompletionTestBase):
    def setUp(self):
        super().setUp()
        self.complete_issue()

    def test_article_is_added_with_the_target_pid_v2(self):
        response = self.complete_article()

        self.assertEqual(response["status"], choices.STATUS_ADDED, response)
        self.assertEqual(response["source_pid"], SCL_V2)
        self.assertEqual(response["target_pid"], PSI_V2)
        # chave legada e pid v2 da coleção destino no pid provider
        self.assertEqual(
            AMArticle.objects.get(collection=self.psi).new_record, self.article
        )
        collection_pid_v2 = CollectionPidV2.objects.get(collection=self.psi)
        self.assertEqual(collection_pid_v2.pid_provider_xml, self.pid_provider_xml)
        self.assertEqual(collection_pid_v2.pid_v2, PSI_V2)
        self.assertEqual(
            collection_pid_v2.current_version.xml_with_pre.collection, "psi"
        )
        # mesmo documento (pid v3); dados da coleção principal (scl) mantidos
        self.assertEqual(PidProviderXML.objects.count(), 1)
        self.pid_provider_xml.refresh_from_db()
        self.assertEqual(self.pid_provider_xml.v2, SCL_V2)

    def test_article_already_in_target_collection_is_ignored(self):
        self.complete_article()

        response = self.complete_article()

        self.assertEqual(response["status"], choices.STATUS_IGNORED)
        self.assertEqual(response["target_pid"], PSI_V2)

    def test_pid_used_by_another_article_is_ignored(self):
        other = Article.objects.create(journal=self.journal, creator=self.user)
        AMArticle.create_or_update(
            PSI_V2, self.psi, None, self.user, status="done", new_record=other
        )

        response = self.complete_article()

        self.assertEqual(response["status"], choices.STATUS_IGNORED)
        self.assertFalse(CollectionPidV2.objects.filter(collection=self.psi).exists())

    def test_article_without_pid_provider_xml_is_ignored(self):
        Article.objects.filter(pk=self.article.pk).update(pp_xml=None, pid_v3=None)

        response = self.complete_article()

        self.assertEqual(response["status"], choices.STATUS_IGNORED)
        self.assertFalse(AMArticle.objects.filter(collection=self.psi).exists())


class CollectionCompletionTasksTest(CoreCollectionCompletionTestBase):
    def test_issue_task_completes_the_issue_and_dispatches_the_article_tasks(self):
        completion = CollectionCompletion.create(
            self.user, self.journal, self.scl, self.psi, 2009, 2009
        )
        item = completion.add_item(
            self.user, choices.ITEM_TYPE_ISSUE, self.issue.pk, label="2009 v.20 n.3"
        )

        with patch.object(tasks.task_complete_article, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                tasks.task_complete_issue(item_id=item.pk, user_id=self.user.pk)

        item.refresh_from_db()
        self.assertEqual(item.status, choices.STATUS_ADDED)
        self.assertEqual(item.target_pid, PSI_ISSUE_PID)
        article_item = item.children.get()
        self.assertEqual(article_item.status, choices.STATUS_TODO)
        self.assertFalse(completion.is_finished)
        apply_async.assert_called_once_with(
            kwargs={
                "item_id": article_item.pk,
                "user_id": self.user.pk,
                "target_issue_id": self.issue.pk,
            }
        )

        tasks.task_complete_article(**apply_async.call_args.kwargs["kwargs"])

        article_item.refresh_from_db()
        self.assertEqual(article_item.status, choices.STATUS_ADDED, article_item.reason)
        self.assertEqual(article_item.target_pid, PSI_V2)
        self.assertTrue(completion.is_finished)
        self.assertEqual(
            completion.totals,
            {"issue": {"added": 1}, "article": {"added": 1}},
        )

    def test_articles_are_ignored_when_the_issue_is_not_completed(self):
        other = Issue.objects.create(journal=self.journal, year="2009", creator=self.user)
        AMIssue.create_or_update(
            PSI_ISSUE_PID, self.psi, None, self.user, status="done", new_record=other
        )
        completion = CollectionCompletion.create(
            self.user, self.journal, self.scl, self.psi, 2009, 2009
        )
        item = completion.add_item(self.user, choices.ITEM_TYPE_ISSUE, self.issue.pk)

        with patch.object(tasks.task_complete_article, "apply_async") as apply_async:
            tasks.task_complete_issue(item_id=item.pk, user_id=self.user.pk)

        apply_async.assert_not_called()
        self.assertTrue(completion.is_finished)
        self.assertEqual(
            completion.totals,
            {"issue": {"ignored": 1}, "article": {"ignored": 1}},
        )

    def test_unexpected_error_is_reported(self):
        completion = CollectionCompletion.create(
            self.user, self.journal, self.scl, self.psi, 2009, 2009
        )
        item = completion.add_item(self.user, choices.ITEM_TYPE_ISSUE, self.issue.pk)

        with patch.object(handlers, "complete_issue", side_effect=ValueError("boom")):
            tasks.task_complete_issue(item_id=item.pk, user_id=self.user.pk)

        item.refresh_from_db()
        self.assertEqual(item.status, choices.STATUS_ERROR)
        self.assertIn("boom", item.reason)


class CollectionCompletionViewsTest(CoreCollectionCompletionTestBase):
    def form_data(self):
        return {
            "journal": self.journal.pk,
            "source_collection": self.scl.pk,
            "target_collection": self.psi.pk,
            "start_year": 2009,
            "end_year": 2009,
        }

    def test_only_admin_users(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("collection_completion:list"))
        self.assertIn(response.status_code, (302, 403))

    def test_form_lists_issues_and_confirmation_dispatches_tasks(self):
        admin = User.objects.create_superuser(username="admin", password="x")
        self.client.force_login(admin)

        response = self.client.post(
            reverse("collection_completion:create"), self.form_data()
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, SCL_ISSUE_PID)

        data = {**self.form_data(), "issues": [str(self.issue.pk)]}
        with patch.object(tasks.task_complete_issue, "apply_async") as apply_async:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    reverse("collection_completion:confirm"), data
                )

        completion = CollectionCompletion.objects.get()
        self.assertRedirects(
            response,
            reverse("collection_completion:report", args=[completion.pk]),
            fetch_redirect_response=False,
        )
        item = completion.items.get()
        apply_async.assert_called_once_with(
            kwargs={"item_id": item.pk, "user_id": admin.pk}
        )
        response = self.client.get(
            reverse("collection_completion:report", args=[completion.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_collections_must_be_different(self):
        admin = User.objects.create_superuser(username="admin", password="x")
        self.client.force_login(admin)

        response = self.client.post(
            reverse("collection_completion:create"),
            {**self.form_data(), "target_collection": self.scl.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].is_valid())
