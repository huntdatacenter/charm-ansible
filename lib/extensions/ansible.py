# https://github.com/juju/charm-helpers/blob/master/charmhelpers/contrib/ansible/__init__.py

import json
import logging
import os
import stat
import subprocess
from copy import deepcopy

from .contexts import juju_state_to_yaml

logger = logging.getLogger(__name__)
charm_dir = os.environ.get('CHARM_DIR', '')
ansible_hosts_path = '/etc/ansible/hosts'
# Ansible will automatically include any vars in the following
# file in its inventory when run locally.
ansible_vars_path = '/etc/ansible/host_vars/localhost'


class Ansible():

    def __init__(self):
        self.charm = None
        self.model = None
        self.app_name = None

    def init_charm(self, charm):
        self.charm = charm
        self.model = charm.model
        try:
            self.app_name = self.model.app.name
        except Exception:
            logger.warning('Exception on set app_name')
            if charm_dir and isinstance(charm_dir, str) and charm_dir.split('/')[0]:
                self.app_name = charm_dir.split('/')[0]
            if not self.app_name:
                logger.error('Could not set app_name')

    def install_ansible_support(self, from_ppa=True, ppa_location='ppa:ansible/ansible'):
        """Installs Ansible via APT.
        By default this installs Ansible from the `PPA`_ linked from
        the Ansible `website`_ or from a PPA set in ``ppa_location``.
        .. _PPA: https://launchpad.net/~ansible/+archive/ubuntu/ansible
        .. _website: http://docs.ansible.com/intro_installation.html#latest-releases-via-apt-ubuntu
        If ``from_ppa`` is ``False``, then Ansible will be installed from
        Ubuntu's Universe repositories.
        """
        # if from_ppa:
        #     charmhelpers.fetch.add_source(ppa_location)
        #     charmhelpers.fetch.apt_update(fatal=True)
        # charmhelpers.fetch.apt_install('ansible')
        try:
            if '/etc/ansible' in ansible_hosts_path:
                os.makedirs('/etc/ansible/host_vars', mode=0o755, exist_ok=True)
        except Exception as e:
            logger.warning('install_ansible_support failed to create /etc/ansible: {}'.format(str(e)))
        with open(ansible_hosts_path, 'w+') as hosts_file:
            config = ' '.join([
                'localhost',
                'ansible_connection=local',
                'ansible_remote_tmp=/root/.ansible/tmp',
                'ansible_python_interpreter=/usr/bin/python3'
            ])
            hosts_file.write('{}\n'.format(config))

    def apply_playbook(self, playbook, tags=None, extra_vars=None):
        """Run a playbook.
        This helper runs a playbook with juju state variables as context,
        therefore variables set in application config can be used directly.
        List of tags (--tags) and dictionary with extra_vars (--extra-vars)
        can be passed as additional parameters.
        Read more about playbook `_variables`_ online.
        .. _variables: https://docs.ansible.com/ansible/latest/user_guide/playbooks_variables.html
        Example::
            # Run ansible/playbook.yaml with tag install and pass extra
            # variables var_a and var_b
            apply_playbook(
                playbook='ansible/playbook.yaml',
                tags=['install'],
                extra_vars={'var_a': 'val_a', 'var_b': 'val_b'}
            )
            # Run ansible/playbook.yaml with tag config and extra variable nested,
            # which is passed as json and can be used as dictionary in playbook
            apply_playbook(
                playbook='ansible/playbook.yaml',
                tags=['config'],
                extra_vars={'nested': {'a': 'value1', 'b': 'value2'}}
            )
            # Custom config file can be passed within extra_vars
            apply_playbook(
                playbook='ansible/playbook.yaml',
                extra_vars="@some_file.json"
            )
        """
        tags = tags or []
        tags = ",".join(tags)
        if self.model or not hasattr(self.model, 'config'):
            model_config = dict(deepcopy(self.model.config))
            model_config['app_name'] = self.app_name
        else:
            model_config = {}
        juju_state_to_yaml(
            ansible_vars_path, model_config=model_config, namespace_separator='__',
            allow_hyphens_in_keys=False, mode=(stat.S_IRUSR | stat.S_IWUSR))

        # we want ansible's log output to be unbuffered
        env = os.environ.copy()
        # proxy_settings = charmhelpers.core.hookenv.env_proxy_settings()
        # if proxy_settings:
        #     env.update(proxy_settings)
        charm_dir = os.getenv('CHARM_DIR', None)
        if charm_dir:
            env_path = os.path.join(charm_dir, 'venv/bin')
            env['PATH'] = env['PATH'] if env_path in env['PATH'] else '{}:{}'.format(env_path, env['PATH'])
            logger.info('Ansible PATH: {}'.format(env['PATH']))
        env['PYTHONUNBUFFERED'] = "1"
        call = [
            'python3',
            'venv/bin/ansible-playbook',
            '-c',
            'local',
            playbook,
        ]
        if tags:
            call.extend(['--tags', '{}'.format(tags)])
        if extra_vars:
            call.extend(['--extra-vars', json.dumps(extra_vars)])
        subprocess.check_call(call, cwd=charm_dir, env=env)
