from datetime import datetime

from django.db import IntegrityError, models
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel, InlinePanel, ObjectList, TabbedInterface
from wagtail.fields import RichTextField
from wagtail.models import Orderable
from wagtailautocomplete.edit_handlers import AutocompletePanel

from core.forms import CoreAdminModelForm
from core.models import (
    CommonControlField,
    Language,
    License,
    TextLanguageMixin,
    TextWithLang,
    BaseExport,
)
from journal.models import Journal, SciELOJournal
from location.models import City
from .exceptions import TocSectionGetError
from .utils.extract_digits import _get_digits
from issue.am_export.articlemeta_format import get_articlemeta_format_issue


class Issue(CommonControlField, ClusterableModel):
    """
    Class that represent an Issue
    """

    journal = models.ForeignKey(
        Journal,
        verbose_name=_("Journal"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    sections = models.ManyToManyField("TocSection", blank=True)
    license = models.ManyToManyField(License, blank=True)
    code_sections = models.ManyToManyField("SectionIssue", blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, blank=True, null=True)
    number = models.CharField(_("Issue number"), max_length=20, null=True, blank=True)
    volume = models.CharField(_("Issue volume"), max_length=20, null=True, blank=True)
    season = models.CharField(
        _("Issue season"),
        max_length=20,
        null=True,
        blank=True,
        help_text="Ex: Jan-Abr.",
    )
    year = models.CharField(_("Issue year"), max_length=20, null=True, blank=True)
    month = models.CharField(_("Issue month"), max_length=20, null=True, blank=True)
    supplement = models.CharField(_("Supplement"), max_length=20, null=True, blank=True)
    markup_done = models.BooleanField(_("Markup done"), default=False)
    order = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=_(
            "This number controls the order issues appear for a specific year on the website grid"
        ),
    )
    issue_pid_suffix = models.CharField(max_length=4, null=True, blank=True)
    legacy_issues = models.ManyToManyField("LegacyIssue")

    autocomplete_search_field = "journal__title"

    def autocomplete_label(self):
        return str(self)

    panels_issue = [
        AutocompletePanel("journal"),
        FieldPanel("volume"),
        FieldPanel("number"),
        FieldPanel("supplement"),
    ]

    panels_manager = [
        FieldPanel("order"),
        FieldPanel("issue_pid_suffix", read_only=True),
        FieldPanel("markup_done"),
    ]

    panels_bibliographic_strip = [
        InlinePanel("issue_title", label=_("Issue title")),
        AutocompletePanel("city"),
        FieldPanel("season"),
        FieldPanel("month"),
        FieldPanel("year"),
        InlinePanel("bibliographic_strip"),
    ]

    panels_summary = [
        AutocompletePanel("sections"),
        AutocompletePanel("code_sections"),
    ]

    panels_license = [
        AutocompletePanel("license"),
    ]

    edit_handler = TabbedInterface(
        [
            ObjectList(panels_issue, heading=_("Issue")),
            ObjectList(panels_manager, heading=_("Management")),
            ObjectList(panels_bibliographic_strip, heading=_("Bibliographic Strip")),
            ObjectList(panels_summary, heading=_("Sections")),
            ObjectList(panels_license, heading=_("License")),
        ]
    )

    class Meta:
        verbose_name = _("Issue")
        verbose_name_plural = _("Issues")
        indexes = [
            models.Index(
                fields=[
                    "number",
                ]
            ),
            models.Index(
                fields=[
                    "volume",
                ]
            ),
            models.Index(
                fields=[
                    "year",
                ]
            ),
            models.Index(
                fields=[
                    "supplement",
                ]
            ),
        ]

    def get_journal_pid(self, collection):
        return self.journal.get_journal_pid(collection)

    def get_journal_acron(self, collection):
        return self.journal.get_journal_acron(collection)

    def get_issue_pid(self, collection):
        """Informações de código"""
        try:
            issue_pid = self.legacy_issues.filter(collection=collection).first().pid
        except AttributeError:
            issue_pid = None

        if issue_pid and len(issue_pid) == 17:
            return issue_pid

        if self.journal.scielojournal_set.count() > 1:
            raise ValueError(f"Unable to find issue pid for {self} {collection}")

        journal_pid = self.get_journal_pid(collection)
        year = self.year
        issue_pid_suffix = self.issue_pid_suffix
        issue_pid = f"{journal_pid}{year}{issue_pid_suffix}"

        if issue_pid and len(issue_pid) == 17:
            return issue_pid
        raise ValueError(f"Unable to find issue pid for {self} {collection}")

    @property
    def collections(self):
        items = []
        for item in self.journal.scielojournal_set.all():
            items.append(item.collection)
        return items

    @classmethod
    def select_issues(
        cls,
        collection_acron_list=None,
        journal_acron_list=None,
        journal_pid_list=None,
        year=None,
        volume=None,
        issue=None,
        supplement=None,
        from_date=None,
        until_date=None,
    ):
        """
        Método para filtrar issues com base em múltiplos critérios.
        
        Args:
            collection_acron_list: Lista de acrônimos de coleções (via SciELOJournal)
            journal_acron_list: Lista de acrônimos de journals
            year: Ano de publicação
            issue_folder: String no formato vXnYsZ (ex: v10n2s1)
            from_date: Data inicial de atualização
            until_date: Data final de atualização
            **kwargs: Outros filtros do Django ORM
            
        Returns:
            QuerySet de Issues filtradas
        """
        params = {}
        if collection_acron_list:
            params["journal__scielojournal_set__collection__acron3__in"] = collection_acron_list
        if journal_acron_list:
            params["journal__scielojournal_set__journal_acron__in"] = journal_acron_list
        if journal_pid_list:
            params["journal__scielojournal_set__pid__in"] = journal_pid_list
        if year:
            params["year"] = year
        if volume:
            params["volume"] = volume
        if number:
            params["number"] = number
        if supplement:
            params["supplement"] = supplement
        if from_date:
            params["updated__gte"] = from_date
        if until_date:
            params["updated__lte"] = until_date
        return cls.objects.filter(**params).select_related("journal").distinct()

    @property
    def data(self):
        d = dict()
        if self.journal:
            d.update(self.journal.data)
        d.update(
            {
                "issue__number": self.number,
                "issue__volume": self.volume,
                "issue__season": self.season,
                "issue__year": self.year,
                "issue__month": self.month,
                "issue__supplement": self.supplement,
            }
        )
        return d

    @property
    def bibliographic(self):
        data = self.bibliographic_strip.all().values(
            "text",
            "language__code2",
        )
        return [
            {
                "text": obj.get("text"),
                "language": obj.get("language__code2"),
            }
            for obj in data
        ]

    @classmethod
    def get_or_create(
        cls,
        journal,
        number,
        volume,
        season,
        year,
        month,
        supplement,
        user,
        markup_done=False,
        sections=None,
        issue_pid_suffix=None,
        order=None,
    ):
        return cls.create_or_update(
            user,
            journal,
            volume,
            number,
            supplement,
            year,
            season,
            month,
            markup_done,
            sections,
            issue_pid_suffix,
            order,
        )

    @classmethod
    def get(cls, journal, volume, number, supplement, year):
        """
        Busca uma issue existente com os parâmetros fornecidos.
        
        Args:
            journal: Journal da issue
            volume: Volume da issue
            number: Número da issue
            supplement: Suplemento
            
        Returns:
            Issue encontrada

        Raises:
            Issue.DoesNotExist
        """
        return cls.objects.get(
            journal=journal,
            volume=volume,
            number=number,
            supplement=supplement,
            year=year,
        )
    
    @classmethod
    def create(
        cls,
        user,
        journal,
        volume,
        number,
        supplement,
        year,
        season=None,
        month=None,
        markup_done=False,
        sections=None,
        issue_pid_suffix=None,
        order=None,
    ):
        """
        Cria uma nova issue com os parâmetros fornecidos.
        
        Args:
            journal: Journal da issue
            volume: Volume da issue
            number: Número da issue
            supplement: Suplemento
            year: Ano
            season: Temporada (opcional)
            month: Mês (opcional)
            user: Usuário criador
            markup_done: Flag de markup concluído
            sections: Seções da issue (opcional)
            issue_pid_suffix: Sufixo PID (opcional)
            order: Ordem (opcional)
            
        Returns:
            Nova issue criada
        """
        issue = cls()
        issue.journal = journal
        issue.volume = volume
        issue.number = number
        issue.supplement = supplement
        issue.season = season
        issue.year = year
        issue.month = month
        issue.markup_done = markup_done
        issue.creator = user
        issue.order = order
        issue.issue_pid_suffix = issue_pid_suffix
        issue.save()
        
        if sections:
            issue.sections.set(sections)
            
        return issue
    
    @classmethod
    def create_or_update(
        cls,
        user,
        journal,
        volume,
        number,
        supplement,
        year,
        season=None,
        month=None,
        markup_done=False,
        sections=None,
        issue_pid_suffix=None,
        order=None,
    ):
        """
        Busca uma issue existente e atualiza, ou cria uma nova se não existir.
        
        Args:
            user: Usuário criador/atualizador
            journal: Journal da issue
            volume: Volume da issue
            number: Número da issue
            supplement: Suplemento
            year: Ano
            season: Temporada (opcional)
            month: Mês (opcional)
            markup_done: Flag de markup concluído
            sections: Seções da issue (opcional)
            issue_pid_suffix: Sufixo PID (opcional)
            order: Ordem (opcional)
            
        Returns:
            Tupla (issue, created) onde created é True se foi criada nova issue
        """
        try:
            issue = cls.get(
                journal=journal,
                volume=volume,
                number=number,
                supplement=supplement,
                year=year,
            )
            issue.updated_by = user
            issue.season = season
            issue.year = year
            issue.month = month
            issue.markup_done = markup_done
            issue.order = order
            issue.issue_pid_suffix = issue_pid_suffix
            issue.save()
            if sections:
                issue.sections.set(sections)
            return issue
        except cls.DoesNotExist:
            return cls.create(
                user,
                journal,
                volume,
                number,
                supplement,
                year,
                season,
                month,
                markup_done,
                sections,
                issue_pid_suffix,
                order,
            )

    def __unicode__(self):
        return "%s, %s, %s" % (self.journal, self.issue_folder, self.year)

    def __str__(self):
        return "%s, %s, %s" % (self.journal, self.issue_folder, self.year)

    @property
    def issue_folder(self):
        labels = [(self.volume, "v"), (self.number, "n"), (self.supplement, "s")]
        return "".join([f"{prefix}{value}" for value, prefix in labels if value])

    @property
    def issue_type(self):
        volume = self.volume
        number = self.number
        supplement = self.supplement

        if supplement is not None:
            return "supplement"

        if number:
            if "spe" in number:
                return "special"
                # self.data["spe_text"] = number.split("spe")[-1]
            if number == "ahead":
                return "ahead"

            return "regular"

        return "volume_issue"

    def articlemeta_format(self, collection):
        return get_articlemeta_format_issue(
            self,
            self.legacy_issues.filter(collection=collection.acron3).first(),
        )

    def save(self, *args, **kwargs):
        if not self.issue_pid_suffix:
            self.issue_pid_suffix = self.generate_issue_pid_suffix()
        if not self.order:
            self.order = self.generate_order()
        super().save(*args, **kwargs)

    def generate_issue_pid_suffix(self):
        return str(self.generate_order()).zfill(4)

    def generate_order_supplement(self, suppl_start=1000):
        suppl_val = _get_digits(self.supplement)
        return suppl_start + suppl_val

    def generate_order_number(self, spe_start=2000):
        parts = self.number.split("spe")[-1]
        spe_val = _get_digits(parts)
        return spe_start + spe_val
    
    def generate_order(self, suppl_start=1000, spe_start=2000):
        if self.supplement is not None:
            return self.generate_order_supplement(suppl_start)

        if not self.number:
            return 1

        if "spe" in self.number:
            return self.generate_order_number(spe_start)
        if self.number == "ahead":
            return 9999

        number = _get_digits(self.number)
        return number or 1

    base_form_class = CoreAdminModelForm


class IssueTitle(Orderable, CommonControlField):
    issue = ParentalKey(
        Issue,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="issue_title",
    )
    title = models.CharField(_("Issue Title"), max_length=100, blank=True, null=True)
    language = models.ForeignKey(
        Language, on_delete=models.CASCADE, blank=True, null=True
    )

    panels = [FieldPanel("title"), AutocompletePanel("language")]

    def __str__(self):
        return self.title


class BibliographicStrip(Orderable, TextWithLang, CommonControlField):
    issue = ParentalKey(
        Issue,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bibliographic_strip",
    )


class TocSection(TextLanguageMixin, CommonControlField):
    """
    <article-categories>
        <subj-group subj-group-type="heading">
          <subject>NOMINATA</subject>
        </subj-group>
      </article-categories>
    """

    text = RichTextField(
        max_length=100, blank=True, null=True, help_text="For JATs is subject."
    )
    autocomplete_search_field = "plain_text"

    def autocomplete_label(self):
        return str(self.plain_text)

    class Meta:
        verbose_name = _("TocSection")
        verbose_name_plural = _("TocSections")
        unique_together = [("plain_text", "language")]
        indexes = [
            models.Index(
                fields=[
                    "plain_text",
                ]
            ),
        ]

    @classmethod
    def get(
        cls,
        value,
        language,
    ):
        if value and language:
            try:
                return cls.objects.get(plain_text=value, language=language)
            except cls.MultipleObjectsReturned:
                return cls.objects.filter(plain_text=value, language=language).first()
        raise TocSectionGetError(
            "TocSection.get requires value and language parameters"
        )

    @classmethod
    def create(
        cls,
        value, 
        language,
        user,
    ):
        try:
            obj = cls()
            obj.plain_text = value
            obj.language = language
            obj.creator = user
            obj.save()
            return obj
        except IntegrityError:
            return cls.get(value=value, language=language)

    @classmethod
    def get_or_create(
        cls,
        value,
        language,
        user,
    ):
        try:
            return cls.get(value=value, language=language)
        except cls.DoesNotExist:
            return cls.create(value=value, language=language, user=user)

    def __unicode__(self):
        return f"{self.plain_text} - {self.language}"

    def __str__(self):
        return f"{self.plain_text} - {self.language}"


class CodeSectionIssue(CommonControlField):
    code = models.CharField(_("Code"), max_length=40, unique=True, null=True, blank=True)

    def __str__(self):
        return f"{self.code}"
    

class SectionIssue(TextWithLang, CommonControlField):
    code_section = models.ForeignKey(
        CodeSectionIssue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    autocomplete_search_field = "text"

    def autocomplete_label(self):
        return str(self)

    def __str__(self):
        return f"{self.code}"
    
    class Meta:
        unique_together = [("code_section", "language")]

    def __str__(self):
        return f"{self.code_section.code} - {self.text} ({self.language.code2 if self.language else 'N/A'})"


class LegacyIssue(models.Model):
    """
    Modelo que representa a coleta de dados de Issue na API Article Meta.

    from:
        https://articlemeta.scielo.org/api/v1/issue/?collection={collection}&issn={issn}"

        https://github.com/scieloorg/articles_meta/blob/master/docs/source/api/issue_identifiers.rst
    """
    collection = models.CharField(
        _("Collection acronym"),
        max_length=17,
        blank=True,
        null=True,
    )
    pid = models.CharField(
        _("PID"),
        max_length=17,
        blank=True,
        null=True,
    )
    processing_date = models.CharField(
        _("Processing date"),
        max_length=10,
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=10,
        choices=[
            ('HAS_ID', _('has id')),
            ('HAS_DATA', _('has data')),
            ('HAS_ISSUE', _('has issue')),
        ],
        default='HAS_ID'
    )
    data = models.JSONField(null=True, blank=True)

    autocomplete_search_field = "pid"

    class Meta:
        verbose_name = _("Legacy Issue")
        verbose_name_plural = _("Legacy Issues")
        indexes = [
            models.Index(
                fields=[
                    "-processing_date", "collection", "pid"
                ]
            ),
            models.Index(
                fields=[
                    "collection", "pid"
                ]
            ),
            models.Index(
                fields=[
                    "status"
                ]
            ),
        ]


    def __str__(self):
        return f"{self.pid} {self.collection}"

    def autocomplete_label(self):
        return str(self)

    @classmethod
    def get(
        cls,
        collection,
        pid,
        processing_date=None,
    ):
        params = {}
        if processing_date:
            params["processing_date"] = processing_date
        if collection and pid:
            try:
                return cls.objects.get(collection=collection, pid=pid, **params)
            except cls.DoesNotExist:
                return cls.objects.get(collection=collection, pid=pid)
        raise ValueError(f"LegacyIssue.get_or_create requires collection ({collection}) and pid ({pid})")

    @classmethod
    def create(
        cls,
        collection,
        pid,
        processing_date,
        data,
    ):
        if collection and pid:
            obj = cls()
            obj.collection = collection
            obj.pid = pid
            obj.processing_date = processing_date
            obj.data = data
            obj.save()
            return obj
            
        raise ValueError(f"LegacyIssue.get_or_create requires collection ({collection}) and pid ({pid})")

    @classmethod
    def create_or_update(
        cls,
        collection,
        pid,
        processing_date,
        data,
        status=None,
    ):
        if collection and pid:
            try:
                obj = cls.get(collection=collection, pid=pid, processing_date=processing_date)
            except cls.MultipleObjectsReturned:
                obj = cls.filter(collection=collection, pid=pid).order_by("-processing_date").first()
            except cls.DoesNotExist:
                return cls.create(collection, pid, processing_date, data)

            obj.data = data
            obj.processing_date = processing_date
            if status:
                obj.status = status
            obj.save()
            return obj
        raise ValueError(f"LegacyIssue.get_or_create requires collection ({collection}) and pid ({pid})")

    @classmethod
    def select(cls, collection, issn=None, pid=None, status=None):
        params = {}
        if status:
            params["status"] = status
        if pid:
            params["pid"] = pid
        if issn:
            params["pid__startswith"] = issn
        return cls.objects.filter(collection=collection, **params)


class IssueExport(BaseExport):
    parent = ParentalKey(
        Issue, on_delete=models.CASCADE, related_name="export",
    )
