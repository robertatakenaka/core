import os

from django.db import models, IntegrityError
from django.db.models import Q
from django.utils.translation import gettext as _
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.forms import CoreAdminModelForm
from core.models import CommonControlField
from core.utils.standardizer import remove_extra_spaces
from location.models import Country, Location

from . import choices
from .forms import ScimagoForm


class Institution(CommonControlField, ClusterableModel):
    name = models.TextField(_("Name"), null=True, blank=True)
    institution_type = models.TextField(
        _("Institution Type"), choices=choices.inst_type, null=True, blank=True
    )
    location = models.ForeignKey(
        Location, null=True, blank=True, on_delete=models.SET_NULL
    )

    acronym = models.TextField(_("Institution Acronym"), null=True, blank=True)
    level_1 = models.TextField(_("Organization Level 1"), null=True, blank=True)
    level_2 = models.TextField(_("Organization Level 2"), null=True, blank=True)
    level_3 = models.TextField(_("Organization Level 3"), null=True, blank=True)
    url = models.URLField("url", blank=True, null=True)

    logo = models.ImageField(_("Logo"), blank=True, null=True)

    official = models.ForeignKey(
        "Institution",
        verbose_name=_("Institution"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_official = models.CharField(
        _("Is official"),
        null=True,
        blank=True,
        choices=choices.is_official,
        max_length=6,
    )

    autocomplete_search_field = "name"

    def autocomplete_label(self):
        return self.name

    base_form_class = CoreAdminModelForm
    panels = [
        FieldPanel("name"),
        FieldPanel("acronym"),
        FieldPanel("institution_type"),
        AutocompletePanel("location"),
        FieldPanel("level_1"),
        FieldPanel("level_2"),
        FieldPanel("level_3"),
        FieldPanel("url"),
        FieldPanel("logo"),
        AutocompletePanel("official"),
        FieldPanel("is_official"),
    ]

    class Meta:
        unique_together = [
            ("name", "acronym", "level_1", "level_2", "level_3", "location"),
        ]
        indexes = [
            models.Index(
                fields=[
                    "name",
                ]
            ),
            models.Index(
                fields=[
                    "institution_type",
                ]
            ),
            models.Index(
                fields=[
                    "acronym",
                ]
            ),
            models.Index(
                fields=[
                    "url",
                ]
            ),
        ]

    def __unicode__(self):
        return "%s | %s | %s | %s | %s | %s" % (
            self.name,
            self.acronym,
            self.level_1,
            self.level_2,
            self.level_3,
            self.location,
        )

    def __str__(self):
        return "%s | %s | %s | %s | %s | %s" % (
            self.name,
            self.acronym,
            self.level_1,
            self.level_2,
            self.level_3,
            self.location,
        )

    @property
    def data(self):
        _data = {
            "institution__name": self.name,
            "institution__acronym": self.acronym,
            "institution__level_1": self.level_1,
            "institution__level_2": self.level_2,
            "institution__level_3": self.level_3,
            "institution__url": self.url,
        }
        if self.official:
            _data.update(self.official.data)
        _data.update(
            {
                "institution__is_official": self.is_official,
            }
        )

        return _data

    @classmethod
    def get(
        cls,
        name,
        acronym,
        level_1,
        level_2,
        level_3,
        location,
    ):
        if name or acronym:
            try:
                return cls.objects.get(
                    name__iexact=name,
                    acronym__iexact=acronym,
                    level_1__iexact=level_1,
                    level_2__iexact=level_2,
                    level_3__iexact=level_3,
                    location=location,
                )
            except cls.MultipleObjectsReturned:
                return cls.objects.filter(
                    name__iexact=name,
                    acronym__iexact=acronym,
                    level_1__iexact=level_1,
                    level_2__iexact=level_2,
                    level_3__iexact=level_3,
                    location=location,
                ).first()
        raise ValueError("Requires name or acronym parameters")

    @classmethod
    def create_or_update(
        cls,
        name,
        acronym,
        level_1,
        level_2,
        level_3,
        location,
        official,
        is_official,
        url,
        institution_type,
        user,
    ):
        name = remove_extra_spaces(name)
        acronym = remove_extra_spaces(acronym)
        level_1 = remove_extra_spaces(level_1)
        level_2 = remove_extra_spaces(level_2)
        level_3 = remove_extra_spaces(level_3)
        institution_type = remove_extra_spaces(institution_type)

        try:
            institution = cls.get(
                name=name,
                acronym=acronym,
                level_1=level_1,
                level_2=level_2,
                level_3=level_3,
                location=location,
            )
            institution.updated_by = user
            institution.institution_type = institution_type or institution.institution_type
            institution.official = official or institution.official
            institution.is_official = is_official or institution.is_official
            institution.url = url or institution.url
            institution.save()
            return institution
        except cls.DoesNotExist:
            return cls.create(
                user=user,
                name=name,
                acronym=acronym,
                level_1=level_1,
                level_2=level_2,
                level_3=level_3,
                location=location,
                official=official,
                is_official=is_official,
                url=url,
                institution_type=institution_type,
            )

    @classmethod
    def create(
        cls,
        user,
        name,
        acronym,
        level_1,
        level_2,
        level_3,
        location,
        official,
        is_official,
        url,
        institution_type,
    ):

        try:
            obj = cls()
            obj.creator = user
            obj.name = name
            obj.acronym = acronym
            obj.level_1 = level_1
            obj.level_2 = level_2
            obj.level_3 = level_3
            obj.location = location
            obj.official = official
            obj.is_official = is_official
            obj.url = url
            obj.institution_type = institution_type
            obj.save()
            return obj
        except IntegrityError:
            return cls.get(
                name=name,
                acronym=acronym,
                level_1=level_1,
                level_2=level_2,
                level_3=level_3,
                location=location,
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


class Sponsor(CommonControlField):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    autocomplete_search_field = "institution__name"

    def autocomplete_label(self):
        return str(self.institution)

    panels = [
        AutocompletePanel("institution"),
    ]

    base_form_class = CoreAdminModelForm


class Publisher(CommonControlField):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    autocomplete_search_field = "institution__name"

    def autocomplete_label(self):
        return str(self.institution)

    panels = [
        AutocompletePanel("institution"),
    ]

    base_form_class = CoreAdminModelForm


class CopyrightHolder(CommonControlField):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    autocomplete_search_field = "institution__name"

    def autocomplete_label(self):
        return str(self.institution)

    panels = [
        AutocompletePanel("institution"),
    ]

    base_form_class = CoreAdminModelForm


class Owner(CommonControlField):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    autocomplete_search_field = "institution__name"

    def autocomplete_label(self):
        return str(self.institution)

    panels = [
        AutocompletePanel("institution"),
    ]

    base_form_class = CoreAdminModelForm


class EditorialManager(CommonControlField):
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )

    autocomplete_search_field = "institution__name"

    def autocomplete_label(self):
        return str(self.institution)

    panels = [
        AutocompletePanel("institution"),
    ]

    base_form_class = CoreAdminModelForm


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
    is_official = models.BooleanField(
        _("Is official"),
        null=True,
        blank=True,
    )
    official = models.ForeignKey(
        "self",
        verbose_name=_("Official name"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    autocomplete_search_field = "name"

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
                    "is_official",
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
        }
        return _data

    @classmethod
    def _get(cls, name=None, acronym=None):
        if name or acronym:
            try:
                return cls.objects.get(
                    name__iexact=name,
                    acronym__iexact=acronym,
                )
            except cls.MultipleObjectsReturned:
                return cls.objects.filter(
                    name__iexact=name,
                    acronym__iexact=acronym,
                ).first()
        raise ValueError(
            "InstitutionIdentification.get requires name or acronym parameters"
        )

    @classmethod
    def _create(
        cls,
        user,
        name,
        acronym,
        is_official,
        official,
    ):
        try:
            obj = cls()
            obj.creator = user
            obj.name = name
            obj.acronym = acronym
            obj.is_official = is_official or obj.is_official
            obj.official = official or obj.official
            obj.save()
        except IntegrityError:
            return cls.get(name, acronym)
        return obj

    @classmethod
    def create_or_update(
        cls,
        user,
        name,
        acronym,
        is_official,
        official,
    ):
        name = remove_extra_spaces(name)
        acronym = remove_extra_spaces(acronym)

        try:
            obj = cls._get(name=name, acronym=acronym)
            obj.updated_by = user
            obj.is_official = is_official or obj.is_official
            obj.official = official or obj.official
            obj.save()
            return obj
        except cls.DoesNotExist:
            return cls._create(
                user,
                name,
                acronym,
                is_official,
                official,
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
                cls.create_or_update(
                    user=user,
                    name=row.get(column_labels["name"]),
                    acronym=row.get(column_labels["acronym"]),
                    is_official=is_official,
                    official=None,
                )
