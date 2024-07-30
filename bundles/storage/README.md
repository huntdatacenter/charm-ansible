# Using Ansible charm to add storage

Find existing storage pool:
```bash
juju list-storage-pools
```

Or create a new one:
```bash
juju help create-storage-pool
```

```bash
juju deploy ./bundles/storage/bundle.yaml
```

Upgrade of charm:
```bash
juju refresh ubuntu-storage --path ./ansible.charm
```

Running action to print debug logs from inside ansible:
```bash
juju run ubuntu-storage/leader ansible-playbook diff=1 check=1 tags=debug verbosity=4
```

```
TASK [Print all extra vars] ****************************************************
ok: [localhost] => {
    "hostvars[inventory_hostname]": {
        "ansible_check_mode": true,
        "ansible_config_file": null,
        "ansible_connection": "local",
        "ansible_facts": {},
        "ansible_playbook_python": "/usr/bin/python3",
        "ansible_remote_tmp": "/root/.ansible/tmp",
        "ansible_version": "Unknown",
        "app_name": "ubuntu-storage",
        "charm_dir": "/var/lib/juju/agents/unit-ubuntu-storage-0/charm",
        "crontab": "",
        "group_names": [
            "ungrouped"
        ],
        "groups": {
            "all": [
                "localhost"
            ],
            "ungrouped": [
                "localhost"
            ]
        },
        "ingress_address": "10.209.9.135",
        "inventory_dir": "/etc/ansible",
        "inventory_file": "/etc/ansible/hosts",
        "inventory_hostname": "localhost",
        "inventory_hostname_short": "localhost",
        "leader": true,
        "local_unit": "ubuntu-storage/0",
        "omit": "__omit_place_holder__5f7ea0c7965826acfa7911dcbc4ca9982b7339d4",
        "playbook": "- hosts: localhost\n  connection: local\n  become: true\n  gather_facts: false\n\n  tasks:\n    - name: Run apt update\n      ansible.builtin.apt:\n        update_cache: true\n      become: true\n      tags:\n        - never\n        - install\n        - start\n\n    - name: Print all available facts\n      ansible.builtin.debug:\n        var: ansible_facts\n      ignore_errors: true\n      tags:\n        - never\n        - install\n        - debug\n\n    - name: Print all extra vars\n      ansible.builtin.debug:\n        var: hostvars[inventory_hostname]\n      ignore_errors: true\n      tags:\n        - never\n        - install\n        - debug\n\n    # - name: Install cmatrix\n    #   ansible.builtin.apt:\n    #     name:\n    #       - \"cmatrix\"\n    #   become: true\n    #   tags:\n    #     - never\n    #     - install\n    #     - start\n\n    # - name: Remove cmatrix\n    #   ansible.builtin.apt:\n    #     name:\n    #       - \"cmatrix\"\n    #     state: absent\n    #   become: true\n    #   tags:\n    #     - never\n    #     - stop\n",
        "playbook_dir": "/var/lib/juju/agents/unit-ubuntu-storage-0/charm",
        "storage_bind_mount": "/opt/charm-ansible/ubuntu-storage/storage",
        "storage_mount": "",
        "storage_volume": "/var/lib/juju/storage/data/1",
        "storages": {
            "data": "/var/lib/juju/storage/data/1"
        },
        "unit_private_address": "10.209.9.135",
        "unit_public_address": "10.209.9.135"
    }
}
```
