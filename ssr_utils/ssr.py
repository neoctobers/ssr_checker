# coding:utf-8
import os
import sys
import time
import socket
import requests_cache
import proxy_fn
import subprocess
import profig
import tempfile
import common_patterns
import cli_print as cp
import urllib.parse
import proxychains_conf_generator
import ip_query
from qwert import list_fn
from qwert import file_fn
from qwert import base64
from .errors import *


class SSR:
    def __init__(self, path_to_config: str = 'config.ini'):
        self._cfg = profig.Config(path_to_config)
        self._cfg.init('path.python', '/usr/bin/python3')
        self._cfg.init('path.python_ssr', '/data/repo/shadowsocksr/shadowsocks/local.py')
        self._cfg.init('path.proxychains4', '/usr/bin/proxychains4')
        self._cfg.init('ssr_utils.local_port', 13431)
        self._cfg.init('ssr_utils.path_to_pre_proxy', 'pre_proxy.txt')
        self._cfg.init('ssr_utils.proxychains4_cache_time', 300)
        self._cfg.sync()

        self._path_to_config = path_to_config

        self._server = None
        self._port = None
        self._method = None
        self._password = None
        self._protocol = None
        self._proto_param = None
        self._obfs = None
        self._obfs_param = None

        self._remarks = None
        self._group = None

        self._server_ip = None
        self._server_domain = None

        self._local_address = None
        self._local_port = None
        self._path_to_ssr_conf = None

        self._exit_ip = None

        self._cmd = None
        self._cmd_prefix = None
        self._sub_progress = None
        pass

    def __reset_attributes(self):
        self._server = ''
        self._port = 443
        self._method = ''
        self._password = ''
        self._protocol = 'origin'
        self._proto_param = None
        self._obfs = 'plain'
        self._obfs_param = None

        self._remarks = None
        self._group = None

        self._server_ip = None
        self._server_domain = None

        self._local_address = None
        self._local_port = None
        self._path_to_ssr_conf = None

        self._exit_ip = None

    @property
    def server(self):
        return self._server

    @property
    def port(self):
        return self._port

    @property
    def method(self):
        return self._method

    @property
    def password(self):
        return self._password

    @property
    def protocol(self):
        return self._protocol

    @property
    def proto_param(self):
        return self._proto_param or ''

    @property
    def obfs(self):
        return self._obfs

    @property
    def obfs_param(self):
        return self._obfs_param or ''

    @property
    def remarks(self):
        return self._remarks or ''

    @remarks.setter
    def remarks(self, value: str):
        self._remarks = value

    @property
    def group(self):
        return self._group or ''

    @group.setter
    def group(self, value: str):
        self._group = value

    @property
    def server_ip(self):
        if self._server_ip:
            return self._server_ip

        # ip == server?
        if common_patterns.is_ip_address(self.server):
            self._server_ip = self.server
            return self._server_ip

        # domain
        self._server_domain = self.server

        # domain 2 exit_ip
        self._server_ip = socket.gethostbyname(self._server_domain)
        return self._server_ip

    @property
    def server_domain(self):
        if self._server_domain:
            return self._server_domain

        # domain
        if not common_patterns.is_ip_address(self.server):
            self._server_domain = self.server
            return self._server_domain

        # None
        return self._server_domain

    @property
    def local_address(self):
        return self._local_address or '127.0.0.1'

    @local_address.setter
    def local_address(self, value: str):
        self._local_address = value

    @property
    def local_port(self):
        return self._local_port or self._cfg['ssr_utils.local_port']

    @local_port.setter
    def local_port(self, value: int):
        self._local_port = value

    @property
    def path_to_ssr_conf(self):
        return self._path_to_ssr_conf or os.path.join(os.getcwd(), 'shadowsocksr-config.json')

    @property
    def exit_ip(self):
        return self._exit_ip

    @property
    def exit_country(self):
        if self._exit_ip:
            return self._exit_ip['country']
        return None

    @property
    def exit_country_code(self):
        if self._exit_ip:
            return self._exit_ip['country_code']
        return None

    @property
    def pc4_conf_file(self):
        if os.path.exists(self._cfg['ssr_utils.path_to_pre_proxy']):
            path_to_pc4_conf_file = os.path.join(tempfile.gettempdir(), 'ssr_utils_pc4.conf')

            if os.path.exists(path_to_pc4_conf_file) and \
                    time.time() - os.stat(path_to_pc4_conf_file).st_mtime \
                    < self._cfg['ssr_utils.proxychains4_cache_time']:
                return path_to_pc4_conf_file

            lines = file_fn.read_to_list(self._cfg['ssr_utils.path_to_pre_proxy'])
            if lines:
                lines = list_fn.unique(lines)
                for line in lines:
                    requests_proxies = proxy_fn.line2requests_proxies(line)

                    # valid, and generate pc4 conf
                    try:
                        ip = ip_query.ip_query(requests_proxies=requests_proxies)
                        if ip:
                            g = proxychains_conf_generator.Generator(
                                proxy=line,
                                quiet_mode=True,
                            )
                            return g.write(path_to_conf=path_to_pc4_conf_file)

                    except Exception as e:
                        cp.error(e)
                        pass

            cp.error('No available proxy in "{}". Remove it if do not need a proxy.'.format(
                self._cfg['ssr_utils.path_to_pre_proxy'],
            ))
            cp.ex()

        return None

    @property
    def invalid_attributes(self):
        keys = [
            'server',
            'port',
            'method',
            'password',
            'protocol',
            'obfs',
        ]

        for key in keys:
            if not getattr(self, key):
                cp.error('Attribute `{}` is invalid.'.format(key))
                return True
        return False

    def load(self, obj):
        self.__reset_attributes()

        keys = {
            'server': '',
            'port': 443,
            'method': '',
            'password': '',
            'protocol': 'origin',
            'proto_param': None,
            'obfs': 'plain',
            'obfs_param': None,

            'remarks': None,
            'group': None,
        }

        for key, value in keys.items():
            setattr(self, '_{}'.format(key), getattr(obj, key, value))

    def set(self,
            server: str = '',
            port: int = 443,
            method: str = '',
            password: str = '',
            protocol: str = 'origin',
            proto_param: str = '',
            obfs: str = 'plain',
            obfs_param: str = '',

            remarks: str = None,
            group: str = None,
            ):
        self.__reset_attributes()

        self._server = server
        self._port = port
        self._method = method
        self._password = password
        self._protocol = protocol
        self._proto_param = proto_param
        self._obfs = obfs
        self._obfs_param = obfs_param

        if remarks:
            self._remarks = remarks
        if group:
            self._group = group

    @property
    def config(self):
        # check attributes
        if self.invalid_attributes:
            return None

        return {
            'server': self._server,
            'port': self._port,
            'method': self._method,
            'password': self._password,
            'protocol': self._protocol,
            'proto_param': self._proto_param,
            'obfs': self._obfs,
            'obfs_param': self._obfs_param,

            'remarks': self.remarks,
            'group': self.group,
        }

    @property
    def url(self):
        # check attributes
        if self.invalid_attributes:
            return None

        prefix = '{server}:{port}:{protocol}:{method}:{obfs}:{password}'.format(
            server=self._server,
            port=self._port,
            protocol=self._protocol,
            method=self._method,
            obfs=self._obfs,
            password=base64.encode(self._password, urlsafe=True))

        suffix_list = []
        if self._proto_param:
            suffix_list.append('protoparam={proto_param}'.format(
                proto_param=base64.encode(self.proto_param, urlsafe=True),
            ))

        if self._obfs_param:
            suffix_list.append('obfsparam={obfs_param}'.format(
                obfs_param=base64.encode(self.obfs_param, urlsafe=True),
            ))

        suffix_list.append('remarks={remarks}'.format(
            remarks=base64.encode(self.remarks, urlsafe=True),
        ))

        suffix_list.append('group={group}'.format(
            group=base64.encode(self.group, urlsafe=True),
        ))

        return 'ssr://{}'.format(base64.encode('{prefix}/?{suffix}'.format(
            prefix=prefix,
            suffix='&'.join(suffix_list),
        ), urlsafe=True))

    @url.setter
    def url(self, url: str):
        self.__reset_attributes()

        r = url.split('://')

        try:
            if r[0] == 'ssr':
                self.__parse_ssr(r[1])
            elif r[0] == 'ss':
                self.__parse_ss(r[1])
        except Exception as e:
            cp.error(e)
            pass

    def __parse_ssr(self, ssr_base64: str):
        ssr = ssr_base64.split('#')[0]
        ssr = base64.decode(ssr)

        if isinstance(ssr, bytes):
            return

        ssr_list = ssr.split(':')
        password_and_params = ssr_list[5].split('/?')

        self._server = ssr_list[0]
        self._port = int(ssr_list[1])
        self._protocol = ssr_list[2]
        self._method = ssr_list[3]
        self._obfs = ssr_list[4]
        self._password = base64.decode(password_and_params[0])

        params_dict = dict()
        for param in password_and_params[1].split('&'):
            param_list = param.split('=')
            params_dict[param_list[0]] = base64.decode(param_list[1])

        params_dict_keys = params_dict.keys()
        for key in ['proto_param', 'obfs_param', 'remarks', 'group']:
            tmp_key = key.replace('_', '')
            if tmp_key in params_dict_keys:
                setattr(self, '_{}'.format(key), params_dict[tmp_key])

    def __parse_ss(self, ss_base64: str):
        ss = ss_base64.split('#')
        if len(ss) > 1:
            self._remarks = urllib.parse.unquote(ss[1])
        ss = base64.decode(ss[0])

        if isinstance(ss, bytes):
            return

        # use split and join, in case of the password contains "@"/":"
        str_list = ss.split('@')

        server_and_port = str_list[-1].split(':')
        method_and_pass = '@'.join(str_list[0:-1]).split(':')

        self._server = server_and_port[0]
        self._port = int(server_and_port[1])
        self._method = method_and_pass[0]
        self._password = ':'.join(method_and_pass[1:])

    @property
    def plain(self):
        # check attributes
        if self.invalid_attributes:
            return None

        return '     server: {server}\n' \
               '       port: {port}\n' \
               '     method: {method}\n' \
               '   password: {password}\n' \
               '   protocol: {protocol}\n' \
               'proto_param: {proto_param}\n' \
               '       obfs: {obfs}\n' \
               ' obfs_param: {obfs_param}\n' \
               '    remarks: {remarks}\n' \
               '      group: {group}'.format(server=self.server,
                                             port=self.port,
                                             method=self.method,
                                             password=self.password,
                                             protocol=self.protocol,
                                             proto_param=self.proto_param,
                                             obfs=self.obfs,
                                             obfs_param=self.obfs_param,
                                             remarks=self.remarks,
                                             group=self.group,
                                             )

    @property
    def config_json_string(self):
        return self.get_config_json_string()

    def get_config_json_string(self, by_ip: bool = False):
        # check attributes
        if self.invalid_attributes:
            return None

        configs = list()

        # by: ip / server
        if by_ip:
            configs.append('"server": "{}",'.format(self.server_ip))
        else:
            configs.append('"server": "{}",'.format(self.server))

        configs.append('"server_port": {},'.format(self.port))
        configs.append('"method": "{}",'.format(self.method))
        configs.append('"password": "{}",'.format(self.password))
        configs.append('"protocol": "{}",'.format(self.protocol))
        configs.append('"protocol_param": "{}",'.format(self.proto_param))
        configs.append('"obfs": "{}",'.format(self.obfs))
        configs.append('"obfs_param": "{}",'.format(self.obfs_param))
        configs.append('"local_address": "{}",'.format(self.local_address))
        configs.append('"local_port": {}'.format(self.local_port))

        return '{\n' + '\n'.join(configs) + '\n}'

    def write_config_file(self, path_to_file=None, by_ip: bool = False, plain_to_console: bool = False):
        # check attributes
        if self.invalid_attributes:
            return None

        if path_to_file:
            self._path_to_ssr_conf = path_to_file

        cp.about_t('Generating', self.path_to_ssr_conf, 'for shadowsocksr')
        with open(self.path_to_ssr_conf, 'wb') as f:
            json_string = self.get_config_json_string(by_ip=by_ip)
            f.write(json_string.encode('utf-8'))
            cp.success()
            if plain_to_console:
                cp.plain_text(json_string)

    @property
    def is_available(self):
        return self.get_available()

    def get_available(self):
        if self.invalid_attributes:
            return None

        # check system
        if 'win32' == sys.platform:
            raise SystemNotSupportedException('Cannot use property `is_available` in windows.')

        # READY
        cp.job('CHECK AVAILABLE')

        self._path_to_ssr_conf = os.path.join(tempfile.gettempdir(), 'ssr_utils_{time}.json'.format(
            time=str(time.time()).replace('.', '').ljust(17, '0'),
        ))

        # cmd with pc4
        pc4_conf_file = self.pc4_conf_file
        if pc4_conf_file:
            cp.about_to('Use', pc4_conf_file, 'for proxychains')
            self._cmd = '{path_to_pc4} -q -f {pc4_conf_file} '.format(
                path_to_pc4=self._cfg['path.proxychains4'],
                pc4_conf_file=pc4_conf_file,
            )
        else:
            self._cmd = ''

        # Python SSR
        self._cmd += '{python} {python_ssr} -c {path_to_config}'.format(
            python=self._cfg['path.python'],
            python_ssr=self._cfg['path.python_ssr'],
            path_to_config=self.path_to_ssr_conf,
        )

        # By server_ip
        self.write_config_file(by_ip=True)

        ip = self.__ip_query(hint='by IP')
        if ip:
            self._server = self._server_ip
            self.__remove_ssr_conf()
            print()
            return ip

        # By server/domain
        if self.server_ip != self.server:
            self.write_config_file()
            ip = self.__ip_query(hint='by Server/Domain')
            self.__remove_ssr_conf()
            print()
            return ip

        return None

    def __ip_query(self, hint: str):
        cp.about_t('Start a sub progress of SSR', hint)

        # sub progress
        self._sub_progress = subprocess.Popen(
            self._cmd.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
        )

        # Group PID
        gpid = os.getpgid(self._sub_progress.pid)
        cp.wr(cp.Fore.LIGHTYELLOW_EX + '(G)PID {} '.format(gpid))

        # wait, during the progress launching.
        for i in range(0, 5):
            cp.wr(cp.Fore.LIGHTBLUE_EX + '.')
            cp.fi()
            time.sleep(1)
        cp.success(' Next.')

        # Request for IP
        ip = None
        try:
            cp.about_t('Try to request for the IP address')

            ip = ip_query.ip_query(requests_proxies=proxy_fn.requests_proxies(host=self.local_address,
                                                                              port=self.local_port,
                                                                              ))

            if ip:
                cp.success('{} {}'.format(ip['ip'], ip['country']))
            else:
                cp.fx()

        except Exception as e:
            # ConnectionError?
            cp.fx()
            cp.error(e)

        finally:
            cp.about_t('Kill SSR sub progress', 'PID {pid}'.format(pid=gpid))
            os.killpg(gpid, 9)
            cp.success('Done.')

        if ip:
            self._exit_ip = ip
            return ip

        return None

    def __remove_ssr_conf(self):
        cp.about_t('Deleting', self.path_to_ssr_conf, 'config file')
        os.remove(self.path_to_ssr_conf)
        cp.success()

    @staticmethod
    def __is_port_open(port: int):
        cp.about_t('Checking', 'local port #.{}'.format(port))

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(('127.0.0.1', port))
            s.shutdown(2)
            cp.success('is open')
            return True
        except:
            cp.success('is down')
            return False


def get_urls_by_subscribe(url: str,
                          cache_backend='sqlite',
                          cache_expire_after=300,
                          request_proxies=None,
                          ):
    # request session
    request_session = requests_cache.core.CachedSession(
        cache_name=os.path.join(tempfile.gettempdir(), 'ssr_utils_cache'),
        backend=cache_backend,
        expire_after=cache_expire_after,
    )

    # request headers
    request_session.headers.update(
        {
            'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/71.0.3578.80 '
                          'Safari/537.36'
        }
    )

    # get resp
    resp = request_session.get(url, proxies=request_proxies)
    if resp.status_code == 200:
        return get_urls_by_base64(resp.text)

    return list()


def get_urls_by_base64(text_base64: str):
    text = base64.decode(text_base64)
    if isinstance(text, str):
        return list_fn.remove_and_unique(text.split('\n'))
    return list()


def get_urls_by_string(string: str):
    return list_fn.unique(common_patterns.findall_ssr_urls(string=string))
