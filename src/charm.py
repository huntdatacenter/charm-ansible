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

import os
import sys
import subprocess
import logging
from yaml import safe_load

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus
#from ops.model import BlockedStatus
from ops.model import MaintenanceStatus

sys.path.append('lib')

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
        # self.framework.observe(self.on.fortune_action, self._on_fortune_action)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.remove, self._on_stop)
        self.framework.observe(self.on.upgrade_charm, self._on_install)
        self.framework.observe(self.on.post_series_upgrade, self._on_install)
        self._stored.set_default(things=[])

    def _on_config_changed(self, event):
        playbook = self.config.get('playbook')
        with open('playbook.yaml', 'w') as f:
            f.write(playbook)

    def _on_install(self, event):
        self.unit.status = MaintenanceStatus("Installing")

        playbook = self.config.get('playbook')
        with open('playbook.yaml', 'w') as f:
            f.write(playbook)

        subprocess.check_call(["ls", "-la", os.getenv("JUJU_CHARM_DIR")])

        try:
            ansible.install_ansible_support()
            logger.debug("Ansible support installed")
        except Exception as e:
            logger.error("Installing Ansible support failed: {}".format(str(e)))

        try:
            ansible.init_charm(self)
            logger.debug("Ansible extension initiated")
        except Exception as e:
            logger.error("Init Ansible failed: {}".format(str(e)))

        try:
            # Install apt/pip3 dependencies
            ansible.apply_playbook(
                playbook='./playbook.yaml',
                tags=["install"]
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format((str(e))))
        else:
            self.unit.status = ActiveStatus("Unit is ready")


    def _on_start(self, event):
        self.unit.status = MaintenanceStatus("Starting")
        try:
            ansible.init_charm(self)
            logger.debug("Ansible extension initiated")
        except Exception as e:
            logger.error("Init Ansible failed: {}".format(str(e)))

        try:
            # Install apt/pip3 dependencies
            ansible.apply_playbook(
                playbook='./playbook.yaml',
                tags=["start"]
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format((str(e))))
        else:
            self.unit.status = ActiveStatus("Unit is ready")


    def _on_stop(self, event):
        self.unit.status = MaintenanceStatus("Stopping")
        try:
            ansible.init_charm(self)
            logger.debug("Ansible extension initiated")
        except Exception as e:
            logger.error("Init Ansible failed: {}".format(str(e)))

        try:
            # Install apt/pip3 dependencies
            ansible.apply_playbook(
                playbook='./playbook.yaml',
                tags=["stop"]
            )
        except Exception as e:
            logger.error("Ansible playbook failed: {}".format((str(e))))







    # def _on_fortune_action(self, event):
    #     """Just an example to show how to receive actions."""

    #     fail = event.params["fail"]
    #     if fail:
    #         event.fail(fail)
    #     else:
    #         event.set_results({"fortune": "A bug in the code is worth two in the documentation."})



if __name__ == "__main__":
    main(AnsibleCharm)


