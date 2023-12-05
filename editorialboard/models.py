import logging
import csv
import os
from datetime import datetime

from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.models import Orderable
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.choices import MONTHS
from core.models import CommonControlField, Gender
from core.forms import CoreAdminModelForm
from core.utils.standardizer import remove_extra_spaces
from location.models import Location
from journal.models import Journal
from researcher.models import Researcher, Affiliation
from editorialboard import choices


class DeclaredRoleModel(CommonControlField):
    role = models.CharField(
        _("Role"), max_length=16, choices=choices.ROLE, null=True, blank=True
    )
    declared_role = models.CharField(
        _("Declared Role"), max_length=128, null=True, blank=True
    )

    class Meta:
        unique_together = ["declared_role", "role"]
        indexes = [
            models.Index(
                fields=[
                    "declared_role",
                ]
            ),
            models.Index(
                fields=[
                    "role",
                ]
            ),
        ]

    def __str__(self):
        return f"{self.role} | {self.declared_role}"

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return DeclaredRoleModel.objects.filter(
            Q(declared_role__icontains=any_value) | Q(role__icontains=any_value)
        )

    def autocomplete_label(self):
        return f"{self.role} | {self.declared_role}"

    @classmethod
    def get_or_create(
        cls,
        user,
        declared_role,
        role,
    ):
        if not declared_role:
            raise ValueError(
                "DeclaredRoleModel.create_or_update requires declared_role"
            )
        try:
            declared_role = remove_extra_spaces(declared_role)
            role = role or cls.get_std_role(declared_role)
            return cls.objects.get(declared_role=declared_role, role=role)
        except cls.DoesNotExist:
            return cls.create(user, declared_role, role)

    @classmethod
    def create(
        cls,
        user,
        declared_role,
        role,
    ):
        if not declared_role:
            raise ValueError(
                "DeclaredRoleModel.create_or_update requires declared_role"
            )
        declared_role = remove_extra_spaces(declared_role)
        role = role or cls.get_std_role(declared_role)
        try:
            obj = cls()
            obj.creator = user
            obj.declared_role = declared_role
            obj.role = role
            obj.save()
            return obj
        except IntegrityError as e:
            return cls.objects.get(declared_role=declared_role, role=role)

    @classmethod
    def get_std_role(cls, declared_role):
        # EDITOR_IN_CHIEF = "in-chief"
        # EXECUTIVE_EDITOR = "executive"
        # ASSOCIATE_EDITOR = "associate"
        # TECHNICAL_TEAM = "technical"
        declared_role = declared_role.lower()
        if "chef" in declared_role:
            return choices.EDITOR_IN_CHIEF
        if len(declared_role.split()) == 1 or "exec" in declared_role:
            return choices.EXECUTIVE_EDITOR
        if (
            "assoc" in declared_role
            or "área" in declared_role
            or "seç" in declared_role
            or "cient" in declared_role
            or "editor " in declared_role
        ):
            return choices.ASSOCIATE_EDITOR


class EditorialBoard(CommonControlField, ClusterableModel):
    journal = models.ForeignKey(
        Journal, null=True, blank=True, related_name="+", on_delete=models.SET_NULL
    )
    initial_year = models.CharField(max_length=4, blank=True, null=True)
    final_year = models.CharField(max_length=4, blank=True, null=True)

    class Meta:
        unique_together = [["journal", "initial_year", "final_year"]]

        indexes = [
            models.Index(
                fields=[
                    "initial_year",
                ]
            ),
            models.Index(
                fields=[
                    "final_year",
                ]
            ),
        ]

    panels = [
        FieldPanel("initial_year"),
        FieldPanel("final_year"),
        InlinePanel("editorial_board_member"),
    ]
    base_form_class = CoreAdminModelForm

    @staticmethod
    def autocomplete_custom_queryset_filter(any_value):
        return EditorialBoard.objects.filter(
            Q(journal__title__icontains=any_value) |
            Q(initial_year__icontains=any_value) |
            Q(final_year__icontains=any_value)
        )

    def autocomplete_label(self):
        return str(self)

    def __str__(self):
        return f"{self.journal.title} {self.initial_year}-{self.final_year}"

    @classmethod
    def get_or_create(
        cls,
        journal,
        initial_year,
        final_year,
        user=None,
    ):
        try:
            return cls.objects.get(
                journal=journal,
                initial_year=initial_year,
                final_year=final_year,
            )
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.journal = journal
            obj.initial_year = initial_year
            obj.final_year = final_year
            obj.save()
            return obj

    def get_members(self):
        return EditorialBoardMember.objects.filter(
            editorial_board_member__editorial_board=self,
        )


class EditorialBoardMember(CommonControlField, Orderable):
    editorial_board = ParentalKey(
        EditorialBoard,
        on_delete=models.SET_NULL,
        related_name="editorial_board_member",
        null=True,
    )
    researcher = models.ForeignKey(
        Researcher, null=True, blank=True, related_name="+", on_delete=models.SET_NULL
    )
    role = models.ForeignKey(
        DeclaredRoleModel, null=True, blank=True, on_delete=models.SET_NULL
    )
    initial_month = models.CharField(
        max_length=2, blank=True, null=True, choices=MONTHS, default="01"
    )
    final_month = models.CharField(
        max_length=2, blank=True, null=True, choices=MONTHS, default="12")

    class Meta:
        indexes = [
            models.Index(
                fields=[
                    "editorial_board",
                ]
            ),
            models.Index(
                fields=[
                    "role",
                ]
            ),
        ]

    panels = [
        AutocompletePanel("editorial_board", read_only=True),
        AutocompletePanel("researcher", read_only=True),
        AutocompletePanel("role"),
        FieldPanel("initial_month"),
        FieldPanel("final_month"),
    ]
    base_form_class = CoreAdminModelForm

    @classmethod
    def get(
        cls,
        editorial_board,
        researcher,
        role,
    ):
        if editorial_board and researcher and role:
            return cls.objects.get(
                editorial_board=editorial_board,
                researcher=researcher,
                role=role,
            )
        raise ValueError("EditorialBoardMember.get requires editorial_board and member and role")

    @classmethod
    def create_or_update(
        cls,
        user,
        editorial_board,
        researcher,
        initial_month,
        final_month,
        declared_role,
        role,
    ):
        try:
            obj_role = DeclaredRoleModel.get_or_create(
                user, declared_role, role,
            )
            obj = cls.get(
                editorial_board=editorial_board,
                researcher=researcher,
                role=obj_role,
            )
            obj.updated_by = user
        except cls.DoesNotExist:
            obj = cls()
            obj.creator = user
            obj.editorial_board = editorial_board
            obj.researcher = researcher
            obj.role = obj_role

        obj.initial_month = initial_month or obj.initial_month
        obj.final_month = final_month or obj.final_month
        obj.role = obj_role or obj.role
        obj.save()
        return obj

    @classmethod
    def load(cls, user, file_path, column_labels=None):
        """
            "journal": "Periódico",
            "year": "Data",
            "member": "Nome do membro",
            "role": "Cargo / instância do membro",
            "institution": "Instituição",
            "division": "Departamento",
            "city": "Cidade",
            "state": "Estado",
            "country": "País",
            "lattes": "CV Lattes",
            "orcid": "ORCID iD",
            "email": "Email",
        """
        column_labels = column_labels or {
            "journal": "Periódico",
            "year": "Data",
            "member": "Nome do membro",
            "role": "Cargo / instância do membro",
            "institution": "Instituição",
            "division": "Departamento",
            "city": "Cidade",
            "state": "Estado",
            "country": "País",
            "lattes": "CV Lattes",
            "orcid": "ORCID iD",
            "email": "Email",
        }

        with open(file_path, "r") as csvfile:
            rows = csv.DictReader(
                csvfile, delimiter=",", fieldnames=list(column_labels.values())
            )
            for line, row in enumerate(rows):
                cls.load_row(
                    user=user,
                    journal_title=row.get(column_labels["journal"]),
                    year=row.get(column_labels["year"]),
                    fullname=row.get(column_labels["member"]),
                    declared_role=row.get(column_labels["role"]),
                    institution_name=row.get(column_labels["institution"]),
                    institution_div1=row.get(column_labels["division"]),
                    # institution_div2=row.get("div2"),
                    institution_city=row.get(column_labels["city"]),
                    institution_state=row.get(column_labels["state"]),
                    institution_country=row.get(column_labels["country"]),
                    lattes=row.get(column_labels["lattes"]),
                    orcid=row.get(column_labels["orcid"]),
                    email=row.get(column_labels["email"]),
                )

    @classmethod
    def load_row(
        cls,
        user,
        journal_title=None,
        year=None,
        fullname=None,
        declared_role=None,
        role=None,
        institution_name=None,
        institution_div1=None,
        institution_div2=None,
        institution_city=None,
        institution_state=None,
        institution_country=None,
        lattes=None,
        orcid=None,
        email=None,
        gender_code=None,
        gender_identification_status=None,
    ):

        locations = []
        for loc in Location.standardize(
            institution_city,
            institution_state,
            institution_country,
            user=user,
        ):
            locations.append(loc["location"])

        researcher = None
        for affiliation in Affiliation.create_or_update_with_declared_name(
            user,
            declared_name=institution_name,
            level_1=institution_div1,
            level_2=None,
            level_3=None,
            locations=locations,
            url=None,
        ):

            researcher = Researcher.create_or_update(
                user,
                given_names=None,
                last_name=None,
                suffix=None,
                declared_name=fullname,
                affiliation=affiliation,
                year=year,
                orcid=orcid,
                lattes=lattes,
                other_ids=None,
                email=email,
                gender=None,
                gender_identification_status=None,
            )

        if researcher is None:
            researcher = Researcher.create_or_update(
                user,
                given_names=None,
                last_name=None,
                suffix=None,
                declared_name=fullname,
                affiliation=None,
                year=year,
                orcid=orcid,
                lattes=lattes,
                other_ids=None,
                email=email,
                gender=None,
                gender_identification_status=None,
            )
        try:
            journal_title = journal_title and journal_title.strip()
            journal = Journal.objects.get(
                Q(title__icontains=journal_title) |
                Q(official__title__icontains=journal_title)
            )
            logging.info(f"EditorialBoard {journal_title} OK")
        except Journal.DoesNotExist as e:
            logging.info(f"EditorialBoard {journal_title} {e}")
            editorial_board = None
        else:
            editorial_board = EditorialBoard.get_or_create(
                journal,
                initial_year=year,
                final_year=year,
                user=user,
            )
            if researcher and editorial_board:
                EditorialBoardMember.create_or_update(
                    user,
                    editorial_board,
                    researcher,
                    initial_month=None,
                    final_month=None,
                    declared_role=declared_role,
                    role=None,
                )


class EditorialBoardMemberFile(models.Model):
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
