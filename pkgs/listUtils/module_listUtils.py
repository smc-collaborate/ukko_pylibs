def asWithoutNonesOrDuplicates(src: list) -> list:
    return [x for x in list(dict.fromkeys(src)) if x is not None]
