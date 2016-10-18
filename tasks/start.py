from cloudify import ctx

import os


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)


from utils import SystemController


systemctl = SystemController('amqp-middleware')

systemctl.execute('start')
systemctl.execute('status')

ctx.logger.info('AMQP Middleware is up and running!')
