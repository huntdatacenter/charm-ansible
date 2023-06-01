# Testing bundles

Start multipass VM

```
make up
```

Build charm

```
make build
```

Deploy testing bundle

```
cd bundles

juju deploy ./jammy.yaml

watch-juju
```

Test if cmatrix got installed

```
juju ssh cmatrix/0 -- cmatrix
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
