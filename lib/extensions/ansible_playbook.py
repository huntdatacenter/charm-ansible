"""
Ansible Playbook runner
=======================

.. code-block:: python

    from .ansible_playbook import Ansible, AnsiblePlaybook

    ansible = Ansible()
    ansible.install_ansible_support()
    ansible.init_charm(charm)

    ansible.apply_playbook('playbook.yaml', tags=['install'], extra_vars={})

"""

import logging
import os
import subprocess
import sys
import yaml
import stat
import json
from functools import wraps
from copy import deepcopy

log = logging.getLogger(__name__)
charm_dir = os.getenv('CHARM_DIR', None)
unit_name = os.getenv('JUJU_UNIT_NAME', None)
ansible_hosts_path = '/etc/ansible/hosts'
# Ansible will automatically include any vars in the following
# file in its inventory when run locally.
ansible_vars_path = '/etc/ansible/host_vars/localhost'

ansible_remote_tmp = '/root/.ansible/tmp'


class AnsiblePlaybookError(Exception):
    """Exception - Ansible Playbook Error."""

    pass


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
            log.warning('Exception on set app_name')
            if charm_dir and isinstance(charm_dir, str) and charm_dir.split('/')[0]:
                self.app_name = charm_dir.split('/')[0]
            if not self.app_name:
                log.error('Could not set app_name')

    def install_ansible_support(self):
        """Create ansible configs."""
        try:
            if ansible_hosts_path and ansible_hosts_path.startswith('/etc/ansible'):
                os.makedirs('/etc/ansible/host_vars', mode=0o755, exist_ok=True)
        except Exception as e:
            log.warning('install_ansible_support failed to create /etc/ansible: {}'.format(str(e)))
        with open(ansible_hosts_path, 'w+') as hosts_file:
            hosts_file.write('[all]\n')
            config = ' '.join([
                'localhost',
                'ansible_connection=local',
                'ansible_remote_tmp=/root/.ansible/tmp',
                # 'ansible_python_interpreter=/usr/bin/python3',
                '',  # newline in the end
            ])
            hosts_file.write(config)

    def apply_playbook(
        self, playbook, tags=None, extra_vars={}, env={}, diff=False, check=False, throw=False
    ):
        """
        Run ansible playbook.

        Execute playbook file.
        """
        kwargs = {}
        if tags:
            kwargs['tags'] = tags.split(',') if isinstance(tags, str) else tags
        pb = AnsiblePlaybook(
            self.charm,
            self.model,
            self.app_name,
            inventory_path=ansible_hosts_path,
            connection="local",
            basedir=charm_dir,
            become=True,
            diff=diff,
            check=check,
            **kwargs
        )

        if charm_dir and os.path.exists(os.path.join(charm_dir, playbook)):
            pb_path = os.path.join(charm_dir, playbook)
        elif os.path.exists(os.path.abspath(playbook)):
            pb_path = os.path.abspath(playbook)
        else:
            pb_path = playbook
        if "/./" in pb_path:
            pb_path = pb_path.replace("/./", "/")

        log.info(f'Run playbook: {pb_path}')
        returncode, results = pb.run(
            pb_path,
            subset="localhost",
            extra_vars=extra_vars,
            env=env,
        )
        if returncode != 0:
            log.error(f"Failed to run ansible playbook: {pb_path}")
            if throw:
                raise AnsiblePlaybookError("Ansible Playbook returned non-zero exit code.")
        return returncode, results


class AnsiblePlaybook:
    def __init__(
        self, charm, model, app_name, inventory_path=ansible_hosts_path, basedir=charm_dir,
        local_tmp='/tmp', remote_tmp=ansible_remote_tmp, **kw
    ):
        from ansible.parsing.dataloader import DataLoader
        from ansible.inventory.manager import InventoryManager
        from ansible.vars.manager import VariableManager

        self.charm = charm
        self.model = model
        self.app_name = app_name

        self.whichpython = sys.executable
        self.loader = DataLoader()
        if basedir and os.path.exists(basedir):
            self.loader.set_basedir(basedir)

        self.inventory = InventoryManager(loader=self.loader, sources=inventory_path)
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)

        try:
            self.verbosity = int(kw.get('verbosity', 0))
        except Exception as e:
            log.error(e)
            self.verbosity = 0

        self._cli_args = dict(
            listtags=kw.get('listtags', False),
            listtasks=kw.get('listtasks', False),
            listhosts=kw.get('listhosts', False),
            connection=kw.get('connection', 'ssh'),
            connection_password_file=kw.get('connection_password_file', None),
            module_path=kw.get('module_path', None),
            forks=kw.get('forks', 10),
            remote_user=kw.get('remote_user', None),
            private_key_file=kw.get('private_key_file', None),
            host_key_checking=kw.get('host_key_checking', True),
            ssh_common_args=kw.get('ssh_common_args', None),
            ssh_extra_args=kw.get('ssh_extra_args', None),
            sftp_extra_args=kw.get('sftp_extra_args', None),
            scp_extra_args=kw.get('scp_extra_args', None),
            become=kw.get('become', True),
            become_method=kw.get('become_method', 'sudo'),
            become_user=kw.get('become_user', 'root'),
            become_ask_pass=kw.get('become_ask_pass', False),  # -K
            ask_pass=kw.get('ask_pass', False),  # -k
            tags=kw.get('tags', []),
            skip_tags=kw.get('skip_tags', []),
            timeout=kw.get('timeout', 30),
            task_timeout=kw.get('task_timeout', 0),
            force_handlers=kw.get('force_handlers', False),
            flush_cache=kw.get('flush_cache', False),
            check=kw.get('check', False),
            diff=kw.get('diff', False),
            syntax=kw.get('syntax', False),
            start_at_task=kw.get('start_at_task', None),
            verbosity=self.verbosity,
            # Added tmp
            local_tmp=local_tmp,
            remote_tmp=remote_tmp,
        )

    def _get_cli_args(self, args={}):
        from ansible.module_utils.common.collections import ImmutableDict
        cli_args = self._cli_args.copy()
        if args:
            cli_args.update(args)
        return ImmutableDict(**cli_args)

    def run(
        self, playbook_path, subset=None, extra_vars={}, passwords={}, env={},
        verbosity=0, debug=False, debug_executor=False, **kw
    ):
        from ansible import context
        try:
            from ansible.utils.display import initialize_locale
        except Exception:
            from ansible.cli import initialize_locale
        from ansible.executor.playbook_executor import PlaybookExecutor, display
        from ansible.playbook import Playbook

        if self.model and hasattr(self.model, 'config'):
            model_config = dict(deepcopy(self.model.config))
            model_config['app_name'] = self.app_name
        else:
            model_config = {}

        extra = juju_state_to_yaml(
            ansible_vars_path, model_config=model_config, namespace_separator='__',
            allow_hyphens_in_keys=False, mode=(stat.S_IRUSR | stat.S_IWUSR)
        )
        extra.update(extra_vars)

        try:
            display.verbosity = int(verbosity) if verbosity > self.verbosity else int(self.verbosity)
        except Exception as e:
            log.error(e)
            display.verbosity = 0
        context.CLIARGS = self._get_cli_args(kw)
        initialize_locale()
        if not os.path.exists(playbook_path):
            log.error(f"Ansible Playbook does not exist: {playbook_path}")
            return 255, {}

        try:
            p = Playbook.load(playbook_path, variable_manager=self.variable_manager, loader=self.loader)
        except Exception as e:
            log.error(e)
            log.error("File is not a valid Ansible Playbook")
            return 255, {}

        if subset:
            self.inventory.subset(subset)
        else:
            self.inventory.subset(None)

        try:
            patterns = {play.hosts for play in p.get_plays()}
            # Create deduplicated list of hosts
            hosts = list({host.name for pattern in patterns for host in self.inventory.get_hosts(pattern=pattern)})
        except Exception as e:
            log.warning(e, exc_info=True)
            hosts = []

        if not hosts:
            log.error(f"No hosts found: subset={subset} patterns={','.join(patterns)}")
            return 255, {}

        if debug:
            log.info(f"Target hosts: {hosts}")

        for key, value in extra.items():
            self.variable_manager.extra_vars[key] = value
        self.variable_manager.extra_vars['ansible_check_mode'] = True if context.CLIARGS['check'] else False

        try:
            os.environ["WHICHPYTHON"] = self.whichpython
            os.environ["ANSIBLE_FORCE_COLOR"] = "1"
            # NOTE do not apply for all - maybe base on parameter
            # os.environ["ANSIBLE_SSH_ARGS"] = "-o StrictHostKeyChecking=accept-new"
            os.environ["ANSIBLE_PYTHON_INTERPRETER"] = self.whichpython

            for key, value in env.items():
                os.environ[key] = value if isinstance(value, str) else str(value)
            executor = PlaybookExecutor(
                playbooks=[playbook_path], inventory=self.inventory,
                variable_manager=self.variable_manager, loader=self.loader,
                passwords=passwords
            )
            returncode = executor.run()
            if debug:
                log.info(f"Task status: returncode={returncode} success={(returncode == 0)}")
        except Exception as e:
            log.error(e)
        finally:
            os.environ.pop('WHICHPYTHON', None)
            os.environ.pop('ANSIBLE_PYTHON_INTERPRETER', None)

        try:
            results = {}
            if executor._tqm and hosts:
                for host in hosts:
                    results[host] = executor._tqm._stats.summarize(host)
                executor._tqm.cleanup()
        except Exception as e:
            log.error(e)

        if debug_executor:
            return returncode, results, executor

        return returncode, results


def dict_keys_without_hyphens(a_dict):
    """Return the a new dict with underscores instead of hyphens in keys."""
    return dict(
        (key.replace('-', '_'), val) for key, val in a_dict.items())


cache = {}


def cached(func):
    """Cache return values for multiple executions of func + args
    For example::
        @cached
        def unit_get(attribute):
            pass
        unit_get('test')
    will cache the result of unit_get + 'test' for future calls.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        global cache
        key = json.dumps((func, args, kwargs), sort_keys=True, default=str)
        try:
            return cache[key]
        except KeyError:
            pass  # Drop out of the exception handler scope.
        res = func(*args, **kwargs)
        cache[key] = res
        return res
    wrapper._wrapped = func
    return wrapper


@cached
def unit_get(attribute):
    """Get the unit ID for the remote unit"""
    _args = ['unit-get', '--format=json', attribute]
    try:
        return json.loads(subprocess.check_output(_args).decode('UTF-8'))
    except ValueError:
        return None


def juju_state_to_yaml(
    yaml_path, model_config={}, namespace_separator=':',
    allow_hyphens_in_keys=True, mode=None
):
    """Update the juju config and state in a yaml file.
    This includes any current relation-get data, and the charm
    directory.
    This function was created for the ansible and saltstack
    support, as those libraries can use a yaml file to supply
    context to templates, but it may be useful generally to
    create and update an on-disk cache of all the config, including
    previous relation data.
    By default, hyphens are allowed in keys as this is supported
    by yaml, but for tools like ansible, hyphens are not valid [1].
    [1] http://www.ansibleworks.com/docs/playbooks_variables.html#what-makes-a-valid-variable-name
    """
    config = model_config

    # Add the charm_dir which we will need to refer to charm
    # file resources etc.
    config['charm_dir'] = charm_dir
    config['local_unit'] = os.environ['JUJU_UNIT_NAME']
    config['unit_private_address'] = unit_get('private-address')
    config['unit_public_address'] = unit_get('public-address')

    # Don't use non-standard tags for unicode which will not
    # work when salt uses yaml.safe_load.
    yaml.add_representer(
        str, lambda dumper, value: dumper.represent_scalar('tag:yaml.org,2002:str', value)
    )

    yaml_dir = os.path.dirname(yaml_path)
    if not os.path.exists(yaml_dir):
        os.makedirs(yaml_dir)

    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as existing_vars_file:
            existing_vars = yaml.safe_load(existing_vars_file.read())
    else:
        with open(yaml_path, "w+"):
            pass
        existing_vars = {}

    if mode is not None:
        os.chmod(yaml_path, mode)

    if not allow_hyphens_in_keys:
        config = dict_keys_without_hyphens(config)
    existing_vars.update(config)

    # update_relations(existing_vars, namespace_separator)

    with open(yaml_path, "w+") as fp:
        fp.write(yaml.dump(existing_vars, default_flow_style=False))

    return existing_vars
