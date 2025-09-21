import json

from core.utils.utils import fetch_data


def get_crossref_metadata(doi):
    """
    Consulta a API do Crossref para obter metadados de um DOI.

    Args:
        doi (str): O DOI (Digital Object Identifier) da obra.

    Returns:
        dict: Um dicionário contendo os metadados da obra, ou None se a consulta falhar.
    """
    # A URL da API do Crossref para obter informações de uma obra
    url = f"https://api.crossref.org/works/{doi}"

    # É uma boa prática usar um User-Agent para identificar sua aplicação
    headers = {"User-Agent": "core.scielo.org (tecnologia@scielo.org)"}

    try:
        return fetch_data(url, headers=headers, json=True, timeout=30)
    except Exception as e:
        return {"error": str(e)}


# Exemplo de uso
doi_exemplo = "10.1038/s41586-020-2187-5"
metadata = get_crossref_metadata(doi_exemplo)

if metadata:
    # Imprime alguns metadados para demonstração
    print("Metadados encontrados:")
    print(f"Título: {metadata.get('title', ['Não disponível'])[0]}")
    print(
        f"Autores: {[author['given'] + ' ' + author['family'] for author in metadata.get('author', [])]}"
    )
    print(f"Revista: {metadata.get('container-title', ['Não disponível'])[0]}")
    print(f"URL: {metadata.get('URL')}")
else:
    print("Não foi possível obter os metadados para o DOI fornecido.")
