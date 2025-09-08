import logging
import sys
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Subquery
from django.utils.translation import gettext_lazy as _

from article import controller
from article.models import Article, ArticleFormat, ArticleSource
from article.sources.preprint import harvest_preprints
from article.sources.xmlsps import load_article
from collection.models import Collection
from config import celery_app
from core.utils.extracts_normalized_email import extracts_normalized_email
from core.utils.utils import fetch_data, _get_user
from journal.models import SciELOJournal
from pid_provider.choices import PPXML_STATUS_DONE, PPXML_STATUS_TODO
from pid_provider.models import PidProviderXML
from pid_provider.provider import PidProvider
from researcher.models import ResearcherIdentifier
from tracker.models import UnexpectedEvent


User = get_user_model()


# ==============================================================================
# SUMÁRIO DE TAREFAS CELERY / CELERY TASKS SUMMARY
# ==============================================================================
#
# TAREFAS DE IMPORTAÇÃO E CARREGAMENTO / IMPORT AND LOADING TASKS
# - load_preprint: Coleta e carrega preprints de servidor OAI-PMH
# - task_get_opac_xmls: Obtém XMLs de artigos do OPAC via API
# - task_load_article_from_article_source: Processa XMLs de ArticleSource
# - task_load_articles: Carrega artigos de PidProviderXML
#
# TAREFAS DE ATUALIZAÇÃO E COMPLEMENTAÇÃO DE DADOS / DATA UPDATE TASKS
# - load_funding_data: Carrega dados de financiamento da pesquisa
# - task_articles_complete_data: Dispara complementação em lote
# - article_complete_data: Completa dados de um artigo específico
# - transfer_license_statements_fk_to_article_license: Migra dados de licença
# - normalize_stored_email: Normaliza emails em ResearcherIdentifier
#
# TAREFAS DE LIMPEZA E MANUTENÇÃO / CLEANUP AND MAINTENANCE TASKS
# - task_mark_articles_as_deleted_without_pp_xml: Marca artigos órfãos como deletados
# - remove_duplicate_articles_task: Remove artigos duplicados
#
# TAREFAS DE CONVERSÃO E FORMATAÇÃO / CONVERSION AND FORMATTING TASKS
# - task_convert_xml_to_other_formats_for_articles: Dispara conversão em lote
# - convert_xml_to_other_formats: Converte XML para outros formatos
#
# TAREFAS DE EXPORTAÇÃO / EXPORT TASKS
# - task_export_articles_to_articlemeta: Exporta artigos em lote para ArticleMeta
# - task_export_article_to_articlemeta: Exporta um artigo para ArticleMeta
# ==============================================================================


# ==============================================================================
# TAREFAS DE IMPORTAÇÃO E CARREGAMENTO / IMPORT AND LOADING TASKS
# - load_preprint: Coleta e carrega preprints de servidor OAI-PMH
# - task_get_opac_xmls: Obtém XMLs de artigos do OPAC via API
# - task_load_article_from_article_source: Processa XMLs de ArticleSource
# - task_load_articles: Carrega artigos de PidProviderXML
# ==============================================================================
@celery_app.task(bind=True, name=_("load_preprints"))
def load_preprint(self, user_id, oai_pmh_preprint_uri):
    """
    Coleta e carrega preprints de um servidor OAI-PMH.

    Args:
        self: Instância da tarefa Celery
        user_id (int): ID do usuário executando a tarefa
        oai_pmh_preprint_uri (str): URI do servidor OAI-PMH de preprints

    Returns:
        None

    Raises:
        User.DoesNotExist: Se o usuário não for encontrado
    """
    user = User.objects.get(pk=user_id)
    ## fazer filtro para não coletar tudo sempre
    harvest_preprints(oai_pmh_preprint_uri, user)
 

@celery_app.task(bind=True, name="task_get_opac_xmls")
def task_get_opac_xmls(
    self,
    username=None,
    user_id=None,
    begin_date=None,
    end_date=None,
    limit=None,
    pages=None,
    force_update=None,
    domain=None,
    collection_acron=None,
    timeout=None,
    auto_solve_pid_conflict=None,
):
    """
    Obtém e processa XMLs de artigos do OPAC via API.

    Coleta metadados de artigos através da API do OPAC e dispara
    o processamento dos XMLs correspondentes.

    Args:
        self: Instância da tarefa Celery
        username (str, optional): Nome do usuário executando a tarefa
        user_id (int, optional): ID do usuário executando a tarefa
        begin_date (str, optional): Data inicial no formato YYYY-MM-DD. Default: "2000-01-01"
        end_date (str, optional): Data final no formato YYYY-MM-DD. Default: data atual
        limit (int, optional): Limite de documentos por página. Default: 100
        pages (int, optional): Número total de páginas a processar
        force_update (bool, optional): Se True, força atualização mesmo se já existe
        domain (str, optional): Domínio do OPAC. Default: "www.scielo.br"
        collection_acron (str, optional): Acrônimo da coleção. Default: "scl"
        timeout (int, optional): Timeout em segundos para requisições. Default: 5
        auto_solve_pid_conflict (bool, optional): Se True, resolve conflitos de PID automaticamente

    Returns:
        None

    Side Effects:
        - Cria/atualiza ArticleSource para cada artigo encontrado
        - Processa XMLs através de ArticleSource.process_xml()
        - Registra UnexpectedEvent em caso de erro

    API Response Example:
        {
            "begin_date":"2023-06-01 00-00-00",
            "collection":"scl",
            "dictionary_date": "Sat, 01 Jul 2023 00:00:00 GMT",
            "pages": 10,
            "documents":{
                "JFhVphtq6czR6PHMvC4w38N": {
                    "aop_pid":"",
                    "create":"Sat, 28 Nov 2020 23:42:43 GMT",
                    "default_language":"en",
                    "journal_acronym":"aabc",
                    "pid":"S0001-37652012000100017",
                    "pid_v1":"S0001-3765(12)08400117",
                    "pid_v2":"S0001-37652012000100017",
                    "pid_v3":"JFhVphtq6czR6PHMvC4w38N",
                    "publication_date":"2012-05-22",
                    "update":"Fri, 30 Jun 2023 20:57:30 GMT"
                }
            }
        }
    """
    page = 1
    domain = domain or "www.scielo.br"
    limit = limit or 100
    collection_acron = collection_acron or "scl"
    end_date = end_date or datetime.utcnow().isoformat()[:10]
    timeout = timeout or 5
    begin_date = begin_date or "2000-01-01"

    user = _get_user(self.request, username=username, user_id=user_id)

    while True:
        try:
            uri = (
                f"https://{domain}/api/v1/counter_dict?end_date={end_date}"
                f"&begin_date={begin_date}&limit={limit}&page={page}"
            )
            response = fetch_data(uri, json=True, timeout=timeout, verify=True)

            pages = pages or response["pages"]
            documents = response["documents"]

        except Exception as e:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            UnexpectedEvent.create(
                exception=e,
                exc_traceback=exc_traceback,
                detail={
                    "task": "task_get_opac_xmls",
                    "uri": uri,
                },
            )

        else:
            for pid_v3, document in documents.items():
                try:
                    # Processa diretamente os dados do artigo e chama provide_pid_for_opac_and_am_xml
                    acron = document["journal_acronym"]
                    xml_uri = f"https://www.scielo.br/j/{acron}/a/{pid_v3}/?format=xml"
                    origin_date = datetime.strptime(
                        document.get("update") or document.get("create"),
                        "%a, %d %b %Y %H:%M:%S %Z",
                    ).isoformat()[:10]
                    year = document["publication_date"][:4]

                    article_source = ArticleSource.create_or_update(
                        user,
                        url=xml_uri,
                        source_date=origin_date,
                        force_update=force_update,
                    )
                    article_source.process_xml(
                        user, load_article, force_update, auto_solve_pid_conflict
                    )

                except Exception as e:
                    exc_type, exc_value, exc_traceback = sys.exc_info()
                    UnexpectedEvent.create(
                        exception=e,
                        exc_traceback=exc_traceback,
                        detail={
                            "task": "task_get_opac_xmls",
                            "pid_v3": pid_v3,
                            "document": document,
                        },
                    )

        finally:
            page += 1
            if page > pages:
                break


@celery_app.task(bind=True, name="task_load_article_from_article_source")
def task_load_article_from_article_source(
    self,
    username=None,
    user_id=None,
    force_update=None,
    status__in=None,
    auto_solve_pid_conflict=None,
):
    """
    Processa XMLs armazenados em ArticleSource para criar/atualizar artigos.

    Args:
        self: Instância da tarefa Celery
        username (str, optional): Nome do usuário executando a tarefa
        user_id (int, optional): ID do usuário executando a tarefa
        force_update (bool, optional): Se True, força reprocessamento
        status__in (list, optional): Lista de status para filtrar ArticleSource
        auto_solve_pid_conflict (bool, optional): Se True, resolve conflitos de PID automaticamente

    Returns:
        None

    Side Effects:
        - Processa XMLs através de ArticleSource.process_xmls()
        - Cria/atualiza artigos no banco de dados
        - Registra UnexpectedEvent em caso de erro
    """
    try:
        user = _get_user(self.request, username=username, user_id=user_id)
        ArticleSource.process_xmls(
            user, load_article, status__in, force_update, auto_solve_pid_conflict
        )

    except Exception as e:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=e,
            exc_traceback=exc_traceback,
            detail={
                "task": "task_load_article_from_article_source",
                "status__in": status__in,
                "force_update": force_update,
            },
        )


@celery_app.task(bind=True, name="task_load_articles")
def task_load_articles(
    self,
    user_id=None,
    username=None,
):
    """
    Tarefa para carregar artigos a partir de arquivos XML do PidProvider.

    Processa todos os objetos PidProviderXML com status TODO, carregando
    os artigos correspondentes e marcando como DONE quando processados
    com sucesso.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        None

    Side Effects:
        - Cria/atualiza artigos no banco de dados
        - Atualiza status de PidProviderXML para DONE quando bem-sucedido
        - Registra UnexpectedEvent em caso de erro
        - Dispara tarefa de marcação de artigos deletados após conclusão
    """
    try:
        user = _get_user(self.request, username, user_id)

        generator_articles = (
            PidProviderXML.objects.select_related("current_version")
            .filter(proc_status=PPXML_STATUS_TODO)
            .iterator()
        )

        for item in generator_articles:
            try:
                article = load_article(
                    user,
                    file_path=item.current_version.file.path,
                    v3=item.v3,
                    pp_xml=item,
                )
                if article and article.valid:
                    item.proc_status = PPXML_STATUS_DONE
                    item.save()
            except Exception as exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                UnexpectedEvent.create(
                    exception=exception,
                    exc_traceback=exc_traceback,
                    detail={
                        "task": "article.tasks.load_articles",
                        "item": str(item),
                    },
                )

        task_mark_articles_as_deleted_without_pp_xml.apply_async(
            kwargs=dict(
                user_id=user_id or user.id,
                username=username or user.username,
            )
        )
    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.load_articles",
            },
        )


# ==============================================================================
# TAREFAS DE ATUALIZAÇÃO E COMPLEMENTAÇÃO DE DADOS / DATA UPDATE TASKS
# - load_funding_data: Carrega dados de financiamento da pesquisa
# - task_articles_complete_data: Dispara complementação em lote
# - article_complete_data: Completa dados de um artigo específico
# - transfer_license_statements_fk_to_article_license: Migra dados de licença
# - normalize_stored_email: Normaliza emails em ResearcherIdentifier
# ==============================================================================
@celery_app.task()
def load_funding_data(user, file_path):
    """
    Carrega dados de financiamento a partir de um arquivo.

    Args:
        user: ID do usuário que está executando a operação
        file_path (str): Caminho para o arquivo contendo dados de financiamento

    Returns:
        None

    Raises:
        User.DoesNotExist: Se o usuário não for encontrado
    """
    user = User.objects.get(pk=user)
    controller.read_file(user, file_path)


# ==============================================================================
# TAREFAS DE ATUALIZAÇÃO E COMPLEMENTAÇÃO DE DADOS / DATA UPDATE TASKS
# - task_articles_complete_data: Dispara complementação em lote
# - article_complete_data: Completa dados de um artigo específico
# - transfer_license_statements_fk_to_article_license: Migra dados de licença
# - normalize_stored_email: Normaliza emails em ResearcherIdentifier
# ==============================================================================
@celery_app.task(bind=True)
def task_articles_complete_data(
    self, user_id=None, username=None, from_date=None, force_update=False
):
    """
    Dispara complementação de dados para todos os artigos.

    Processa todos os artigos, disparando tarefas assíncronas individuais
    para completar dados faltantes.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        from_date (str, optional): Data inicial para filtrar artigos (não utilizado)
        force_update (bool): Se True, força atualização mesmo se dados já existem

    Returns:
        None

    Side Effects:
        - Dispara múltiplas tarefas assíncronas article_complete_data
        - Registra UnexpectedEvent em caso de erro
    """
    try:
        user = _get_user(self.request, username, user_id)

        for item in Article.objects.iterator():
            try:
                article_complete_data.apply_async(
                    kwargs={
                        "user_id": user.id,
                        "username": user.username,
                        "item_id": item.id,
                    }
                )
            except Exception as exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                UnexpectedEvent.create(
                    exception=exception,
                    exc_traceback=exc_traceback,
                    detail={
                        "task": "article.tasks.task_articles_complete_data",
                        "item": str(item),
                    },
                )
    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.task_articles_complete_data",
            },
        )


@celery_app.task(bind=True)
def article_complete_data(
    self, user_id=None, username=None, item_id=None, force_update=None
):
    """
    Completa dados faltantes de um artigo específico.

    Atualmente preenche o campo sps_pkg_name baseado no pid_v3.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        item_id (int): ID do artigo a ser processado
        force_update (bool, optional): Se True, força atualização (não utilizado)

    Returns:
        None

    Side Effects:
        - Atualiza campo sps_pkg_name do artigo se necessário
    """
    user = _get_user(self.request, username, user_id)
    try:
        item = Article.objects.get(pk=item_id)
        if item.pid_v3 and not item.sps_pkg_name:
            item.sps_pkg_name = PidProvider.get_sps_pkg_name(item.pid_v3)
            item.save()
    except Article.DoesNotExist:
        pass


@celery_app.task(bind=True)
def transfer_license_statements_fk_to_article_license(
    self, user_id=None, username=None
):
    """
    Migra dados de licença do modelo antigo para o campo article_license.

    Transfere informações de license_statements ou license para o novo
    campo unificado article_license.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        None

    Side Effects:
        - Atualiza campo article_license de múltiplos artigos
        - Registra atualização no log quando houver mudanças
    """
    user = _get_user(self.request, username, user_id)
    articles_to_update = []
    for instance in Article.objects.filter(article_license__isnull=True):

        new_license = None
        if (
            instance.license_statements.exists()
            and instance.license_statements.first().url
        ):
            new_license = instance.license_statements.first().url
        elif instance.license and instance.license.license_type:
            new_license = instance.license.license_type

        if new_license:
            instance.article_license = new_license
            instance.updated_by = user
            articles_to_update.append(instance)

    if articles_to_update:
        Article.objects.bulk_update(
            articles_to_update, ["article_license", "updated_by"]
        )
        logging.info("The article_license of model Articles have been updated")


@celery_app.task(bind=True)
def normalize_stored_email(self):
    """
    Normaliza emails armazenados em ResearcherIdentifier.

    Processa todos os identificadores de tipo EMAIL que não estão
    normalizados, extraindo e salvando o email normalizado.

    Args:
        self: Instância da tarefa Celery

    Returns:
        None

    Side Effects:
        - Atualiza campo identifier de múltiplos ResearcherIdentifier
        - Realiza bulk_update para otimizar performance
    """
    updated_list = []
    re_identifiers = ResearcherIdentifier.get_items_with_invalid_email()

    for re_identifier in re_identifiers:
        email = extracts_normalized_email(raw_email=re_identifier.identifier)
        if email:
            re_identifier.identifier = email
            updated_list.append(re_identifier)

    ResearcherIdentifier.objects.bulk_update(updated_list, ["identifier"])


# ==============================================================================
# TAREFAS DE LIMPEZA E MANUTENÇÃO / CLEANUP AND MAINTENANCE TASKS
# - task_mark_articles_as_deleted_without_pp_xml: Marca artigos órfãos como deletados
# - remove_duplicate_articles_task: Remove artigos duplicados
# ==============================================================================
@celery_app.task(bind=True, name="task_mark_articles_as_deleted_without_pp_xml")
def task_mark_articles_as_deleted_without_pp_xml(self, user_id=None, username=None):
    """
    Marca artigos como deletados quando não possuem referência PidProviderXML.

    Esta tarefa identifica artigos órfãos (sem pp_xml associado) e os marca
    com status DATA_STATUS_DELETED.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        None

    Side Effects:
        - Atualiza status de artigos sem pp_xml para DATA_STATUS_DELETED
        - Registra quantidade de artigos atualizados no log
        - Registra UnexpectedEvent em caso de erro
    """
    try:
        user = _get_user(self.request, username, user_id)

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


@celery_app.task(bind=True)
def remove_duplicate_articles_task(self, user_id=None, username=None, pid_v3=None):
    """
    Tarefa Celery para remover artigos duplicados.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário (não utilizado)
        username (str, optional): Nome do usuário (não utilizado)
        pid_v3 (str, optional): PID v3 específico para remover duplicatas

    Returns:
        None

    Side Effects:
        - Chama remove_duplicate_articles() para executar a remoção
    """
    ids_to_exclude = []
    try:
        if pid_v3:
            duplicates = (
                Article.objects.filter(pid_v3=pid_v3)
                .values("pid_v3")
                .annotate(pid_v3_count=Count("pid_v3"))
                .filter(pid_v3_count__gt=1, valid=False)
            )
        else:
            duplicates = (
                Article.objects.values("pid_v3")
                .annotate(pid_v3_count=Count("pid_v3"))
                .filter(pid_v3_count__gt=1, valid=False)
            )
        for duplicate in duplicates:
            article_ids = (
                Article.objects.filter(pid_v3=duplicate["pid_v3"])
                .order_by("created")[1:]
                .values_list("id", flat=True)
            )
            ids_to_exclude.extend(article_ids)

        if ids_to_exclude:
            Article.objects.filter(id__in=ids_to_exclude).delete()
    except Exception as exception:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        UnexpectedEvent.create(
            exception=exception,
            exc_traceback=exc_traceback,
            detail={
                "task": "article.tasks.remove_duplicates_articles",
            },
        )


# ==============================================================================
# TAREFAS DE CONVERSÃO E FORMATAÇÃO / CONVERSION AND FORMATTING TASKS
# - task_convert_xml_to_other_formats_for_articles: Dispara conversão em lote
# - convert_xml_to_other_formats: Converte XML para outros formatos
# ==============================================================================
@celery_app.task(bind=True)
def task_convert_xml_to_other_formats_for_articles(
    self, user_id=None, username=None, from_date=None, force_update=False
):
    """
    Dispara conversão de XML para outros formatos para todos os artigos.

    Processa todos os artigos com sps_pkg_name definido, disparando
    tarefas assíncronas individuais para conversão de formato.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        from_date (str, optional): Data inicial para filtrar artigos (não utilizado)
        force_update (bool): Se True, força atualização mesmo se já convertido

    Returns:
        None

    Side Effects:
        - Dispara múltiplas tarefas assíncronas convert_xml_to_other_formats
        - Registra UnexpectedEvent em caso de erro
    """
    try:
        user = _get_user(self.request, username, user_id)

        for item in Article.objects.filter(sps_pkg_name__isnull=False).iterator():
            logging.info(item.pid_v3)
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


@celery_app.task(bind=True)
def convert_xml_to_other_formats(
    self, user_id=None, username=None, item_id=None, force_update=None
):
    """
    Converte XML de um artigo específico para outros formatos.

    Gera formatos alternativos (PDF, HTML, etc.) a partir do XML do artigo.

    Args:
        self: Instância da tarefa Celery
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa
        item_id (int): ID do artigo a ser convertido
        force_update (bool, optional): Se True, força reconversão mesmo se já existe

    Returns:
        None

    Side Effects:
        - Cria/atualiza registros ArticleFormat
        - Registra progresso no log
    """
    user = _get_user(self.request, username, user_id)

    try:
        article = Article.objects.get(pk=item_id)
    except Article.DoesNotExist:
        logging.info(f"Not found {item_id}")
        return

    done = False
    try:
        article_format = ArticleFormat.objects.get(article=article)
        done = True
    except ArticleFormat.MultipleObjectsReturned:
        done = True
    except ArticleFormat.DoesNotExist:
        done = False
    logging.info(f"Done {done}")

    if not done or force_update:
        ArticleFormat.generate_formats(user, article=article)


# ==============================================================================
# TAREFAS DE EXPORTAÇÃO / EXPORT TASKS
# - task_export_articles_to_articlemeta: Exporta artigos em lote para ArticleMeta
# - task_export_article_to_articlemeta: Exporta um artigo para ArticleMeta
# ==============================================================================
@celery_app.task(bind=True, name="task_export_articles_to_articlemeta")
def task_export_articles_to_articlemeta(
    self,
    collections=[],
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

    Permite filtrar artigos por diversos critérios antes da exportação.
    Os filtros from_date e until_date operam sobre o campo 'updated' de Article.

    Args:
        self: Instância da tarefa Celery
        collections (list, optional): Lista de acrônimos de coleções. Ex: ['scl', 'mex']
        issn (str, optional): ISSN do periódico para filtrar artigos
        number (str, optional): Número específico da edição
        volume (str, optional): Volume específico da edição
        year_of_publication (int, optional): Ano de publicação
        from_date (str, optional): Data inicial para filtro (formato ISO)
        until_date (str, optional): Data final para filtro (formato ISO)
        days_to_go_back (int, optional): Número de dias para retroceder a partir de hoje ou until_date
        force_update (bool): Se True, força atualização de registros existentes. Default: True
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        dict: Estatísticas da exportação incluindo total processado, sucessos e falhas

    Side Effects:
        - Exporta artigos para o banco ArticleMeta
        - Atualiza registros existentes se force_update=True

    Examples:
        # Exportar artigos de uma coleção específica
        task_export_articles_to_articlemeta.delay(
            collections=['scl'],
            from_date='2024-01-01',
            until_date='2024-12-31'
        )

        # Exportar artigos de um periódico específico
        task_export_articles_to_articlemeta.delay(
            issn='1234-5678',
            year_of_publication=2024,
            force_update=True
        )
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    return controller.bulk_export_articles_to_articlemeta(
        collections=collections,
        issn=issn,
        number=number,
        volume=volume,
        year_of_publication=year_of_publication,
        from_date=from_date,
        until_date=until_date,
        days_to_go_back=days_to_go_back,
        force_update=force_update,
        user=user,
        client=None,
    )


@celery_app.task(bind=True, name="task_export_article_to_articlemeta")
def task_export_article_to_articlemeta(
    self, pid_v3=None, force_update=True, user_id=None, username=None
):
    """
    Exporta um único artigo para o banco de dados ArticleMeta.

    Args:
        self: Instância da tarefa Celery
        pid_v3 (str): Identificador PID v3 do artigo a ser exportado
        force_update (bool): Se True, força atualização mesmo se já existe. Default: True
        user_id (int, optional): ID do usuário executando a tarefa
        username (str, optional): Nome do usuário executando a tarefa

    Returns:
        bool: True se a exportação foi bem-sucedida, False caso contrário

    Raises:
        Article.DoesNotExist: Se o artigo com o pid_v3 fornecido não existir

    Side Effects:
        - Exporta artigo para o banco ArticleMeta
        - Atualiza registro existente se force_update=True

    Example:
        # Exportar um artigo específico
        task_export_article_to_articlemeta.delay(
            pid_v3='JFhVphtq6czR6PHMvC4w38N',
            force_update=True,
            user_id=1
        )
    """
    user = _get_user(self.request, username=username, user_id=user_id)

    return controller.export_article_to_articlemeta(
        pid_v3=pid_v3,
        user=user,
        force_update=force_update,
        client=None
    )