# charm-ansible

Ansible subordinate charm executes preconfigured ansible playbook
  to handle minor details that are out of scope of superior charm.

## Deploy

See the example in `bundles` directory.

Simple way to deploy playbook as a charm:

```
juju deploy huntdatacenter-charm-ansible --config playbook=@playbook.yaml
```

## Ansible playbook

Playbook should use tags matching charm hooks:
- `install`
- `start` (called after installation)
- `stop` (called before removal)

## Configuration

See `config.yaml`.

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
