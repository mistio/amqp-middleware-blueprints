from cloudify import ctx
from cloudify.state import ctx_parameters as inputs

import os
import sys


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)
try:
    from utils import run_command
    from utils import SystemController
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from utils import run_command
    from utils import SystemController


systemctl = SystemController('amqp-middleware')
systemctl.execute('disable')
systemctl.execute('delete')
systemctl.execute('reload')

if inputs['remove_source']:
    ctx.logger.info('Removing AMQP Middleware directory')
    cmd = ['rm', '-rf', '/opt/amqp-middleware']
    run_command(cmd, su=True)
