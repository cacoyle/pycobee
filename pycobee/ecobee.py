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


from collections import namedtuple, OrderedDict
from urllib.parse import urljoin
from os import getcwd, path
from time import sleep, time

from .utils import sqlite_data_factory

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

        super().__init__()

        # sqlite3 creates db file on connect, check to see if table exists
        # break out all of this stuff into backend agnostic methods
        self.db_conn = sqlite3.connect(self.db)

        table_check = self.db_conn.execute(
            '''
            select name from sqlite_master
            where type="table" and name="ECOBEE"
            ''').fetchall()

        if not any(['ECOBEE' in x for x in table_check]):
            self.__initialize_sqlite_db()
            initial_token = self.initialize_application()
            breakpoint()
            self.__write_token_to_backend(initial_token)

        if not hasattr(self, 'token_data'):
            self.token_data = self.__load_token_from_db()

        breakpoint()
        thermostats = self.get('/thermostat')

    def check_token(self):
        """
        Check to see if a token has expired, and if needed refresh.
        """

        if time() >= self.token_data.expires_at:
            new_token = self.get_token(
                self.token_data.app_key,
                refresh_token=self.token_data.refresh_token
            )
            breakpoint()

            new_token['issued'] = time()
            new_token['expires_at'] = new_token['issued'] + new_token['expires_in']
            new_token.pop('expires_in')

            merged_data = self.token_data._asdict() | new_token
            breakpoint()

            # self.token_data = self.token_data(**merged_data)


    def request(self, method, endpoint, params=None, data=None, json=None, check_response=False, **kwargs):
        """
        Override default requests.Session.request method to check for token expiration.
        """

        url = urljoin(self.url, endpoint)

        self.check_token()

        response = super().request(
            method,
            url,
            params,
            data=data,
            json=json,
            **kwargs
        )

        if check_response:
            response.raise_for_status()

        return response


    def __load_token_from_db(self):
        """
        Load token data from sqlite.

        returns TokenData namedtuple.
        """

        self.db_conn.row_factory = sqlite_data_factory

        cursor = self.db_conn.cursor()
        # Make table name app specific
        row = cursor.execute('select * from ECOBEE')

        result = row.fetchone()

        if not result:
            raise Exception('Unable to load token data from backend')

        return result

    def __write_token_to_backend(self, token):
        cursor = self.db_conn.cursor()

        # Change this to update or key off issued as primary
        cursor.execute(f'''
            INSERT INTO ECOBEE (
                {",".join(token._fields)}
            ) VALUES (
                {('?,' * len(self.__DEFAULT_DB_COLUMNS)).rstrip(',')}
            )
            ''',
            token
        )
        self.db_conn.commit()
        breakpoint()


    def __initialize_sqlite_db(self):
        """
        Create initial sqlite db.
        """

        conn = sqlite3.connect(self.db)

        cursor = conn.cursor()

        cursor.execute(
            f'''
            create table ECOBEE (
            {",".join([f"{k} {v}" for k,v in self.__DEFAULT_DB_COLUMNS.items()])}
            )
            '''
        )

        conn.commit()
        conn.close()

    def initialize_application(self, max_retries=5):
        result = requests.get(
            urljoin(self.url, 'authorize'),
            params={
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
            token_result = self.get_token(code=initial_code, app_key=self.app_key)
            if token_result.get('error', None) == 'authorization_pending':
                sleep(60)
                retry_count += 1
            else:
                break

        if retry_count == max_retries:
            # Create an actual error class for this.
            raise(f'Authorization timed out after {max_retries} attempts.')

        token_result['app_key'] = self.app_key
        token_result['initial_code'] = initial_code
        token_result['pin'] = pin
        token_result['issued'] = time()
        token_result['expires_at'] = token_result['issued'] + token_result['expires_in']

        token_data = namedtuple('TokenData', token_result)

        return token_data(**token_result)


    def get_token(self, app_key, code=None, refresh_token=None):
        """
        Get or refresh api tokens.
        """

        if not code and not refresh_token:
            raise ValueError('code or refresh_token must be defined.')

        params = {
            'client_id': app_key,
            'ecobee_type': 'jwt'
        }

        if refresh_token:
            params.update({
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            })
        else:
            params.update({
                'grant_type': 'ecobeePin',
                'code': code
            })

        # Use requests native method to avoid recursion
        result = requests.post(
            urljoin(self.url, 'token'),
            params=params
        )

        return result.json()

    def __del__(self):
        """
        Try to ensure that all important tokens are committed.
        """

        # self.__commit_tokens()
        pass
