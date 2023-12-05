import logging
import sys

from tracker.models import UnexpectedEvent


def replace_researcher_relationships(origin, destination):

    replace_origin_by_destination_in_article(origin, destination)
    replace_origin_by_destination_in_book(origin, destination)
    replace_origin_by_destination_in_editorial_board_member(origin, destination)
    deleted = delete_origin(origin)
    if not deleted:
        origin.to_delete = True
        origin.save()


def replace_origin_by_destination_in_article(origin, destination):
    for article in origin.article_set.all():
        try:
            article.researchers.remove(origin)
            article.researchers.add(destination)
            article.save()
        except Exception as exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=exception,
                exc_traceback=exc_traceback,
                detail={
                    "operation": "replace_origin_by_destination_in_article",
                    "related_to": "article",
                    "origin": str(origin),
                    "destination": str(destination),
                },
            )


def replace_origin_by_destination_in_book(origin, destination):
    for book in origin.book_set.all():
        try:
            book.researchers.remove(origin)
            book.researchers.add(destination)
            book.save()
        except Exception as exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=exception,
                exc_traceback=exc_traceback,
                detail={
                    "operation": "replace_origin_by_destination_in_book",
                    "related_to": "book",
                    "origin": str(origin),
                    "destination": str(destination),
                },
            )


def replace_origin_by_destination_in_editorial_board_member(origin, destination):
    for editorial_board_member in EditorialBoardMember.objects.filter(
        member=origin
    ).iterator():
        try:
            editorial_board_member.member = destination
            editorial_board_member.save()
        except Exception as exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=exception,
                exc_traceback=exc_traceback,
                detail={
                    "operation": "replace_origin_by_destination_in_editorial_board_member",
                    "related_to": "editorial_board_member",
                    "origin": str(origin),
                    "destination": str(destination),
                },
            )


def delete_origin(origin):

    if (
        not origin.article_set.exists()
        and not origin.book_set.exists()
        and not origin.editorial_board_member_set.exists()
    ):
        try:
            origin.delete()
            return True
        except Exception as exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=exception,
                exc_traceback=exc_traceback,
                detail={
                    "operation": "delete_origin",
                    "delete": "origin",
                    "origin": str(origin),
                },
            )
    return False
