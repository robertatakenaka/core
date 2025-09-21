import logging
import traceback
from datetime import datetime

from core.mongodb import write_item
from core.models import ExportDestination
from journal.models import SciELOJournal, JournalExport


def get_journal_data(journal, collection):
    """Prepara dados do periódico para exportação."""
    return journal.articlemeta_format(collection)


def save_am_journal_data(user, journal_export, data):
    """Salva dados do periódico no ArticleMeta."""
    try:
        record_id = write_item("journals", data)
        if record_id:
            journal_export.finish(user, completed=True, events=[f"Saved to AM: {record_id}"])
            return record_id
        raise Exception(f"Failed to save journal {data.get('collection')} {data.get('issn')}")
    except Exception as e:
        journal_export.finish(
            user, 
            completed=False, 
            events=[], 
            exceptions=traceback.format_exc()
        )
        raise


def export_journal_to_articlemeta(
    user, 
    scielo_journal, 
    destination, 
    force_update=False,
):
    """Exporta um periódico para ArticleMeta."""
    try:
        # Inicia ou recupera exportação
        journal_export = JournalExport.get_demand(
            user,
            parent=scielo_journal.journal,
            destination=destination,
            pid=scielo_journal.issn_scielo,
            collection=scielo_journal.collection.acron3,
            version=None,
            force_update=force_update,
        )
        
        if not journal_export:
            logging.info(f"Journal {scielo_journal.journal_acron} already exported")
            return True
        
        # Prepara dados do periódico
        journal_data = get_journal_data(scielo_journal.journal, scielo_journal.collection)
        
        # Salva no ArticleMeta
        save_am_journal_data(user, journal_export, journal_data)
        return True
        
    except Exception as e:
        logging.error(f"Error exporting journal {scielo_journal.issn_scielo}: {e}")
        return False


def bulk_export_journals_to_articlemeta(
    user,
    destination=None,
    collection_acron_list=None,
    journal_acron_list=None,
    from_date=None,
    until_date=None,
    force_update=False,
):
    """Exporta múltiplos periódicos para ArticleMeta."""
    # Obtém destino
    if not destination:
        destination = ExportDestination.get_or_create("articlemeta", user)
    
    queryset = SciELOJournal.select_scielo_journals(
        collection_acron_list=collections,
        journal_acron_list=journal_acron_list,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
    )
    
    for scielo_journal in queryset.iterator():
        export_journal_to_articlemeta(
            user=user,
            scielo_journal=scielo_journal,
            destination=destination,
            force_update=force_update,
        )
    
    logging.info("Export completed")