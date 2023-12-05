import logging


ITEMS_SEP_FOR_INST = [";", "|", ")"]
PARTS_SEP_FOR_INST = [" - ", "- ", " -", "(", "/", ")"]

ITEMS_SEP_FOR_LOCATION = [";", ", ", "|", "/"]
PARTS_SEP_FOR_LOCATION = [" - ", "- ", " -", ", ", "(", "/"]

ITEMS_SEP_FOR_CITY = [",", "|"]
PARTS_SEP_FOR_CITY = []


def get_splitted_text_multiple(text, items_separators=None):
    text = text and text.strip()
    if not text:
        return []

    parts_separators = PARTS_SEP_FOR_INST
    items_separators = items_separators or ITEMS_SEP_FOR_INST

    PARTBR = "~PARTBR~"
    LINEBR = "~LINEBR~"
    text_ = text
    text_ = remove_extra_spaces(text_)

    for sep in items_separators:
        text_ = text_.replace(sep, LINEBR)
    for sep in parts_separators:
        text_ = text_.replace(sep, PARTBR)

    for row in text_.split(LINEBR):
        row = row and row.strip()
        if not row:
            continue
        logging.info(f"row: {row}")
        parts = row.split(PARTBR)
        parts = [x.strip() for x in parts if x.strip()]
        if len(parts) == 1 and not parts[0].isalnum():
            # skip non alpha numerica itens that could be separator
            continue
        yield parts


def get_splitted_text_one(text):
    text = text and text.strip()
    if not text:
        return []

    PARTBR = "~PARTBR~"
    LINEBR = "~LINEBR~"
    text_ = text
    text_ = remove_extra_spaces(text_)

    seps = set()
    splitted_text = text_.split()
    for item in splitted_text:
        item = item and item.strip()
        if not item:
            continue
        if len(item) == 1 and not item.isalnum():
            seps.add(item)
    seps.update(ITEMS_SEP_FOR_INST)
    seps.update(PARTS_SEP_FOR_INST)

    logging.info(f"seps: {seps}")
    for sep in seps:
        text_ = text_.replace(sep, PARTBR)

    logging.info(f"text_: {text_}")
    ret = [item.strip() for item in text_.split(PARTBR) if item.strip()]
    logging.info(f"ret: {ret}")
    return ret


def remove_extra_spaces(text):
    text = text and text.strip()
    if not text:
        return text
    # padroniza a quantidade de espaços
    return " ".join([item.strip() for item in text.split() if item.strip()])


def standardize_acronym_and_name(
    original, possible_multiple_return=None, q_locations=None
):
    """
    Dado o texto original, identifica pares de acrônimo e nome,
    ou lista de acrônimos ou lista de nomes.
    Retorna um ou mais itens dependendo do valor de q_locations que
    deve ser correspondente à quantidade de itens identificados,
    caso contrário, retornará `{"name": original}

    Parameters
    ----------
    possible_multiple_return : boolean
    q_locations : int
        indica se é esperado 1 instituição ou várias

    """
    logging.info(f"texto: {original}")
    parts_separators = PARTS_SEP_FOR_INST
    items_separators = ITEMS_SEP_FOR_INST

    if possible_multiple_return and q_locations and q_locations > 1:

        acrons = []
        names = []
        splitted_text = list(get_splitted_text_multiple(original))
        logging.info(f"get_splitted_text_multiple: {splitted_text}")
        for parts in splitted_text:
            if len(parts) == 2:
                if len(parts[0]) > len(parts[1]):
                    name, acron = parts
                else:
                    acron, name = parts
                acrons.append(acron)
                names.append(name)
            elif len(parts) == 1:
                value = parts[0]
                if " " not in value and value.upper() == value and len(value) < 20:
                    acrons.append(value)
                else:
                    names.append(value)

        yield from standardize_acronym_and_name_multiple(
            splitted_text,
            acrons,
            names,
            original,
            q_locations,
        )
    else:
        acrons = []
        names = []
        parts = get_splitted_text_one(original)
        logging.info(f"get_splitted_text_one: {parts}")
        if not parts:
            return
        if len(parts) == 2:
            if len(parts[0]) > len(parts[1]):
                name, acron = parts
            else:
                acron, name = parts
            acrons.append(acron)
            names.append(name)
        elif len(parts) == 1:
            value = parts[0]
            if " " not in value and value.upper() == value and len(value) < 20:
                acrons.append(value)
            else:
                names.append(value)
        elif len(parts) > 2:
            for part in parts:
                if " " not in part and part.upper() == part and len(part) < 20:
                    acrons.append(part)
                else:
                    names.append(part)
        logging.info(acrons)
        logging.info(names)
        x = standardize_acronym_and_name_one(acrons, names, original)
        logging.info(x)
        yield x


def standardize_acronym_and_name_one(acrons, names, original):
    """
    Retorna um par acron e name ou somente um name ou somente um acron,
    caso contrário retorna `{"name": original}`
    """
    logging.info((acrons, names, original))
    if not original:
        return {"name": None}

    original = remove_extra_spaces(original)

    if acrons and not names:
        if len(acrons) == 1:
            return {"acronym": acrons[0]}

    if names and not acrons:
        if len(names) == 1:
            return {"name": names[0]}

    if len(names) == len(acrons) == 1:
        for name, acron in zip(names, acrons):
            logging.info(f".......{name} {acron}")
            return {"acronym": acron, "name": name}

    if len(acrons) == 1 and len(names) > 1:
        d = {"acronym": acrons[0]}
        d.update(name_and_divisions(names))
        return d

    # retorna o original
    return {"name": original}


def standardize_acronym_and_name_multiple(
    splitted_text,
    acrons,
    names,
    original,
    q_locations,
):
    """
    Retorna os pares acron e name ou somente names ou somente acrons,
    mas somente se a quantidade está coerente com q_locations,
    caso contrário retorna `{"name": original}`
    """
    if not original:
        yield {"name": None}
        return
    original = remove_extra_spaces(original)

    if acrons and not names:
        if q_locations == len(acrons):
            for acron in acrons:
                yield {"acronym": acron}
        return

    if names and not acrons:
        if q_locations == len(names):
            for name in names:
                yield {"name": name}
        return

    match = False
    if len(names) == len(acrons) == q_locations:
        for acron, name in zip(acrons, names):
            yield {"acronym": acron, "name": name}

    elif q_locations == len(splitted_text):
        for parts in splitted_text:
            if len(parts) == 2:
                name, acron = parts
                yield {"acronym": acron, "name": name}
            elif len(parts) == 1:
                value = parts[0]
                if " " not in value and value.upper() == value and len(value) < 20:
                    yield {
                        "acronym": value,
                    }
                else:
                    yield {"name": value}
    else:
        yield {"name": original}


def name_and_divisions(splitted_text):
    keys = ("name", "level_1", "level_2", "level_3")
    d = {}
    for k, v in zip(keys, splitted_text):
        d[k] = v
    return d


def standardize_code_and_name(original):
    """
    Dado o texto original, identifica pares de code e nome.
    Os separadores podem separar code e nome e/ou itens de lista.
    Ex.: USP / Unicamp
    São Paulo/SP, Rio de Janeiro/RJ
    """
    text_ = original
    text_ = text_ and text_.strip()
    if not text_:
        return []

    text_ = remove_extra_spaces(text_)
    if not text_:
        yield {"name": None}
        return

    items_separators = ITEMS_SEP_FOR_LOCATION
    parts_separators = PARTS_SEP_FOR_LOCATION

    PARTBR = "~PARTBR~"
    LINEBR = "~LINEBR~"
    for sep in items_separators:
        text_ = text_.replace(sep, PARTBR)
    for sep in parts_separators:
        text_ = text_.replace(sep, PARTBR)

    codes = []
    names = []
    for item in text_.split(PARTBR):
        item = item.strip()
        if not item:
            continue
        if len(item) == 2:
            codes.append(item)
        else:
            names.append(item)

    if len(names) == len(codes):
        for acron, name in zip(codes, names):
            yield {"code": acron, "name": name}
    elif len(names) == 0:
        for acron in codes:
            yield {"code": acron}
    elif len(codes) == 0:
        for name in names:
            yield {"name": name}
    else:
        # como o texto está bem fora do padrão,
        # pode-se evidenciar retornando o original
        yield {"name": original}


def standardize_name(original):
    original = original and original.strip()
    if not original:
        return

    items_separators = ITEMS_SEP_FOR_CITY

    LINEBR = "~LINEBR~"

    text_ = original
    text_ = remove_extra_spaces(text_)

    for sep in items_separators:
        text_ = text_.replace(sep, LINEBR)

    for row in text_.split(LINEBR):
        row = row and row.strip()
        if not row:
            continue
        yield {"name": row}
