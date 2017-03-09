from cloudify import ctx
from cloudify.state import ctx_parameters as inputs

import os
import sys
import json
import requests


ctx.download_resource(
    os.path.join('tasks', 'utils.py'),
    os.path.join(os.path.dirname(__file__), 'utils.py')
)

try:
    from utils import add_cloud
except ImportError:
    sys.path.append(os.path.dirname(__file__))
    from utils import add_cloud


if inputs.cloud_creds:
    for provider, data in inputs.cloud_creds.iteritems():
        add_cloud(provider, data)
