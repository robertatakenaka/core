from django.http import HttpResponseRedirect
from django.urls import path
from django.utils.translation import gettext as _
from wagtail import hooks
from wagtail.contrib.modeladmin.options import (
    ModelAdmin,
    ModelAdminGroup,
    modeladmin_register,
)
from wagtail.contrib.modeladmin.views import CreateView

from .button_helper import EditorialBoardMemberHelper
from .models import (
    EditorialBoard,
    EditorialBoardMember,
    EditorialBoardMemberFile,
    DeclaredRoleModel,
)
from .views import import_file_ebm, validate_ebm


class DeclaredRoleModelCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class DeclaredRoleModelAdmin(ModelAdmin):
    model = DeclaredRoleModel
    create_view_class = DeclaredRoleModelCreateView
    menu_label = _("DeclaredRoleModel")
    menu_icon = "folder"
    menu_order = 9
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = ("declared_role", "role", "updated", "created")
    list_filter = ("role",)
    search_fields = ("declared_role",)


class EditorialBoardCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class EditorialBoardAdmin(ModelAdmin):
    model = EditorialBoard
    create_view_class = EditorialBoardCreateView
    menu_label = _("EditorialBoard")
    menu_icon = "folder"
    menu_order = 9
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = (
        "journal",
        "initial_year",
        "final_year",
        "created",
        "updated",
    )
    list_filter = ("initial_year", "final_year")
    search_fields = (
        "journal__title",
        "initial_year",
        "final_year",
    )


class EditorialBoardMemberCreateView(CreateView):
    def form_valid(self, form):
        self.object = form.save_all(self.request.user)
        return HttpResponseRedirect(self.get_success_url())


class EditorialBoardMemberAdmin(ModelAdmin):
    model = EditorialBoardMember
    menu_label = _("Editorial Board Member")
    menu_icon = "folder"
    menu_order = 200
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = (
        "editorial_board",
        "researcher",
        "role",
        "initial_month",
        "final_month",
        "created",
        "updated",
    )
    list_filter = ("role", )
    search_fields = (
        "editorial_board__journal__title",
        "researcher__person_name__fullname",
        "editorial_board__initial_year",
        "editorial_board__final_year",
        "role__declared_role",
    )


class EditorialBoardMemberFileAdmin(ModelAdmin):
    model = EditorialBoardMemberFile
    button_helper_class = EditorialBoardMemberHelper
    menu_label = "Editorial Board Member Upload"
    menu_icon = "folder"
    menu_order = 200
    add_to_settings_menu = False
    exclude_from_explorer = False
    list_display = ("attachment", "line_count", "is_valid")
    list_filter = ("is_valid",)
    search_fields = ("attachment",)


class EditorialBoardMemberAdminGroup(ModelAdminGroup):
    menu_label = "Editorial Board Member"
    menu_icon = "folder-open-inverse"  # change as required
    menu_order = 200  # will put in 3rd place (000 being 1st, 100 2nd)
    items = (
        DeclaredRoleModelAdmin,
        EditorialBoardAdmin,
        EditorialBoardMemberAdmin,
        EditorialBoardMemberFileAdmin,
    )


modeladmin_register(EditorialBoardMemberAdminGroup)


@hooks.register("register_admin_urls")
def register_editorial_url():
    return [
        path(
            "editorialboard/editorialboradmember/validate",
            validate_ebm,
            name="validate_ebm",
        ),
        path(
            "editorialboard/editorialboradmember/import_file",
            import_file_ebm,
            name="import_file_ebm",
        ),
    ]
