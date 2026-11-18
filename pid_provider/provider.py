from core.utils.profiling_tools import profile_method, profile_staticmethod
from pid_provider.base_pid_provider import BasePidProvider
from pid_provider.models import PidProviderXML
from pid_provider.multi_collection import (
    get_journal_pid_from_v2,
    get_xml_collections,
    normalize_acron,
)


def get_xml_collection_acron(xml_with_pre, xml_collections):
    """
    Identifica a coleção de origem do XML que não a informa (custom-meta)
    entre as coleções do periódico (ver get_xml_collections)

    Restringe as coleções do periódico, nesta ordem:
    - pelo PID do periódico contido no pid v2 (issn_scielo)
    - pelo acrônimo do periódico

    Returns
    -------
    str
        acrônimo da coleção ou None, se não houver uma única coleção candidata
        (ex.: periódico com o mesmo PID e acrônimo em mais de uma coleção)
    """
    journal_pid = get_journal_pid_from_v2(xml_with_pre.v2)
    criteria = (
        ("journal_pid", journal_pid and journal_pid.upper()),
        ("journal_acron", normalize_acron(xml_with_pre.journal_acron)),
    )
    candidates = list(xml_collections)
    for key, value in criteria:
        if len(candidates) <= 1:
            break
        if not value:
            continue
        matched = [
            item
            for item in candidates
            if normalize_acron(item[key]) == value.lower()
        ]
        if matched:
            candidates = matched
    if len(candidates) == 1:
        return candidates[0]["collection"].acron3
    return None


class PidProvider(BasePidProvider):
    """
    Recebe XML para validar ou atribuir o ID do tipo v3
    """

    @profile_method
    def provide_pid_for_xml_with_pre(
        self, xml_with_pre, name, user, collection_acron=None, **kwargs
    ):
        """
        Core: completa a coleção de origem do XML (custom-meta) antes do
        registro, que é comum ao Upload, onde a coleção sempre está no XML.

        No Core, o XML pode chegar sem a coleção, por exemplo, enviado
        (API) por versão do Upload anterior à inserção da coleção no XML.
        Sem a coleção, o pid v2 e a versão do XML por coleção
        (CollectionPidV2) não seriam registrados quando o periódico está em
        mais de uma coleção. Não identificada uma única coleção, o registro
        segue sem ela (registro legado), como no Upload.
        """
        if not xml_with_pre.collection and not collection_acron:
            collection_acron = get_xml_collection_acron(
                xml_with_pre, get_xml_collections(xml_with_pre)
            )
        return super().provide_pid_for_xml_with_pre(
            xml_with_pre, name, user, collection_acron=collection_acron, **kwargs
        )

    @staticmethod
    @profile_staticmethod
    def get_xmltree(pid_v3):
        try:
            return PidProviderXML.get_xml_with_pre(pid_v3).xmltree
        except (PidProviderXML.DoesNotExist, AttributeError):
            return None

    @staticmethod
    @profile_staticmethod
    def get_sps_pkg_name(pid_v3):
        try:
            return PidProviderXML.get_xml_with_pre(pid_v3).sps_pkg_name
        except (PidProviderXML.DoesNotExist, AttributeError):
            return None

    # OBSOLETO: o pid v2 é corrigido por coleção em proc.models.ArticleProc.fix_pid_v2
    @profile_method
    def fix_pid_v2(self, user, pid_v3, correct_pid_v2):
        return PidProviderXML.fix_pid_v2(user, pid_v3, correct_pid_v2)
