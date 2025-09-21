import logging
import sys

from django.db import IntegrityError, transaction

from core.models import Language
from core.utils.rename_dictionary_keys import rename_issue_dictionary_keys
from issue.am_import.correspondencia import correspondencia_issue
from issue.models.models import CodeSectionIssue, Issue, SectionIssue, TocSection
from tracker.models import UnexpectedEvent


def normalize_markup_done(markup_done):
    val = extract_value(markup_done)
    if val in ("0", 0, None, ""):
        markup_done = False
    elif val in ("1", 1):
        markup_done = True
    else:
        markup_done = False
    return markup_done


def create_or_update_issue(
    user,
    issue_data: dict,
    collection_acron: str,
    issn: str
):
    """
    Cria ou atualiza um Issue a partir dos dados do LegacyIssue.
    """
    issue_dict = rename_issue_dictionary_keys(
        [issue_data], correspondencia_issue
    )
    issue_pid_suffix = issue_data.get("code")[9:]
    issue = get_or_create_issue(
        collection_acron3=collection_acron,
        issn_scielo=issn,
        volume=issue_dict.get("volume"),
        number=issue_dict.get("number"),
        supplement_volume=issue_dict.get("supplement_volume"),
        supplement_number=issue_dict.get("supplement_number"),
        data_iso=issue_dict.get("date_iso"),
        sections_data=issue_dict.get("sections_data"),
        markup_done=issue_dict.get("markup_done"),
        user=user,
        order=int(issue_pid_suffix),
        issue_pid_suffix=issue_pid_suffix,
        season=None,
    )
    # FIXME - faltam dados para importar do AM, como por exemplo bibliographic strip
    return issue


def get_or_create_issue(
    collection_acron3,
    issn_scielo,
    volume,
    number,
    supplement_volume,
    supplement_number,
    data_iso,
    sections_data,
    markup_done,
    user,
    order,
    issue_pid_suffix,
    force_update,
    season,
):
    issn_scielo = extract_value(issn_scielo)
    volume = extract_value(volume)
    number = extract_value(number)
    supplement = extract_value(supplement_number) or extract_value(supplement_volume)


    if not force_update:
        issue = Issue.select_issues(
            collection_acron_list=[collection_acron3],
            journal_pid_list=[issn_scielo],
            volume=volume,
            number=number,
            supplement=supplement_volume or supplement_number,
        ).first()
        if issue:
            return issue

    data = extract_value(data_iso)
    markup_done = normalize_markup_done(markup_done)

    obj = Issue.get_or_create(
        journal=scielo_journal.journal,
        volume=volume,
        number=number,
        supplement=supplement,
        year=data[:4],
        month=data[4:6],
        sections=get_or_create_sections(sections_data, user),
        markup_done=markup_done,
        order=order,
        issue_pid_suffix=issue_pid_suffix,
        user=user,
        season=season,
    )
    data_code_sections = get_or_create_code_sections(sections_data, user)
    for section in data_code_sections:
        obj.code_sections.add(section)
    return obj


def extract_date(date):
    if date:
        return [(x.get("a"), x.get("m")) for x in date][0]
    return None, None


def get_or_create_sections(sections, user):
    data = []
    if sections and isinstance(sections, list):
        for section in sections:
            text = section.get("t", "")
            lang_code2 = section.get("l")
            language = Language.get_or_create(code2=lang_code2, creator=user)
            try:
                with transaction.atomic():
                    obj, _ = TocSection.objects.get_or_create(
                        plain_text=text,
                        language=language,
                        defaults={
                            "creator": user,
                        }
                    )
            except IntegrityError as e:
                obj, _ = TocSection.objects.get(
                    plain_text=text,
                    language=language,
                )
            data.append(obj)
    return data


def extract_value(value):
    if value and isinstance(value, list):
        return [x.get("_") for x in value][0]


def get_or_create_code_sections(sections_data, user):
    data = []
    if sections_data and isinstance(sections_data, list):
        for section in sections_data:
            code = section.get("c")
            lang_code2 = section.get("l")
            text = section.get("t", "")
            try:
                code_section, _ = CodeSectionIssue.objects.get_or_create(
                    code=code,
                    defaults={
                        "creator": user,
                    }
                )
                language = Language.get_or_create(code2=lang_code2, creator=user)
                try:
                    with transaction.atomic():
                        issue_section, _ = SectionIssue.objects.get_or_create(
                            code_section=code_section,
                            language=language,
                            defaults={
                                "text": text,
                                "creator": user,
                            }
                        )
                except IntegrityError as e:
                    issue_section, _ = SectionIssue.objects.get(
                        code_section=code_section,
                        language=language,
                    )
                data.append(issue_section)
            except Exception as e:
                logging.error(f"Erro ao criar section_issue: {e}")
                exc_type, exc_value, exc_traceback = sys.exc_info()
                UnexpectedEvent.create(
                    exception=e,
                    exc_traceback=exc_traceback,
                    detail={
                        "function": "get_or_create_code_sections",
                        "section": section,
                    },
                )
    return data

