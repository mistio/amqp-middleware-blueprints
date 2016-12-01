from cloudify.workflows import ctx
from cloudify.workflows import parameters as inputs


consumer = ctx.get_node('consumer')
consumer = [instance for instance in consumer.instances][0]
consumer.execute_operation(
    'cloudify.interfaces.lifecycle.update',
    kwargs={'cloud_creds': inputs.credentials}
)
