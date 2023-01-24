# https://github.com/juju/charm-helpers/blob/master/charmhelpers/contrib/templating/contexts.py

import os

import six
import yaml

from .core import hookenv

charm_dir = os.environ.get('CHARM_DIR', '')


def dict_keys_without_hyphens(a_dict):
    """Return the a new dict with underscores instead of hyphens in keys."""
    return dict(
        (key.replace('-', '_'), val) for key, val in a_dict.items())


def juju_state_to_yaml(
    yaml_path, model_config={}, namespace_separator=':',
    allow_hyphens_in_keys=True, mode=None
):
    """Update the juju config and state in a yaml file.
    This includes any current relation-get data, and the charm
    directory.
    This function was created for the ansible and saltstack
    support, as those libraries can use a yaml file to supply
    context to templates, but it may be useful generally to
    create and update an on-disk cache of all the config, including
    previous relation data.
    By default, hyphens are allowed in keys as this is supported
    by yaml, but for tools like ansible, hyphens are not valid [1].
    [1] http://www.ansibleworks.com/docs/playbooks_variables.html#what-makes-a-valid-variable-name
    """
    config = model_config

    # Add the charm_dir which we will need to refer to charm
    # file resources etc.
    config['charm_dir'] = charm_dir
    config['local_unit'] = hookenv.local_unit()
    config['unit_private_address'] = hookenv.unit_private_ip()
    config['unit_public_address'] = hookenv.unit_private_ip()

    # Don't use non-standard tags for unicode which will not
    # work when salt uses yaml.safe_load.
    yaml.add_representer(six.text_type,
                         lambda dumper, value: dumper.represent_scalar(
                             six.u('tag:yaml.org,2002:str'), value))

    yaml_dir = os.path.dirname(yaml_path)
    if not os.path.exists(yaml_dir):
        os.makedirs(yaml_dir)

    if os.path.exists(yaml_path):
        with open(yaml_path, "r") as existing_vars_file:
            existing_vars = yaml.safe_load(existing_vars_file.read())
    else:
        with open(yaml_path, "w+"):
            pass
        existing_vars = {}

    if mode is not None:
        os.chmod(yaml_path, mode)

    if not allow_hyphens_in_keys:
        config = dict_keys_without_hyphens(config)
    existing_vars.update(config)

    # update_relations(existing_vars, namespace_separator)

    with open(yaml_path, "w+") as fp:
        fp.write(yaml.dump(existing_vars, default_flow_style=False))
