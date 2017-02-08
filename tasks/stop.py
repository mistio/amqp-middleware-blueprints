from cloudify import ctx
from cloudify.exceptions import CommandExecutionException

import os
import sys


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)

try:
    from utils import SystemController
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from utils import SystemController


try:
    systemctl = SystemController('amqp-middleware')
    systemctl.execute('stop')
except CommandExecutionException as exc:
    ctx.logger.error(exc)
