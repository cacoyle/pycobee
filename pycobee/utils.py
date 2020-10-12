def sqlite_data_factory(cursor, row):
    from collections import namedtuple

    fields = [col[0] for col in cursor.description]
    Row = namedtuple("Row", fields)
    return Row(*row)
