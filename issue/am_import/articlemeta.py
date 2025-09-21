import logging
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Generator, Optional, List
from urllib.parse import urlencode

from collection.models import Collection
from core.utils.utils import fetch_data
from issue.am_import.issue_loader import create_or_update_issue
from issue.models import LegacyIssue, Issue
from journal.models import SciELOJournal
from tracker.models import UnexpectedEvent


# ============================================================================
# Função principal de entrada
# ============================================================================

def load_issue_from_article_meta(
    user,
    collection=None,
    issn_scielo=None,
    from_date=None,
    until_date=None,
    limit=None,
    timeout=None,
    reset=None,
    force_update=None,
):
    """
    Carrega issues do ArticleMeta de forma otimizada.
    
    1. Verifica se já tem todos os issues na base
    2. Se sim, processa apenas os PENDING
    3. Se não, faz a coleta completa
    """
    Issue.objects.filter(journal__isnull=True).delete()
    LegacyIssue.objects.filter(status="PENDING").update(status="HAS_ID")

    params = {}
    
    if collection:
        params["collection__acron3"] = collection
    if issn_scielo:
        params["issn_scielo"] = issn_scielo

    items = SciELOJournal.objects.filter(**params).values_list(
        "collection__acron3", "issn_scielo"
    )

    for collection_acron3, issn_scielo in items:
        try:
            process_collection_issues(
                user=user,
                collection_acron=collection_acron3,
                issn=issn_scielo,
                from_date=from_date,
                until_date=until_date,
                limit=limit or 1000,
                timeout=timeout or 30,
                reset=reset,
                force_update=force_update,
            )
                
        except Exception as exc:
            logging.error(f"Error processing {collection_acron3}/{issn_scielo}: {exc}")
            UnexpectedEvent.create(
                exception=exc,
                exc_traceback=sys.exc_info()[2],
                action="issue.sources.articlemeta.load_issue_from_article_meta",
                detail={
                    "collection": collection_acron3,
                    "issn": issn_scielo
                },
            )


def process_collection_issues(
    user,
    collection_acron,
    issn,
    from_date=None,
    until_date=None,
    limit=None,
    timeout=None,
    reset=None,
    force_update=None,
):
    params = {}
    if from_date and until_date:
        params["processing_date__range"] = (from_date, until_date)
    if from_date:
        params["processing_date__gte"] = from_date
    if until_date:
        params["processing_date__lte"] = until_date

    if reset:
        LegacyIssue.select(collection_acron, issn=issn).filter(**params).update(status="HAS_ID")

    if force_update:
        LegacyIssue.select(collection_acron, issn=issn, status="HAS_ISSUE").filter(**params).update(status="HAS_DATA")

    manager = Manager(user, collection_acron, issn, limit, timeout)
    manager.harvest_identifiers()
    manager.harvest_issues()


class LegacyIssueHarvester:
    """
    Harvester responsável apenas por fazer consultas à API ArticleMeta.
    """

    def __init__(
        self,
        collection_acron: str,
        issn: Optional[str] = None,
        from_date: Optional[str] = None,
        until_date: Optional[str] = None,
        limit: int = 1000,
        timeout: int = 30,
        offset: int = 0,
    ):
        """
        Inicializa o harvester de issues do ArticleMeta.
        """
        self.base_url_identifiers = "https://articlemeta.scielo.org/api/v1/issue/identifiers"
        self.base_url_issue = "https://articlemeta.scielo.org/api/v1/issue"
        self.collection_acron = collection_acron
        self.issn = issn
        self.from_date = from_date or "1997-01-01"
        self.until_date = until_date or datetime.utcnow().isoformat()[:10]
        self.limit = limit or 1000
        self.timeout = timeout or 30
        self.offset = offset or 0

    def _build_params(self, offset: int = 0, limit: Optional[int] = None) -> dict:
        """
        Constrói parâmetros para requisições à API.
        """
        params = {
            "collection": self.collection_acron,
            "limit": limit or self.limit,
            "offset": offset,
        }
        
        if self.issn:
            params["issn"] = self.issn
        if self.from_date:
            params["from"] = self.from_date
        if self.until_date:
            params["until"] = self.until_date
            
        return {k: v for k, v in params.items() if v is not None}

    def get_total_issues(self) -> int:
        """
        Obtém o total de issues do ArticleMeta.
        """
        try:
            params = self._build_params(offset=0, limit=1)
            url = f"{self.base_url_identifiers}?{urlencode(params)}"
            
            response = fetch_data(url, json=True, timeout=self.timeout, verify=True)
            return response.get("meta", {}).get("total", 0)
            
        except Exception as exc:
            logging.error(f"Error getting total from ArticleMeta: {exc}")
            return 0

    def fetch_issue_data(self, issue_code: str) -> Optional[dict]:
        """
        Busca dados completos de um issue específico.
        """
        try:
            url = (
                f"{self.base_url_issue}?"
                f"code={issue_code}&collection={self.collection_acron}"
            )
            
            return fetch_data(url, json=True, timeout=self.timeout, verify=True)
            
        except Exception as exc:
            logging.error(f"Error fetching issue data for {issue_code}: {exc}")
            return None

    def harvest_identifiers(self) -> Generator[Dict[str, Any], None, None]:
        """
        Gera identificadores dos issues do ArticleMeta.
        """
        offset = self.offset

        while True:
            try:
                params = self._build_params(offset)
                url = f"{self.base_url_identifiers}?{urlencode(params)}"

                logging.info(f"Fetching AM issue identifiers from: {url}")

                response = fetch_data(url, json=True, timeout=self.timeout, verify=True)
                objects = response.get("objects", [])

                if not objects:
                    logging.info(f"No more issues found for collection {self.collection_acron}")
                    break

                for item in objects:
                    if item.get("code"):
                        yield item
                    else:
                        logging.warning(f"Issue without code: {item}")

                meta = response.get("meta", {})
                total = meta.get("total", 0)
                
                if len(objects) < self.limit or offset + self.limit >= total:
                    logging.info(f"Reached last page for collection {self.collection_acron}")
                    break

                offset += self.limit

            except Exception as e:
                logging.error(f"Error harvesting AM issues: {e}")
                break


# ============================================================================
# Funções de interoperação entre LegacyIssueHarvester e LegacyIssue
# ============================================================================

class Manager:
    def __init__(self, user, collection_acron, issn, limit=None, timeout=None):
        self.user = user
        self.collection_acron = collection_acron
        self.issn = issn
        self.h = LegacyIssueHarvester(
            collection_acron=collection_acron,
            issn=issn,
            limit=limit,
            timeout=timeout,
        )

    def has_all_identifiers(self):
        return self.h.get_total_issues() == LegacyIssue.select(self.collection_acron, issn=self.issn).count()

    def harvest_identifiers(self):
        legacy_issue = LegacyIssue.select(self.collection_acron, issn=self.issn).order_by("-processing_date").first()
        from_date = None
        if legacy_issue:
            from_date = legacy_issue.processing_date
        harvester = LegacyIssueHarvester(
            collection_acron=self.collection_acron,
            issn=self.issn,
            from_date=from_date,
        )
        for item in harvester.harvest_identifiers():
            try:
                legacy_issue = LegacyIssue.create_or_update(
                    collection=self.collection_acron,
                    pid=item["code"],
                    data=item,
                    processing_date=item["processing_date"],
                )
            except Exception as e:
                continue

    def harvest_issues(self):
        legacy_issues = LegacyIssue.select(
            self.collection_acron,
            issn=self.issn,
            status="HAS_ID",
        )
        for legacy_issue in legacy_issues:
            self.fetch_issue_data(legacy_issue)

    def fetch_issue_data(self, legacy_issue):
        try:
            issue_data = self.h.fetch_issue_data(legacy_issue.pid)
            if issue_data and issue_data.get("issue"):
                legacy_issue.processing_date = issue_data.get("processing_date")
                legacy_issue.data = issue_data
                legacy_issue.status = "HAS_DATA"
                legacy_issue.save()
                return issue_data
        except Exception as exc:
            return

    def create_or_update_issues(self):
        legacy_issues = LegacyIssue.select(
            self.collection_acron,
            issn=self.issn,
            status="HAS_DATA",
        )
        for legacy_issue in legacy_issues:
            self.create_or_update_issue(legacy_issue)

    def create_or_update_issue(self, legacy_issue):
        try:
            issue = create_or_update_issue(
                user=self.user,
                issue_data=legacy_issue.data["issue"],
                collection_acron=self.collection_acron,
                issn=self.issn
            )
            issue.legacy_issues.add(legacy_issue)
            legacy_issue.status = "HAS_ISSUE"
            legacy_issue.save()
        except Exception as exc:
            pass
