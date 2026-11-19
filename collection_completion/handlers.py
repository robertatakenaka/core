"""
Core: regras da complementação de coleções (ver models.py)

Os fascículos e artigos do Core não são por coleção: Issue e Article são
únicos e a presença em cada coleção, com o PID da coleção, é registrada em
AMIssue e AMArticle (chaves legadas, collection + pid). No pid provider, o
documento tem o pid v2 e a versão do XML de cada coleção em CollectionPidV2.

Completar a coleção destino:
- fascículo: cria AMIssue da coleção destino com o PID do fascículo na
  coleção destino (PID do periódico na coleção destino + ano + ordem)
- artigo: registra no pid provider o XML da coleção origem com o pid v2 e a
  coleção destino (CollectionPidV2 da coleção destino) e cria AMArticle da
  coleção destino com esse pid v2 (S + PID do fascículo na coleção destino +
  ordem do artigo na coleção origem)

Não publica o conteúdo.

Mesma interface de handlers.py do Upload (scms-upload), cujas regras são
outras (o Upload não completa fascículos: eles vêm do Core)
"""

from django.db import transaction
from django.db.models import Count
from django.utils.translation import gettext as _

from article.models import AMArticle, Article
from collection.models import Collection
from collection_completion import choices
from collection_completion.pids import (
    belongs_to_issue,
    build_article_pid,
    build_issue_pid,
    get_issue_order,
    is_valid_article_pid,
)
from issue.models import AMIssue, Issue
from journal.models import Journal, SciELOJournal
from pid_provider.models import CollectionPidV2, PidProviderXML
from pid_provider.provider import PidProvider

ORIGIN = "collection_completion"


def result(status, reason=None, **kwargs):
    return {"status": status, "reason": reason and str(reason), **kwargs}


def get_journals_queryset():
    """
    Periódicos presentes em mais de uma coleção
    """
    journal_ids = (
        SciELOJournal.objects.filter(journal__isnull=False, collection__isnull=False)
        .values("journal")
        .annotate(total=Count("collection", distinct=True))
        .filter(total__gt=1)
        .values("journal")
    )
    return Journal.objects.filter(id__in=journal_ids).order_by("title")


def get_journal_collections(journal):
    return list(
        Collection.objects.filter(
            id__in=SciELOJournal.objects.filter(journal=journal).values("collection")
        )
    )


def get_journal_pid(journal, collection):
    item = (
        SciELOJournal.objects.filter(journal=journal, collection=collection)
        .exclude(issn_scielo__isnull=True)
        .first()
    )
    return item and item.issn_scielo


def get_issue_label(issue):
    parts = [issue.year]
    if issue.volume:
        parts.append(f"v.{issue.volume}")
    if issue.number:
        parts.append(f"n.{issue.number}")
    if issue.supplement:
        parts.append(f"s.{issue.supplement}")
    return " ".join(part for part in parts if part)


def get_issue_pid(issue, collection):
    item = AMIssue.objects.filter(new_record=issue, collection=collection).first()
    return item and item.pid


def get_source_issues(journal, source_collection, target_collection, years):
    """
    Fascículos do periódico, dos anos informados, presentes na coleção
    origem (AMIssue)

    Returns
    -------
    list of dict
        [{"id", "label", "source_pid", "target_pid"}]
        target_pid: PID do fascículo, se já está na coleção destino
    """
    items = []
    issues = (
        Issue.objects.filter(
            journal=journal,
            year__in=years,
            legacy_issue__collection=source_collection,
        )
        .distinct()
        .order_by("year", "order", "volume", "number", "supplement")
    )
    for issue in issues:
        items.append(
            {
                "id": str(issue.pk),
                "label": get_issue_label(issue),
                "source_pid": get_issue_pid(issue, source_collection),
                "target_pid": get_issue_pid(issue, target_collection),
            }
        )
    return items


def get_article_pid(article, collection, issue_pid):
    """
    pid v2 do artigo na coleção: AMArticle da coleção ou, na falta,
    Article.pid_v2, se for de artigo do fascículo na coleção
    """
    item = AMArticle.objects.filter(new_record=article, collection=collection).first()
    if item and item.pid:
        return item.pid
    if belongs_to_issue(article.pid_v2, issue_pid):
        return article.pid_v2
    return None


def get_article_label(article):
    return article.sps_pkg_name or article.pid_v3 or str(article.pk)


def get_source_articles(issue, source_collection, source_issue_pid):
    items = []
    for article in Article.objects.filter(issue=issue).order_by("pid_v2", "pk"):
        pid = get_article_pid(article, source_collection, source_issue_pid)
        if not pid:
            # artigo não está na coleção origem
            continue
        items.append(
            {"id": str(article.pk), "label": get_article_label(article), "pid": pid}
        )
    return items


def complete_issue(user, journal, source_collection, target_collection, issue_id):
    """
    Adiciona o fascículo à coleção destino (AMIssue)

    Returns
    -------
    dict
        {"status", "reason", "source_pid", "target_pid", "target_issue_id",
        "articles": [{"id", "label", "pid"}]}
        target_issue_id: Issue.id se o fascículo está (ou foi adicionado) na
        coleção destino, senão None (os artigos não são completados)
    """
    issue = Issue.objects.get(pk=issue_id, journal=journal)
    source_pid = get_issue_pid(issue, source_collection)
    articles = get_source_articles(issue, source_collection, source_pid)
    data = {"source_pid": source_pid, "articles": articles}

    target_pid = get_issue_pid(issue, target_collection)
    if target_pid:
        return result(
            choices.STATUS_IGNORED,
            _("The issue is already in the target collection"),
            target_pid=target_pid,
            target_issue_id=issue.pk,
            **data,
        )

    journal_pid = get_journal_pid(journal, target_collection)
    if not journal_pid:
        return result(
            choices.STATUS_IGNORED,
            _("The journal has no PID (issn_scielo) in the target collection"),
            **data,
        )

    # ordem do fascículo: a do Issue ou, na falta, a do PID da origem
    issue_order = issue.issue_pid_suffix or get_issue_order(source_pid)
    target_pid = build_issue_pid(journal_pid, issue.year, issue_order)
    if not target_pid:
        return result(
            choices.STATUS_IGNORED,
            _("Unable to build the issue PID: journal PID {}, year {}, issue order {}").format(
                journal_pid, issue.year, issue_order
            ),
            **data,
        )

    # chave legada sem vínculo (new_record) com o mesmo PID é vinculada
    conflict = (
        AMIssue.objects.filter(
            collection=target_collection, pid=target_pid, new_record__isnull=False
        )
        .exclude(new_record=issue)
        .first()
    )
    if conflict:
        return result(
            choices.STATUS_IGNORED,
            _("The PID {} is already used by another issue in the target collection: {}").format(
                target_pid, conflict.new_record
            ),
            target_pid=target_pid,
            **data,
        )

    AMIssue.create_or_update(
        target_pid, target_collection, None, user, status="done", new_record=issue
    )
    return result(
        choices.STATUS_ADDED,
        target_pid=target_pid,
        target_issue_id=issue.pk,
        **data,
    )


def get_pid_provider_xml(article):
    if article.pp_xml:
        return article.pp_xml
    if article.pid_v3:
        return PidProviderXML.objects.filter(v3=article.pid_v3).first()
    return None


def get_source_xml_with_pre(pid_provider_xml, source_collection):
    version = pid_provider_xml.get_current_version(collection=source_collection)
    return version and version.xml_with_pre


class ArticleRegistrationError(Exception): ...


def complete_article(user, source_collection, target_collection, article_id, target_issue_id):
    """
    Adiciona o artigo à coleção destino: registra no pid provider o XML com
    o pid v2 e a coleção destino (CollectionPidV2) e cria AMArticle

    Returns
    -------
    dict
        {"status", "reason", "source_pid", "target_pid", "detail"}
    """
    article = Article.objects.select_related("issue").get(pk=article_id)
    issue = Issue.objects.get(pk=target_issue_id)
    source_issue_pid = get_issue_pid(issue, source_collection)
    source_pid = get_article_pid(article, source_collection, source_issue_pid)
    data = {"source_pid": source_pid}

    target_am_article = AMArticle.objects.filter(
        new_record=article, collection=target_collection
    ).first()
    if target_am_article:
        return result(
            choices.STATUS_IGNORED,
            _("The article is already in the target collection"),
            target_pid=target_am_article.pid,
            **data,
        )

    if not is_valid_article_pid(source_pid):
        return result(
            choices.STATUS_IGNORED,
            _("The article has no valid PID v2 in the source collection: {}").format(
                source_pid
            ),
            **data,
        )

    target_issue_pid = get_issue_pid(issue, target_collection)
    target_pid = build_article_pid(target_issue_pid, source_pid)
    if not target_pid:
        return result(
            choices.STATUS_IGNORED,
            _("Unable to build the article PID: issue PID in the target collection {}").format(
                target_issue_pid
            ),
            **data,
        )
    data["target_pid"] = target_pid

    # chave legada sem vínculo (new_record) com o mesmo PID é vinculada
    conflict = (
        AMArticle.objects.filter(
            collection=target_collection, pid=target_pid, new_record__isnull=False
        )
        .exclude(new_record=article)
        .first()
    )
    if conflict:
        return result(
            choices.STATUS_IGNORED,
            _("The PID {} is already used by another article in the target collection: {}").format(
                target_pid, conflict.new_record
            ),
            **data,
        )

    pid_provider_xml = get_pid_provider_xml(article)
    if not pid_provider_xml:
        return result(
            choices.STATUS_IGNORED,
            _("The article has no XML registered in the PID provider"),
            **data,
        )

    collection_pid_v2 = CollectionPidV2.objects.filter(
        collection=target_collection, pid_v2=target_pid
    ).exclude(pid_provider_xml=pid_provider_xml).first()
    if collection_pid_v2:
        return result(
            choices.STATUS_IGNORED,
            _("The PID {} is already registered for another document (PID v3 {}) in the target collection").format(
                target_pid, collection_pid_v2.pid_provider_xml and collection_pid_v2.pid_provider_xml.v3
            ),
            **data,
        )
    collection_pid_v2 = CollectionPidV2.objects.filter(
        collection=target_collection, pid_provider_xml=pid_provider_xml
    ).first()
    if collection_pid_v2 and collection_pid_v2.pid_v2 != target_pid:
        return result(
            choices.STATUS_IGNORED,
            _("The document is already registered in the target collection with the PID v2 {}").format(
                collection_pid_v2.pid_v2
            ),
            **data,
        )

    xml_with_pre = get_source_xml_with_pre(pid_provider_xml, source_collection)
    if not xml_with_pre:
        return result(
            choices.STATUS_IGNORED,
            _("The article has no XML of the source collection in the PID provider"),
            **data,
        )

    target_acron = target_collection.acron3
    xml_with_pre.v2 = target_pid
    xml_with_pre.collection = target_acron

    # registro no pid provider e chave legada: tudo ou nada
    with transaction.atomic():
        registered = PidProvider().provide_pid_for_xml_with_pre(
            xml_with_pre,
            pid_provider_xml.pkg_name or xml_with_pre.sps_pkg_name,
            user,
            origin=ORIGIN,
            registered_in_core=True,
            collection_acron=target_acron,
        )
        registered.pop("xml_with_pre", None)
        error = registered.get("error_type") or registered.get("error_msg")
        if error:
            raise ArticleRegistrationError(
                _("Unable to register the XML in the PID provider: {} {}").format(
                    error, registered.get("error_msg") or registered.get("error_message")
                )
            )
        if registered.get("v3") != pid_provider_xml.v3 or registered.get("v2") != target_pid:
            raise ArticleRegistrationError(
                _("Unexpected PIDs registered: v3 {} (expected {}), v2 {} (expected {})").format(
                    registered.get("v3"), pid_provider_xml.v3, registered.get("v2"), target_pid
                )
            )
        AMArticle.create_or_update(
            target_pid, target_collection, None, user, status="done", new_record=article
        )

    return result(
        choices.STATUS_ADDED,
        detail={
            "v3": registered.get("v3"),
            "v2": registered.get("v2"),
            "record_status": registered.get("record_status"),
        },
        **data,
    )
