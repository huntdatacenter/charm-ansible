# charm-ansible

Ansible subordinate charm executes preconfigured ansible playbook
to handle minor details that are out of scope of superior charm.

## Deploy

See the example in `bundles` directory.

Simple way to deploy playbook as a charm:

```
juju deploy huntdatacenter-ansible "${app_name}" --config playbook=@playbook.yaml
juju integrate "${app_name}:juju-info" "${superior_app}:juju-info"
```

## Ansible playbook

Playbook should use tags matching charm hooks:
- `install`
- `start` (called after installation - start hook)
- `stop` (called before removal - stop hook)
- `config` (called after config changes - config-changed hook)

## Configuration

See `config.yaml`.

```
juju config "${app_name}"
```

## Actions

See `actions.yaml`.

```
juju list-actions "${app_name}"
```

## Storage

List storage pools
```bash
juju list-storage-pools -m $model
```

Test adding storage

```bash
unit_name=
pool=tmpfs  # lxd
size=2G
juju add-storage -m $model "${unit_name}" "data=${pool},${size}"
```

Use config to set mode, owner, and group for the storage directory.

## Development

To start development environment in Multipass run:

```
make up
```

Run `make` or `make help` command to see help.

```
build                Build charm
deploy               Deploy charm
name                 Print name of the VM
list                 List existing VMs
up                   Start a VM
fwd                  Forward app port: make unit=prometheus/0 port=9090 fwd
down                 Stop the VM
ssh                  Connect into the VM
destroy              Destroy the VM
help                 Show this help
```
