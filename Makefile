# Run `make` or `make help` command to get help

# Use one shell for all commands in a target recipe
.ONESHELL:
.EXPORT_ALL_VARIABLES:
.PHONY: help clean rename build deploy list launch mount umount bootstrap up down ssh destroy bridge
# Set default goal
.DEFAULT_GOAL := help
# Use bash shell in Make instead of sh
SHELL := /bin/bash

# Charm variables
CHARM_NAME := ansible.charm
CHARMHUB_NAME := huntdatacenter-ansible
CHARM_STORE_URL := https://charmhub.io/huntdatacenter-charm-ansible
CHARM_HOMEPAGE := https://github.com/huntdatacenter/charm-ansible/
CHARM_BUGS_URL := https://github.com/huntdatacenter/charm-ansible/issues
CHARM_BUILD := ansible_ubuntu-20.04-amd64-arm64_ubuntu-22.04-amd64-arm64_ubuntu-24.04-amd64-arm64.charm

# Multipass variables
UBUNTU_VERSION = noble
MOUNT_TARGET = /home/ubuntu/vagrant
DIR_NAME = "$(shell basename $(shell pwd))"
VM_NAME = juju-dev--$(DIR_NAME)

clean:  ## Remove artifacts
	charmcraft clean --verbose
	rm -vf $(CHARM_BUILD) $(CHARM_NAME)

$(CHARM_BUILD):
	charmcraft pack --verbose

$(CHARM_NAME): $(CHARM_BUILD)
	mv -v $(CHARM_BUILD) $(CHARM_NAME)

build: $(CHARM_NAME)  ## Build charm

clean-build: $(CHARM_NAME)  ## Build charm from scratch

deploy:  ## Deploy charm
	juju deploy ./$(CHARM_NAME)

login:
	bash -c "test -s ~/.charmcraft-auth || charmcraft login --export ~/.charmcraft-auth"

release: login  ## Release charm
	@echo "# -- Releasing charm: https://charmhub.io/$(CHARMHUB_NAME)"
	$(eval CHARMCRAFT_AUTH := $(shell cat ~/.charmcraft-auth))
	charmcraft upload --name $(CHARMHUB_NAME) --release latest/stable $(CHARM_NAME)


name:  ## Print name of the VM
	echo "$(VM_NAME)"

list:  ## List existing VMs
	multipass list

launch:
	multipass launch $(UBUNTU_VERSION) -v --timeout 3600 --name $(VM_NAME) --memory 4G --cpus 4 --disk 20G --cloud-init juju.yaml \
	&& multipass exec $(VM_NAME) -- cloud-init status

mount:
	echo "Assure allowed in System settings > Privacy > Full disk access for multipassd"
	multipass mount --type 'classic' --uid-map $(shell id -u):1000 --gid-map $(shell id -g):1000 $(PWD) $(VM_NAME):$(MOUNT_TARGET)

umount:
	multipass umount $(VM_NAME):$(MOUNT_TARGET)

recreate-default-model:
	juju destroy-model --no-prompt default --destroy-storage --force
	juju add-model default \
	&& juju model-config -m default enable-os-upgrade=false

bootstrap:
	multipass exec -d $(MOUNT_TARGET) $(VM_NAME) -- tmux new-session -s workspace "bash bin/bootstrap.sh; bash --login"
#	$(eval ARCH := $(shell multipass exec $(VM_NAME) -- dpkg --print-architecture))
#	multipass exec $(VM_NAME) -- juju bootstrap localhost lxd --bootstrap-constraints arch=$(ARCH) \
#	&& multipass exec $(VM_NAME) -- juju add-model default \
#	&& multipass exec $(VM_NAME) -- juju model-config -m default enable-os-upgrade=false

up: launch mount bootstrap ssh  ## Start a VM

fwd:  ## Forward app port: make unit=prometheus/0 port=9090 fwd
	$(eval VMIP := $(shell multipass exec $(VM_NAME) -- hostname -I | cut -d' ' -f1))
	echo "Opening browser: http://$(VMIP):$(port)"
	bash -c "(sleep 1; open 'http://$(VMIP):$(port)') &"
	multipass exec $(VM_NAME) -- juju ssh $(unit) -N -L 0.0.0.0:$(port):0.0.0.0:$(port)

down:  ## Stop the VM
	multipass down $(VM_NAME)

ssh:  ## Connect into the VM
	multipass exec -d $(MOUNT_TARGET) $(VM_NAME) -- bash

preseed:  ## Pre-seed ubuntu images: make codename=jammy version=22.04 preseed
	$(eval ARCH := $(shell multipass exec $(VM_NAME) -- dpkg --print-architecture))
	@echo "Download ubuntu-$(version)-server-cloudimg-$(ARCH).squashfs"
	wget --tries=15 --retry-connrefused --timeout=15 --random-wait=on -O /home/ubuntu/ubuntu-$(version)-server-cloudimg-$(ARCH).squashfs https://cloud-images.ubuntu.com/releases/$(version)/release/ubuntu-$(version)-server-cloudimg-$(ARCH).squashfs \
	&& sleep 10 \
	&& echo "Download ubuntu-$(version)-server-cloudimg-$(ARCH)-lxd.tar.xz" \
	&& wget --tries=15 --retry-connrefused --timeout=15 --random-wait=on -O /home/ubuntu/ubuntu-$(version)-server-cloudimg-$(ARCH)-lxd.tar.xz https://cloud-images.ubuntu.com/releases/$(version)/release/ubuntu-$(version)-server-cloudimg-$(ARCH)-lxd.tar.xz \
	&& multipass exec $(VM_NAME) -- lxc image import /home/ubuntu/ubuntu-$(version)-server-cloudimg-$(ARCH)-lxd.tar.xz /home/ubuntu/ubuntu-$(version)-server-cloudimg-$(ARCH).squashfs --alias juju/$(codename)@$(version)/$(ARCH)

destroy:  ## Destroy the VM
	multipass delete -v --purge $(VM_NAME)

bridge:
	sudo route -nv add -net 192.168.64.0/24 -interface bridge100
	# Delete if exists: sudo route -nv delete -net 192.168.64.0/24

# Display target comments in 'make help'
help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {sub("\\\\n",sprintf("\n%22c"," "), $$2);printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
