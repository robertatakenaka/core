import logging
import sys
import traceback
from datetime import datetime, timedelta

from celery import group
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Subquery
from django.utils.translation import gettext_lazy as _

from article import controller
from article.destination.articlemeta import (
    bulk_data_export_to_articlemeta,
    export_article_to_articlemeta,
)
from article.models import Article, ArticleFormat, ArticleSource, ArticleExportDestination
from article.sources.preprint import harvest_preprints
from article.sources.xmlsps import load_article
from article.utils.harvesters import AMHarvester, OPACHarvester
from collection.models import Collection
from config import celery_app
from core.utils.utils import _get_user, fetch_data
from journal.models import SciELOJournal
from pid_provider.choices import PPXML_STATUS_DONE, PPXML_STATUS_TODO
from pid_provider.models import PidProviderXML
from pid_provider.provider import PidProvider
from researcher.models import ResearcherIdentifier
from tracker.models import UnexpectedEvent

User = get_user_model()


# ==============================================================================
# MÓDULO DE TAREFAS CELERY PARA PROCESSAMENTO DE ARTIGOS CIENTÍFICOS
# ==============================================================================
"""
Este módulo contém tarefas assíncronas Celery para o sistema de gerenciamento
de artigos científicos da plataforma SciELO. As tarefas cobrem todo o ciclo
de vida dos artigos, desde a importação até a exportação.

Categorias principais de tarefas:
1. Importação e Carregamento - Coleta de artigos de diversas fontes
2. Atualização de Dados - Complementação e normalização de informações
3. Limpeza e Manutenção - Remoção de duplicatas e dados órfãos
4. Conversão de Formatos - Geração de PDF, HTML e outros formatos
5. Exportação - Envio de artigos para sistemas externos

Dependências principais:
- Celery: Framework de tarefas assíncronas
- Django: ORM e autenticação
- MongoDB: Armazenamento via ArticleMeta
- XML/JATS: Formato padrão dos artigos científicos
"""

# ==============================================================================
# SUMÁRIO DE TAREFAS / TASK SUMMARY
# ==============================================================================
#
# TAREFAS DE IMPORTAÇÃO E CARREGAMENTO / IMPORT AND LOADING TASKS
# ----------------------------------------------------------------
# - load_preprint: Coleta preprints de servidor OAI-PMH
# - task_select_articles_to_load_from_api: Orquestra carregamento de múltiplas coleções
# - task_select_articles_to_load_from_collection_endpoint: Coleta artigos de uma coleção específica
# - task_load_article_from_xml_endpoint: Processa um XML de endpoint específico
# - task_select_articles_to_load_from_article_source: Processa XMLs pendentes em ArticleSource
# - task_select_articles_to_load_from_pid_provider: Carrega artigos de PidProviderXML
# - task_load_article_from_pp_xml: Carrega um artigo específico do PidProviderXML
#
# TAREFAS DE ATUALIZAÇÃO DE DADOS / DATA UPDATE TASKS
# ----------------------------------------------------
# - task_select_articles_to_complete_data: Dispara complementação em lote
# - task_complete_article_data: Completa dados de um artigo específico
# - task_select_emails_to_normalize: Normaliza emails em ResearcherIdentifier
#
# TAREFAS DE LIMPEZA E MANUTENÇÃO / CLEANUP TASKS
# -----------------------------------------------
# - task_mark_articles_as_deleted_without_pp_xml: Marca artigos órfãos como deletados
# - task_remove_duplicate_articles: Remove artigos duplicados por pid_v3
#
# TAREFAS DE CONVERSÃO DE FORMATOS / FORMAT CONVERSION TASKS
# ---------------------------------------------------------
# - task_convert_xml_to_other_formats_for_articles: Dispara conversão em lote
# - convert_xml_to_other_formats: Converte XML para PDF/HTML/outros
#
# TAREFAS DE EXPORTAÇÃO / EXPORT TASKS
# -----------------------------------
# - task_select_articles_to_export_to_articlemeta: Exporta lote para ArticleMeta
# - task_export_article_to_articlemeta: Exporta artigo individual para ArticleMeta
# ==============================================================================


# ==============================================================================
# TAREFAS DE IMPORTAÇÃO E CARREGAMENTO / IMPORT AND LOADING TASKS
# ==============================================================================


@celery_app.task(bind=True, name=_("load_preprints"))
def load_preprint(self, user_id, oai_pmh_preprint_uri):
    """
    Coleta e carrega preprints de um servidor OAI-PMH.

    Utiliza o protocolo OAI-PMH (Open Archives Initiative Protocol for Metadata
    Harvesting) para coletar metadados e XMLs de preprints.

    Args:
        self: Instância da tarefa Celery
        user_id (int): ID do usuário executando a tarefa
        oai_pmh_preprint_uri (str): URI do servidor OAI-PMH de preprints
            Ex: "https://preprints.scielo.org/index.php/scielo/oai"

    Returns:
        None

    Raises:
        User.DoesNotExist: Se o usuário não for encontrado

    Side Effects:
        - Cria/atualiza registros de preprints no banco
        - Registra logs de progresso da coleta

    Notes:
        - TODO: Implementar filtros para coleta incremental
        - A função atualmente coleta todos os registros disponíveis
    """
    user = User.objects.get(pk=user_id)
    ## TODO: fazer filtro para não coletar tudo sempre
    harvest_preprints(oai_pmh_preprint_uri, user)


@celery_app.task(bind=True, name="task_select_articles_to_load_from_api")
def task_select_articles_to_load_from_api(
    self,
    username=None,
    user_id=None,
    collection_acron_list=None,
    from_date=None,
    until_date=None,
    limit=None,
    timeout=None,
    force_update=None,
    auto_solve_pid_conflict=None,
    opac_url=None,
):
    """
    Tarefa orquestradora para carregar artigos de múltiplas coleções via API.

    Dispara tarefas paralelas para cada coleção, otimizando o processamento
    em larga escala. Se nenhuma coleção for especificada, processa todas as
    coleções conhecidas do SciELO.

    Args:
        self: Instância da tarefa Celery
        username (str, optional): Nome do usuário executando a tarefa
        user_id (int, optional): ID do usuário executando a tarefa
        collection_acron_list (list, optional): Lista de acrônimos das coleções.
            Se None, usa lista padrão com todas as coleções SciELO.
            Ex: ["scl", "arg", "mex", "esp"]
        from_date (str, optional): Data inicial para coleta (formato ISO)
        until_date (str, optional): Data final para coleta (formato ISO)
        limit (int, optional): Limite de artigos por coleção
        timeout (int, optional): Timeout em segundos para requisições HTTP
        force_update (bool, optional): Força atualização mesmo se já existe
        auto_solve_pid_conflict (bool, optional): Resolve conflitos de PID automaticamente

    Returns:
        None

    Side Effects:
        - Garante que coleções estão carregadas no banco
        - Dispara uma tarefa para cada coleção em collection_acron_list
        - Registra UnexpectedEvent em caso de erro

    Examples:
        # Carregar artigos de coleções específicas
        task_select_articles_to_load_from_api.delay(
            collection_acron_list=["scl", "mex"],
            from_date="2024-01-01",
            until_date="2024-12-31"
        )

        # Carregar artigos de todas as coleções com limite
        task_select_articles_to_load_from_api.delay(
            limit=100,
            force_update=True
        )
    """
    try:
        user = _get_user(self.request, username=username, user_id=user_id)

        # Define coleções padrão se não especificadas
        if not collection_acron_list:
            collection_acron_list = [
                "scl",  # Brasil
                "arg",
                "bol",
                "chl",
                "col",
                "cri",
                "cub",
                "ecu",
                "esp",
                "mex",
                "prt",
                "pry",
                "sza",
                "ury",
                "ven",
                "wid",
                "psi",
                "rve",
                "spa",  # Coleções temáticas
            ]

        # Garante que as coleções estão carregadas no banco
        if Collection.objects.count() == 0:
            Collection.load(user)

        # Dispara tarefa para cada coleção
        for collection_acron in collection_acron_list:
            task_select_articles_to_load_from_collection_endpoint.apply_async(
                kwargs={
                    "username": username,
                    "user_id": user_id,
                    "collection_acron": collection_acron,
                    "from_date": from_date,
                    "until_date": until_date,
                    "limit": limit,
                    "timeout": timeout,
                    "force_update": force_update,
                    "auto_solve_pid_conflict": auto_solve_pid_conflict,
                    "opac_url": opac_url,
                }
            )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "task_select_articles_to_load_from_api",
                "collection_acron_list": collection_acron_list,
                "from_date": from_date,
                "until_date": until_date,
                "limit": limit,
                "timeout": timeout,
            },
        )


@celery_app.task(
    bind=True, name="task_select_articles_to_load_from_collection_endpoint"
)
def task_select_articles_to_load_from_collection_endpoint(
    self,
    username=None,
    user_id=None,
    collection_acron=None,
    from_date=None,
    until_date=None,
    limit=None,
    timeout=None,
    force_update=None,
    auto_solve_pid_conflict=None,
    opac_url=None,
):
    """
    Coleta artigos de uma coleção específica via endpoint OPAC ou ArticleMeta.

    Utiliza harvesters especializados para cada tipo de endpoint:
    - OPACHarvester: Para coleção Brasil (scl)
    - AMHarvester: Para demais coleções via ArticleMeta

    Args:
        self: Instância da tarefa Celery
        username (str, optional): Nome do usuário executando a tarefa
        user_id (int, optional): ID do usuário executando a tarefa
        collection_acron (str): Acrônimo da coleção (obrigatório).
            Ex: "scl", "mex", "arg"
        from_date (str, optional): Data inicial para coleta (formato ISO)
        until_date (str, optional): Data final para coleta (formato ISO)
        limit (int, optional): Limite de documentos a coletar
        timeout (int, optional): Timeout em segundos para requisições
        force_update (bool, optional): Força atualização de artigos existentes
        auto_solve_pid_conflict (bool, optional): Resolve conflitos de PID

    Returns:
        None

    Raises:
        ValueError: Se collection_acron não for fornecido

    Side Effects:
        - Dispara task_load_article_from_xml_endpoint para cada documento
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - OPAC é usado apenas para Brasil (scl) por questões de performance
        - ArticleMeta é usado para todas as outras coleções
    """
    try:
        if not collection_acron:
            raise ValueError("Missing collection_acron")

        # Seleciona o harvester apropriado baseado na coleção
        if collection_acron == "scl":
            harvester = OPACHarvester(
                opac_url or "www.scielo.br",
                collection_acron,
                from_date=from_date,
                until_date=until_date,
                limit=limit,
                timeout=timeout,
            )
        else:
            harvester = AMHarvester(
                collection_acron,
                from_date=from_date,
                until_date=until_date,
                limit=limit,
                timeout=timeout,
            )

        # Itera sobre documentos e dispara tarefas individuais
        for document in harvester.harvest_documents():
            task_load_article_from_xml_endpoint.delay(
                username,
                user_id,
                document["xml_url"],
                document.get("processing_date") or document["metadata"]["updated_at"],
                force_update,
                auto_solve_pid_conflict,
            )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "task_select_articles_to_load_from_collection_endpoint",
                "collection_acron": collection_acron,
                "from_date": from_date,
                "until_date": until_date,
                "limit": limit,
                "timeout": timeout,
                "force_update": force_update,
            },
        )


@celery_app.task(bind=True, name="task_load_article_from_xml_endpoint")
def task_load_article_from_xml_endpoint(
    self,
    username=None,
    user_id=None,
    xml_url=None,
    source_date=None,
    force_update=None,
    auto_solve_pid_conflict=None,
):
    """
    Carrega um artigo individual a partir de uma URL de XML.

    Cria ou atualiza um ArticleSource e processa o XML para criar/atualizar
    o artigo no banco de dados.

    Args:
        self: Instância da tarefa Celery
        username (str, optional): Nome do usuário executando a tarefa
        user_id (int, optional): ID do usuário executando a tarefa
        xml_url (str): URL do XML do artigo
            Ex: "https://www.scielo.br/scielo.php?script=sci_arttext&pid=..."
        source_date (str, optional): Data de última atualização na fonte
        force_update (bool, optional): Força reprocessamento mesmo se já completado
        auto_solve_pid_conflict (bool, optional): Resolve conflitos de PID automaticamente

    Returns:
        None

    Side Effects:
        - Cria/atualiza registro ArticleSource
        - Processa XML e cria/atualiza Article
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - Pula processamento se ArticleSource já está COMPLETED e force_update=False
        - XML é baixado e armazenado localmente antes do processamento
    """
    try:
        user = _get_user(self.request, username=username, user_id=user_id)

        # Cria ou atualiza ArticleSource
        article_source = ArticleSource.create_or_update(
            user=user,
            url=xml_url,
            source_date=source_date,
            force_update=force_update,
        )

        # Pula se já processado e não é atualização forçada
        if article_source.status == ArticleSource.StatusChoices.COMPLETED:
            return

        # Processa o XML
        article_source.process_xml(
            user=user,
            load_article=load_article,
            force_update=force_update,
            auto_solve_pid_conflict=auto_solve_pid_conflict,
        )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "task_load_article_from_xml_endpoint",
                "xml_url": xml_url,
                "source_date": source_date,
                "force_update": force_update,
            },
        )


@celery_app.task(bind=True, name="task_select_articles_to_load_from_article_source")
def task_select_articles_to_load_from_article_source(
    self,
    username=None,
    user_id=None,
    from_date=None,
    until_date=None,
    force_update=None,
    auto_solve_pid_conflict=None,
):
    """
    Processa ArticleSources pendentes ou que necessitam reprocessamento.

    Busca ArticleSources com status pendente ou erro e processa seus XMLs.
    Útil para reprocessar falhas anteriores ou completar processamentos interrompidos.

    Args:
        self: Instância da tarefa Celery
        username (str, optional): Nome do usuário executando a tarefa
        user_id (int, optional): ID do usuário executando a tarefa
        from_date (str, optional): Data inicial para filtrar ArticleSources
        until_date (str, optional): Data final para filtrar ArticleSources
        force_update (bool, optional): Força reprocessamento de todos
        auto_solve_pid_conflict (bool, optional): Resolve conflitos de PID

    Returns:
        None

    Side Effects:
        - Processa XMLs de ArticleSources selecionados
        - Atualiza status dos ArticleSources
        - Registra UnexpectedEvent em caso de erro

    Examples:
        # Reprocessar falhas dos últimos 7 dias
        task_select_articles_to_load_from_article_source.delay(
            from_date=(datetime.now() - timedelta(days=7)).isoformat(),
            force_update=True
        )
    """
    try:
        user = _get_user(self.request, username=username, user_id=user_id)

        # Obtém queryset de ArticleSources para processar
        for article_source in ArticleSource.get_queryset_to_complete_data(
            from_date,
            until_date,
            force_update,
        ):
            article_source.process_xml(
                user=user,
                load_article=load_article,
                force_update=force_update,
                auto_solve_pid_conflict=auto_solve_pid_conflict,
            )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "task_select_articles_to_load_from_article_source",
                "from_date": from_date,
                "until_date": until_date,
                "force_update": force_update,
            },
        )


@celery_app.task(bind=True, name="task_select_articles_to_load_from_pid_provider")
def task_select_articles_to_load_from_pid_provider(
    self,
    user_id=None,
    username=None,
    collection_acron_list=None,
    journal_acron_list=None,
    from_pub_year=None,
    until_pub_year=None,
    from_updated_date=None,
    until_updated_date=None,
    proc_status_list=None,
    export_to_articlemeta=None,
    force_update=None,
):
    """
    Carrega artigos em lote a partir de registros PidProviderXML.

    PidProviderXML é o sistema central de gerenciamento de PIDs (identificadores
    persistentes) dos artigos. Esta tarefa processa XMLs armazenados no sistema
    de PIDs.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        collection_acron_list (list, optional): Lista de acrônimos de coleções
        journal_acron_list (list, optional): Lista de acrônimos de periódicos
        from_pub_year (int, optional): Ano inicial de publicação
        until_pub_year (int, optional): Ano final de publicação
        from_updated_date (str, optional): Data inicial de atualização
        until_updated_date (str, optional): Data final de atualização
        proc_status_list (list, optional): Lista de status a processar
            Ex: [PPXML_STATUS_TODO, PPXML_STATUS_ERROR]
        export_to_articlemeta (bool, optional): Exporta para ArticleMeta após carregar

    Returns:
        None

    Side Effects:
        - Dispara task_load_article_from_pp_xml para cada PidProviderXML
        - Exporta para ArticleMeta se export_to_articlemeta=True
        - Registra UnexpectedEvent em caso de erro

    Examples:
        # Carregar artigos de 2024 de periódicos específicos
        task_select_articles_to_load_from_pid_provider.delay(
            journal_acron_list=["abc", "xyz"],
            from_pub_year=2024,
            until_pub_year=2024,
            export_to_articlemeta=True
        )
    """
    try:
        user = _get_user(self.request, username, user_id)

        # Busca PidProviderXMLs baseado nos filtros
        pp_xml_items = controller.get_pp_xml_ids_to_load_articles(
            collection_acron_list=collection_acron_list,
            journal_acron_list=journal_acron_list,
            from_pub_year=from_pub_year,
            until_pub_year=until_pub_year,
            from_updated_date=from_updated_date,
            until_updated_date=until_updated_date,
            proc_status_list=proc_status_list,
        )

        # Cria grupo de tarefas para processamento paralelo
        group(
            task_load_article_from_pp_xml.s(
                pp_xml_id=pp_xml_id,
                user_id=user_id or user.id,
                username=username or user.username,
                collection_acron_list=collection_acron_list,
                export_to_articlemeta=export_to_articlemeta,
                force_update=force_update,
            )
            for pp_xml_id in pp_xml_items
        ).apply_async()

    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_select_articles_to_load_from_pid_provider",
                "collection_acron_list": collection_acron_list,
                "journal_acron_list": journal_acron_list,
                "from_pub_year": from_pub_year,
                "until_pub_year": until_pub_year,
                "from_updated_date": from_updated_date,
                "until_updated_date": until_updated_date,
                "proc_status_list": proc_status_list,
                "export_to_articlemeta": export_to_articlemeta,
            },
        )


@celery_app.task(bind=True, name="task_load_article_from_pp_xml")
def task_load_article_from_pp_xml(
    self,
    pp_xml_id,
    user_id=None,
    username=None,
    collection_acron_list=None,
    export_to_articlemeta=None,
    force_update=None,
):
    """
    Carrega um artigo específico a partir de um PidProviderXML.

    Processa o XML armazenado no PidProviderXML, cria/atualiza o Article
    e opcionalmente exporta para ArticleMeta.

    Args:
        self: Instância da tarefa Celery
        pp_xml_id (int): ID do PidProviderXML a processar (obrigatório)
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        export_to_articlemeta (bool, optional): Exporta para ArticleMeta após carregar

    Returns:
        None

    Side Effects:
        - Cria/atualiza Article no banco
        - Atualiza status do PidProviderXML para DONE
        - Verifica disponibilidade do artigo
        - Exporta para ArticleMeta se solicitado
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - O XML é lido diretamente do arquivo armazenado no PidProviderXML
        - A verificação de disponibilidade valida URLs e assets do artigo
    """
    try:
        user = _get_user(self.request, username, user_id)

        # Busca o PidProviderXML com suas relações
        pp_xml = PidProviderXML.objects.select_related("current_version").get(
            id=pp_xml_id
        )

        # Carrega o artigo do arquivo XML
        article = load_article(
            user,
            file_path=pp_xml.current_version.file.path,
            v3=pp_xml.v3,
            pp_xml=pp_xml,
        )

        # Verifica disponibilidade (URLs, assets, etc)
        article.check_availability(user)

        # Exporta para ArticleMeta se solicitado
        if export_to_articlemeta:
            destination = ArticleExportDestination.get_or_create("articlemeta", user)
            version = None
            export_article_to_articlemeta(
                user,
                article,
                destination,
                collection_acron_list,
                version,
                force_update,
            )

    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_load_article_from_pp_xml",
                "pp_xml_id": pp_xml_id,
                "export_to_articlemeta": export_to_articlemeta,
                "force_update": force_update,
            },
        )


# ==============================================================================
# TAREFAS DE ATUALIZAÇÃO E COMPLEMENTAÇÃO DE DADOS / DATA UPDATE TASKS
# ==============================================================================


@celery_app.task(bind=True, name="task_select_articles_to_complete_data")
def task_select_articles_to_complete_data(
    self,
    user_id=None,
    username=None,
    collection_acron_list=None,
    journal_acron_list=None,
    from_pub_year=None,
    until_pub_year=None,
    force_update=None,
    from_updated_date=None,
    until_updated_date=None,
    data_status_list=None,
    valid=None,
    pp_xml__isnull=None,
    sps_pkg_name__isnull=None,
    article_license__isnull=None,
):
    """
    Dispara complementação de dados para artigos incompletos.

    Identifica artigos com dados faltantes e dispara tarefas individuais
    para completar informações como sps_pkg_name, licença, etc.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        collection_acron_list (list, optional): Filtro por coleções
        journal_acron_list (list, optional): Filtro por periódicos
        from_pub_year (int, optional): Ano inicial de publicação
        until_pub_year (int, optional): Ano final de publicação
        force_update (bool, optional): Força atualização de todos
        from_updated_date (str, optional): Data inicial de atualização
        until_updated_date (str, optional): Data final de atualização
        data_status_list (list, optional): Lista de status de dados
        valid (bool, optional): Filtro por artigos válidos
        pp_xml__isnull (bool, optional): Filtro por presença de pp_xml
        sps_pkg_name__isnull (bool, optional): Filtro por presença de sps_pkg_name
        article_license__isnull (bool, optional): Filtro por presença de licença

    Returns:
        None

    Side Effects:
        - Dispara task_complete_article_data para cada artigo selecionado
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - Por padrão, busca artigos sem pp_xml, sps_pkg_name ou licença
        - Útil para manutenção e limpeza de dados
    """
    try:
        user = _get_user(self.request, username, user_id)

        # Seleciona artigos baseado nos filtros
        articles = Article.select_articles(
            collection_acron_list=collection_acron_list,
            journal_acron_list=journal_acron_list,
            from_pub_year=from_pub_year,
            until_pub_year=until_pub_year,
            from_updated_date=from_updated_date,
            until_updated_date=until_updated_date,
            data_status_list=data_status_list,
            valid=valid,
            pp_xml__isnull=pp_xml__isnull or True,  # Padrão: sem pp_xml
            sps_pkg_name__isnull=sps_pkg_name__isnull
            or True,  # Padrão: sem sps_pkg_name
            article_license__isnull=article_license__isnull
            or True,  # Padrão: sem licença
        )

        # Dispara tarefa para cada artigo
        for item_id in articles.values_list("id", flat=True):
            try:
                task_complete_article_data.apply_async(
                    kwargs={
                        "user_id": user.id,
                        "username": user.username,
                        "item_id": item_id,
                        "force_update": force_update,
                    }
                )
            except Exception as exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                UnexpectedEvent.create(
                    exception=exception,
                    exc_traceback=exc_traceback,
                    detail={
                        "task": "article.tasks.task_select_articles_to_complete_data",
                        "item_id": item_id,
                    },
                )
    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_select_articles_to_complete_data",
                "collection_acron_list": collection_acron_list,
                "journal_acron_list": journal_acron_list,
                "from_pub_year": from_pub_year,
                "until_pub_year": until_pub_year,
                "from_updated_date": from_updated_date,
                "until_updated_date": until_updated_date,
                "data_status_list": data_status_list,
                "valid": valid,
                "pp_xml__isnull": pp_xml__isnull,
                "sps_pkg_name__isnull": sps_pkg_name__isnull,
                "article_license__isnull": article_license__isnull,
            },
        )


@celery_app.task(bind=True, name="task_complete_article_data")
def task_complete_article_data(
    self, user_id=None, username=None, item_id=None, force_update=None
):
    """
    Completa dados faltantes de um artigo específico.

    Busca PidProviderXML correspondente e completa informações como
    sps_pkg_name, licença, e outros metadados derivados.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        item_id (int): ID do artigo a processar (obrigatório)
        force_update (bool, optional): Força atualização mesmo se dados existem

    Returns:
        None

    Side Effects:
        - Atualiza campos do Article
        - Pode criar relações com PidProviderXML
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - Principal função é derivar sps_pkg_name do pid_v3
        - Também pode completar licença e outros metadados
    """
    user = _get_user(self.request, username, user_id)
    try:
        item = Article.objects.get(pk=item_id)

        # Tenta buscar PidProviderXML correspondente
        try:
            pp_xml = PidProviderXML.objects.get(v3=item.pid_v3)
        except PidProviderXML.DoesNotExist:
            pp_xml = None
        else:
            # Completa dados usando informações do PidProviderXML
            item.complete_data(pp_xml)

    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_complete_article_data",
                "item_id": item_id,
            },
        )


@celery_app.task(bind=True, name="task_select_emails_to_normalize")
def task_select_emails_to_normalize(self):
    """
    Normaliza emails armazenados em ResearcherIdentifier.

    Processa identificadores do tipo EMAIL, extraindo e normalizando
    o formato. Remove prefixos como "mailto:" e padroniza o formato.

    Args:
        self: Instância da tarefa Celery

    Returns:
        None

    Side Effects:
        - Atualiza campo identifier de ResearcherIdentifier
        - Realiza bulk_update para otimização

    Examples:
        Transforma:
        - "mailto:autor@exemplo.com" -> "autor@exemplo.com"
        - "AUTOR@EXEMPLO.COM" -> "autor@exemplo.com"
    """
    ResearcherIdentifier.task_select_emails_to_normalize()


# ==============================================================================
# TAREFAS DE LIMPEZA E MANUTENÇÃO / CLEANUP AND MAINTENANCE TASKS
# ==============================================================================


@celery_app.task(bind=True, name="task_mark_articles_as_deleted_without_pp_xml")
def task_mark_articles_as_deleted_without_pp_xml(self, user_id=None, username=None):
    """
    Marca artigos órfãos (sem PidProviderXML) como deletados.

    Identifica artigos que não possuem PidProviderXML associado e os marca
    com status DATA_STATUS_DELETED. Útil para limpeza após migração ou
    sincronização com sistema de PIDs.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        None

    Side Effects:
        - Atualiza data_status de artigos órfãos para DELETED
        - Registra quantidade atualizada no log
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - Só executa se houver discrepância entre total de PidProviderXML e Articles com pp_xml
        - Não remove fisicamente os artigos, apenas marca como deletados
    """
    try:
        user = _get_user(self.request, username, user_id)

        # Verifica se há discrepância
        if (
            PidProviderXML.objects.count()
            == Article.objects.filter(pp_xml__isnull=False).count()
        ):
            logging.info("No orphan articles found. Skipping.")
            return

        # Marca artigos órfãos como deletados
        updated_count = Article.mark_as_deleted_articles_without_pp_xml(user)

        logging.info(
            f"Task completed successfully. {updated_count} articles marked as deleted."
        )

    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_mark_articles_as_deleted_without_pp_xml",
            },
        )
        logging.error(
            f"Error in task_mark_articles_as_deleted_without_pp_xml: {exception}"
        )


@celery_app.task(bind=True, name="task_remove_duplicate_articles")
def task_remove_duplicate_articles(self, user_id=None, username=None, pid_v3=None):
    """
    Remove artigos duplicados baseado no pid_v3.

    Identifica artigos com mesmo pid_v3 e mantém apenas o mais antigo,
    removendo os demais. Considera apenas artigos marcados como inválidos.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário (não utilizado atualmente)
        username (str, optional): Nome do usuário (não utilizado atualmente)
        pid_v3 (str, optional): PID específico para remover duplicatas.
            Se None, processa todos os PIDs duplicados.

    Returns:
        None

    Side Effects:
        - Remove fisicamente artigos duplicados do banco
        - Mantém apenas o registro mais antigo de cada pid_v3
        - Registra UnexpectedEvent em caso de erro

    Examples:
        # Remover duplicatas de um PID específico
        task_remove_duplicate_articles.delay(pid_v3="S0001-37652024000100101")

        # Remover todas as duplicatas
        task_remove_duplicate_articles.delay()

    Notes:
        - Apenas artigos com valid=False são considerados para remoção
        - O artigo mais antigo (por created) é sempre mantido
    """
    ids_to_exclude = []
    try:
        if pid_v3:
            # Processa apenas um PID específico
            duplicates = (
                Article.objects.filter(pid_v3=pid_v3)
                .values("pid_v3")
                .annotate(pid_v3_count=Count("pid_v3"))
                .filter(pid_v3_count__gt=1, valid=False)
            )
        else:
            # Processa todos os PIDs duplicados
            duplicates = (
                Article.objects.values("pid_v3")
                .annotate(pid_v3_count=Count("pid_v3"))
                .filter(pid_v3_count__gt=1, valid=False)
            )

        # Coleta IDs dos duplicados (exceto o mais antigo)
        for duplicate in duplicates:
            article_ids = (
                Article.objects.filter(pid_v3=duplicate["pid_v3"])
                .order_by("created")[1:]  # Pula o primeiro (mais antigo)
                .values_list("id", flat=True)
            )
            ids_to_exclude.extend(article_ids)

        # Remove duplicados
        if ids_to_exclude:
            deleted_count = Article.objects.filter(id__in=ids_to_exclude).delete()[0]
            logging.info(f"Removed {deleted_count} duplicate articles")

    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_remove_duplicate_articles",
                "pid_v3": pid_v3,
            },
        )


# ==============================================================================
# TAREFAS DE CONVERSÃO E FORMATAÇÃO / CONVERSION AND FORMATTING TASKS
# ==============================================================================


@celery_app.task(bind=True, name="task_convert_xml_to_other_formats_for_articles")
def task_convert_xml_to_other_formats_for_articles(
    self, user_id=None, username=None, from_date=None, force_update=False
):
    """
    Dispara conversão de XML para outros formatos em lote.

    Processa artigos com sps_pkg_name definido, gerando versões em
    PDF, HTML, EPUB e outros formatos a partir do XML fonte.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        from_date (str, optional): Data inicial (não utilizado atualmente)
        force_update (bool): Se True, reconverte mesmo se já existe. Default: False

    Returns:
        None

    Side Effects:
        - Dispara convert_xml_to_other_formats para cada artigo
        - Registra UnexpectedEvent em caso de erro

    Notes:
        - Requer sps_pkg_name definido no artigo
        - Conversão pode ser demorada para artigos complexos
    """
    try:
        user = _get_user(self.request, username, user_id)

        # Processa apenas artigos com sps_pkg_name
        for item in Article.objects.filter(sps_pkg_name__isnull=False).iterator():
            logging.info(f"Processing conversion for: {item.pid_v3}")
            try:
                convert_xml_to_other_formats.apply_async(
                    kwargs={
                        "user_id": user.id,
                        "username": user.username,
                        "item_id": item.id,
                        "force_update": force_update,
                    }
                )
            except Exception as exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                UnexpectedEvent.create(
                    exception=exception,
                    exc_traceback=exc_traceback,
                    detail={
                        "task": "article.tasks.task_convert_xml_to_other_formats_for_articles",
                        "item": str(item),
                    },
                )
    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_convert_xml_to_other_formats_for_articles",
            },
        )


@celery_app.task(bind=True, name="convert_xml_to_other_formats")
def convert_xml_to_other_formats(
    self, user_id=None, username=None, item_id=None, force_update=None
):
    """
    Converte XML de um artigo específico para outros formatos.

    Gera versões do artigo em diferentes formatos (PDF, HTML, EPUB)
    usando ferramentas de conversão especializadas.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        item_id (int): ID do artigo a converter (obrigatório)
        force_update (bool, optional): Força reconversão se já existe

    Returns:
        None

    Side Effects:
        - Cria/atualiza registros ArticleFormat
        - Gera arquivos nos formatos configurados
        - Registra progresso no log

    Notes:
        - Pula conversão se ArticleFormat já existe e force_update=False
        - Pode processar múltiplos ArticleFormat se houver duplicatas
        - Usa ArticleFormat.generate_formats() para conversão real
    """
    user = _get_user(self.request, username, user_id)

    try:
        article = Article.objects.get(pk=item_id)
    except Article.DoesNotExist:
        logging.info(f"Article not found: {item_id}")
        return

    done = False
    try:
        article_format = ArticleFormat.objects.get(article=article)
        done = True
    except ArticleFormat.MultipleObjectsReturned:
        # Múltiplos formatos já existem
        done = True
    except ArticleFormat.DoesNotExist:
        done = False

    logging.info(
        f"Conversion status for {article.pid_v3}: {'Done' if done else 'Pending'}"
    )

    if not done or force_update:
        ArticleFormat.generate_formats(user, article=article)


# ==============================================================================
# TAREFAS DE EXPORTAÇÃO / EXPORT TASKS
# ==============================================================================


@celery_app.task(bind=True, name="task_select_articles_to_export_to_articlemeta")
def task_select_articles_to_export_to_articlemeta(
    self,
    collection_acron_list=None,
    issn=None,
    number=None,
    volume=None,
    year_of_publication=None,
    from_date=None,
    until_date=None,
    days_to_go_back=None,
    force_update=True,
    user_id=None,
    username=None,
):
    """
    Exporta artigos em lote para o banco de dados ArticleMeta.

    ArticleMeta é o sistema de armazenamento centralizado de metadados
    de artigos do SciELO, baseado em MongoDB. Esta tarefa permite
    exportação seletiva baseada em múltiplos critérios.

    Args:
        self: Instância da tarefa Celery
        collection_acron_list (list, optional): Lista de acrônimos de coleções
            Ex: ['scl', 'mex', 'arg']
        issn (str, optional): ISSN do periódico (formato: XXXX-XXXX)
        number (str, optional): Número da edição
        volume (str, optional): Volume da edição
        year_of_publication (int, optional): Ano de publicação
        from_date (str, optional): Data inicial (campo 'updated' do Article)
        until_date (str, optional): Data final (campo 'updated' do Article)
        days_to_go_back (int, optional): Dias para retroceder de until_date ou hoje
        force_update (bool): Força atualização de registros existentes. Default: True
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        None

    Side Effects:
        - Exporta artigos para MongoDB/ArticleMeta
        - Atualiza registros existentes se force_update=True
        - Cria novos registros se não existirem

    Examples:
        # Exportar artigos de coleções específicas do último mês
        task_select_articles_to_export_to_articlemeta.delay(
            collection_acron_list=['scl', 'mex'],
            days_to_go_back=30,
            force_update=True
        )

        # Exportar artigos de um periódico específico de 2024
        task_select_articles_to_export_to_articlemeta.delay(
            issn='1234-5678',
            year_of_publication=2024,
            force_update=False
        )

        # Exportar artigos atualizados em período específico
        task_select_articles_to_export_to_articlemeta.delay(
            from_date='2024-01-01',
            until_date='2024-12-31',
            collection_acron_list=['scl']
        )

    Notes:
        - Os filtros from_date/until_date operam sobre Article.updated
        - days_to_go_back é calculado a partir de until_date ou data atual
        - A exportação usa bulk_data_export_to_articlemeta para otimização
    """
    try:
        user = _get_user(self.request, username=username, user_id=user_id)

        # Obtém queryset baseado nos filtros
        queryset = Article.get_queryset(
            collection_acron_list,
            issn,
            number,
            volume,
            year_of_publication,
            from_date,
            until_date,
            days_to_go_back,
        )

        # Realiza exportação em lote
        destination = ArticleExportDestination.get_or_create("articlemeta", user)
        version = None
        bulk_data_export_to_articlemeta(
            user,
            destination,
            version,
            queryset,
            collection_acron_list,
            force_update,
        )
    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_export_article_to_articlemeta",
                "collection_acron_list": collection_acron_list,
                "issn": issn,
                "number": number,
                "volume": volume,
                "year_of_publication": year_of_publication,
                "from_date": from_date,
                "until_date": until_date,
                "days_to_go_back": days_to_go_back,
                "force_update": force_update,
            },
        )


@celery_app.task(bind=True, name="task_export_article_to_articlemeta")
def task_export_article_to_articlemeta(
    self, article_id=None, pid_v3=None, force_update=True, user_id=None, username=None
):
    """
    Exporta um artigo individual para ArticleMeta.

    Permite exportação de um artigo específico identificado por ID ou PID v3.
    Útil para atualizações pontuais ou correções específicas.

    Args:
        self: Instância da tarefa Celery
        article_id (int, optional): ID do artigo no banco local
        pid_v3 (str, optional): PID v3 do artigo (formato SciELO)
            Ex: "S0001-37652024000100101"
        force_update (bool): Força atualização se já existe. Default: True
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        None

    Raises:
        Article.DoesNotExist: Se artigo não for encontrado

    Side Effects:
        - Exporta artigo para ArticleMeta
        - Atualiza registro se existir e force_update=True
        - Registra UnexpectedEvent se artigo não existir

    Examples:
        # Exportar por ID
        task_export_article_to_articlemeta.delay(
            article_id=12345,
            force_update=True
        )

        # Exportar por PID v3
        task_export_article_to_articlemeta.delay(
            pid_v3="S0001-37652024000100101",
            force_update=False
        )

    Notes:
        - Deve fornecer article_id OU pid_v3, não ambos
        - Usa export_article_instances_to_articlemeta para exportação
        - Version é definida como timestamp ISO atual
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    try:
        # Busca artigo por ID ou PID
        if article_id:
            article = Article.objects.get(id=article_id)
        elif pid_v3:
            article = Article.objects.get(pid_v3=pid_v3)
        else:
            raise ValueError("Must provide either article_id or pid_v3")

    except Article.DoesNotExist:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            item=pid_v3 or article_id,
            exception=Article.DoesNotExist,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_export_article_to_articlemeta",
                "article_id": article_id,
                "pid_v3": pid_v3,
            },
        )
        return

    try:
        # Realiza exportação
        destination = ArticleExportDestination.get_or_create("articlemeta", user)
        version = None
        export_article_to_articlemeta(
            user,
            article,
            destination,
            collection_acron_list,
            version,
            force_update,
        )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            item=pid_v3 or article_id,
            exception=Article.DoesNotExist,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_export_article_to_articlemeta",
                "article_id": article_id,
                "pid_v3": pid_v3,
            },
        )
        return
