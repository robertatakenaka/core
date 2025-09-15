import logging
import sys
import traceback
from datetime import datetime

from django.db.models import Q
from packtools.sps.formats.am import am

from core.mongodb import write_to_db
from core.utils import date_utils
from journal.models import SciELOJournal
from tracker.models import UnexpectedEvent

from .models import Article, ArticleExport, ArticleExportDestination


class ArticleExportError(Exception): ...


def get_export_destination(destination_name="articlemeta", user=None):
    """Obtém o destino de exportação."""
    try:
        return ArticleExportDestination.objects.get(acronym=destination_name)
    except ArticleExportDestination.MultipleObjectReturned:
        return ArticleExportDestination.objects.filter(acronym=destination_name).first()
    except ArticleExportDestination.DoesNotExist:
        obj = ArticleExportDestination()
        obj.acronym = destination_name
        obj.creator = user
        obj.save()
        return obj


def get_target_collections(selected_collection_acron_list, article):
    if selected_collection_acron_list:
        target_collections = [
            c for c in article.collections if c.acron3 in selected_collection_acron_list
        ]
    else:
        target_collections = article.collections

    if not target_collections:
        raise ValueError("No article collections found to export")


def check_exportation_demand(
    destination,
    user,
    article,
    collection,
    version,
    force_update=None,
):
    """Exporta um artigo para uma única coleção."""
    if force_update:
        return ArticleExport.start(article, destination, collection, version, user)
    if not ArticleExport.is_exported(article, destination, collection, version):
        return ArticleExport.start(article, destination, collection, version, user)
    raise ArticleExportError(f"{article} {collection} is already exported")


def get_article_exports(
    destination, user, article, target_collections, version, force_update=None
):
    if not target_collections:
        target_collections = article.collections
    for target_collection in target_collections:
        try:
            yield check_exportation_demand(
                destination, user, article, target_collection, version, force_update
            )
        except ArticleExportError:
            yield {
                "collection": target_collection,
                "exceptions": traceback.format_exc(),
            }


def get_article_data(
    user,
    article,
):
    """Exporta um artigo para o ArticleMeta."""
    # Obtém o destino de exportação

    try:
        event = article.add_event(user, "prepare to export data to am")
        # Prepara dados externos
        external_data = {
            "pid_v3": article.pid_v3,
            "code": article.pid_v2,
            "created_at": article.created.strftime("%Y-%m-%d"),
            "document_type": article.article_type,
            "processing_date": article.updated,
            "publication_date": article.pub_date,
            "publication_year": article.issue.year,
            "version": "xml",
        }

        # Constrói formato ArticleMeta
        article_data = am.build(article.xmltree, external_data)
        event.finish(user, completed=True, detail=detail)

        return article_data, external_data

    except Exception as e:
        event.finish(
            user, completed=False, detail=detail, exceptions=traceback.format_exc()
        )
        raise


def get_journal_data(journal, collection):
    return journal.articlemeta_format(collection.acron3)


def get_issue_data(issue, collection):
    issue_data = issue.articlemeta_format(collection.acron3)
    issue_data["processing_date"] = datetime.strptime(
        issue_data["processing_date"], "%Y-%m-%d"
    )
    return issue_data


def complete_data(
    article,
    collection,
    article_data,
    external_data,
):
    try:
        events = []
        article_data = article_data.copy()
        external_data = external_data.copy()

        issue_data = get_issue_data(article.issue, collection)
        events.append(f"Got issue data {collection}")

        # Prepara dados específicos da coleção
        external_data.update({"collection": collection.acron3})
        events.append(f"Updated article data with collection {collection}")

        # Enriquece dados do artigo
        # Article data
        article_data.update(external_data)
        article_data["code"] = article_data["article"]["code"]
        events.append(f"Updated article data with article code {article_data['code']}")

        # Issue data
        article_data["code_issue"] = issue_data["code"]
        article_data["issue"] = issue_data["issue"]
        events.append(
            f"Updated article data with issue data {article_data['code_issue']}"
        )

        # Journal data
        article_data["code_title"] = [
            x for x in issue_data["code_title"] if x is not None
        ]
        article_data["title"] = issue_data["title"]
        events.append(
            f"Updated article data with journal data {article_data['code_title']}"
        )

        return {"article_data": article_data, "events": events}

    except Exception as e:
        # Registra a exceção e finaliza com erro
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exception_info = {
            "type": exc_type.__name__ if exc_type else type(e).__name__,
            "message": str(e),
            "traceback": str(exc_traceback),
        }
        events.append(traceback.format_exc())
        return {"events": events, "exceptions": traceback.format_exc()}


def save_article_data(
    user,
    article_export,
    data,
):
    """Exporta um artigo para uma única coleção."""
    try:
        record_id = write_item("articles", data)
        if record_id:
            article_export.finish(user, completed=True)
            return record_id
        raise Exception(f"Article {data.get('collection')} {data.get('code')}")
    except Exception as e:
        # Registra a exceção e finaliza com erro
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exception_info = {
            "type": exc_type.__name__ if exc_type else type(e).__name__,
            "message": str(e),
            "traceback": str(exc_traceback),
        }
        article_export.finish(user, completed=False, exceptions=traceback.format_exc())


def export_article_to_articlemeta(
    user,
    article,
    article_exports,
):
    """Exporta um artigo para uma única coleção."""
    try:
        items = []
        event = article.add_event(user, "export article to AM")
        article_data, external_data = get_article_data(user, article)
        for article_export in article_exports:
            item = {"collection": article_export.collection}
            try:
                complete_data_response = complete_data(
                    article_export.article,
                    article_export.collection,
                    article_data,
                    external_data,
                )
            except AttributeError:
                event = article.add_event(user, "get article export AM")
                event.finish(user, completed=False, detail=article_export)
            else:
                item["saved"] = save_article_data(
                    user, article_export, complete_data_response["article_data"]
                )
            items.append(item)
        event.finish(user, completed=True, detail=items)
    except Exception as e:
        # Registra a exceção e finaliza com erro
        exc_type, exc_value, exc_traceback = sys.exc_info()
        exception_info = {
            "type": exc_type.__name__ if exc_type else type(e).__name__,
            "message": str(e),
            "traceback": str(exc_traceback),
        }
        event.finish(user, completed=False, exceptions=traceback.format_exc())


def export_article_instances_to_articlemeta(
    destination,
    target_collections,
    user,
    article,
    version=None,
    force_update=None,
):
    # Exporta para cada coleção
    article_exports = get_article_exports(
        destination, user, article, target_collections, version, force_update
    )
    return export_article_to_articlemeta(user, article, article_exports)


def bulk_data_export_to_articlemeta(
    user,
    queryset,
    force_update=None,
):
    """Exporta múltiplos artigos para o ArticleMeta."""
    # Obtém queryset filtrado

    total_articles = queryset.count()
    if total_articles == 0:
        raise ValueError(f"No article to export to AM")

    destination = get_export_destination("articlemeta", user)
    version = datetime.utcnow().isoformat()
    for article in queryset.iterator():
        export_article_instances_to_articlemeta(
            destination,
            article.collections,
            user,
            article,
            version,
            force_update,
        )
