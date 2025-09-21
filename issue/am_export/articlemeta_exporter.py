import logging
import traceback
from datetime import datetime

from core.mongodb import write_item
from core.models import ExportDestination
from issue.models import Issue, IssueExport


def get_issue_data(issue, collection):
    """Prepara dados do periódico para exportação."""
    item = issue.articlemeta_format(collection)
    item["title"] = issue.journal.articlemeta_format(collection)
    return item


def save_am_issue_data(user, issue_export, data):
    """Salva dados do periódico no ArticleMeta."""
    try:
        record_id = write_item("issues", data)
        if record_id:
            issue_export.finish(user, completed=True, events=[f"Saved to AM: {record_id}"])
            return record_id
        raise Exception(f"Failed to save issue {data.get('collection')} {data.get('issn')}")
    except Exception as e:
        issue_export.finish(
            user, 
            completed=False, 
            events=[], 
            exceptions=traceback.format_exc()
        )
        raise


def export_issue_to_articlemeta(
    user, 
    issue,
    collection,
    destination, 
    force_update=False,
):
    """Exporta um periódico para ArticleMeta."""
    try:
        # Inicia ou recupera exportação
        issue_export = IssueExport.get_demand(
            user,
            parent=issue,
            destination=destination,
            pid=issue.get_issue_pid(collection),
            collection=collection.acron3,
            version=None,
            force_update=force_update,
        )
        
        if not issue_export:
            logging.info(f"Issue {issue} already exported")
            return True
        
        # Prepara dados do periódico
        issue_data = get_issue_data(issue, collection)
        
        # Salva no ArticleMeta
        save_am_issue_data(user, issue_export, issue_data)
        return True
        
    except Exception as e:
        logging.error(f"Error exporting issue {issue} {collection}: {e}")
        return False


def bulk_export_issues_to_articlemeta(
    user,
    destination,
    collection_acron_list=None,
    journal_acron_list=None,
    year=None,
    issue_folder=None,
    from_date=None,
    until_date=None,
    force_update=None,
):
    """Exporta múltiplos periódicos para ArticleMeta."""
    # Obtém destino
    queryset = Issue.select_scielo_issues(
        collection_acron_list=collection_acron_list,
        journal_acron_list=journal_acron_list,
        year=year,
        issue_folder=issue_folder,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
    )
    
    for issue in queryset.iterator():
        for collection in issue.collections:
            if collection.acron3 not in collection_acron_list:
                continue
            export_issue_to_articlemeta(
                user=user,
                issue=issue,
                collection=collection,
                destination=destination,
                force_update=force_update,
            )
