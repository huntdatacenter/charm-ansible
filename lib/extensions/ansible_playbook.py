"""
Ansible Playbook runner
=======================

.. code-block:: python

    from .ansible_playbook import Ansible, AnsiblePlaybook

    ansible_manager = Ansible()
    ansible_manager.install_ansible_support()
    ansible_manager.init_charm(charm)

    ansible_manager.apply_playbook('playbook.yaml', tags=['install'], extra_vars={})

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
log.setLevel(logging.WARNING)

CHARM_DIR = os.getenv('CHARM_DIR', os.getcwd())
LOCAL_UNIT_NAME = os.getenv('JUJU_UNIT_NAME', None)

try:
    charm_hosts_path = os.path.join(CHARM_DIR, "hosts.ini")
    if os.path.exists(charm_hosts_path):
        ANSIBLE_HOSTS_PATH = charm_hosts_path
    else:
        raise Exception(f"Hosts file not found: {charm_hosts_path}")
except Exception as e:
    log.warning(e, exc_info=True)
    log.error(f"Failed to set ansible hosts path to CHARM_DIR/hosts.ini: {str(e)}")
    ANSIBLE_HOSTS_PATH = "/etc/ansible/hosts"
    log.error(f"Continue using default: {ANSIBLE_HOSTS_PATH}")

# Ansible will automatically include any vars in the following
# file in its inventory when run locally.
HOST_VARS_DIR = os.path.join(os.path.dirname(ANSIBLE_HOSTS_PATH), 'host_vars')
ANSIBLE_VARS_PATH = os.path.join(HOST_VARS_DIR, 'localhost')

ANSIBLE_REMOTE_TMP_DIR = '/root/.ansible/tmp'


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
            if CHARM_DIR and isinstance(CHARM_DIR, str) and CHARM_DIR.split('/')[0]:
                self.app_name = CHARM_DIR.split('/')[0]
            if not self.app_name:
                log.error('Could not set app_name')

    def install_ansible_support(self):
        """Create ansible configs."""
        try:
            # if ANSIBLE_HOSTS_PATH and ANSIBLE_HOSTS_PATH.startswith('/etc/ansible'):
            #     os.makedirs('/etc/ansible/host_vars', mode=0o755, exist_ok=True)
            os.makedirs('/etc/ansible/host_vars', mode=0o755, exist_ok=True)
            if HOST_VARS_DIR and not HOST_VARS_DIR.startswith('/etc/ansible'):
                os.makedirs(HOST_VARS_DIR, mode=0o755, exist_ok=True)
        except Exception as e:
            log.warning(e, exc_info=True)
            log.warning('install_ansible_support failed to create /etc/ansible: {}'.format(str(e)))
        if ANSIBLE_HOSTS_PATH.startswith('/etc/ansible'):
            with open(ANSIBLE_HOSTS_PATH, 'w+') as hosts_file:
                hosts_file.write('[all]\n')
                localhost_config = ' '.join([
                    'localhost',
                    'ansible_connection=local',
                    f'ansible_remote_tmp={ANSIBLE_REMOTE_TMP_DIR}',
                    # 'ansible_python_interpreter=/usr/bin/python3',
                ]).strip()
                hosts_file.write(localhost_config)
                hosts_file.write('\n')  # newline in the end

    def apply_playbook(
        self, playbook, tags=None, extra_vars={}, env={}, diff=False, check=False, become=True, throw=False,
        verbosity=0,
    ):
        """
        Run ansible playbook.

        Charm config variables are processed using 'juju_state_to_yaml' function and then passed as extra variables.

        extra_vars - overrides all extra variables passed to the playbook including charm config.

        Execute playbook file.
        """
        kwargs = {}
        kw_run = {}
        if tags:
            kwargs['tags'] = tags.split(',') if isinstance(tags, str) else tags
        if verbosity:
            try:
                if int(verbosity) >= 0:
                    kwargs['verbosity'] = int(verbosity)
                    kw_run['verbosity'] = int(verbosity)
            except Exception as e:
                log.error(f"Failed to set verbosity parameter [verbosity={verbosity}]: {e}")
        pb = AnsiblePlaybook(
            self.charm,
            self.model,
            self.app_name,
            inventory_path=ANSIBLE_HOSTS_PATH,
            connection="local",
            basedir=CHARM_DIR,
            become=become,
            diff=diff,
            check=check,
            **kwargs
        )

        if CHARM_DIR and os.path.exists(os.path.join(CHARM_DIR, playbook)):
            pb_path = os.path.join(CHARM_DIR, playbook)
        elif os.path.exists(os.path.abspath(playbook)):
            pb_path = os.path.abspath(playbook)
        else:
            pb_path = playbook
        if "/./" in pb_path:
            pb_path = pb_path.replace("/./", "/")

        # log.info(f'Run playbook: {pb_path}')
        returncode, results = pb.run(
            pb_path,
            subset="localhost",
            extra_vars=extra_vars,
            env=env,
            **kw_run,
        )
        if returncode != 0:
            log.error(f"Failed to run ansible playbook: {pb_path} (tags={tags})")
            log.error(f"extra_vars:\n{extra_vars!r}")
            log.error(f"env:\n{env!r}")
            if throw:
                raise AnsiblePlaybookError(f"Ansible Playbook '{pb_path}' returned non-zero exit code.")

        pb = None
        return returncode, results


class AnsiblePlaybook:
    def __init__(
        self, charm, model, app_name, inventory_path=ANSIBLE_HOSTS_PATH, basedir=CHARM_DIR,
        local_tmp='/tmp', remote_tmp=ANSIBLE_REMOTE_TMP_DIR, **kw
    ):
        from ansible.plugins.loader import add_all_plugin_dirs
        from ansible.plugins.loader import init_plugin_loader
        from ansible.parsing.dataloader import DataLoader
        from ansible.inventory.manager import InventoryManager
        from ansible.vars.manager import VariableManager
        from ansible.utils.collection_loader import AnsibleCollectionConfig

        self.charm = charm
        self.model = model
        self.app_name = app_name
        self.basedir = basedir

        self.whichpython = sys.executable
        self.loader = DataLoader()
        if self.basedir and os.path.exists(self.basedir):
            self.loader.set_basedir(self.basedir)
            add_all_plugin_dirs(self.basedir)
            if not AnsibleCollectionConfig.collection_finder:
                init_plugin_loader(self.basedir)

        self.inventory = InventoryManager(loader=self.loader, sources=inventory_path)
        self.variable_manager = VariableManager(loader=self.loader, inventory=self.inventory)

        try:
            self.verbosity = int(kw.get('verbosity', 0))
        except Exception as e:
            log.warning(e, exc_info=True)
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
            # ansible >=9.0.0
            from ansible.cli import initialize_locale
        from ansible.executor.playbook_executor import PlaybookExecutor, display
        from ansible.playbook import Playbook

        if self.model and hasattr(self.model, 'config'):
            model_config = dict(deepcopy(self.model.config))
            model_config['app_name'] = self.app_name
        else:
            model_config = {}

        extra = juju_state_to_yaml(
            ANSIBLE_VARS_PATH, model_config=model_config, namespace_separator='__',
            allow_hyphens_in_keys=False, mode=(stat.S_IRUSR | stat.S_IWUSR)
        )
        extra.update(extra_vars)

        try:
            display.verbosity = int(verbosity) if verbosity > self.verbosity else int(self.verbosity)
        except Exception as e:
            log.warning(e, exc_info=True)
            log.error(f"Failed to set verbosity for playbook run: {playbook_path}")
            display.verbosity = 0
        context.CLIARGS = self._get_cli_args(kw)
        initialize_locale()

        if not os.path.exists(playbook_path):
            log.error(f"Ansible Playbook does not exist: {playbook_path}")
            return 255, {}

        try:
            p = Playbook.load(playbook_path, variable_manager=self.variable_manager, loader=self.loader)
        except Exception as e:
            log.warning(e, exc_info=True)
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

        pythonpath_items = [
            f"{CHARM_DIR}/venv",
            f"{CHARM_DIR}/lib",
        ]

        whichpython_original = os.getenv("WHICHPYTHON")
        pythonpath_original = os.getenv("PYTHONPATH", "")
        virtualenv_original = os.getenv("VIRTUAL_ENV", "")

        try:
            os.environ["WHICHPYTHON"] = self.whichpython
            os.environ["ANSIBLE_FORCE_COLOR"] = "1"
            # NOTE do not apply for all - maybe base on parameter
            # os.environ["ANSIBLE_SSH_ARGS"] = "-o StrictHostKeyChecking=accept-new"
            os.environ["ANSIBLE_PYTHON_INTERPRETER"] = self.whichpython

            try:
                pythonpath_items.extend(env.get('PYTHONPATH', '').split(':'))
            except Exception as e:
                log.warning(e, exc_info=True)
            try:
                pythonpath_items.extend(pythonpath_original.split(':'))
            except Exception as e:
                log.warning(e, exc_info=True)
            os.environ["PYTHONPATH"] = ":".join([x for x in pythonpath_items if x])
            os.environ["VIRTUAL_ENV"] = f"{CHARM_DIR}/venv"

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
            if whichpython_original:
                os.environ["WHICHPYTHON"] = whichpython_original
            else:
                os.environ.pop('WHICHPYTHON', None)
            if pythonpath_original:
                os.environ["PYTHONPATH"] = pythonpath_original
            else:
                os.environ.pop('PYTHONPATH', None)
            if virtualenv_original:
                os.environ["VIRTUAL_ENV"] = virtualenv_original
            else:
                os.environ.pop('VIRTUAL_ENV', None)
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

    # Add the CHARM_DIR which we will need to refer to charm
    # file resources etc.
    config['charm_dir'] = CHARM_DIR
    config['local_unit'] = LOCAL_UNIT_NAME
    config['unit_private_address'] = unit_get('private-address')
    config['unit_public_address'] = unit_get('public-address')

    # Don't use non-standard tags for unicode which will not
    # work when salt uses yaml.safe_load.
    yaml.add_representer(
        str, lambda dumper, value: dumper.represent_scalar('tag:yaml.org,2002:str', value)
    )

    yaml_dir = os.path.dirname(yaml_path)
    if not os.path.exists(yaml_dir):
        os.makedirs(yaml_dir, mode=0o755, exist_ok=True)

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
