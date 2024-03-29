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
    from extensions import ansible
    # from extensions.network import close_port
    # from extensions.network import open_port
    # from extensions.network import parse_port
    # from extensions.network import unit_private_ip

except Exception as e:
    logging.error('Failed to import lib extensions: {}'.format(str(e)))


logger = logging.getLogger(__name__)


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
        self._stored.set_default(things=[])
        self._stored.set_default(storages={})

    def _on_config_changed(self, event):
        self.__update_ansible_playbook()

        try:
            ansible.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        try:
            ansible.apply_playbook(
                playbook='playbook.yaml',
                tags=["config"],
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))

    def __update_ansible_playbook(self):
        playbook = self.config.get('playbook')
        with open('playbook.yaml', 'w') as f:
            f.write(playbook)

    def _on_install(self, event):
        self.unit.status = MaintenanceStatus("Installing")

        try:
            ansible.install_ansible_support()
            logger.debug("Ansible support installed")
        except Exception as e:
            logger.error("Installing Ansible support failed: {}".format(str(e)))

        self.__update_ansible_playbook()

        # subprocess.check_call(["ls", "-la", os.getenv("JUJU_CHARM_DIR")])

        try:
            ansible.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        try:
            ansible.apply_playbook(
                playbook='playbook.yaml',
                tags=["install"]
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))
        else:
            self.unit.status = ActiveStatus("Unit is ready")

    def _on_start(self, event):
        self.unit.status = MaintenanceStatus("Starting")
        try:
            ansible.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        try:
            ansible.apply_playbook(
                playbook='playbook.yaml',
                tags=["start"]
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))
        else:
            self.unit.status = ActiveStatus("Unit is ready")

    def _on_stop(self, event):
        self.unit.status = MaintenanceStatus("Stopping")
        try:
            ansible.init_charm(self)
        except Exception as e:
            logger.error("Init Ansible extension failed: {}".format(str(e)))

        try:
            ansible.apply_playbook(
                playbook='playbook.yaml',
                tags=["stop"]
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format(str(e)))

    def _on_ansible_playbook_action(self, event):
        """Run ansible playbook."""

        tags = event.params["tags"]
        try:
            if event.params.get("extra"):
                extra_vars = json.loads(event.params["extra"])
            else:
                extra_vars = {}
        except Exception as e:
            logger.error(e)
            event.log("Failed to process parameter - 'extra': {}".format(str(e)))
            event.fail("Failed to process parameter - 'extra': {}".format(str(e)))
            return
        try:
            ansible.init_charm(self)
        except Exception as e:
            logger.error(e)
            event.log("Init Ansible extension failed: {}".format(str(e)))
            event.fail("Init Ansible extension failed: {}".format(str(e)))
            return

        try:
            returncode, results = ansible.apply_playbook(
                playbook='playbook.yaml',
                tags=tags,
                extra_vars=extra_vars,
                env={},
                diff=False,
                check=False,
                throw=True,
            )
        except Exception as e:
            logger.error(e)
            event.log("Ansible playbook failed: {}".format(str(e)))
            event.fail("Ansible playbook failed: {}".format(str(e)))
            return
        else:
            event.set_results({
                "returncode": returncode,
                "results": results,
            })

    def _on_data_storage_attached(self, event):
        try:
            storage_name = 'data'
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
            logger.error("Error printing storages: {}".format(str(e)))


if __name__ == "__main__":
    main(AnsibleCharm)
