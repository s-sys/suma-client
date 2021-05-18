"""SuseManager client module."""

import logging
import ssl
import time

from xmlrpc.client import ServerProxy


LOGGER = logging.getLogger(__name__)


class SuseManagerClient:
    """Interface to communicate with SuseManager."""
    # pylint: disable=too-many-instance-attributes

    STATUS_DOWN = 'down'
    STATUS_FAILED = 'failed'
    STATUS_SUCCESS = 'success'

    def __init__(self, **kwargs):
        """Set variables while building class."""
        self._client = None
        self._token = None
        self._error = None
        self._host = kwargs.get('host', None)
        self._user = kwargs.get('user', None)
        self._passwd = kwargs.get('passwd', None)
        self._keep_session = kwargs.get('keep_session', False)
        _skip_ssl = kwargs.get('skip_ssl', True)
        if _skip_ssl:
            self._ssl_cert = ssl._create_unverified_context()  # pylint: disable=protected-access
        else:
            self._ssl_cert = None

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def create_client(self):
        """Creates the client object."""
        self._client = ServerProxy(
            f'{self._host}/rpc/api',
            verbose=0,
            context=self._ssl_cert,
            use_datetime=True,
        )

    def login(self):
        """Log into SuseManager."""
        self.create_client()
        try:
            self._token = self._client.auth.login(self._user, self._passwd)
        except TimeoutError as err_timeout:
            LOGGER.info('SuseManagerClient Login: Timeout - %s', err_timeout)
            self._error = err_timeout
            return SuseManagerClient.STATUS_DOWN
        except ssl.SSLError as err:
            LOGGER.info('SuseManagerClient Login: SSL Problem - %s', err)
            self._error = ('SSL Problem', err)
            return SuseManagerClient.STATUS_FAILED
        except Exception as err:  # pylint: disable=broad-except
            LOGGER.warning('SuseManagerClient Login: Exception - %s', err)
            self._error = err
            return SuseManagerClient.STATUS_FAILED

        LOGGER.info('SuseManagerClient Login: Success')
        return SuseManagerClient.STATUS_SUCCESS

    def logout(self):
        """Log out of SuseManager."""
        if not self._token:
            return
        if not self._keep_session:
            LOGGER.debug('SuseManagerClient Logout')
            self._client.auth.logout(self._token)
            self._client = None
            self._token = None

    def get_error(self):
        """Returns the last error."""
        return self._error

    def run_command(self, class_name, function_name, args=None, retry_times=5):
        """Execute a SuseManager command."""
        if not self._token:
            self.login()
        n_tries = 0
        while n_tries < retry_times:
            susemanager = getattr(self._client, class_name)
            function_api = getattr(susemanager, function_name)
            result = None
            if not args:
                args = []
            try:
                LOGGER.debug('SuseManagerClient Run Command: Executing')
                result = function_api(self._token, *args)
            except TimeoutError as err_timeout:
                LOGGER.info('SuseManagerClient Run Command: Timeout - %s', err_timeout)
                n_tries += 1
                LOGGER.info('SuseManagerClient Run Command: Failed - Retrying (%d/%d)', n_tries, retry_times)
                time.sleep(2)
            except Exception as err:
                LOGGER.warning('SuseManagerClient Run Command: Exception - %s', err)
                raise err
            LOGGER.debug('SuseManagerClient Run Command: Success')
            return result
        return None
