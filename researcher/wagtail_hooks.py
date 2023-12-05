from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _
from wagtail.contrib.modeladmin.options import (
    ModelAdmin,
    ModelAdminGroup,
    modeladmin_register,
)
from wagtail.contrib.modeladmin.views import CreateView

from .models import (
    Researcher,
    PersonName,
    Affiliation,
    ResearcherIdentifier,
    ResearcherAKA,
)


class ResearcherCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class ResearcherAdmin(ModelAdmin):
    model = Researcher
    create_view_class = ResearcherCreateView
    menu_label = _("Researcher")
    menu_icon = "folder"
    menu_order = 9
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = (
        "person_name",
        "year",
        "affiliation",
        "created",
        "updated",
    )
    list_filter = ("year",)
    search_fields = (
        "affiliation__institution_identification__name",
        "affiliation__institution_identification__acronym",
        "person_name__fullname",
    )


class ResearcherIdentifierCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class ResearcherIdentifierAdmin(ModelAdmin):
    model = ResearcherIdentifier
    create_view_class = ResearcherIdentifierCreateView
    menu_label = _("Researcher Identifier")
    menu_icon = "folder"
    menu_order = 9
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = (
        "identifier",
        "source_name",
        "created",
        "updated",
    )
    list_filter = ("source_name",)
    search_fields = ("identifier",)


class PersonNameCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class PersonNameAdmin(ModelAdmin):
    model = PersonName
    create_view_class = PersonNameCreateView
    menu_label = _("PersonName")
    menu_icon = "folder"
    menu_order = 9
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = (
        "fullname",
        "given_names",
        "last_name",
        "suffix",
        "prefix",
        "created",
        "updated",
    )
    list_filter = ("suffix", "prefix", "gender")
    search_fields = ("fullname",)


class AffiliationCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class AffiliationAdmin(ModelAdmin):
    model = Affiliation
    create_view_class = AffiliationCreateView
    menu_label = _("Affiliation")
    menu_icon = "folder"
    menu_order = 800
    add_to_settings_menu = False  # or True to add your model to the Settings sub-menu
    exclude_from_explorer = (
        False  # or True to exclude pages of this type from Wagtail's explorer view
    )
    list_display = (
        "institution_identification",
        "location",
        "level_1",
        "level_2",
        "level_3",
        "updated",
        "created",
    )
    search_fields = (
        "institution_identification__name",
        "institution_identification__acronym",
        "level_1",
        "level_2",
        "level_3",
        "location__country__name",
        "location__country__acronym",
        "location__state__name",
        "location__state__acronym",
        "location__city__name",
    )
    list_export = (
        "institution_identification",
        "level_1",
        "level_2",
        "level_3",
        "location",
        "creator",
        "created",
        "updated",
        "updated_by",
    )
    export_filename = "affiliations"


class ResearcherAdminGroup(ModelAdminGroup):
    menu_label = _("Researchers")
    menu_icon = "folder-open-inverse"  # change as required
    menu_order = 7
    items = (
        ResearcherIdentifierAdmin,
        ResearcherAdmin,
        PersonNameAdmin,
        AffiliationAdmin,
    )


modeladmin_register(ResearcherAdminGroup)
