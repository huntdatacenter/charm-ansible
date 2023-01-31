# Testing bundles

Run in vagrant to build the charm
```
cd /vagrant

charmcraft pack --verbose
```

Deploy testing bundle

```
cd /vagrant/bundles

juju deploy /vagrant/bundles/focal.yaml

watch-juju
```

Checking logs during deploy
```
juju debug-log --include cmatrix
```

Testing config update
```
juju config cmatrix playbook

# Updating configured playbook with contents of playbook.yaml
juju config cmatrix playbook="@playbook.yaml"
```
