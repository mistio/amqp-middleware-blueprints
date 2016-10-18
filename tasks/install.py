from cloudify import ctx
from cloudify.state import ctx_parameters as inputs
from cloudify.exceptions import HttpException, NonRecoverableError

import os
import json
import shutil
import requests


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)


import utils


# Definition of constant parameters.
AGENT_VENV = '/opt/amqp-middleware/venv'
AGENT_USER = 'root'
AGENT_GROUP = 'root'


def init():
    """The initial method to be called in order to check certain system-wide
    requirements. For the time being, this method solely verifies whether
    systemd is running.
    """
    try:
        cmd = ['pidof', 'systemd']
        utils.run_command(cmd)
    except CommandExecutionException as exc:
        ctx.logger.error('System requirements not fulfilled')
        raise NonRecoverableError(exc)
    try:
        # Remove base dir, if exists, in case of re-installation.
        shutil.rmtree('/opt/amqp-middleware')
    except OSError:
        pass


def deploy_agent(path=AGENT_VENV):
    """The main method of the `install` workflow, responsible for executing all
    necessary steps in order to configure and initiate the AMQP Middleware.
    """
    ctx.logger.info('Creating virtualenv')
    cmd = ['virtualenv', path]
    utils.run_command(cmd, su=True)

    ctx.logger.info('Installing AMQP Middleware and required dependencies')
    repo = inputs['agent_source']
    cmd = ['%s/bin/pip' % AGENT_VENV, 'install', '-e', repo]
    utils.run_command(cmd, su=True)

    # Get node properties.
    node_properties = ctx.node.properties.copy()
    # No need to store user login information.
    node_properties.pop('user')
    # Get cloud credentials.
    clouds = node_properties.pop('creds', {})

    # Rename kwargs for easier use later on.
    for key in node_properties['manager']:
        if key.startswith('manager_'):
            utils.rename_kwargs(node_properties['manager'],
                          key, key.replace('manager_', ''))

    # Pass all properties to node instance's runtime properties
    # for easier rendering.
    ctx.instance.runtime_properties['config'] = node_properties

    # Register new User and populate account with clouds.
    register()
    populate(clouds)

    ctx.logger.info('Setting user/group permissions for AMQP Middleware')
    cmd = ['chown', '-R', '%s:%s' % (AGENT_USER, AGENT_GROUP), path]
    utils.run_command(cmd, su=True)

    ctx.logger.info('Rendering EnvironmentFile')
    utils.render_to_file(
        os.path.join('service', 'amqp-middleware-env'),
        '/etc/sysconfig/amqp-middleware-env'
    )

    # Configure systemd.
    systemctl = utils.SystemController(service='amqp-middleware')
    systemctl.execute('configure')
    systemctl.execute('enable')
    systemctl.execute('reload')


def register():
    """A helper method to take care of the registration process and store all
    necessary information into the node instance's runtime properties.
    """
    config = ctx.node.properties['stream']
    scheme = 'https' if config['secure'] else 'http'
    url = '%s://%s/api/v1/insights/register' % (scheme,
                                                config['destination_url'])

    ctx.logger.info('Registration process started')
    registration = requests.post(
        url, data=json.dumps(ctx.node.properties['user'])
    )
    if not registration.ok:
        raise HttpException(url=url, code=registration.status_code,
                            message=registration.content)

    resp = registration.json()
    ctx.instance.runtime_properties['insights_url'] = resp['url']
    ctx.instance.runtime_properties['_meta'] = {
        'manager_id': resp['uuid'],
        'token': resp['token'],
    }


def populate(cloud_creds):
    """A helper method responsible for executing HTTP API calls in order to
    transfer cloud credentials right after registration.
    """
    if not cloud_creds:
        ctx.logger.warn('Account will not be populated with clouds')
        return

    dest = ctx.node.properties['stream']['destination_url']
    token = ctx.instance.runtime_properties['_meta']['token']

    for provider, data in cloud_creds.iteritems():
        utils.add_cloud(dest=dest, token=token, cloud=(provider, data))


init()
deploy_agent()
