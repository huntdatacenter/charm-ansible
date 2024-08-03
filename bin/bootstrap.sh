#!/bin/bash

ARCH=$(dpkg --print-architecture)

juju bootstrap localhost lxd --bootstrap-constraints arch=${ARCH}

juju add-model default

sleep 5

juju model-config -m default enable-os-upgrade=false
