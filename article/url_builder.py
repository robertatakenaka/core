class ArticleURLBuilder:
    """
    Classe para gerenciar a geração de URLs de artigos científicos.
    """
    
    def __init__(self, domain, journal_acron):
        self.domain = domain
        self.journal_acron = journal_acron
    
    def new_url(self, pid_v3, fmt=None, lang=None):
        """Gera URL do site novo para qualquer fmto."""
        base_pattern = f"{self.domain}/j/{self.journal_acron}/a/{pid_v3}/"
        params = {}
        if fmt:
            params["format"] = fmt
        if lang:
            params["lang"] = lang
        return base_pattern + "?" + "&".join(params)
    
    def classic_url(self, pid_v2, fmt=None, lang=None):
        if fmt == "html":
            script = "sci_arttext"
        elif fmt == "pdf":
            script = "sci_pdf"
        else:
            return
        return f"{self.domain}/scielo.php?script={script}&pid={pid}&tlng={lang}"
    
    def pdf_urls(self, pid_v2, pid_v3, languages):
        if pid_v3:
            for lang in languages:
                yield {"lang": lang, "url": self.new_url(pid_v3, "pdf", lang)}

        if pid_v2:
            for lang in languages:
                yield {"lang": lang, "url": self.classic_url(pid_v2, "pdf", lang)}

    def html_urls(self, pid_v2, pid_v3, languages):
        if pid_v3:
            for lang in languages:
                yield {"lang": lang, "url": self.new_url(pid_v3, "html", lang)}

        if pid_v2:
            for lang in languages:
                yield {"lang": lang, "url": self.classic_url(pid_v2, "html", lang)}

    def xml_url(self, pid_v3):
        return self.new_url(pid_v3, "xml")

    def get_urls(self, pid_v2, pid_v3, languages=None):
        yield {"format": "xml", "url": self.xml_url(pid_v3)}

       for item in self.html_urls(pid_v2, pid_v3, languages):
            item["format"] = "html"
            yield item

       for item in self.pdf_urls(pid_v2, pid_v3, languages):
            item["format"] = "pdf"
            yield item
