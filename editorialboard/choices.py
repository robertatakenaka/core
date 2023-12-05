from django.utils.translation import gettext_lazy as _

GENDER_IDENTIFICATION_STATUS = [
    ("DECLARED", _("Declarado por el investigador")),
    ("AUTOMATIC", _("Identificado automaticamente por programa de computador")),
    ("MANUAL", _("Identificado por algun usuario")),
]

EDITOR_IN_CHIEF = "in-chief"
EXECUTIVE_EDITOR = "executive"
ASSOCIATE_EDITOR = "associate"
TECHNICAL_TEAM = "technical"
ROLE = [
    (EDITOR_IN_CHIEF, _("Editor-in-chief")),
    (EXECUTIVE_EDITOR, _("Editor")),
    (ASSOCIATE_EDITOR, _("Associate editor")),
    (TECHNICAL_TEAM, _("Technical team")),
]
