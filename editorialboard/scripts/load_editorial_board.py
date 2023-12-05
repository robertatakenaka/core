from django.contrib.auth import get_user_model

from editorialboard.models import EditorialBoardMember


User = get_user_model()


def run(username, file_path=None):
    if not file_path:
        # este arquivo não deve ser versionado
        file_path = "./editorialboard/fixtures/ce.csv"
    user = User.objects.get(username=username)
    EditorialBoardMember.load(user, file_path)
