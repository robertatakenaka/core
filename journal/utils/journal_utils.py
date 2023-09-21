import re

from django.db.models import Q
from core.models import Language, License
from institution.models import Institution
from vocabulary.models import Vocabulary
from reference.models import JournalTitle
from .funcs_extract_am import (
    extract_issn_print_electronic,
    extract_value,
    extract_value_mission,
)
from journal.models import (
    Collection,
    OfficialJournal,
    Journal,
    SciELOJournal,
    Mission,
    Publisher,
    Owner,
    Copyright,
    Annotation,
    Sponsor,
    SubjectDescriptor,
    Subject,
    Standard,
    WebOfKnowledge,
    WebOfKnowledgeSubjectCategory,
    IndexedAt,
)
from location.models import City, Region, Location, State, Country, Address

from datetime import datetime


def create_or_update_journal(
    title,
    short_title,
    other_titles,
    submission_online_url,
    official_journal,
    user,
):
    title = extract_value(title)
    other_titles = get_or_create_other_titles(other_titles=other_titles, user=user)

    journal = Journal.create_or_update(
        user=user,
        official_journal=official_journal,
        title=title,
        short_title=extract_value(short_title),
        other_titles=other_titles,
        submission_online_url=extract_value(submission_online_url),
    )
    return journal


def create_or_update_scielo_journal(
    journal, collection, issn_scielo, journal_acron, status, user
):
    issnl = extract_value(issn_scielo)
    code_status = extract_value(status)
    scielo_journal = SciELOJournal.create_or_update(
        user=user,
        collection=get_collection(collection),
        issn_scielo=issnl,
        journal_acron=extract_value(journal_acron),
        journal=journal,
        code_status=code_status,
    )
    return scielo_journal


def update_panel_scope_and_about(
    journal,
    mission,
    sponsor,
    subject_descriptors,
    subject,
    wos_scie,
    wos_ssci,
    wos_ahci,
    wos_areas,
    user,
):
    get_or_create_mission(journal=journal, mission=mission, user=user)
    get_or_create_sponsor(journal=journal, sponsor=sponsor, user=user)
    get_or_create_subject_descriptor(
        journal=journal,
        subject_descriptors=subject_descriptors,
        user=user,
    )
    create_or_update_subject(journal=journal, subject=subject, user=user)
    create_or_update_wos_db(
        journal=journal,
        wos_scie=wos_scie,
        wos_ssci=wos_ssci,
        wos_ahci=wos_ahci,
        user=user,
    )
    get_or_update_wos_areas(journal=journal, wos_areas=wos_areas, user=user)


def update_panel_interoperation(
    journal, indexed_at, secs_code, medline_code, medline_short_title, user
):
    get_or_create_indexed_at(journal, indexed_at=indexed_at, user=user)
    journal.secs_code = extract_value(secs_code)
    journal.medline_code = extract_value(medline_code)
    journal.medline_short_title = extract_value(medline_short_title)


def update_panel_information(
    journal,
    frequency,
    publishing_model,
    text_language,
    abstract_language,
    standard,
    vocabulary,
    alphabet,
    classification,
    national_code,
    type_of_literature,
    treatment_level,
    level_of_publication,
    user,
):
    create_or_update_journal_languages(
        journal=journal,
        language_data=text_language,
        language_type="text",
        user=user,
    )
    create_or_update_journal_languages(
        journal=journal,
        language_data=abstract_language,
        language_type="abstract",
        user=user,
    )
    get_or_create_vocabulary(vocabulary=vocabulary, journal=journal, user=user)
    create_or_update_standard(standard=standard, journal=journal, user=user)
    journal.frequency = extract_value(frequency)
    journal.publishing_model = extract_value(publishing_model)
    journal.alphabet = extract_value(alphabet)
    journal.classification = extract_value(classification)
    journal.national_code = extract_value(national_code)
    journal.type_of_literature = extract_value(type_of_literature)
    journal.treatment_level = extract_value(treatment_level)
    if len(extract_value(level_of_publication)) < 3:
        journal.level_of_publication = extract_value(level_of_publication)


def update_panel_institution(
    journal,
    publisher,
    copyright_holder,
    address,
    electronic_address,
    publisher_country,
    publisher_state,
    publisher_city,
    user,
):
    location = create_or_update_location(
    address,    
    publisher_country,
    publisher_state,
    publisher_city,
    user,
    )
    url = extract_value(electronic_address)
    copyright_holder = extract_value(copyright_holder)
    publisher = extract_value(publisher)
    
    if isinstance(publisher, str):
        publisher = [publisher]
    
    if publisher:
        for p in publisher:
            if p:
                institution = Institution.create_or_update(
                    inst_name=p,
                    user=user,
                    location=location,
                    url=url,
                    copyright_holder=copyright_holder,
                    inst_acronym=None,
                    level_1=None,
                    level_2=None,
                    level_3=None,
                    official=None,
                    is_official=None,
                )
                publisher = Publisher.objects.get_or_create(
                    page=journal,
                    institution=institution,
                )
                Owner.objects.get_or_create(
                    page=journal,
                    institution=institution,
                )


def update_panel_website(
    journal,
    url_of_the_journal,
    url_of_submission_online,
    url_of_the_main_collection,
    license_of_use,
    user
):
    
    journal.url_of_journal = extract_value(url_of_the_journal)
    journal.collection_main_url = extract_value(url_of_the_main_collection)
    journal.submission_online_url = extract_value(url_of_submission_online)
    license_type = extract_value(license_of_use)
    if license_type:
        license = License.create_or_update(
            license_type=license_type,
            user=user 
        )
        journal.use_license = license

def update_panel_notes(
    journal,
    notes,
    creation_date,
    update_date,
    user,
):
    """
        Ex notes:
            [{'_': 'Editor:'}, {'_': 'Denis Coitinho Silveira'}, {'_': 'Rua Lobo da Costa, 270/501'}, {'_': '90050-110'}, {'_': 'UNISINOS - Universidade do Vale do Rio dos Sinos'}, {'_': 'Porto Alegre'}, {'_': 'RS'}, {'_': 'Brasil'}, {'_': '51 32269513; 51 983107257'}, {'_': 'deniscoitinhosilveira@gmail.com'}]
            [{'_': 'Iniciou no v12n1'}]
    """
    notes = extract_value(notes)
    if notes:
        creation_date = datetime.strptime(extract_value(creation_date), "%Y%m%d")
        update_date = datetime.strptime(extract_value(update_date), "%Y%m%d")
        if isinstance(notes, str):
            notes = [notes]
        n = '\n'.join(notes)
        obj, created = Annotation.objects.get_or_create(
            journal=journal,
            notes=n,
            creation_date=creation_date,
            update_date=update_date,
            updated_by=user,
        )
        if created:
            obj.creator = user
            obj.save()


def update_panel_legacy_compatibility_fields(
    journal,
    center_code,
    identification_number,
    ftp,
    user_subscription,
    subtitle,
    section,
    has_supplement,
    is_supplement,
    acronym_letters,
):
    user_subs = extract_value(user_subscription)
    if user_subs and 2 <= len(user_subs) <= 3:
        journal.user_subscription = user_subs
    journal.center_code = extract_value(center_code)
    journal.identification_number = extract_value(identification_number)
    journal.ftp = extract_value(ftp)
    journal.subtitle = extract_value(subtitle)
    journal.section = extract_value(section)
    journal.has_supplement = extract_value(has_supplement)
    journal.is_supplement = extract_value(is_supplement)
    journal.acronym_letters = extract_value(acronym_letters)


def create_or_update_official_journal(
    title,
    new_title,
    old_title,
    issn_print_or_electronic,
    issn_scielo,
    type_issn,
    current_issn,
    user,
    foundation_year=None,
):
    """
    Ex type_issn:
        [{"_": "ONLIN"}]
    Ex current_issn:
        [{"_": "1676-5648"}]
    """
    title = extract_value(title)
    issnl = extract_value(issn_scielo)

    if type_issn and current_issn:
        for item in type_issn:
            item["t"] = item.pop("_")
        type_issn[0].update(current_issn[0])
    issn = issn_print_or_electronic or type_issn
    issn_print, issn_electronic = extract_issn_print_electronic(
        issn_print_or_electronic=issn
    )

    obj = OfficialJournal.create_or_update(
        user=user,
        issn_print=issn_print,
        issn_electronic=issn_electronic,
        issnl=issnl,
        title=title,
        foundation_year=foundation_year,
    )
    obj.new_title = extract_value(new_title)
    obj.old_title = extract_value(old_title)
    obj.save()
    return obj


def get_collection(collection):
    try:
        return Collection.objects.get(code=collection)
    except Collection.DoesNotExist:
        return None


def get_or_create_other_titles(other_titles, user):
    data = []
    if other_titles:
        ot = extract_value(other_titles)
        if isinstance(ot, str):
            ot = [ot]
        for t in ot:
            obj, created = JournalTitle.objects.get_or_create(
                title=t,
                creator=user,
            )
            data.append(obj)
        # journal.other_titles.set(data)
        return data


def get_or_create_mission(mission, journal, user):
    if mission and isinstance(mission, list):
        missions = extract_value_mission(mission=mission)
        for m in missions:
            obj, created = Mission.objects.get_or_create(
                journal=journal,
                rich_text=m.get("mission"),
                language=Language.get_or_create(code2=m.get("lang")),
                creator=user,
            )


def get_or_create_sponsor(sponsor, journal, user):
    if sponsor and isinstance(sponsor, list):
        for s in sponsor:
            name = extract_value([s])
            ## FIXME
            ## Sponso de diferentes formas (insta_name e insta_acronym)
            ## Ex:
            ## CNPq
            ## Instituto Nacional de Estudos e Pesquisas Educacionais Anísio Teixeira
            ## Fundação Getulio Vargas/ Escola de Administração de Empresas de São Paulo
            ## CNPq - Conselho Nacional de Desenvolvimento Científico e Tecnológico (PIEB)
            if name:
                obj, created = Sponsor.objects.get_or_create(
                    page=journal,
                    institution=Institution.create_or_update(
                        inst_name=name,
                        copyright_holder=None,
                        inst_acronym=None,
                        level_1=None,
                        level_2=None,
                        level_3=None,
                        location=None,
                        official=None,
                        is_official=None,
                        url=None,
                        user=user,
                    ),
                )


def get_or_create_subject_descriptor(subject_descriptors, journal, user):
    """
    subject_descriptors:
        [{'_': 'ECONOMIA, TEORIA ECONÔMICA,  HISTÓRIA ECONÔMICA,  ECONOMIA MONETÁRIA E FISCAL, CRESCIMENTO, FLUTUAÇÕES E PLANEJAMENTO ECONÔMICO'}]
        [{'_': 'MEDICINA'}, {'_': 'PSIQUIATRIA'}, {'_': 'SAUDE MENTAL'}]
        [{'_': 'AGRONOMIA; FITOPATOLOGIA; FITOSSANIDADE'}]
    """
    data = []
    if subject_descriptors:
        sub_desc = extract_value(subject_descriptors)
        if isinstance(sub_desc, str):
            sub_desc = [sub_desc]
        for s in sub_desc:
            # Em alguns casos, subject_descriptors vem separado por "," ou ";"
            for word in re.split(",|;", s):
                word = word.strip()
                obj, created = SubjectDescriptor.objects.get_or_create(
                    value=word,
                    creator=user,
                )
                data.append(obj)
        journal.subject_descriptor.set(data)


def create_or_update_subject(subject, journal, user):
    data = []
    if subject:
        sub = extract_value(subject)
        if isinstance(sub, str):
            sub = [sub]
        for s in sub:
            obj = Subject.create_or_update(code=s, user=user)
            data.append(obj)
        journal.subject.set(data)


def create_or_update_journal_languages(language_data, journal, language_type, user):
    data = []
    if language_data:
        langs = extract_value(language_data)
        if isinstance(langs, str):
            langs = [langs]
        for l in langs:
            obj = Language.get_or_create(code2=l, creator=user)
            if obj:
                data.append(obj)

        if language_type == "text":
            journal.text_language.set(data)
        elif language_type == "abstract":
            journal.abstract_language.set(data)


def get_or_create_vocabulary(vocabulary, journal, user):
    if vocabulary:
        v = extract_value(vocabulary)
        obj = Vocabulary.get_or_create(name=None, acronym=v, user=user)
        journal.vocabulary = obj


def create_or_update_standard(standard, journal, user):
    if standard:
        standard = extract_value(standard)
        obj = Standard.create_or_update(
            code=standard,
            user=user,
        )
        journal.standard = obj


def create_or_update_wos_db(journal, wos_scie, wos_ssci, wos_ahci, user):
    """
    wos_scie, wos_ssci, wos_ahci:
        [{'_': 'SCIE'}]  # Exemplo para wos_scie
        [{'_': 'SSCI'}]  # Exemplo para wos_ssci
        [{'_': 'A&HCI'}]  # Exemplo para wos_ahci
    """
    data = []
    # Haverá um único valor entre os três (wos_scie, wos_ssci, wos_ahci)
    for db in (wos_scie, wos_ssci, wos_ahci):
        wosdb = extract_value(db)
        if wosdb:
            obj = WebOfKnowledge.create_or_update(
                code=wosdb,
                user=user,
            )
            data.append(obj)
    journal.wos_db.set(data)


def get_or_update_wos_areas(journal, wos_areas, user):
    """
    wos_areas:
        [{'_': 'EDUCATION & EDUCATIONAL RESEARCH'}, {'_': 'HISTORY'}, {'_': 'PHILOSOPHY'}, {'_': 'POLITICAL SCIENCE'}, {'_': 'SOCIOLOGY'}]
        [{'_': 'LANGUAGE & LINGUISTICS'}, {'_': 'LITERATURE, GERMAN, DUTCH, SCANDINAVIAN'}]
    """

    data = []
    if wos_areas:
        areas = extract_value(wos_areas)
        if isinstance(areas, str):
            areas = [areas]
        for a in areas:
            obj, created = WebOfKnowledgeSubjectCategory.objects.get_or_create(
                value=a,
                creator=user,
            )
            data.append(obj)
        journal.wos_area.set(data)


def get_or_create_indexed_at(journal, indexed_at, user):
    """
    indexed_at:
        [{'_': 'Index to Dental Literature'}, {'_': 'LILACS'}, {'_': 'Base de Dados BBO'}, {'_': "Ulrich's"}, {'_': 'Biological Abstracts'}, {'_': 'Medline'}]
    """
    data = []
    if indexed_at:
        indexed = extract_value(indexed_at)
        if isinstance(indexed, str):
            indexed = [indexed]
        for i in indexed:
            obj = IndexedAt.objects.filter(
                Q(name__icontains=i) | Q(acronym__icontains=i)
            ).first()
            if not obj:
                obj = IndexedAt.create_or_update(
                    name=i,
                    user=user,
                )
            data.append(obj)
        journal.indexed_at.set(data)


def create_or_update_location(
    address,
    publisher_country,
    publisher_state,
    publisher_city,
    user,
):
    """
    Exemplo de entradas de publisher_country, publisher_state:
    publisher_state:
        [{'_': 'Distrito Capital'}], [{'_': 'DF'}] e None
    publisher_country:
        [{'_': 'CO'}], [{'_': 'Colombia}] e None
    address:
        [{'_': 'Rua Felizardo, 750 Jardim Botânico'}, {'_': 'CEP: 90690-200'}, {'_': 'RS - Porto Alegre'}, {'_': '(51) 3308 5814'}]
    """
    country_value = extract_value(publisher_country)

    if country_value is not None and len(country_value) >= 2:
        country_name = country_value
        country_acronym = None
    else:
        country_name = None
        country_acronym = country_value
    country = Country.get_or_create(
        name=country_name,
        acronym=country_acronym,
        user=user,
    )
    city = City.get_or_create(
        name=extract_value(publisher_city),
        user=user,
    )

    state_value = extract_value(publisher_state)
    if state_value is not None and len(state_value) >= 2:
        state_name = state_value
        state_acronym = None
    else:
        state_name = None
        state_acronym = state_value
    state = State.get_or_create(
        name=state_name,
        acronym=state_acronym,
        user=user,
    )
    
    address = extract_value(address)
    if address:
        if isinstance(address, str):
            address = [address]
        address = '\n'.join(address)
    address = Address.get_or_create(
        name=address,
        user=user,
    )
    location = Location.get_or_create(
        location_region=None,
        location_country=country,
        location_city=city,
        location_state=state,
        location_address=address,
        user=user,
    )
    return location
