from haystack import indexes

from journal.models import SciELOJournal
from .models import Article
from legendarium.formatter import descriptive_format


class BaseArticleIndex(indexes.SearchIndex, indexes.Indexable):
    """
    Classe base abstrata com campos e métodos comuns para índices de artigos.
    """
    text = indexes.CharField(document=True, use_template=True)
    
    # Campos comuns
    titles = indexes.MultiValueField(null=True)
    la = indexes.MultiValueField(null=True)
    kw = indexes.MultiValueField(null=True)
    collab = indexes.MultiValueField(null=True)
    type = indexes.CharField(model_attr="article_type", null=True)
    
    def get_model(self):
        return Article
    
    def prepare_titles(self, obj):
        """Prepara lista de títulos do artigo."""
        if obj.titles:
            return [title.plain_text for title in obj.titles.all()]
    
    def prepare_la(self, obj):
        """Prepara idiomas do artigo."""
        return obj.langs
    
    def prepare_kw(self, obj):
        """Prepara palavras-chave do artigo."""
        if obj.keywords:
            return [keyword.text for keyword in obj.keywords.all()]
    
    def prepare_collab(self, obj):
        """Prepara colaboradores/autores institucionais."""
        if obj.collab:
            return [collab.collab for collab in obj.collab.all()]
    
    def _get_collections(self, obj):
        """Método auxiliar para obter coleções."""
        return obj.collections if hasattr(obj, 'collections') else []
    
    def _get_journal_data(self, obj):
        """Método auxiliar para obter dados do periódico."""
        if obj.journal:
            return SciELOJournal.objects.filter(
                journal=obj.journal, 
                collection__is_active=True
            )
        return []


class ArticleIndex(BaseArticleIndex):
    """
    Índice principal para busca de artigos.
    """
    # DOI e identificadores
    doi = indexes.MultiValueField(null=True)
    ids = indexes.MultiValueField(null=True)
    
    # URLs
    ur = indexes.MultiValueField(null=True)
    
    # Campos específicos com nomes customizados
    titles = indexes.MultiValueField(index_fieldname="ti", null=True)
    au = indexes.MultiValueField(null=True)
    ab = indexes.MultiValueField(null=True)
    orcid = indexes.MultiValueField(null=True)
    au_orcid = indexes.MultiValueField(null=True)
    
    # Metadados do periódico
    collection = indexes.MultiValueField(index_fieldname="in", null=True)
    journal_title = indexes.CharField(null=True)
    pid = indexes.CharField(model_attr="pid_v2", null=True)
    pid_v3 = indexes.CharField(model_attr="pid_v3", null=True)
    publication_year = indexes.CharField(null=True)
    domain = indexes.CharField(null=True)
    issue = indexes.CharField(null=True)
    volume = indexes.CharField(null=True)
    elocation = indexes.CharField(model_attr="elocation_id", null=True)
    start_page = indexes.CharField(model_attr="first_page", null=True)
    end_page = indexes.CharField(model_attr="last_page", null=True)
    pg = indexes.CharField(null=True)
    wok_citation_index = indexes.CharField(null=True)
    subject_areas = indexes.MultiValueField(null=True)
    ta_cluster = indexes.CharField(null=True)
    year_cluster = indexes.CharField(null=True)

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(data_status="PUBLIC")

    def prepare(self, obj):
        """
        Prepara campos dinâmicos para indexação.
        Adiciona títulos e resumos com sufixos de idioma (ti_*, ab_*).
        """
        data = super().prepare(obj)

        # Títulos por idioma
        for title in obj.titles.all():
            if title.language:
                data[f"ti_{title.language.code2}"] = title.plain_text
            else:
                data["ti_"] = title.plain_text

        # Resumos por idioma
        for ab in obj.abstracts.all():
            if ab.language:
                data[f"ab_{ab.language.code2}"] = ab.plain_text
            else:
                data["ab_"] = ab.plain_text

        # PDFs e HTMLs por idioma
        if obj.journal:
            # PDFs
            for item in obj.get_available("pdf"):
                data[f"fulltext_pdf_{item['lang']}"] = item["url"]

            # HTMLs
            for item in obj.get_available("html"):
                data[f"fulltext_html_{item['lang']}"] = item["url"]

        return data
    
    def prepare_ids(self, obj):
        """Prepara todos os identificadores do artigo."""
        ids = []
        if obj.pid_v2:
            ids.append(obj.pid_v2)
        if obj.pid_v3:
            ids.append(obj.pid_v3)
        if obj.id:
            ids.append(obj.id)
        return ids

    def prepare_ur(self, obj):
        """Prepara todas as URLs do artigo."""
        urls = []
        for fmt in ("html", "pdf"):
            urls.extend(list(item["url"] for item in obj.get_available(fmt=fmt)))
        return urls

    def prepare_journal_title(self, obj):
        """Prepara título do periódico."""
        if obj.journal:
            return obj.journal.title

    def prepare_subject_areas(self, obj):
        """Prepara áreas temáticas."""
        return (
            [subj_areas.value for subj_areas in obj.journal.subject.all()]
            if obj.journal
            else None
        )

    def prepare_ta_cluster(self, obj):
        """Prepara acrônimos dos periódicos."""
        sci_journals = self._get_journal_data(obj)
        return [sci_journal.journal_acron for sci_journal in sci_journals]

    def prepare_publication_year(self, obj):
        """Prepara ano de publicação."""
        return obj.issue.year

    def prepare_year_cluster(self, obj):
        """Prepara cluster de ano."""
        return obj.issue.year

    def prepare_collection(self, obj):
        """Prepara coleções."""
        return [collection.acron3 for collection in self._get_collections(obj)]

    def prepare_doi(self, obj):
        """Prepara DOIs."""
        if obj.doi:
            return [doi.value for doi in obj.doi.all()]

    def prepare_orcid(self, obj):
        """Prepara ORCIDs."""
        if obj.researchers:
            return [research.orcid for research in obj.researchers.all()]

    def prepare_au_orcid(self, obj):
        """Prepara autores com ORCID."""
        if obj.researchers:
            return [f"{research.orcid}" for research in obj.researchers.all()]

    def prepare_au(self, obj):
        """Prepara nomes dos autores."""
        if obj.researchers:
            return [research.get_full_name for research in obj.researchers.all()]

    def prepare_issue(self, obj):
        """Prepara número do fascículo."""
        try:
            return obj.issue.number
        except AttributeError:
            pass

    def prepare_volume(self, obj):
        """Prepara volume."""
        try:
            return obj.issue.volume
        except AttributeError:
            pass

    def prepare_ab(self, obj):
        """Prepara resumos."""
        if obj.abstracts:
            return [abstract.plain_text for abstract in obj.abstracts.all()]

    def prepare_domain(self, obj):
        """Prepara domínio."""
        try:
            return obj.journal.main_collection.domain
        except AttributeError:
            pass

    def prepare_pg(self, obj):
        """Prepara paginação."""
        return f"{obj.first_page}-{obj.last_page}"

    def prepare_wok_citation_index(self, obj):
        """Prepara índices WoS."""
        return [wos.code for wos in obj.journal.wos_db.all()] if obj.journal else None


class ArticleOAIIndex(BaseArticleIndex):
    """
    Índice específico para protocolo OAI-PMH.
    Segue o padrão de metadados Dublin Core.
    """
    # Campos OAI-PMH específicos
    id = indexes.CharField(index_fieldname="item.handle", null=True)
    item_id = indexes.CharField(index_fieldname="item.id", null=True)
    updated = indexes.CharField(index_fieldname="item.lastmodified", null=True)
    submitter = indexes.CharField(
        model_attr="creator", index_fieldname="item.submitter", null=True
    )
    deleted = indexes.CharField(index_fieldname="item.deleted", null=True)
    public = indexes.CharField(index_fieldname="item.public", null=True)
    collections = indexes.MultiValueField(index_fieldname="item.collections", null=True)
    communities = indexes.MultiValueField(index_fieldname="item.communities", null=True)
    
    # Metadados Dublin Core
    titles = indexes.MultiValueField(null=True, index_fieldname="metadata.dc.title")
    creator = indexes.MultiValueField(null=True, index_fieldname="metadata.dc.creator")
    collab = indexes.MultiValueField(null=True, index_fieldname="metadata.dc.collab")
    kw = indexes.MultiValueField(null=True, index_fieldname="metadata.dc.subject")
    description = indexes.MultiValueField(index_fieldname="metadata.dc.description")
    dates = indexes.MultiValueField(index_fieldname="metadata.dc.date")
    type = indexes.CharField(
        model_attr="article_type", index_fieldname="metadata.dc.type", null=True
    )
    identifier = indexes.MultiValueField(
        null=True, index_fieldname="metadata.dc.identifier"
    )
    la = indexes.MultiValueField(null=True, index_fieldname="metadata.dc.language")
    license = indexes.MultiValueField(index_fieldname="metadata.dc.rights")
    sources = indexes.MultiValueField(index_fieldname="metadata.dc.source")
    compile = indexes.CharField(
        null=True, index_fieldname="item.compile", use_template=True
    )

    def index_queryset(self, using=None):
        return self.get_model().objects.filter(data_status__in=["PUBLIC", "DELETED"])

    def _prepare_oai_identifier(self, obj):
        """Método auxiliar para gerar identificador OAI."""
        identifier = obj.pid_v2 or obj.doi or obj.pid_v3
        return f"oai:scielo:{identifier}"

    def prepare_id(self, obj):
        """Prepara identificador OAI-PMH."""
        return self._prepare_oai_identifier(obj)

    def prepare_item_id(self, obj):
        """Prepara ID do item OAI-PMH."""
        return self._prepare_oai_identifier(obj)

    def prepare_updated(self, obj):
        """
        Prepara data de última modificação no formato OAI-PMH.
        Formato: 2022-12-20T15:18:22Z
        """
        return obj.updated.strftime("%Y-%m-%dT%H:%M:%SZ")

    def prepare_deleted(self, obj):
        """Prepara flag de exclusão (soft delete)."""
        return obj.data_status == "DELETED"

    def prepare_public(self, obj):
        """Prepara flag de publicação."""
        return obj.data_status == "PUBLIC"

    def prepare_collections(self, obj):
        """Prepara ISSNs das coleções."""
        if obj.journal:
            sci_journals = SciELOJournal.objects.filter(journal=obj.journal)
            return set([j.issn_scielo for j in sci_journals])
        return set()

    def prepare_communities(self, obj):
        """Prepara comunidades OAI."""
        collections = self._get_collections(obj)
        if collections:
            return [f"com_{col.main_name}" for col in collections]
        return []

    def prepare_titles(self, obj):
        """Prepara títulos (sobrescreve método base para retornar set)."""
        titles = super().prepare_titles(obj)
        return set(titles) if titles else set()

    def prepare_creator(self, obj):
        """Prepara criadores/autores."""
        if obj.researchers:
            researchers = obj.researchers.select_related("person_name").filter(
                person_name__isnull=False
            )
            return set([str(researcher.person_name) for researcher in researchers])
        return set()

    def prepare_collab(self, obj):
        """Prepara colaboradores (sobrescreve para retornar set)."""
        collabs = super().prepare_collab(obj)
        return set(collabs) if collabs else set()

    def prepare_kw(self, obj):
        """Prepara palavras-chave (sobrescreve para retornar set)."""
        keywords = super().prepare_kw(obj)
        return set(keywords) if keywords else set()

    def prepare_description(self, obj):
        """Prepara descrições/resumos."""
        if obj.abstracts:
            return set([abs.plain_text for abs in obj.abstracts.all()])
        return set()

    def prepare_dates(self, obj):
        """Prepara datas de publicação no formato OAI."""
        date_parts = [
            obj.pub_date_year or "",
            obj.pub_date_month or "",
            obj.pub_date_day or "",
        ]
        return ["-".join(date_parts)]

    def prepare_identifier(self, obj):
        """
        Prepara todos os identificadores:
        - URLs (HTML e PDF)
        - DOIs
        - PIDs (v2 e v3)
        """
        idents = set()

        # URLs
        idents.update([item["url"] for item in obj.get_available("html")])
        idents.update([item["url"] for item in obj.get_available("pdf")])

        # DOIs
        if obj.doi:
            idents.update([doi.value for doi in obj.doi.all()])

        # PIDs
        if obj.pid_v2:
            idents.add(obj.pid_v2)
        if obj.pid_v3:
            idents.add(obj.pid_v3)

        return idents

    def prepare_license(self, obj):
        """Prepara informações de licença."""
        if obj.license and obj.license.license_type:
            return [obj.license.license_type]
        return []

    def prepare_sources(self, obj):
        """Prepara fontes/origem do artigo."""
        try:
            return obj.source
        except Exception:
            return ""