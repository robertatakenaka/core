import csv
import logging
import os

from django.db import models, IntegrityError
from django.db.models import Q
from django.utils.translation import gettext as _
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.forms import CoreAdminModelForm
from core.models import CommonControlField
from core.utils.standardizer import standardize_acronym_and_name, remove_extra_spaces
from location.models import Country, Location, State

from . import choices
from .forms import ScimagoForm


class Institution(CommonControlField):
    institution_identification = models.ForeignKey(
        "InstitutionIdentification", null=True, blank=True, on_delete=models.SET_NULL
    )
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL
    )
    level_1 = models.TextField(_("Organization Level 1"), null=True, blank=True)
    level_2 = models.TextField(_("Organization Level 2"), null=True, blank=True)
    level_3 = models.TextField(_("Organization Level 3"), null=True, blank=True)
    url = models.URLField("url", blank=True, null=True)

    logo = models.ImageField(_("Logo"), blank=True, null=True)

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return Institution.objects.filter(
            Q(institution_identification__name__icontains=any_value)
            | Q(institution_identification__acronym__icontains=any_value)
        )

    def autocomplete_label(self):
        return f"{self.institution_identification}"

    base_form_class = CoreAdminModelForm
    panels = [
        AutocompletePanel("institution_identification"),
        AutocompletePanel("location"),
        FieldPanel("level_1"),
        FieldPanel("level_2"),
        FieldPanel("level_3"),
        FieldPanel("url"),
        FieldPanel("logo"),
    ]

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "url",
                ]
            ),
        ]

    def __unicode__(self):
        return str(self.institution_identification)

    def __str__(self):
        return str(self.institution_identification)

    @classmethod
    def get(
        cls,
        institution_identification,
        level_1,
        level_2,
        level_3,
        location,
    ):
        if institution_identification:
            try:
                return cls.objects.get(
                    institution_identification=institution_identification,
                    location=location,
                    level_1=level_1,
                    level_2=level_2,
                    level_3=level_3,
                )
            except cls.MultipleObjectsReturned as e:
                data = (
                    name,
                    acronym,
                    level_1,
                    level_2,
                    level_3,
                    location,
                )
                raise cls.MultipleObjectsReturned(f"{e} {str(data)}")
        raise ValueError("Institution.get requires institution_identification")

    @classmethod
    def create_or_update(
        cls,
        user,
        name,
        acronym,
        level_1,
        level_2,
        level_3,
        location,
        url,
        declared_name=None,
    ):
        name = remove_extra_spaces(name)
        acronym = remove_extra_spaces(acronym)

        if declared_name and not name and not acronym:
            for item in cls.create_or_update_with_declared_name(
                user,
                declared_name,
                level_1,
                level_2,
                level_3,
                locations=location and [location],
                url=url,
            ):
                return item

        institution_identification = (
            InstitutionIdentification.create_or_update(
                user,
                name=name,
                acronym=acronym,
                is_official=None,
                official=None,
                institution_type=None,
            )
        )

        try:
            institution = cls.get(
                institution_identification=institution_identification,
                location=location,
                level_1=level_1,
                level_2=level_2,
                level_3=level_3,
            )
            institution.updated_by = user
        except cls.DoesNotExist:
            institution = cls()
            institution.creator = user

        institution.institution_identification = (
            institution_identification or institution.institution_identification
        )
        institution.level_1 = level_1 or institution.level_1
        institution.level_2 = level_2 or institution.level_2
        institution.level_3 = level_3 or institution.level_3
        institution.location = location or institution.location
        institution.url = url or institution.url
        institution.save()
        return institution

    @classmethod
    def create_or_update_with_declared_name(
        cls,
        user,
        declared_name,
        level_1,
        level_2,
        level_3,
        locations,
        url,
    ):
        q_locations = locations and len(locations)
        items = standardize_acronym_and_name(
            declared_name,
            possible_multiple_return=bool(q_locations and q_locations > 1),
            q_locations=q_locations
        )
        for data, location in zip(items, locations or [None]):
            name = data.get("name")
            acronym = data.get("acronym")

            Decl2Std.get_or_create(
                user, declared_name, None, name, acronym,
            )
            yield cls.create_or_update(
                user,
                name,
                acronym,
                level_1=level_1 or data.get("level_1"),
                level_2=level_2 or data.get("level_2"),
                level_3=level_3 or data.get("level_3"),
                location=location,
                url=url,
            )

    @classmethod
    def load(cls, user, file_path=None, column_labels=None, is_official=False):
        """
        Name;Acronym;State Acronym;Institution Type;Level_1;Level_2;Level_3

        "name": "Name",
        "acronym": "Acronym",
        "state": "State Acronym",
        "type": "Institution Type",
        "level_1": "Level_1",
        "level_2": "Level_2",
        "level_3": "Level_3",
        """
        file_path = file_path or "./institution/fixtures/institutions_mec_2.csv"
        if file_path == "./institution/fixtures/institutions_mec_2.csv":
            is_official = True
        column_labels = column_labels or {
            "name": "Name",
            "acronym": "Acronym",
            "state": "State Acronym",
            "type": "Institution Type",
            "level_1": "Level_1",
            "level_2": "Level_2",
            "level_3": "Level_3",
        }

        with open(file_path, "r") as csvfile:
            rows = csv.DictReader(
                csvfile, delimiter=";", fieldnames=list(column_labels.values())
            )
            country = Country.objects.get(acronym="BR")
            for line, row in enumerate(rows):
                logging.info(row)
                name = row.get(column_labels["name"])
                acronym = row.get(column_labels["acronym"])

                if name == column_labels["name"]:
                    continue

                try:
                    state_acronym = row.get(column_labels["state"])
                    state = State.objects.get(acronym=state_acronym)
                except State.DoesNotExist:
                    continue

                location = Location.create_or_update(
                    user=user, country=country, state=state, city=None,
                )
                identification = InstitutionIdentification.create_or_update(
                    user=user,
                    name=name,
                    acronym=acronym,
                    is_official=is_official,
                    official=None,
                    institution_type=row.get(column_labels["type"]),
                )
                cls.create_or_update(
                    user,
                    name=name,
                    acronym=acronym,
                    level_1=None,
                    level_2=None,
                    level_3=None,
                    location=location,
                    url=None,
                )


class InstitutionHistory(models.Model):
    institution = models.ForeignKey(
        "Institution", null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )
    initial_date = models.DateField(_("Initial Date"), null=True, blank=True)
    final_date = models.DateField(_("Final Date"), null=True, blank=True)

    panels = [
        AutocompletePanel("institution", heading=_("Institution")),
        FieldPanel("initial_date"),
        FieldPanel("final_date"),
    ]

    @classmethod
    def get_or_create(cls, institution, initial_date, final_date):
        histories = cls.objects.filter(
            institution=institution, initial_date=initial_date, final_date=final_date
        )
        try:
            history = histories[0]
        except:
            history = cls()
            history.institution = institution
            history.initial_date = initial_date
            history.final_date = final_date
            history.save()
        return history


class BaseHistoryItem(CommonControlField):
    initial_date = models.DateField(_("Initial Date"), null=True, blank=True)
    final_date = models.DateField(_("Final Date"), null=True, blank=True)

    panels = [
        AutocompletePanel("institution"),
        FieldPanel("initial_date"),
        FieldPanel("final_date"),
    ]

    def __str__(self):
        return f"{self.institution} {self.initial_date}-{self.final_date}"

    def autocomplete_label(self):
        return f"{self.initial_date}-{self.final_date} {self.institution}"

    @classmethod
    def get(
        cls,
        institution,
        initial_date,
        final_date,
    ):
        if not institution:
            raise ValueError(
                "Requires institution and initial_date or final_dateparameters"
            )
        return cls.objects.get(
            institution=institution, initial_date=initial_date, final_date=final_date
        )

    @classmethod
    def get_or_create(cls, institution, initial_date=None, final_date=None, user=None):
        try:
            # consultar juntos por institution + initial_date + final_date
            # mesmo que initial_date ou final_date sejam None
            # caso contrário o retorno pode ser MultipleObjectReturned
            return cls.get(
                institution=institution,
                initial_date=initial_date,
                final_date=final_date,
            )
            history.updated_by = user
        except cls.DoesNotExist:
            history = cls()
            history.institution = institution
            history.creator = user

            history.initial_date = initial_date
            history.final_date = final_date
            history.save()
            return history

    class Meta:
        abstract = True


class Sponsor(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return Sponsor.objects.filter(
            Q(institution_identification__name__icontains=any_value)
            | Q(institution_identification__acronym__icontains=any_value)
        )


class SponsorHistoryItem(BaseHistoryItem):
    institution = models.ForeignKey(
        Sponsor,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    panels = [
        AutocompletePanel("institution"),
        FieldPanel("initial_date"),
        FieldPanel("final_date"),
    ]


class Publisher(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return Publisher.objects.filter(
            Q(institution_identification__name__icontains=any_value)
            | Q(institution_identification__acronym__icontains=any_value)
        )


class PublisherHistoryItem(BaseHistoryItem):
    institution = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )


class CopyrightHolder(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return CopyrightHolder.objects.filter(
            Q(institution_identification__name__icontains=any_value)
            | Q(institution_identification__acronym__icontains=any_value)
        )


class CopyrightHolderHistoryItem(BaseHistoryItem):
    institution = models.ForeignKey(
        CopyrightHolder,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    panels = [
        AutocompletePanel("institution"),
        FieldPanel("initial_date"),
        FieldPanel("final_date"),
    ]


class Owner(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return Owner.objects.filter(
            Q(institution_identification__name__icontains=any_value)
            | Q(institution_identification__acronym__icontains=any_value)
        )


class OwnerHistoryItem(BaseHistoryItem):
    institution = models.ForeignKey(
        Owner,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )


class EditorialManager(Institution):
    panels = Institution.panels

    base_form_class = CoreAdminModelForm


class EditorialManagerHistoryItem(BaseHistoryItem):
    institution = models.ForeignKey(
        EditorialManager,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )


class Scimago(CommonControlField, ClusterableModel):
    institution = models.TextField(_("Institution"), null=True, blank=True)
    country = models.ForeignKey(
        Country, null=True, blank=True, on_delete=models.SET_NULL
    )
    url = models.URLField("url", blank=True, null=True)

    panels = [
        FieldPanel("institution"),
        AutocompletePanel("country", heading=_("Country")),
        FieldPanel("url"),
    ]

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "institution",
                ]
            ),
            models.Index(
                fields=[
                    "url",
                ]
            ),
        ]

    def __unicode__(self):
        return "%s | %s | %s" % (
            self.institution,
            self.country,
            self.url,
        )

    def __str__(self):
        return "%s | %s | %s" % (
            self.institution,
            self.country,
            self.url,
        )

    @classmethod
    def get(cls, institution=None, country_acron3=None):
        if institution and country_acron3:
            return cls.objects.get(
                institution__icontains=institution,
                country__acron3__icontains=country_acron3,
            )
        raise ValueError(
            "Scimago.get requires institution and country acronym (3 char)"
        )

    @classmethod
    def create_or_update(cls, user, institution, country_acron3, url):
        try:
            obj = cls.get(institution=institution, country_acron3=country_acron3)
            obj.updated_by = user
        except (cls.DoesNotExist, ValueError):
            obj = cls(creator=user)

        c = Country()
        c = c.get_or_create(user=user, acron3=country_acron3)

        obj.institution = institution or obj.institution
        obj.country = c or obj.country
        obj.url = url or obj.url
        obj.save()
        return obj

    base_form_class = ScimagoForm


class ScimagoFile(models.Model):
    attachment = models.ForeignKey(
        "wagtaildocs.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_valid = models.BooleanField(_("Is valid?"), default=False, blank=True, null=True)
    line_count = models.IntegerField(
        _("Number of lines"), default=0, blank=True, null=True
    )

    def filename(self):
        return os.path.basename(self.attachment.name)

    panels = [FieldPanel("attachment")]


class InstitutionIdentification(CommonControlField):
    name = models.TextField(_("Name"), null=True, blank=True)
    acronym = models.TextField(_("Institution Acronym"), null=True, blank=True)
    institution_type = models.TextField(
        _("Institution Type"), choices=choices.inst_type, null=True, blank=True
    )
    is_official = models.BooleanField(
        _("Is official"),
        null=True,
        blank=True,
    )
    # official = models.ForeignKey(
    #     "self",
    #     verbose_name=_("Official Institution Name"),
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    # )
    official = models.BooleanField(
        _("FIXME"),
        null=True,
        blank=True,
        default=None,
    )

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return InstitutionIdentification.objects.filter(
            Q(name__icontains=any_value) | Q(acronym__icontains=any_value)
        )

    def autocomplete_label(self):
        official = self.is_official and " [official]" or ""
        if self.acronym and self.name:
            return f"{self.acronym} {self.name}{official}"
        if self.acronym:
            return f"{self.acronym}{official}"
        return f"{self.name}{official}"

    base_form_class = CoreAdminModelForm
    panels = [
        FieldPanel("name"),
        FieldPanel("acronym"),
        FieldPanel("is_official"),
        FieldPanel("institution_type"),
        FieldPanel("official"),
    ]

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "name",
                ]
            ),
            models.Index(
                fields=[
                    "acronym",
                ]
            ),
        ]

    def __str__(self):
        official = self.is_official and " [official]" or ""
        if self.acronym and self.name:
            return f"{self.acronym} {self.name}{official}"
        if self.acronym:
            return f"{self.acronym}{official}"
        return f"{self.name}{official}"

    @property
    def data(self):
        _data = {
            "institution__name": self.name,
            "institution__acronym": self.acronym,
            "institution__is_official": self.is_official,
            "institution__type": self.institution_type,
            # "institution__official": str(self.official),
        }
        return _data

    @classmethod
    def get(cls, name=None, acronym=None, std=None):
        name = remove_extra_spaces(name)
        acronym = remove_extra_spaces(acronym)

        if name or acronym:
            return cls.objects.get(
                name__iexact=name,
                acronym__iexact=acronym,
            )
        raise ValueError(
            "InstitutionIdentification.get requires name or acronym parameters"
        )

    @classmethod
    def create_or_update(
        cls,
        user,
        name,
        acronym,
        is_official,
        official,
        institution_type,
    ):
        name = remove_extra_spaces(name)
        acronym = remove_extra_spaces(acronym)

        try:
            obj = cls.get(name=name, acronym=acronym)
            obj.updated_by = user
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.name = name
            obj.acronym = acronym

        obj.institution_type = institution_type or obj.institution_type
        obj.is_official = is_official or obj.is_official
        obj.official = official or obj.official
        obj.save()

        return obj

    @classmethod
    def create_or_update_with_declared_name(cls, declared_name, user):
        """
        Create or update InstitutionIdentification object
        """
        for data in standardize_acronym_and_name(declared_name):
            name = data.get("name")
            acronym = data.get("acronym")

            Decl2Std.get_or_create(
                declared_name, None, name, acronym, user
            )
            return InstitutionIdentification.create_or_update(
                user,
                name=name,
                acronym=acronym,
                is_official=None,
                official=None,
                institution_type=None,
            )

    @classmethod
    def load(cls, user, file_path=None, column_labels=None, is_official=False):
        """
        Name;Acronym;State Acronym;Institution Type;Level_1;Level_2;Level_3

        "name": "Name",
        "acronym": "Acronym",
        "state": "State Acronym",
        "type": "Institution Type",
        "level_1": "Level_1",
        "level_2": "Level_2",
        "level_3": "Level_3",
        """
        file_path = file_path or "./institution/fixtures/institutions_mec_2.csv"
        if file_path == "./institution/fixtures/institutions_mec_2.csv":
            is_official = True
        column_labels = column_labels or {
            "name": "Name",
            "acronym": "Acronym",
            "state": "State Acronym",
            "type": "Institution Type",
            "level_1": "Level_1",
            "level_2": "Level_2",
            "level_3": "Level_3",
        }

        with open(file_path, "r") as csvfile:
            rows = csv.DictReader(
                csvfile, delimiter=";", fieldnames=list(column_labels.values())
            )
            for line, row in enumerate(rows):
                yield cls.create_or_update(
                    user=user,
                    name=row.get(column_labels["name"]),
                    acronym=row.get(column_labels["acronym"]),
                    institution_type=row.get(column_labels["type"]),
                    is_official=is_official,
                )


class Decl2Std(CommonControlField):
    declared_name = models.TextField(_("Declared Name"), null=True, blank=True)
    declared_acronym = models.TextField(_("Declared Acronym"), null=True, blank=True)
    std_name = models.TextField(_("Standardized Name"), null=True, blank=True)
    std_acronym = models.CharField(
        _("Standardized Acronym"), max_length=32, null=True, blank=True
    )

    class Meta:
        # para evitar duplicar registros. Levanta exceção IntegrityError
        unique_together = [
            ("declared_name", "declared_acronym", "std_name", "std_acronym"),
        ]
        indexes = [
            models.Index(
                fields=[
                    "declared_name",
                ]
            ),
            models.Index(
                fields=[
                    "declared_acronym",
                ]
            ),
            models.Index(
                fields=[
                    "std_name",
                ]
            ),
            models.Index(
                fields=[
                    "std_acronym",
                ]
            ),
        ]

    @staticmethod
    def autocomplete_custom_queryset_filter(search_term):
        return Decl2Std.objects.filter(
            Q(declared_acronym__icontains=search_term)
            | Q(declared_name__icontains=search_term)
            | Q(std_acronym__icontains=search_term)
            | Q(std_name__icontains=search_term)
        )

    def autocomplete_label(self):
        return f"{self.declared_acronym} {self.declared_name}"

    @classmethod
    def get_or_create(
        cls,
        user,
        declared_name,
        declared_acronym,
        std_name,
        std_acronym,
    ):
        declared_name = remove_extra_spaces(declared_name)
        declared_acronym = remove_extra_spaces(declared_acronym)
        std_name = remove_extra_spaces(std_name)
        std_acronym = remove_extra_spaces(std_acronym)

        if declared_name or declared_acronym or std_name or std_acronym:
            try:
                return cls._get(
                    declared_name,
                    declared_acronym,
                    std_name,
                    std_acronym,
                )
            except cls.DoesNotExist:
                return cls._create(
                    user,
                    declared_name,
                    declared_acronym,
                    std_name,
                    std_acronym,
                )
        raise ValueError(
            "Decl2Std.create requires declared_name or declared_acronym"
        )

    @classmethod
    def _get(
        cls,
        declared_name,
        declared_acronym,
        std_name,
        std_acronym,
    ):
        if declared_name or declared_acronym:
            try:
                return cls.objects.get(
                    declared_name=declared_name,
                    declared_acronym=declared_acronym,
                    std_name=std_name,
                    std_acronym=std_acronym,
                )
            except cls.MultipleObjectsReturned:
                return cls.objects.filter(
                    declared_name=declared_name,
                    declared_acronym=declared_acronym,
                    std_name=std_name,
                    std_acronym=std_acronym,
                ).first()
        raise ValueError(
            "Decl2Std.get_or_create requires declared_name or declared_acronym"
        )

    @classmethod
    def _create(
        cls,
        user,
        declared_name,
        declared_acronym,
        std_name,
        std_acronym,
    ):
        try:
            if std_acronym and len(std_acronym) > 32:
                data = dict(
                    declared_name=declared_name,
                    declared_acronym=declared_acronym,
                    std_name=std_name,
                    std_acronym=std_acronym,
                )
                logging.info(data)
                if std_name:
                    std_name = declared_name
                else:
                    std_name = std_acronym
                std_acronym = None

            obj = cls()
            obj.creator = user
            obj.declared_name = declared_name
            obj.declared_acronym = declared_acronym
            obj.std_name = std_name
            obj.std_acronym = std_acronym
            obj.save()
            return obj
        except IntegrityError:
            # para evitar duplicar registros. Levanta exceção IntegrityError
            return cls.get(
                declared_name,
                declared_acronym,
                std_name,
                std_acronym,
            )
