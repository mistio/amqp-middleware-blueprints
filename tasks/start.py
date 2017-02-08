from cloudify import ctx

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


systemctl = SystemController('amqp-middleware')

systemctl.execute('start')
systemctl.execute('status')

ctx.logger.info('AMQP Middleware is up and running!')
