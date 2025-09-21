from datetime import datetime

import logging
import sys

from django.contrib.auth import get_user_model
from django.db.models import Q

from config import celery_app
from core.utils.utils import _get_user
from issue.am_import.articlemeta import load_issue_from_article_meta
from issue.am_export import articlemeta_export
from issue.models import Issue
from tracker.models import UnexpectedEvent


User = get_user_model()

logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def task_load_issue_from_article_meta(
    self,
    user_id=None,
    username=None,
    collection=None,
    issn_scielo=None,
    from_date=None,
    until_date=None,
    reset=None,
    limit=None,
    force_update=False,
    timeout=None,
):
    user = _get_user(request=self.request, user_id=user_id, username=username)
    load_issue_from_article_meta(
        user,
        collection=collection,
        issn_scielo=issn_scielo,
        from_date=from_date,
        until_date=until_date,
        reset=reset,
        limit=limit,
        timeout=timeout,
        force_update=force_update
    )


@celery_app.task(bind=True, name="task_export_issues_to_articlemeta")
def task_export_issues_to_articlemeta(
    self,
    collection_acron_list=None,
    journal_acron_list=None,
    year=None,
    from_date=None,
    until_date=None,
    force_update=True,
    user_id=None,
    username=None,
):
    """
    Export issues to ArticleMeta Database with flexible filtering.
    
    Args:
        collection_acron_list: List of collection acronyms to filter (e.g., ['scl', 'arg', 'mex'])
        journal_acron_list: List of journal acronyms to filter
        year: Publication year to filter
        issue_folder: Issue folder format (e.g., 'v10n2s1')
        from_date: Filter issues updated from this date (ISO format: 'YYYY-MM-DD')
        until_date: Filter issues updated until this date (ISO format: 'YYYY-MM-DD')
        force_update: Force update existing records
        user_id: User ID for authentication
        username: Username for authentication
    """
    # Get user for authentication
    user = get_user(request=self.request, user_id=user_id, username=username)
    destination = ExportDestination.get_or_create("articlemeta", user)

    return articlemeta_export.bulk_export_issues_to_articlemeta(
        destination,
        user=user,
        collection_acron_list=collection_acron_list,
        journal_acron_list=journal_acron_list,
        year=year,
        from_date=from_date,
        until_date=until_date,
        force_update=force_update,
    )


@celery_app.task(bind=True, name="task_export_issue_to_articlemeta")
def task_export_issue_to_articlemeta(self, issue_code=None, force_update=True, user_id=None, username=None):
    """
    Export a specific issue to ArticleMeta Database.

    Args:
        issue_code: The primary key of the issue to export
        force_update: Force update existing records
        user_id: User ID for authentication
        username: Username for authentication
    """
    user =  _get_user(request=self.request, user_id=user_id, username=username)

    return articlemeta_export.export_issue_to_articlemeta(
        user=user,
        issue_code=issue_code,
        destination=destination,
        force_update=force_update,
    )
