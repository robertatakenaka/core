import datetime
import logging

from django.conf import settings
from pymongo import MongoClient, UpdateOne

MONGODB_DATABASE = settings.MONGODB_DATABASE
MONGODB_URI = settings.MONGODB_URI


def get_client(uri=None):
    """
    Returns a MongoClient instance.
    If no URI is provided, it uses the default MongoDB URI from settings.

    Args:
        uri (str): MongoDB URI. If None, uses the default from settings. Default value should be something like "mongodb://localhost:27017/".

    Returns:
        MongoClient: A MongoClient instance.
    """
    try:
        uri = uri or MONGODB_URI
        return MongoClient(uri)
    except Exception as e:
        raise Exception(f"Failed to connect to MongoDB {uri}: {str(e)}")


def get_mongodb_collection(mongodb_collection_name):
    """
    Returns a MongoClient instance.
    If no URI is provided, it uses the default MongoDB URI from settings.

    Args:
        uri (str): MongoDB URI. If None, uses the default from settings. Default value should be something like "mongodb://localhost:27017/".

    Returns:
        MongoClient: A MongoClient instance.
    """
    try:
        return get_client()[mongodb_collection_name]
    except Exception as e:
        raise Exception(
            f"Failed to connect to MongoDB collection: {mongodb_collection_name}: {str(e)}"
        )


def write_to_db(data, database, collection, force_update=True, client=None):
    """
    Writes data to a MongoDB collection.
    If force_update is True, it replaces the document if it exists or inserts a new one.
    If force_update is False, it inserts a new document.
    If a client is not provided, it uses the default client from settings.

    Args:
        data (dict): Data to be written to the collection.
        database (str): Name of the MongoDB database.
        collection (str): Name of the MongoDB collection.
        force_update (bool): If True, replaces the document if it exists or inserts a new one. If False, inserts a new document.
        client (MongoClient): A MongoClient instance. If None, uses the default client from settings.

    Returns:
        bool: True if successful, False otherwise.

    Raises:
        Exception: If there is an error writing to the collection.
    """
    return write_item(collection, data)


def write_item(mongodb_collection_name, data):
    try:
        mongodb_collection = get_mongodb_collection(mongodb_collection_name)
        # collection = scielo collection
        filter_query = {
            "code": data["code"],
            "collection": data["collection"],
        }

        # A atualização define os campos, incluindo a última visita
        update_data = {
            "$set": data,
        }
        result = mongodb_collection.update_one(filter_query, update_data, upsert=True)

        # Verificando o resultado
        if result.upserted_id:
            return result.upserted_id
        raise Exception(f"Unable to create/update {filter_query}")
    except Exception as e:
        raise Exception(f"Unable to create/update {filter_query}: {str(e)}")


def create_bulks(items_to_upsert, max_per_bulk=None):
    # Construindo a lista de operações de upsert
    requests = []
    max_per_bulk = max_per_bulk or 1000
    count = max_per_bulk
    for data in items_to_upsert:

        # collection = scielo collection
        filter_query = {
            "code": data["code"],
            "collection": data["collection"],
        }

        # A atualização define os campos, incluindo a última visita
        update_data = {
            "$set": data,
        }

        # Adicionando a operação de upsert à lista de requests
        requests.append(UpdateOne(filter_query, update_data, upsert=True))
        count -= 1
        if count == 0:
            yield requests
            requests = []
            count = max_per_bulk

    yield requests


def bulk_write(mongodb_collection_name, items_to_upsert, max_per_bulk=None):
    """
    O limite de 16 MB para o tamanho de um documento BSON

    A ideia do bulk_write é reduzir o "overhead" de rede, ou seja,
    o tempo que a sua aplicação gasta enviando e recebendo comandos do servidor.

    Lotes muito pequenos (por exemplo, 10-20 documentos) ainda
    geram muitas viagens de ida e volta para o banco de dados,
    o que pode prejudicar a performance, anulando o benefício da operação em lote.

    Lotes muito grandes podem exceder o limite de 16 MB, causando erros,
    ou podem sobrecarregar a memória do servidor.

    Quantidade de Referência e Melhor Prática
    Como ponto de partida, a maioria dos desenvolvedores trabalha
    com lotes entre 1.000 a 10.000 documentos, para dados com tamanhos médios.

    """
    exceptions = []
    mongodb_collection = get_mongodb_collection(mongodb_collection_name)

    for bulk in create_bulks(items_to_upsert, max_per_bulk):
        # Executando todas as operações em lote
        try:
            result = mongodb_collection.bulk_write(bulk)
            # result.upserted_ids retorna os ids dos registros atualizados
            yield {"result": result}

            logging.info("Operação em lote concluída com sucesso!")
            logging.info(f" - Documentos correspondidos: {result.matched_count}")
            logging.info(f" - Documentos modificados: {result.modified_count}")
            logging.info(f" - Documentos inseridos (upserted): {result.upserted_count}")

        except Exception as e:
            exceptions.append(f"Ocorreu um erro na operação em lote: {e}")
    yield {"exceptions": exceptions}
