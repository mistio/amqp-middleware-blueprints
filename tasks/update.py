from cloudify import ctx
from cloudify.state import ctx_parameters as inputs

import os
import json
import requests


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)


from utils import add_cloud


if inputs.cloud_creds:
    for provider, data in inputs.cloud_creds.iteritems():
        add_cloud(dest=ctx.node.properties['stream']['destination_url'],
                  token=ctx.instance.runtime_properties['_meta']['token'],
                  cloud=(provider, data))
