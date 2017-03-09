from cloudify import ctx
from cloudify.exceptions import NonRecoverableError
from cloudify.exceptions import \
    CommandExecutionException as _CommandExecutionException

import os
import json
import tempfile
import urlparse
import requests
import subprocess


SYSTEM_DIR = '/usr/lib/systemd/system/'


class CommandExecutionException(_CommandExecutionException):
    """A built-in Cloudify Exception."""
    def __str__(self):
        return "Failed to execute '%s'\nCommand exited with error code %d\n" \
               "Error: %s" % (self.command, self.code, self.output)


class SystemController(object):
    """A class to help control Systemd operations."""

    def __init__(self, service, path=None):
        """Initializes the system controller given a specific service."""
        self.service = service

    def execute(self, action):
        """The main method to be called in order to execute various actions.

        Once the system controller has been instantiated, one is meant to
        make calls to systemd as such:

            systemctl = SystemController('amqp-middleware')
            systemctl.execute('start')

        """
        cmd = getattr(self, action)
        run_command(cmd, su=True)

    @property
    def status(self):
        """Check whether the specified service is running."""
        ctx.logger.info('Checking status of %s service', self.service)
        return ['systemctl', 'status', '%s.service' % self.service]

    @property
    def start(self):
        """Start the specified service."""
        ctx.logger.info('Starting %s service', self.service)
        return ['systemctl', 'start', '%s.service' % self.service]

    @property
    def stop(self):
        """Stop the specified service."""
        ctx.logger.info('Stopping %s service', self.service)
        return ['systemctl', 'stop', '%s.service' % self.service]

    @property
    def restart(self):
        """Restart the specified service."""
        ctx.logger.info('Restarting %s service', self.service)
        return ['systemctl', 'restart', '%s.service' % self.service]

    @property
    def enable(self):
        """Enable the specified service."""
        ctx.logger.info('Enabling %s service', self.service)
        return ['systemctl', 'enable', '%s.service' % self.service]

    @property
    def disable(self):
        """Disable the specified service."""
        ctx.logger.info('Disabling %s service', self.service)
        return ['systemctl', 'disable', '%s.service' % self.service]

    @property
    def configure(self):
        """Configure the specified service."""
        ctx.logger.info('Configuring service %s', self.service)
        svc = os.path.join('service', '%s.service' % self.service)
        tmp = os.path.join(os.path.dirname(__file__), svc.split('/')[-1])
        ctx.download_resource(svc, tmp)
        return ['mv', tmp, SYSTEM_DIR]

    @property
    def delete(self):
        """Delete the specified service's configuration."""
        ctx.logger.info('Removing configuration for service %s', self.service)
        svc = os.path.join(SYSTEM_DIR, '%s.service' % self.service)
        return ['rm', svc]

    @property
    def reload(self):
        """Reload the system daemon."""
        ctx.logger.info('Reloading systemd')
        return ['systemctl', 'daemon-reload']


def run_command(cmd, su=False):
    """Run shell commands, check the output, and raise proper error message
    in case an exception occurs.
    """
    if su:
        cmd.insert(0, 'sudo')
    try:
        output = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        raise CommandExecutionException(command=' '.join(cmd), error='',
                                        output=err.output, code=err.returncode)


def dump_to_file(payload, path):
    """A helper method to JSON-dump a given payload to file."""
    fd, abs_path = tempfile.mkstemp()
    os.close(fd)
    with open(abs_path, 'w') as f:
        f.write(json.dumps(payload, indent=4))
    cmd = ['mv', abs_path, path]
    run_command(cmd, su=True)


def render_to_file(src, dst):
    """Render a file and move it to the desired destination.

    :param src: the current path of the file to be rendered.
    :param dst: the desired path to move the file to.
    """
    tmp = os.path.join(
        os.path.dirname(__file__), src.split('/')[-1]
    )
    ctx.download_resource_and_render(src, tmp)
    cmd = ['mv', tmp, dst]
    run_command(cmd, su=True)


def rename_kwargs(kwargs, old_key, new_key):
    """A helper method that allows to rename a dictionary's keys."""
    if old_key in kwargs:
        if new_key not in kwargs:
            kwargs[new_key] = kwargs.pop(old_key)


def install_pkg(pkgs):
    """Installs missing packages."""
    if not isinstance(pkgs, list):
        pkgs = [pkgs]
    for pkg in pkgs:
        try:
            cmd = ['yum', 'list', 'installed', '-q', pkg]
            run_command(cmd)
        except CommandExecutionException:
            ctx.logger.info('Installing package \'%s\'', pkg)
            cmd = ['yum', 'install', '-yq', pkg]
            run_command(cmd, su=True)
        else:
            ctx.logger.info('Package \'%s\' already installed', pkg)


def add_cloud(provider, data):
    """Transfers cloud credentials to the specified destination endpoint.

    :param provider: Denotes the cloud provider, e.g. "ec2", "openstack", etc.
    :param data: Cloud credentials as specified in the blueprint's inputs YAML.
    """
    ctx.logger.info('Adding "%s" cloud', data['title'])

    if ctx.node.properties['stream']['secure']:
        scheme = 'https'
    else:
        scheme = 'http'
    host = ctx.node.properties['stream']['destination_url']
    if not host:
        NonRecoverableError('No destination_url specified')

    data.update({'provider': provider.lower()})
    headers = {
        'Authorization': ctx.instance.runtime_properties['_meta']['token']
    }
    req = requests.post('%s://%s/api/v1/clouds' % (scheme, host),
                        data=json.dumps(data), headers=headers)
    if not req.ok:
        ctx.logger.error('%d: Cloud "%s" not added successfully: %s',
                         req.status_code, data['title'], req.content)
    else:
        response = req.json()
        clouds = ctx.instance.runtime_properties.pop('clouds', {})
        clouds.update({
            data['title']: response['id']
        })
        ctx.instance.runtime_properties['clouds'] = clouds


def delete_cloud(name):
    """Revokes cloud credentials.

    :param name: The name of the cloud for which to revoke credentials.
    """
    ctx.logger.info('Removing cloud "%s"', name)

    clouds = ctx.instance.runtime_properties.get('clouds', {})
    cloud_id = clouds.get(name)
    if not cloud_id:
        ctx.logger.error('No cloud titled "%s" exists in local storage', name)
        return
    if ctx.node.properties['stream']['secure']:
        scheme = 'https'
    else:
        scheme = 'http'
    host = ctx.node.properties['stream']['destination_url']
    if not host:
        NonRecoverableError('No destination_url specified')

    headers = {
        'Authorization': ctx.instance.runtime_properties['_meta']['token']
    }
    req = requests.delete('%s://%s/api/v1/clouds/%s' % (
                          scheme, host, cloud_id), headers=headers)
    if not req.ok:
        ctx.logger.error('%d: Failed to remove cloud "%s" (%s): %s',
                         req.status_code, name, cloud_id, req.content)
    else:
        ctx.instance.runtime_properties['clouds'].pop(name)
