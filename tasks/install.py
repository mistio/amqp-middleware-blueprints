from cloudify import ctx
from cloudify.state import ctx_parameters as inputs
from cloudify.exceptions import HttpException, NonRecoverableError

import os
import sys
import json
import urlparse
import requests


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)

try:
    import utils
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    import utils


AGENT_BASE = '/opt/amqp-middleware'
AGENT_VENV = '/opt/amqp-middleware/venv'

AGENT_USER = AGENT_GROUP = 'root'


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
        cmd = ['rm', '-rf', AGENT_BASE]
        utils.run_command(cmd, su=True)
    except OSError:
        pass


def deploy_agent():
    """The main method of the `install` workflow, responsible for executing all
    necessary steps in order to configure and initiate the AMQP Middleware.
    """
    ctx.logger.info('Creating virtualenv')
    cmd = ['virtualenv', AGENT_VENV]
    utils.run_command(cmd, su=True)

    ctx.logger.info('Installing AMQP Middleware and required dependencies')
    repo = inputs['agent_source']
    cmd = ['%s/bin/pip' % AGENT_VENV, 'install', '-e', repo]
    utils.run_command(cmd, su=True)

    # Get node properties.
    node_properties = ctx.node.properties.copy()

    # Rename kwargs for easier use later on.
    for key in node_properties['manager']:
        if key.startswith('manager_'):
            utils.rename_kwargs(node_properties['manager'],
                          key, key.replace('manager_', ''))

    # Register new user and populate account with clouds.
    register(node_properties.pop('user'))
    populate(node_properties.pop('creds', {}))

    # Set RabbitMQ host, if missing.
    if not node_properties['manager'].get('rabbitmq_host'):
        rabbitmq_host = node_properties['manager']['host']
        node_properties['manager']['rabbitmq_host'] = rabbitmq_host

    # Pass all properties to the node instance's runtime properties
    # for easier rendering.
    ctx.instance.runtime_properties['config'] = node_properties

    ctx.logger.info('Rendering EnvironmentFile')
    utils.render_to_file(
        os.path.join('service', 'amqp-middleware-env'),
        '/etc/sysconfig/amqp-middleware-env'
    )

    ctx.logger.info('Setting user/group permissions for AMQP Middleware')
    cmd = ['chown', '-R', '%s:%s' % (AGENT_USER, AGENT_GROUP), AGENT_BASE]
    utils.run_command(cmd, su=True)

    # Configure systemd.
    systemctl = utils.SystemController(service='amqp-middleware')
    systemctl.execute('configure')
    systemctl.execute('enable')
    systemctl.execute('reload')


def register(user):
    """A helper method to take care of the registration process and store all
    necessary information into the node instance's runtime properties.
    """
    ctx.logger.info('Registration process started')
    # Get destination URL.
    host = ctx.node.properties['stream']['destination_url']
    # Get proper scheme, verify host, and prepare headers, if applicable.
    if ctx.node.properties['stream']['secure']:
        scheme = 'https'
    else:
        scheme = 'http'
    if not host:
        raise NonRecoverableError('No destination_url specified')
    if urlparse.urlparse(host).scheme:
        raise NonRecoverableError('Malformed destination_url. '
                                  'It must be in the form of: "example.com"')
    headers = {}
    if user.get('exists'):
        if not user.get('token'):
            NonRecoverableError('An existing user is about to be used, but '
                                'no authorization token was specified')
        headers = {'Authorization': user.pop('token')}
    else:
        for key in ('email', 'name'):
            if not user.get(key):
                raise NonRecoverableError('Required input missing: "%s"' % key)

    url = '%s://%s/api/v1/insights/register' % (scheme, host)
    reg = requests.post(url, data=json.dumps(user), headers=headers)
    if not reg.ok:
        raise HttpException(url=url, code=reg.status_code, message=reg.content)

    response = reg.json()
    ctx.instance.runtime_properties.update({
        'insights_url': response['url'],
        '_meta': {
            'token': response['token'],
            'manager_id': response['uuid'],
        }
    })


def populate(clouds):
    """A helper method responsible for executing HTTP API calls in order to
    transfer cloud credentials right after registration.
    """
    if not clouds:
        ctx.logger.warn('Account will not be populated with clouds')
    else:
        for provider, data in clouds.iteritems():
            utils.add_cloud(provider, data)


init()
deploy_agent()
