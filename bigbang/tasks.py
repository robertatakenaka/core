import logging
import sys

from django.contrib.auth import get_user_model
from config import celery_app
from collection.models import Collection
from core.models import Language, License, Gender
from editorialboard.models import RoleModel
from institution.models import Institution, InstitutionType
from location.models import Country, City, State
from journal.models import Standard, Subject, WebOfKnowledge, WebOfKnowledgeSubjectCategory, IndexedAt, DigitalPreservationAgency
from vocabulary.models import Vocabulary
from thematic_areas.models import ThematicArea
from bigbang.utils.scheduler import schedule_task
from bigbang import tasks_scheduler
from tracker.models import UnexpectedEvent


User = get_user_model()


def _get_user(user_id, username):
    if user_id:
        return User.objects.get(pk=user_id)
    if username:
        return User.objects.get(username=username)


@celery_app.task(bind=True)
def task_start(
    self,
    user_id=None,
    username=None,
):
    try:
        user = _get_user(user_id, username)
        Language.load(user)
        Collection.load(user)
        Vocabulary.load(user)
        Standard.load(user)
        Subject.load(user)
        WebOfKnowledge.load(user)
        Country.load(user)
        State.load(user)
        City.load(user)
        ThematicArea.load(user)
        WebOfKnowledgeSubjectCategory.load(user)
        IndexedAt.load(user)
        Institution.load(user)
        RoleModel.load(user)
        License.load(user)
        DigitalPreservationAgency.load(user)
        InstitutionType.load(user)
        Gender.load(user)
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "bigbang.tasks.task_start",
            },
        )


@celery_app.task(bind=True)
def task_create_tasks(
    self,
    user_id=None,
    username=None,
    enable=False,
):
    tasks_scheduler.delete_outdated_tasks()
    tasks_scheduler.schedule_tasks(username)
