#!/bin/bash

ARCH=$(dpkg --print-architecture)

set -x

juju bootstrap localhost lxd --bootstrap-constraints arch=${ARCH}

sleep 1

juju add-model default --config enable-os-upgrade=false
