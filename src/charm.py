#!/usr/bin/env python3
# Copyright 2022 vagrant
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

    https://discourse.charmhub.io/t/4208
"""

import json
import os  # noqa
import subprocess  # noqa
import logging
# from yaml import safe_load
from pathlib import Path

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus
# from ops.model import BlockedStatus
from ops.model import MaintenanceStatus

try:
    import setuppath  # noqa:F401
except Exception as e:
    # OK to fail only when build documentation
    logging.error('Failed to import setuppath: {}'.format(str(e)))
try:
    from extensions import ansible_manager
    # from extensions.network import close_port
    # from extensions.network import open_port
    # from extensions.network import parse_port
    # from extensions.network import unit_private_ip

except Exception as e:
    logging.error('Failed to import lib extensions: {}'.format(str(e)))


logger = logging.getLogger(__name__)

INTERFACE = "juju-info"


class AnsibleCharm(CharmBase):
    """Charm the service."""

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.remove, self._on_stop)
        self.framework.observe(self.on.upgrade_charm, self._on_install)
        self.framework.observe(self.on.post_series_upgrade, self._on_install)
        self.framework.observe(self.on.ansible_playbook_action, self._on_ansible_playbook_action)
        self.framework.observe(self.on.data_storage_attached, self._on_data_storage_attached)
        self.framework.observe(self.on.data_storage_detaching, self._on_data_storage_detaching)
        # self._stored.set_default(things=[])
        self._stored.set_default(storages={})
        self._stored.set_default(storage_name="data")
        self._stored.set_default(crontab="")

    def _on_config_changed(self, event):
        self.__update_ansible_playbook()

        try:
            ansible_manager.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        try:
            extra_vars = self.__get_extra_vars()
        except Exception as e:
            logger.error("Failed to fetch extra vars: {}".format(str(e)))
        try:
            env = self.__get_environ()
        except Exception as e:
            logger.error("Failed to fetch environment variables: {}".format(str(e)))

        try:
            ansible_manager.apply_playbook(
                playbook='playbook.yaml',
                tags=["config"],
                extra_vars=extra_vars,
                env=env,
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))

        # /etc/cron.d/charm_<app_name>
        try:
            self._stored.crontab = self.model.config['crontab']
            cron_content = self._stored.crontab
            app_name = self.app.name
            cronfile_path = os.path.join("/etc/cron.d", f"charm_{app_name.replace('-', '_')}")
            file_path = Path(cronfile_path)
            file_exists = file_path.exists()
            cron_content = cron_content.rstrip('\n') + '\n' if cron_content else ''

            if not file_exists:
                logger.info(f"Creating cron config: {cronfile_path}")
                file_path.touch(mode=0o644, exist_ok=True)
                with open(cronfile_path, "w") as f:
                    f.write(cron_content)
            else:
                current_cron_content = ""
                with open(cronfile_path, "r") as f:
                    current_cron_content = f.read()
                if current_cron_content != cron_content:
                    logger.info(f"Update cron config: {cronfile_path}")
                    with open(cronfile_path, "w") as f:
                        f.write(cron_content)
            file_path.chmod(0o644)
        except Exception as e:
            logger.error("Failed to configure cron: {}".format(str(e)))

    def __get_extra_vars(self, **kwargs):
        extra_vars = {
            'app_name': self.app.name,
            'leader': self.model.unit.is_leader(),
        }

        try:
            extra_vars['ingress_address'] = self.ingress_address
        except Exception as e:
            logger.error("Failed to fetch ingress IP address: {}".format(str(e)))

        try:
            storages = dict(self._stored.storages)
            extra_vars['storages'] = storages
            if self.model.config['storage_mount']:
                storage_bind_mount = self.model.config['storage_mount']
            else:
                storage_bind_mount = os.path.join("/opt/charm-ansible", self.app.name, "storage")
            if storages:
                for key, value in storages.items():
                    if key == self._stored.storage_name:
                        extra_vars['storage_volume'] = value
                        extra_vars['storage_bind_mount'] = storage_bind_mount
                        break
                    else:
                        logger.warning(f"Ignoring storage type: {key}")
        except Exception as e:
            logger.error("Failed to fetch storage variables: {}".format(str(e)))
        return extra_vars

    def __get_environ(self, **kwargs):
        blacklisted = {'SUDO_COMMAND', 'SHLVL'}
        env = {
            'DEBIAN_FRONTEND': 'noninteractive',
        }

        try:
            data = {k: v for k, v in os.environ.items() if k not in blacklisted}
            env.update(data)
        except Exception as e:
            logger.error("Failed to fetch environment variables: {}".format(str(e)))
        return env

    def __update_ansible_playbook(self):
        playbook = self.config.get('playbook')
        with open('playbook.yaml', 'w') as f:
            f.write(playbook)

    def _on_install(self, event):
        self.unit.status = MaintenanceStatus("Installing")

        try:
            ansible_manager.install_ansible_support()
            logger.debug("Ansible support installed")
        except Exception as e:
            logger.error("Installing Ansible support failed: {}".format(str(e)))

        try:
            import ansible
            logger.info(f"Ansible core version: {ansible.__version__}")
            from ansible_collections import ansible_release
            logger.info(f"Ansible collections version: {ansible_release.ansible_version}")
        except Exception as e:
            logger.error("Failed to read the ansible version: {}".format(str(e)))

        try:
            if self.model.unit.is_leader():
                self.unit.set_workload_version(self.charm_version)
        except Exception as e:
            logger.error("Failed to set the charm version: {}".format(str(e)))

        self.__update_ansible_playbook()

        # subprocess.check_call(["ls", "-la", os.getenv("JUJU_CHARM_DIR")])

        try:
            ansible_manager.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        extra_vars = self.__get_extra_vars()
        env = self.__get_environ()

        try:
            ansible_manager.apply_playbook(
                playbook='playbook.yaml',
                tags=["install"],
                extra_vars=extra_vars,
                env=env,
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))
        else:
            self.unit.status = ActiveStatus("Unit is ready")

        try:
            self.__bind_mount_storage()
        except Exception as e:
            logger.error(e)
            logger.error("Error during storage bind mount: {}".format(str(e)))

    def _on_start(self, event):
        self.unit.status = MaintenanceStatus("Starting")
        try:
            ansible_manager.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        extra_vars = self.__get_extra_vars()
        env = self.__get_environ()

        try:
            ansible_manager.apply_playbook(
                playbook='playbook.yaml',
                tags=["start"],
                extra_vars=extra_vars,
                env=env,
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))
        else:
            self.unit.status = ActiveStatus("Unit is ready")

    def _on_stop(self, event):
        self.unit.status = MaintenanceStatus("Stopping")
        try:
            ansible_manager.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        extra_vars = self.__get_extra_vars()
        env = self.__get_environ()

        try:
            ansible_manager.apply_playbook(
                playbook='playbook.yaml',
                tags=["stop"],
                extra_vars=extra_vars,
                env=env,
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))

    @property
    def charm_version(self):
        try:
            # import ansible
            # version = ansible.__version__
            from ansible_collections import ansible_release
            version = ansible_release.ansible_version
        except Exception as e:
            logger.error("Failed to read the ansible version: {}".format(str(e)))
            version = '0.0.1'
        return version

    @property
    def ingress_address(self):
        """The ingress-address of the swarm cluster
        """
        return str(self.model.get_binding(INTERFACE).network.ingress_address)

    def _on_ansible_playbook_action(self, event):
        """
        Run ansible playbook.

        juju run ubuntu-storage/0 ansible-playbook diff=1 check=1 "tags=debug"

        """
        kwargs = {}
        tags = event.params["tags"]

        extra_vars = self.__get_extra_vars()
        env = self.__get_environ()

        show_diff = False
        check_mode = False

        try:
            if event.params.get("extra"):
                extra_vars_overrides = json.loads(event.params["extra"])
                extra_vars.update(extra_vars_overrides)
        except Exception as e:
            logger.error(e)
            event.log(f"Failed to process parameter - 'extra': {str(e)}")
            event.fail(f"Failed to process parameter - 'extra': {str(e)}")
            return
        try:
            ansible_manager.init_charm(self)
        except Exception as e:
            logger.error(e)
            event.log(f"Init Ansible extension failed: {str(e)}")
            event.fail(f"Init Ansible extension failed: {str(e)}")
            return

        try:
            import ansible
            event.log(f"Ansible core version: {ansible.__version__}")
            from ansible_collections import ansible_release
            event.log(f"Ansible collections version: {ansible_release.ansible_version}")
        except Exception as e:
            event.log(f"Failed to read the ansible version: {str(e)}")

        try:
            if str(event.params.get("diff")).lower() in ['1', 'yes', 'y', 'true']:
                show_diff = True
        except Exception as e:
            logger.error(e)
            event.log("Failed to set diff parameter")

        try:
            if str(event.params.get("check")).lower() in ['1', 'yes', 'y', 'true']:
                check_mode = True
        except Exception as e:
            logger.error(e)
            event.log("Failed to set check mode parameter")

        try:
            if event.params.get("verbosity", 0) > 0:
                kwargs["verbosity"] = event.params["verbosity"]
        except Exception as e:
            logger.error(e)
            event.log("Failed to set verbosity parameter")

        try:
            returncode, results = ansible_manager.apply_playbook(
                playbook='playbook.yaml',
                tags=tags,
                extra_vars=extra_vars,
                env=env,
                diff=show_diff,
                check=check_mode,
                throw=True,
                **kwargs
            )
        except Exception as e:
            logger.error(e)
            event.log(f"Ansible playbook failed: {str(e)}")
            event.fail(f"Ansible playbook failed: {str(e)}")
            return
        else:
            event.set_results(dict(
                returncode=returncode,
                results=results,
            ))

    def _on_data_storage_attached(self, event):
        try:
            storage_name = self._stored.storage_name
            volumes = self.model.storages[storage_name]
            logger.info("Attaching storage [{storage_name}]: Found {vol_count} volume(s)".format(
                storage_name=storage_name,
                vol_count=len(volumes),
            ))
            if volumes:
                storage = volumes[0]
                storage_path = storage.location
                # set storage path in configs
                self._stored.storages[storage_name] = str(storage_path)
            else:
                del self._stored.storages[storage_name]
        except Exception as e:
            logger.error("Attaching storage failed [{storage_name}]: {error}".format(
                storage_name=storage_name,
                error=str(e)
            ))
        try:
            logger.info("Storages: {}".format(repr(dict(self._stored.storages))))
        except Exception as e:
            logger.error(f"Error printing storages: {str(e)}")

        self.__bind_mount_storage()

    def __bind_mount_storage(self):
        if dict(self._stored.storages):
            try:
                extra_vars = self.__get_extra_vars()
            except Exception as e:
                logger.error("Failed to fetch extra vars: {}".format(str(e)))
            try:
                env = self.__get_environ()
            except Exception as e:
                logger.error("Failed to fetch environment variables: {}".format(str(e)))

            try:
                ansible_manager.apply_playbook(
                    playbook='playbooks/storage.yaml',
                    tags=['mount'],
                    extra_vars=extra_vars,
                    env=env,
                    diff=True,
                    check=False,
                    throw=True,
                )
            except Exception as e:
                logger.error(e)
                logger.warning(f"Ansible playbook failed: {str(e)}")
        else:
            logger.info("No storage added yet")

    def _on_data_storage_detaching(self, event):
        storage_name = self._stored.storage_name
        try:
            extra_vars = self.__get_extra_vars()
        except Exception as e:
            logger.error("Failed to fetch extra vars: {}".format(str(e)))
        try:
            env = self.__get_environ()
        except Exception as e:
            logger.error("Failed to fetch environment variables: {}".format(str(e)))

        try:
            ansible_manager.apply_playbook(
                playbook='playbooks/storage.yaml',
                tags=['unmount'],
                extra_vars=extra_vars,
                env=env,
                diff=True,
                check=False,
                throw=True,
            )
        except Exception as e:
            logger.error(e)
            logger.warning(f"Ansible playbook failed: {str(e)}")

        try:
            storages = dict(self._stored.storages)
            del storages[storage_name]
            self._stored.storages = storages
        except Exception as e:
            logger.error(e)
            logger.warning(f"Failed to remove storage '{storage_name}' from stored state: {str(e)}")


if __name__ == "__main__":
    main(AnsibleCharm)
