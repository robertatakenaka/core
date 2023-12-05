import logging
import sys
import os

from django.db import models, IntegrityError
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


PREFIXES = (
    "Dr.",
    "Dra.",
    "Doctor",
    "Doutor",
    "Prof",
    "Mest",
    "Post",
    "PhD",
)
SUFFIXES = (
    "Júnior",
    "Jr",
    "Jr.",
    "Junior",
    "Neto",
    "Nieto",
    "Filho",
    "Sr.",
    "Sr",
)


class PersonName(CommonControlField):
    """
    Class that represent the PersonName
    """

    declared_name = models.TextField(
        _("Declared Name"), max_length=256, blank=True, null=True
    )
    given_names = models.CharField(
        _("Given names"), max_length=128, blank=True, null=True
    )
    last_name = models.CharField(_("Last name"), max_length=64, blank=True, null=True)
    suffix = models.CharField(_("Suffix"), max_length=64, blank=True, null=True)
    prefix = models.CharField(_("Prefix"), max_length=64, blank=True, null=True)
    fullname = models.TextField(_("Full Name"), max_length=256, blank=True, null=True)

    gender = models.ForeignKey(Gender, blank=True, null=True, on_delete=models.SET_NULL)
    gender_identification_status = models.CharField(
        _("Gender identification status"),
        max_length=16,
        choices=choices.GENDER_IDENTIFICATION_STATUS,
        null=True,
        blank=True,
    )

    panels = [
        FieldPanel("prefix"),
        FieldPanel("given_names"),
        FieldPanel("last_name"),
        FieldPanel("suffix"),
        FieldPanel("fullname"),
        FieldPanel("declared_name"),
        FieldPanel("gender"),
        FieldPanel("gender_identification_status"),
    ]
    base_form_class = CoreAdminModelForm

    class Meta:
        unique_together = [
            ("declared_name", "gender"),
            ("fullname", "last_name", "given_names", "suffix", "gender"),
        ]

        indexes = [
            models.Index(
                fields=[
                    "fullname",
                ]
            ),
            models.Index(
                fields=[
                    "last_name",
                ]
            ),
            models.Index(
                fields=[
                    "declared_name",
                ]
            ),
        ]

    def __str__(self):
        if self.fullname:
            return self.fullname
        if self.last_name and self.given_names:
            return f"{self.given_names} {self.last_name} {self.suffix}"
        if self.declared_name:
            return self.declared_name

    @staticmethod
    def autocomplete_custom_queryset_filter(search_term):
        return PersonName.objects.filter(
            Q(last_name__icontains=search_term)
            | Q(fullname__icontains=search_term)
            | Q(given_names__icontains=search_term)
        )

    def autocomplete_label(self):
        if self.fullname:
            return self.fullname
        if self.last_name and self.given_names:
            return f"{self.given_names} {self.last_name} {self.suffix}"
        if self.declared_name:
            return self.declared_name

    @property
    def get_full_name(self):
        # usado no search_index
        if self.suffix and self.last_name:
            return f"{self.last_name} {self.suffix}, {self.given_names}"
        if self.last_name:
            return f"{self.last_name}, {self.given_names}"
        return self.declared_name

    @staticmethod
    def join_names(given_names, last_name, suffix):
        return " ".join(
            [
                remove_extra_spaces(item)
                for item in (given_names, last_name, suffix)
                if remove_extra_spaces(item)
            ]
        )

    @staticmethod
    def split_names(declared_name):
        """
        Separar as partes do nome se declared_name está nos formatos:
        last_name, given_names ou last_name, given_names, suffix
        Caso contrário, levanta exceção
        """
        declared_name = remove_extra_spaces(declared_name)
        if not declared_name:
            return {}

        parts = {}
        if declared_name.count(",") == 1:
            names = declared_name.split(",")
            if names[0].count(" ") in (0, 1):
                parts["last_name"] = names[0]
                parts["given_names"] = names[-1].strip()
                return parts
        if "," in declared_name:
            # nao foi possível identificar partes do nome
            return {}

        names = declared_name.split()

        if names[-1].title() in SUFFIXES:
            parts["suffix"] = names[-1]
            names = names[:-1]

        prefixes = []
        for name_ in names[:2]:
            for pref in PREFIXES:
                if name_.title().startswith(pref):
                    prefixes.append(name_)
        if prefixes:
            parts["prefix"] = " ".join(prefixes)
            names = names[len(prefixes) :]

        parts["last_name"] = names[-1]
        parts["given_names"] = " ".join(names[:-1])
        return parts

    @staticmethod
    def standardize(given_names, last_name, suffix, declared_name):
        """
        Remove espaços extras iniciais e finais
        Garante que o conteúdo de declared_name seja o nome completo
        Obtém last_name, given_names, suffix de declared_name, se não fornecidos
        """
        prefix = None
        given_names = remove_extra_spaces(given_names)
        last_name = remove_extra_spaces(last_name)
        suffix = remove_extra_spaces(suffix)
        declared_name = remove_extra_spaces(declared_name)
        fullname = None

        parts = PersonName.split_names(declared_name)
        prefix = prefix or parts.get("prefix")
        given_names = given_names or parts.get("given_names")
        last_name = last_name or parts.get("last_name")
        suffix = suffix or parts.get("suffix")

        if last_name and given_names:
            fullname = PersonName.join_names(given_names, last_name, suffix)

        return dict(
            given_names=given_names,
            last_name=last_name,
            suffix=suffix,
            declared_name=declared_name,
            prefix=prefix,
            fullname=fullname,
        )

    @classmethod
    def _get(
        cls,
        given_names,
        last_name,
        suffix,
        declared_name,
        gender,
    ):
        if declared_name or last_name:
            try:
                return cls.objects.get(
                    declared_name__iexact=declared_name,
                    last_name__iexact=last_name,
                    given_names__iexact=given_names,
                    suffix__iexact=suffix,
                    gender=gender,
                )
            except cls.MultipleObjectsReturned:
                # TODO remover os duplicados
                return cls.objects.filter(
                    declared_name__iexact=declared_name,
                    last_name__iexact=last_name,
                    given_names__iexact=given_names,
                    suffix__iexact=suffix,
                    gender=gender,
                ).first()
        raise ValueError(
            "PersonName.get requires given_names and last_names or declared_name parameters"
        )

    def _save(
        self,
        user,
        given_names,
        last_name,
        suffix,
        declared_name,
        gender,
        gender_identification_status,
        prefix,
        fullname,
    ):
        if self.creator:
            self.updated_by = user
        else:
            self.creator = user
        self.given_names = given_names or self.given_names
        self.last_name = last_name or self.last_name
        self.suffix = suffix or self.suffix
        self.prefix = prefix or self.prefix
        self.fullname = fullname or self.fullname
        self.declared_name = declared_name or self.declared_name
        self.gender = gender or self.gender
        self.gender_identification_status = (
            gender_identification_status or self.gender_identification_status
        )
        self.save()

    @classmethod
    def create_or_update(
        cls,
        user,
        given_names,
        last_name,
        suffix,
        declared_name,
        gender,
        gender_identification_status,
    ):
        std = PersonName.standardize(given_names, last_name, suffix, declared_name)
        given_names = std.get("given_names")
        last_name = std.get("last_name")
        suffix = std.get("suffix")
        declared_name = std.get("declared_name")
        prefix = std.get("prefix")
        fullname = std.get("fullname")
        gender = std.get("gender")
        gender_identification_status = std.get("gender_identification_status")
        if prefix == "Dra.":
            gender = Gender.get_or_create(user, code="F")
            gender_identification_status = "AUTOMATIC"
        elif suffix:
            gender = Gender.get_or_create(user, code="M")
            gender_identification_status = "AUTOMATIC"
        else:
            gender = None
            gender_identification_status = None

        try:
            obj = cls._get(given_names, last_name, suffix, declared_name, gender)
        except cls.DoesNotExist:
            obj = cls()
        try:
            obj._save(
                user,
                given_names,
                last_name,
                suffix,
                declared_name,
                gender,
                gender_identification_status,
                prefix,
                fullname,
            )
            return obj
        except IntegrityError:
            return cls._get(given_names, last_name, suffix, declared_name, gender)


class ResearcherIdentifier(CommonControlField, ClusterableModel):
    """
    Class that represent the Researcher with any id
    """

    identifier = models.CharField(_("ID"), max_length=64, blank=True, null=True)
    source_name = models.CharField(
        _("Source name"), max_length=64, blank=True, null=True
    )

    panels = [
        FieldPanel("identifier"),
        FieldPanel("source_name"),
        InlinePanel("researcher_also_known_as"),
    ]

    base_form_class = ResearcherForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return ResearcherIdentifier.objects.filter(identifier__icontains=any_value)

    def autocomplete_label(self):
        return f"{self.identifier} {self.source_name}"

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "identifier",
                ]
            ),
            models.Index(
                fields=[
                    "source_name",
                ]
            ),
        ]

    @classmethod
    def get(
        cls,
        identifier,
        source_name,
    ):
        if source_name and identifier:
            return cls.objects.get(
                source_name=source_name,
                identifier=identifier,
            )
        raise ValueError("ResearcherIdentifier.get requires source_name and identifier")

    @classmethod
    def get_or_create(
        cls,
        user,
        identifier,
        source_name,
    ):
        try:
            obj = cls.get(identifier, source_name)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.identifier = identifier
            obj.source_name = source_name
            obj.save()
        return obj


class ResearcherAKA(Orderable):
    researcher_identifier = ParentalKey(
        ResearcherIdentifier,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="researcher_also_known_as",
    )
    researcher = models.ForeignKey(
        "Researcher", blank=True, null=True, on_delete=models.SET_NULL
    )

    base_form_class = ResearcherForm

    panels = [
        AutocompletePanel("researcher"),
    ]

    @classmethod
    def get(
        cls,
        researcher_identifier,
        researcher,
    ):
        if researcher and researcher_identifier:
            return cls.objects.get(
                researcher=researcher,
                researcher_identifier=researcher_identifier,
            )
        raise ValueError(
            "ResearcherIdentifier.get requires researcher and researcher_identifier"
        )

    @classmethod
    def get_or_create(
        cls,
        user,
        researcher_identifier,
        researcher,
    ):
        try:
            obj = cls.get(researcher_identifier, researcher)
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.researcher_identifier = researcher_identifier
            obj.researcher = researcher
            obj.save()
        return obj


class Researcher(CommonControlField, ClusterableModel):
    """
    Class that represent the Researcher
    """

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
        return ResearcherBase.objects.filter(
            Q(person_name__fullname__icontains=any_value)
            | Q(year__icontains=any_value)
            | Q(affiliation__institution_identification__name__icontains=any_value)
            | Q(affiliation__institution_identification__acronym__icontains=any_value)
        )

    def autocomplete_label(self):
        return f"{self}"

    def __str__(self):
        return f"{self.person_name} {self.year} {self.affiliation}"

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
            obj = cls.objects.get(
                person_name=person_name, affiliation=affiliation, year=year
            )
        except cls.DoesNotExist:
            obj = cls()
            obj.person_name = person_name
            obj.affiliation = affiliation
            obj.year = year
            obj.save()
        return obj

    @property
    def get_full_name(self):
        if self.person_name:
            return self.person_name.get_full_name
        return ""

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
        email=None,
        gender=None,
        gender_identification_status=None,
    ):
        person_name = PersonName.create_or_update(
            user,
            given_names=given_names,
            last_name=last_name,
            suffix=suffix,
            declared_name=declared_name,
            gender=gender,
            gender_identification_status=gender_identification_status,
        )

        researcher = cls.get_or_create(
            user=user,
            person_name=person_name,
            affiliation=affiliation,
            year=year,
        )

        try:
            ids = []
            if orcid:
                orcid = orcid.split("/")[-1]
                ids.append({"identifier": orcid, "source_name": "ORCID"})
            if lattes:
                lattes = lattes.split("/")[-1]
                ids.append({"identifier": lattes, "source_name": "LATTES"})
            if email:
                for email_ in email.replace(",", ";").split(";"):
                    ids.append({"identifier": email_, "source_name": "EMAIL"})

            for id_ in ids:
                # {"identifier": email_, "source_name": "EMAIL"}
                ResearcherAKA.get_or_create(
                    user=user,
                    researcher_identifier=ResearcherIdentifier.get_or_create(
                        user, **id_
                    ),
                    researcher=researcher,
                )

            if other_ids:
                for id_ in other_ids:
                    # id_ do tipo ResearcherIdentifier
                    ResearcherAKA.get_or_create(
                        user=user,
                        researcher_identifier=id_,
                        researcher=researcher,
                    )
        except Exception as e:
            logging.exception(
                f"Unable to register researcher with ID {person_name} {affiliation} {year} {e}"
            )

        return researcher


class Affiliation(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm
