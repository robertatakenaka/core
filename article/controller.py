import csv
import logging
import sys

from django.db.models import Q

from institution.models import Sponsor
from journal.models import SciELOJournal
from pid_provider.choices import PPXML_STATUS_TODO
from pid_provider.models import PidProviderXML

from .models import Article, ArticleFunding


def load_financial_data(row, user):
    article_findings = []
    for institution in row.get("funding_source").split(","):
        sponsor = Sponsor.get_or_create(
            user=user,
            name=institution,
            acronym=None,
            level_1=None,
            level_2=None,
            level_3=None,
            location=None,
            official=None,
            is_official=None,
            url=None,
            institution_type=None,
        )
        article_findings.append(
            ArticleFunding.get_or_create(
                award_id=row.get("award_id"), funding_source=sponsor, user=user
            )
        )
    article = Article.get_or_create(
        pid_v2=row.get("pid_v2"), fundings=article_findings, user=user
    )

    return article


def read_file(user, file_path):
    with open(file_path, "r") as csvfile:
        data = csv.DictReader(csvfile)
        for row in data:
            logging.debug(row)
            load_financial_data(row, user)


def get_pp_xml_ids_to_load_articles(
    collection_acron_list=None,
    journal_acron_list=None,
    from_pub_year=None,
    until_pub_year=None,
    from_updated_date=None,
    until_updated_date=None,
    proc_status_list=None,
):
    return select_pp_xml(
        collection_acron_list,
        journal_acron_list,
        from_pub_year,
        until_pub_year,
        from_updated_date,
        until_updated_date,
        proc_status_list=proc_status_list or [PPXML_STATUS_TODO],
    ).values_list("id", flat=True)


def select_pp_xml(
    collection_acron_list=None,
    journal_acron_list=None,
    from_pub_year=None,
    until_pub_year=None,
    from_updated_date=None,
    until_updated_date=None,
    proc_status_list=None,
    params=None,
):
    params = params or {}

    q = Q()
    if journal_acron_list or collection_acron_list:
        issns = SciELOJournal.get_issn_list(collection_acron_list, journal_acron_list)
        issn_print_list = issns["issn_print_list"]
        issn_electronic_list = issns["issn_electronic_list"]

        if issn_print_list or issn_electronic_list:
            q = Q(issn_print__in=issn_print_list) | Q(
                issn_electronic__in=issn_electronic_list
            )
        elif issn_print_list:
            q = Q(issn_print__in=issn_print_list)
        elif issn_electronic_list:
            q = Q(issn_electronic__in=issn_electronic_list)

    if from_updated_date:
        params["updated__gte"] = from_updated_date
    if until_updated_date:
        params["updated__lte"] = until_updated_date

    if from_pub_year:
        params["pub_year__gte"] = from_pub_year
    if until_pub_year:
        params["pub_year__lte"] = until_pub_year

    if proc_status_list:
        params["proc_status__in"] = proc_status_list

    return PidProviderXML.objects.filter(q, **params)
