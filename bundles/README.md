# Testing bundles

Deploy testing bundle

```
juju deploy /vagrant/focal.yaml

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
