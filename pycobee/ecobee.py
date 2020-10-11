#!/usr/bin/env python

"""
Simple Ecobee API Interface.

See https://www.ecobee.com/developers/ for information on setting up your own
custom app.

You'll need an application key to initialize this class, which will take care
of the remaining setup and configuration short of approving the application
with a PIN in the 'My Apps' section of the portal.

If initial authorization times out, or your sqlite db is lost or corrupted,
you will have to re-register your application in the portal.
"""


from collections import namedtuple
from urllib.parse import urljoin
from os import getcwd, path
from time import sleep

import arrow
import requests
import sqlite3

class Ecobee(requests.Session):

    __DEFAULT_SQLITE_DB = path.join(getcwd(), '.ecobee.db')
    __DEFAULT_ECOBEE_API_URL = 'https://api.ecobee.com'

    __DEFAULT_DB_COLUMNS = {
        'app_key': 'text',
        'pin': 'text',
        'initial_code': 'text',
        'access_token': 'text',
        'token_type': 'text',
        'expires_in': 'integer',
        'refresh_token': 'text',
        'scope': 'text',
        'issued': 'integer',
        'expires_at': 'integer'
    }

    def __init__(self, app_key, url=__DEFAULT_ECOBEE_API_URL, dbfile=__DEFAULT_SQLITE_DB, **kwargs):

        self.url = url if url else self.__DEFAULT_ECOBEE_API_URL
        self.db = dbfile if dbfile else self.__DEFAULT_SQLITE_DB
        self.app_key = app_key
        # self.token_data = namedtuple('TokenData', list(self.__DEFAULT_DB_COLUMNS.keys()))

        super().__init__()

        # sqlite3 implicitly creates db file, check to see if table exists
        self.db_conn = sqlite3.connect(self.db)

        table_check = self.db_conn.execute(
            '''
            select name from sqlite_master
            where type="table" and name="ECOBEE"
            ''').fetchall()

        if not any(['ECOBEE' in x for x in table_check]):
            self.__initialize_sqlite_db()
            init_token_request = self.initialize_application()

        self.token_data = self.__load_token_from_db()

        breakpoint()

    def __token_data_factory(self, cursor, row):
        """
        """

        fields = [col[0] for col in cursor.description]
        Row = namedtuple("Row", fields)
        return Row(*row)

    def __load_token_from_db(self):
        """
        Load token data from sqlite.

        returns TokenData namedtuple.
        """

        self.db_conn.row_factory = self.__token_data_factory

        cursor = self.db_conn.cursor()
        # Make table name app specific
        row = cursor.execute('select * from ECOBEE')

        result = row.fetchone()

        return result


    def __initialize_sqlite_db(self):
        """
        Create initial sqlite db.
        """

        conn = sqlite3.connect(self.db)

        cursor = conn.cursor()

        cursor.execute(
            'create table ECOBEE (' \
            f'{",".join([f"{k} {v}" for k,v in self.__DEFAULT_DB_COLUMNS.items()])}' \
            ')'
        )

        conn.commit()
        conn.close()

    # def __commit_tokens(self, *args):
    def __commit_tokens(self):
        c = self.db_conn.cursor()
        # Fake data for now
        print(f'insert into ECOBEE values ({("?," * len(self.__DEFAULT_DB_COLUMNS)).rstrip(",")})')
        c.execute(f'insert into ECOBEE values ({("?," * len(self.__DEFAULT_DB_COLUMNS)).rstrip(",")})', ('abc1024', 'pb12', 'Bearer', 1234567890, 'abc2048', 'read,write', 1234567890, 1234567890))
        self.db_conn.commit()
        breakpoint()
        c.close()

    def __read_tokens(self):
        cursor = self.db_conn.cursor()
        cursor.execute(f'select {",".join(self.__DEFAULT_DB_COLUMNS.keys())} from ECOBEE')
        # for thing in map(self.token_data._make, c.fetchall()):
        #     breakpoint()
        #     print(thing.key_id)
        #
        self.token_data = self.token_data._make(cursor.fetchone())
        breakpoint()
        cursor.close()

    def initialize_application(self, max_retries=5):
        result = self.get(
            urljoin(self.url, 'authorize'),
            params = {
                "response_type": "ecobeePin",
                "client_id": self.app_key,
                "scope": "smartRead,smartWrite"
            }
        )

        result.raise_for_status()

        json_result = result.json()

        pin = json_result['ecobeePin']
        initial_code = json_result['code']

        print(f'Please enter the following pin under the app section in your ecobee account: {pin}')

        retry_count = 0

        # This needs to be tested more
        while retry_count <= max_retries:
            token_result = self.get_token(initial_code, self.app_key)
            if token_result.get('error', None) == 'authorization_pending':
                sleep(60)
                retry_count += 1
            else:
                break

        if retry_count == max_retries:
            # Create an actual error class for this.
            raise(f'Authorization timed out after {max_retres} attempts.')

        return json_result

    def get_token(self, code, app_key):
        result = self.post(
            urljoin(self.url, 'token'),
            params={
                'grant_type': 'ecobeePin',
                'code': code,
                'client_id': app_key,
                'ecobee_type': 'jwt'

            }
        )

        return result.json()

    def __del__(self):
        """
        Try to ensure that all important tokens are committed.
        """

        pass

