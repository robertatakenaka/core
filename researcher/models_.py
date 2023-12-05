import logging
import sys
import os

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.models import Orderable
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.choices import MONTHS
from core.models import CommonControlField, Gender
from core.forms import CoreAdminModelForm
from core.utils.standardizer import remove_extra_spaces
from institution.models import Institution, BaseHistoryItem
from journal.models import Journal
from researcher.controller import replace_researcher_relationships
from tracker.models import UnexpectedEvent

from . import choices
from .forms import ResearcherForm


class PersonName(CommonControlField):
    """
    Class that represent the PersonName
    """

    declared_name = models.CharField(
        _("Declared Name"), max_length=256, blank=True, null=True
    )
    given_names = models.CharField(
        _("Given names"), max_length=128, blank=True, null=True
    )
    last_name = models.CharField(_("Last name"), max_length=128, blank=True, null=True)
    suffix = models.CharField(_("Suffix"), max_length=64, blank=True, null=True)
    prefix = models.CharField(_("Prefix"), max_length=64, blank=True, null=True)
    fullname = models.TextField(null=True, blank=True)
    panels = [
        FieldPanel("prefix"),
        FieldPanel("given_names"),
        FieldPanel("last_name"),
        FieldPanel("suffix"),
        FieldPanel("fullname"),
        FieldPanel("declared_name"),
    ]
    base_form_class = CoreAdminModelForm

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "fullname",
                ]
            ),
        ]

    def __unicode__(self):
        return self.get_full_name

    def __str__(self):
        return self.get_full_name

    @staticmethod
    def autocomplete_custom_queryset_filter(search_term):
        return PersonName.objects.filter(
            Q(last_name__icontains=search_term)
            | Q(declared_name__icontains=search_term)
            | Q(given_names__icontains=search_term)
        )

    def autocomplete_label(self):
        return (
            self.declared_name or f"{self.given_names} {self.last_name} {self.suffix}"
        )

    @property
    def get_full_name(self):
        # usado no search_index
        if self.suffix and self.last_name:
            return f"{self.last_name} {self.suffix}, {self.given_names}"
        if self.last_name:
            return f"{self.last_name}, {self.given_names}"
        return self.declared_name

    @classmethod
    def join_names(cls, given_names, last_name, suffix):
        return " ".join(
            [
                remove_extra_spaces(item)
                for item in (given_names, last_name, suffix)
                if item
            ]
        )

    @classmethod
    def split_names(cls, declared_name):
        """
        Separar as partes do nome se declared_name está nos formatos:
        last_name, given_names ou last_name, given_names, suffix
        Caso contrário, levanta exceção
        """
        declared_name = remove_extra_spaces(declared_name)
        if declared_name:
            if "," in declared_name:
                names = declared_name.split(",")
                if len(names) in (2, 3):
                    names = (
                        [None] + [remove_extra_spaces(name) for name in names] + [None]
                    )
                    if len(names) > 2:
                        return names[:3]
            else:
                names = declared_name.split()
                last_name = names[-1]
                suffix = None
                prefixes = []
                for name_ in names[:2]:
                    for pref in (
                        "Dr.",
                        "Dra.",
                        "Doctor",
                        "Doutor",
                        "Prof",
                        "Mest",
                        "Post",
                        "PhD",
                    ):
                        if name_.title().startswith(pref):
                            prefixes.append(name_)
                prefix = " ".join(prefixes)
                if prefixes:
                    names = names[len(prefixes) :]
                if last_name.title() in (
                    "Júnior",
                    "Jr",
                    "Jr.",
                    "Junior",
                    "Neto",
                    "Nieto",
                    "Filho",
                ):
                    suffix = last_name
                    last_name = names[-2]
                    given_names = " ".join(names[:-2])
                else:
                    given_names = " ".join(names[:-1])
                return prefix, last_name, given_names, suffix

        raise ValueError(
            f"PersonName.split_names: {declared_name} is unable to split in last name, given names, suffix"
        )

    @classmethod
    def get(
        cls,
        given_names,
        last_name,
        suffix,
        declared_name,
    ):
        (
            last_name,
            given_names,
            suffix,
            declared_name,
            prefix,
            fullname,
        ) = cls.standardize(given_names, last_name, suffix, declared_name)
        if declared_name or last_name:
            return cls.objects.get(
                fullname__iexact=fullname,
                last_name__iexact=last_name,
                given_names__iexact=given_names,
                suffix__iexact=suffix,
            )
        raise ValueError(
            "PersonName.get requires given_names and last_names or declared_name parameters"
        )

    @classmethod
    def standardize(cls, given_names, last_name, suffix, declared_name):
        """
        Remove espaços extras iniciais e finais
        Garante que o conteúdo de declared_name seja o nome completo
        Obtém last_name, given_names, suffix de declared_name, se não fornecidos
        """
        given_names = remove_extra_spaces(given_names)
        last_name = remove_extra_spaces(last_name)
        suffix = remove_extra_spaces(suffix)
        declared_name = remove_extra_spaces(declared_name)

        try:
            prefix, last_name, given_names, suffix = cls.split_names(declared_name)
        except ValueError:
            prefix = None

        if last_name and given_names:
            fullname = cls.join_names(given_names, last_name, suffix)

        return given_names, last_name, suffix, declared_name, prefix, fullname

    @classmethod
    def create_or_update(
        cls,
        user,
        given_names,
        last_name,
        suffix,
        declared_name,
    ):

        (
            given_names,
            last_name,
            suffix,
            declared_name,
            prefix,
            fullname,
        ) = cls.standardize(given_names, last_name, suffix, declared_name)
        try:
            obj = cls.get(given_names, last_name, suffix, declared_name)
            obj.updated_by = user or obj.updated_by
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user

        obj.declared_name = declared_name or obj.declared_name
        obj.given_names = given_names or obj.given_names
        obj.last_name = last_name or obj.last_name
        obj.suffix = suffix or obj.suffix

        obj.prefix = prefix or obj.prefix
        obj.fullname = fullname or obj.fullname

        obj.save()
        return obj


class UnidentifiedResearcher(CommonControlField):
    person_name = models.ForeignKey(
        PersonName, on_delete=models.SET_NULL, blank=True, null=True
    )
    year = models.CharField(_("Year"), max_length=4, null=True, blank=True)
    affiliation = models.ForeignKey(
        "Affiliation", on_delete=models.SET_NULL, null=True, blank=True
    )

    panels = [
        AutocompletePanel("person_name"),
        FieldPanel("year"),
        AutocompletePanel("affiliation"),
    ]

    base_form_class = CoreAdminModelForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return UnidentifiedResearcher.objects.filter(
            Q(person_name__declared_name__icontains=any_value)
            | Q(year__icontains=any_value)
            | Q(affiliation__institution_identification__name__icontains=any_value)
            | Q(affiliation__institution_identification__acronym__icontains=any_value)
        )

    def autocomplete_label(self):
        return f"{self.researcher_id}"

    def __str__(self):
        return f"{self.person_name} {self.year} {self.affiliation}"

    @classmethod
    def get(
        cls,
        person_name,
        affiliation,
        year,
    ):
        if person_name:
            year = remove_extra_spaces(year)
            return cls.objects.get(
                person_name=person_name,
                affiliation=affiliation,
                year=year,
            )
        raise ValueError("UnidentifiedResearcher.get requires person_name")

    @classmethod
    def get_or_create(
        cls,
        user,
        person_name,
        affiliation,
        year,
    ):
        year = remove_extra_spaces(year)
        try:
            obj = cls.get(person_name, affiliation, year)
        except cls.DoesNotExist:
            obj = cls()
            obj.person_name = person_name
            obj.affiliation = affiliation
            obj.year = year
            obj.save()
        return obj


class ResearcherId(CommonControlField):
    """
    Class that represent the Researcher with any id
    """

    researcher_id = models.CharField(_("ID"), max_length=256, blank=True, null=True)
    source_name = models.CharField(
        _("Source name"), max_length=256, blank=True, null=True
    )

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return ResearcherId.objects.filter(researcher_id__icontains=any_value)

    def autocomplete_label(self):
        return f"{self.researcher_id}"

    panels = [FieldPanel("researcher_id"), FieldPanel("source_name")]

    base_form_class = ResearcherForm

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "researcher_id",
                ]
            ),
        ]

    @classmethod
    def get(
        cls,
        researcher_id,
        source_name,
    ):
        if source_name and researcher_id:
            return cls.objects.get(
                source_name=source_name,
                researcher_id=researcher_id,
            )
        raise ValueError(
            "IdentifiedResearcher.get requires source_name and researcher_id"
        )

    @classmethod
    def get_or_create(
        cls,
        user,
        researcher_id,
        source_name,
    ):
        try:
            obj = cls.get(researcher_id, source_name)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.researcher_id = researcher_id
            obj.source_name = source_name
            obj.save()
        return obj


class Researcher(CommonControlField, ClusterableModel):
    """
    Class that represent the Researcher
    """

    orcid = models.CharField(_("ORCID"), max_length=32, blank=True, null=True)
    lattes = models.CharField(_("Lattes"), max_length=32, blank=True, null=True)
    other_ids = models.ManyToManyField(ResearcherId)

    gender = models.ForeignKey(Gender, blank=True, null=True, on_delete=models.SET_NULL)
    gender_identification_status = models.CharField(
        _("Gender identification status"),
        max_length=16,
        choices=choices.GENDER_IDENTIFICATION_STATUS,
        null=True,
        blank=True,
    )
    name_aff_year = models.ManyToManyField(UnidentifiedResearcher)
    main_person_name = models.ForeignKey(
        PersonName, blank=True, null=True, on_delete=models.SET_NULL
    )
    to_delete = models.BooleanField(default=False)

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return Researcher.objects.filter(
            Q(orcid__icontains=any_value)
            | Q(main_person_name__declared_name__icontains=any_value)
        )

    def autocomplete_label(self):
        return f"{self.orcid} {self.main_person_name and self.main_person_name.declared_name}"

    panels = [
        FieldPanel("orcid"),
        FieldPanel("lattes"),
        # AutocompletePanel("other_ids"),
        InlinePanel("researcher_email", label=_("Email")),
        FieldPanel("gender"),
        FieldPanel("gender_identification_status"),
        AutocompletePanel("name_aff_year"),
    ]

    base_form_class = ResearcherForm

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "lattes",
                ]
            ),
            models.Index(
                fields=[
                    "orcid",
                ]
            ),
        ]

    @property
    def get_full_name(self):
        if self.main_person_name:
            return self.main_person_name.get_full_name
        return ""

    def __unicode__(self):
        return self.get_full_name

    def __str__(self):
        return self.get_full_name

    @classmethod
    def get(
        cls,
        name_aff_year,
        orcid=None,
        lattes=None,
    ):
        orcid = orcid and orcid.split("/")[-1]
        lattes = lattes and lattes.split("/")[-1]

        q = None
        if orcid:
            if q is None:
                q = Q(orcid=orcid)
            else:
                q |= Q(orcid=orcid)

        if lattes:
            if q is None:
                q = Q(lattes=lattes)
            else:
                q |= Q(lattes=lattes)

        if name_aff_year:
            if q is None:
                q = Q(name_aff_year=name_aff_year)
            else:
                q |= Q(name_aff_year=name_aff_year)

        if q:
            try:
                return cls.objects.get(q, to_delete=False)
            except cls.MultipleObjectsReturned:
                return cls.objects.get(q)

        raise ValueError("Researcher.get requires name_aff_year")

    @classmethod
    def migrate_items(cls, origin, destination):
        orcid_ = None
        lattes_ = None
        other = None
        for item in cls.objects.filter(q).iterator():
            if item.orcid:
                orcid_ = item
            if item.lattes:
                lattes_ = item
            if not item.lattes and not item.orcid:
                other = item
        if other and orcid_:
            cls.migrate_item(other, orcid_)
        if lattes_ and orcid_:
            cls.migrate_item(lattes_, orcid_)
        if not orcid_ and other and lattes_:
            cls.migrate_item(other, lattes_)

    @classmethod
    def migrate_item(cls, origin, destination):
        if destination and origin:
            destination.orcid = origin.orcid or destination.orcid
            destination.lattes = origin.lattes or destination.lattes
            destination.gender = origin.gender or destination.gender
            destination.gender_identification_status = (
                origin.gender_identification_status
                or destination.gender_identification_status
            )
            destination.save()
            for name_aff_year in origin.name_aff_year.iterator():
                destination.name_aff_year.add(name_aff_year)
            destination.save()
            replace_researcher_relationships(origin, destination)

    @classmethod
    def create_or_update(
        cls,
        user,
        given_names=None,
        last_name=None,
        suffix=None,
        declared_name=None,
        affiliation=None,
        year=None,
        orcid=None,
        lattes=None,
        other_ids=None,
        gender=None,
        gender_identification_status=None,
    ):
        orcid = orcid and orcid.split("/")[-1]
        lattes = lattes and lattes.split("/")[-1]

        person_name = models.PersonName.create_or_update(
            user,
            given_names=given_names,
            last_name=surname,
            suffix=suffix,
            declared_name=declared_name,
        )

        name_aff_year = UnidentifiedResearcher.get_or_create(
            user=user,
            person_name=person_name,
            affiliation=affiliation,
            year=year,
        )
        try:
            obj = cls.get(name_aff_year, orcid, lattes)
            obj.updated_by = user
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user

        obj.gender = gender or obj.gender
        obj.gender_identification_status = (
            gender_identification_status or obj.gender_identification_status
        )
        obj.orcid = orcid or obj.orcid
        obj.lattes = lattes or obj.lattes
        obj.other_ids = other_ids or obj.other_ids
        obj.save()

        obj.name_aff_year.add(name_aff_year)
        obj.set_main_person_name()
        return obj

    def add_emails(self, user, emails):
        # Cria relacionamentos de Researcher com ResearcherEmail
        ResearcherEmail.create_or_update(user, researcher=self, email=email)

    def set_main_person_name(self):
        records = list(self.name_aff_year.iterator())
        items = []
        for i, item in enumerated(records):
            k = (
                len(item.declared_name),
                len(item.suffix),
                len(item.given_names),
                len(item.last_name),
            )
            items.append((k, i))
        index = sorted(items)[-1][1]
        self.main_person_name = records[index]
        self.save()


class ResearcherEmail(Orderable):
    researcher = ParentalKey(
        Researcher,
        on_delete=models.SET_NULL,
        related_name="researcher_email",
        blank=True,
        null=True,
    )
    email = models.EmailField(_("Email"), max_length=128, blank=True, null=True)

    @classmethod
    def create_or_update(cls, user, researcher, email):
        emails = email and email.replace(",").replace(";").replace(" ").split(" ")
        emails = [email for email in emails if email]
        for email in emails:
            try:
                obj = cls.objects.get(researcher=researcher, email=email)
                obj.updated_by = user
            except cls.DoesNotExist:
                obj = cls()
                obj.researcher = researcher
                obj.creator = user
            obj.email = email
            obj.save()
        return obj

    @classmethod
    def get_researcher(
        cls,
        email,
        person_name,
    ):
        if email and person_name:
            obj = cls.objects.get(
                email,
                researcher__person_name=person_name,
            )
            return obj.researcher
        raise ValueError("Researcher.get_by_email requires email and person_name")


class Affiliation(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm
