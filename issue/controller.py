import json
import logging
import sys
import traceback

from django.db.models import Count

from core.mongodb import write_item
from issue.models import AMIssue, Issue, IssueExporter
from tracker.models import UnexpectedEvent


def export_issue_to_articlemeta(
    user,
    issue,
    collection_acron_list=None,
    force_update=None,
    version=None,
):
    try:
        events = None
        if not issue:
            raise ValueError("export_issue_to_articlemeta requires issue")
        legacy_keys_items = list(issue.get_legacy_keys(collection_acron_list, is_active=True))
        if not legacy_keys_items:
            UnexpectedEvent.create(
                exception=ValueError("No legacy keys found for issue"),
                detail={
                    "operation": "export_issue_to_articlemeta",
                    "issue": str(issue),
                    "collection_acron_list": collection_acron_list,
                    "force_update": force_update,
                    "events": events,
                },
            )
            return
        for legacy_keys in legacy_keys_items:
            try:
                exporter = None
                response = None
                events = []
                col = legacy_keys.get("collection")
                pid = legacy_keys.get("pid")
                logging.info(
                    (user, issue, "articlemeta", pid, col, version, force_update)
                )
                events.append("check articlemeta exportation demand")
                exporter = IssueExporter.get_demand(
                    user, issue, "articlemeta", pid, col, version, force_update
                )
                if not exporter:
                    # não encontrou necessidade de exportar
                    continue

                events.append("building articlemeta format for issue")
                issue_data = issue.articlemeta_format(col.acron3)

                try:
                    json.dumps(issue_data)
                except Exception as e:
                    logging.exception(e)
                    response = str(issue_data)
                    raise e

                events.append("writing issue to articlemeta database")
                response = write_item("issues", issue_data)
                exporter.finish(
                    user,
                    completed=True,
                    events=events,
                    response=response,
                    errors=None,
                    exceptions=None,
                )
            except Exception as e:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exporter:
                    exporter.finish(
                        user,
                        completed=False,
                        events=events,
                        response=response,
                        errors=None,
                        exceptions=traceback.format_exc(),
                    )
                else:
                    UnexpectedEvent.create(
                        exception=e,
                        exc_traceback=exc_traceback,
                        detail={
                            "operation": "export_article_to_articlemeta",
                            "issue": str(issue),
                            "collection": str(col),
                            "events": events,
                            "traceback": traceback.format_exc(),
                        },
                    )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "operation": "export_issue_to_articlemeta",
                "issue": issue,
                "collection_acron_list": collection_acron_list,
                "force_update": force_update,
                "events": events,
            },
        )


def bulk_export_issues_to_articlemeta(
    user=None,
    collection_acron_list=None,
    journal_acron_list=None,
    publication_year=None,
    volume=None,
    number=None,
    supplement=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    force_update=None,
    version=None,
):
    """
    Export issues to ArticleMeta Database with flexible filtering.

    Args:
        user: User object for authentication
        collection_acron_list: List of collections acronyms (e.g., ["scl", "mex"])
        journal_acron_list: List of journal acronyms to filter
        publication_year: Filter by publication year
        volume: Filter by volume number
        number: Filter by issue number
        supplement: Filter by supplement
        from_date: Export issues modified from this date
        until_date: Export issues modified until this date
        days_to_go_back: Export issues modified from this number of days ago
        force_update: Force update existing records
        version: Version identifier for export
    """
    try:
        queryset = Issue.select_issues(
            collection_acron_list=collection_acron_list,
            journal_acron_list=journal_acron_list,
            publication_year=publication_year,
            volume=volume,
            number=number,
            supplement=supplement,
            from_date=from_date,
            until_date=until_date,
            days_to_go_back=days_to_go_back,
        )
        if not queryset.exists():
            UnexpectedEvent.create(
                exception=ValueError("No issues found for the given filters"),
                detail={
                    "function": "bulk_export_issues_to_articlemeta",
                    "collection_acron_list": collection_acron_list,
                    "journal_acron_list": journal_acron_list,
                    "publication_year": publication_year,
                    "volume": volume,
                    "number": number,
                    "supplement": supplement,
                    "from_date": str(from_date) if from_date else None,
                    "until_date": str(until_date) if until_date else None,
                    "days_to_go_back": days_to_go_back,
                    "force_update": force_update,
                },
            )
            return
        for issue in queryset.iterator():
            try:
                export_issue_to_articlemeta(
                    user,
                    issue=issue,
                    collection_acron_list=collection_acron_list,
                    force_update=force_update,
                    version=version,
                )
            except Exception as e:
                # Registra erro do issue mas continua processando outros
                exc_type, exc_value, exc_traceback = sys.exc_info()
                UnexpectedEvent.create(
                    exception=e,
                    exc_traceback=exc_traceback,
                    detail={
                        "function": "bulk_export_issues_to_articlemeta",
                        "issue_id": issue.id,
                        "journal_acron": getattr(issue, "journal_acron", None),
                        "publication_year": getattr(issue, "publication_year", None),
                        "volume": getattr(issue, "volume", None),
                        "number": getattr(issue, "number", None),
                        "supplement": getattr(issue, "supplement", None),
                        "force_update": force_update,
                    },
                )
                continue
                
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "function": "bulk_export_issues_to_articlemeta",
                "collection_acron_list": collection_acron_list,
                "journal_acron_list": journal_acron_list,
                "publication_year": publication_year,
                "volume": volume,
                "number": number,
                "supplement": supplement,
                "from_date": str(from_date) if from_date else None,
                "until_date": str(until_date) if until_date else None,
                "days_to_go_back": days_to_go_back,
                "force_update": force_update,
            },
        )
        raise

def _choose_am_issue_to_keep(am_issues, article_pids_v2):
    """
    Escolhe, entre AMIssue duplicados (mesmo issue e coleção), o que deve
    ser mantido: o que corresponde a mais pid_v2 de artigos do issue;
    em caso de empate, prefere o migrado (com data) e depois o mais antigo.
    """

    def score(am_issue):
        matches = sum(
            1 for pid_v2 in article_pids_v2 if pid_v2[1:].startswith(am_issue.pid or "-")
        )
        return (matches, bool(am_issue.data), -am_issue.created.timestamp())

    return max(am_issues, key=score)


def fix_issue_legacy_keys(
    user,
    collection_acron_list=None,
    journal_acron_list=None,
    publication_year=None,
    dry_run=True,
):
    """
    Corrige chaves legadas de issues e artigos:

    1. Remove AMIssue gerados (sem data) duplicados para o mesmo issue e
       coleção, mantendo o que corresponde aos pid_v2 dos artigos.
       AMIssue migrados (com data) nunca são removidos.
    2. Recria AMArticle dos artigos com pid_v2 que não possuem chave legada.

    Args:
        user: usuário responsável
        collection_acron_list: filtra por coleções
        journal_acron_list: filtra por periódicos
        publication_year: filtra por ano
        dry_run: se True, apenas relata o que seria feito

    Returns:
        dict com estatísticas da operação
    """
    # evita importação circular
    from article.models import Article

    stats = {
        "dry_run": dry_run,
        "issues_with_duplicates": 0,
        "am_issues_deleted": [],
        "am_issues_kept_with_data_conflict": [],
        "articles_without_legacy_keys": 0,
        "articles_fixed": 0,
        "articles_still_without_legacy_keys": [],
        "errors": 0,
    }

    issue_ids = list(
        Issue.select_issues(
            collection_acron_list=collection_acron_list,
            journal_acron_list=journal_acron_list,
            publication_year=publication_year,
        ).values_list("id", flat=True)
    )
    if not issue_ids:
        return stats

    # 1. AMIssue duplicados por (issue, coleção)
    duplicated = (
        AMIssue.objects.filter(new_record_id__in=issue_ids)
        .values("new_record_id", "collection_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for item in duplicated.iterator():
        try:
            stats["issues_with_duplicates"] += 1
            am_issues = list(
                AMIssue.objects.filter(
                    new_record_id=item["new_record_id"],
                    collection_id=item["collection_id"],
                ).select_related("collection")
            )
            article_pids_v2 = list(
                Article.objects.filter(
                    issue_id=item["new_record_id"], pid_v2__isnull=False
                ).values_list("pid_v2", flat=True)
            )
            keep = _choose_am_issue_to_keep(am_issues, article_pids_v2)
            for am_issue in am_issues:
                if am_issue.pk == keep.pk:
                    continue
                if am_issue.data:
                    # migrado: não remove, apenas relata
                    stats["am_issues_kept_with_data_conflict"].append(str(am_issue))
                    continue
                stats["am_issues_deleted"].append(str(am_issue))
                if not dry_run:
                    am_issue.delete()
        except Exception as e:
            stats["errors"] += 1
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=e,
                exc_traceback=exc_traceback,
                detail={
                    "operation": "fix_issue_legacy_keys.dedup_am_issue",
                    "item": item,
                },
            )

    # 2. artigos sem AMArticle
    articles = (
        Article.objects.filter(
            issue_id__in=issue_ids,
            pid_v2__isnull=False,
            legacy_article__isnull=True,
        )
        .select_related("issue", "journal")
        .distinct()
    )
    stats["articles_without_legacy_keys"] = articles.count()
    if dry_run:
        return stats

    for article in articles.iterator():
        try:
            article.create_legacy_keys(user, force_update=True)
            if article.legacy_article.exists():
                stats["articles_fixed"] += 1
            else:
                stats["articles_still_without_legacy_keys"].append(
                    f"{article.pid_v2} {article.issue}"
                )
        except Exception as e:
            stats["errors"] += 1
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=e,
                exc_traceback=exc_traceback,
                detail={
                    "operation": "fix_issue_legacy_keys.article",
                    "article": str(article),
                    "pid_v2": article.pid_v2,
                },
            )
    return stats
