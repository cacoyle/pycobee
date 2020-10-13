#!/usr/bin/env python

"""
Persistent backend support class.

Desired backends:
[  ] sqlite3
[  ] redis
[  ] MySQL/Cassandra
"""

class backend(object):
    """
    Base backend class.
    """

    def __init__(self, uri, *args, **kwargs):
        import inspect
        import sys

        desired_class = uri.split('://')[0]

        class_map = {}

        classes = inspect.getmembers(
            sys.modules[__name__],
            inspect.isclass
        )

        for cls in classes:
            if not issubclass(cls[1], backend):
                continue

            class_map[cls[0].lower()] = cls[1]

        cls = class_map.get(desired_class.lower(), None)

        if not cls:
            raise ValueError(f'Unknown backend: {desired_backend}')

        new_backend = cls(uri, *args, **kwargs)

        return new_backend


class sqlite(backend):
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        pass

    @staticmethod
    def bullshit():
        print("That's bulshit, man.")

class mysql(backend):
    def __init__(self):
        super().__init__()

        pass

class redis(backend):
    def __init__(self):
        super().__init__()

        pass
