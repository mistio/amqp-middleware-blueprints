from cloudify import ctx
from cloudify.exceptions import CommandExecutionException

import os


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)


from utils import SystemController


try:
    systemctl = SystemController('amqp-middleware')
    systemctl.execute('stop')
except CommandExecutionException as exc:
    ctx.logger.error(exc)
