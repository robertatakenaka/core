import hashlib
import logging

from django.utils.translation import gettext as _
from pid_provider import exceptions


LOGGER = logging.getLogger(__name__)
LOGGER_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class PidProviderXMLAdapter:

    def __init__(self, xml_with_pre, pkg_name=None):
        self.xml_with_pre = xml_with_pre
        self.pkg_name = pkg_name

    def __getattr__(self, name):
        logging.debug(type(self.xml_with_pre))
        try:
            return getattr(self.xml_with_pre, name)
        except Exception as e:
            logging.exception(e)
            raise AttributeError(
                f"Unable to get PidProviderXMLAdapter.{name} {type(e)} {e}")

    @property
    def v2_prefix(self):
        return f"S{self.journal_issn_electronic or self.journal_issn_print}{self.pub_year}"

    @property
    def links(self):
        if not hasattr(self, '_links') or not self._links:
            self._links = _str_with_64_char("|".join(self.xml_with_pre.links))
        return self._links

    @property
    def collab(self):
        if not hasattr(self, '_collab') or not self._collab:
            self._collab = _str_with_64_char(self.xml_with_pre.collab)
        return self._collab

    @property
    def surnames(self):
        if not hasattr(self, '_surnames') or not self._surnames:
            self._surnames = _str_with_64_char(
                "|".join([
                    _standardize(person.get("surname"))
                    for person in self.authors.get("person")
                ]))
        return self._surnames

    @property
    def article_titles_texts(self):
        if not hasattr(self, '_article_titles_texts') or not self._article_titles_texts:
            self._article_titles_texts = None
            if self.xml_with_pre.article_titles_texts:
                self._article_titles_texts = _str_with_64_char(
                    "|".join(sorted(self.xml_with_pre.article_titles_texts)))
        return self._article_titles_texts

    @property
    def partial_body(self):
        if not hasattr(self, '_partial_body') or not self._partial_body:
            self._partial_body = _str_with_64_char(self.xml_with_pre.partial_body)
        return self._partial_body

    def query_params(self, filter_by_issue=False, aop_version=False):
        """
        Get query parameters

        Arguments
        ---------
        filter_by_issue: bool
        aop_version: bool

        Returns
        -------
        dict
        """
        _params = dict(
            z_surnames=self.surnames or None,
            z_collab=self.collab or None,
        )
        if not any(_params.values()):
            _params['main_doi'] = self.main_doi

        if not any(_params.values()):
            _params['z_links'] = self.links

        if not any(_params.values()):
            _params['z_partial_body'] = self.partial_body

        if not any(_params.values()):
            _params['pkg_name'] = self.pkg_name

        _params['elocation_id'] = self.elocation_id
        if aop_version:
            _params['issue__isnull'] = True
        else:
            if filter_by_issue:
                _params['issue__pub_year'] = self.pub_year
                _params['issue__volume'] = self.volume
                _params['issue__number'] = self.number
                _params['issue__suppl'] = self.suppl
                _params['fpage'] = self.fpage
                _params['fpage_seq'] = self.fpage_seq
                _params['lpage'] = self.lpage

        _params["journal__issn_print"] = self.journal_issn_print
        _params["journal__issn_electronic"] = self.journal_issn_electronic
        _params['article_pub_year'] = self.article_pub_year
        _params['z_article_titles_texts'] = self.article_titles_texts

        LOGGER.info(_params)
        return _params

    def validate_query_params(self, query_params):
        """
        Validate query parameters

        Arguments
        ---------
        filter_by_issue: bool
        aop_version: bool

        Returns
        -------
        bool
        """
        _params = query_params
        if not any([
                _params.get("journal__issn_print"),
                _params.get("journal__issn_electronic"),
                ]):
            raise exceptions.NotEnoughParametersToGetDocumentRecordError(
                _("No attribute enough for disambiguations {}").format(
                    _params,
                )
            )

        if not any([
                _params.get("article_pub_year"),
                _params.get("issue__pub_year"),
                ]):
            raise exceptions.NotEnoughParametersToGetDocumentRecordError(
                _("No attribute enough for disambiguations {}").format(
                    _params,
                )
            )

        if any([
                _params.get('main_doi'),
                _params.get('fpage'),
                _params.get('elocation_id'),
                ]):
            return True

        if not any([
                _params.get('z_surnames'),
                _params.get('z_collab'),
                _params.get('z_links'),
                _params.get('pkg_name'),
                ]):
            raise exceptions.NotEnoughParametersToGetDocumentRecordError(
                _("No attribute enough for disambiguations {}").format(
                    _params,
                ))
        return True

    @property
    def query_list(self):
        LOGGER.info(f"self.is_aop: {self.is_aop}")
        if self.is_aop:
            # o xml_adapter não contém dados de issue
            # não indica na consulta o valor para o atributo issue
            # então o registro encontrado pode ou não ter dados de issue
            params = self.query_params(aop_version=False)
            if self.validate_query_params(params):
                yield params
        else:
            # o xml_adapter contém dados de issue
            # inclui na consulta os dados de issue
            params = self.query_params(filter_by_issue=True)
            if self.validate_query_params(params):
                yield params

            # busca por registro cujo valor de issue is None
            params = self.query_params(aop_version=True)
            if self.validate_query_params(params):
                yield params


def _standardize(text):
    return (text or '').strip().upper()


def _str_with_64_char(text):
    """
    >>> import hashlib
    >>> m = hashlib.sha256()
    >>> m.update(b"Nobody inspects")
    >>> m.update(b" the spammish repetition")
    >>> m.digest()
    b'\x03\x1e\xdd}Ae\x15\x93\xc5\xfe\\\x00o\xa5u+7\xfd\xdf\xf7\xbcN\x84:\xa6\xaf\x0c\x95\x0fK\x94\x06'
    >>> m.digest_size
    32
    >>> m.block_size
    64
    hashlib.sha224(b"Nobody inspects the spammish repetition").hexdigest()
    """
    if not text:
        return None
    return hashlib.sha256(_standardize(text).encode("utf-8")).hexdigest()
