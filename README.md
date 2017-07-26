# amqp-middleware-blueprints

This repository contains blueprints for installing Mist.io - Cloudify Manager
RabbitMQ middleware used to stream monitoring data.

## Installation

Mist.io's [AMQP Middleware](https://gitlab.ops.mist.io/mistio/amqp-middleware)
can be installed by using the corresponding Cloudify blueprint.

### Requirements

All that is required is the Cloudify CLI:

    pip install cloudify

and the corresponding Cloudify blueprint. See the [tags](https://gitlab.ops.mist.io/mistio/amqp-middleware-blueprints/tags)
section in order to download the version of the blueprints corresponding to the
most suited [version](https://gitlab.ops.mist.io/mistio/amqp-middleware/tags)
of the middleware.

It is **important** to use a version of the Cloudify CLI that supports local
execution of workflows.

### Configuration

Once downloaded, the `amqp-middleware-blueprints/` directory will be present
in the current working path. All available/required configuration options can
be found under the `inputs/` directory.

In order to setup Mist.io's AMQP Middleware the `local-blueprint-inputs.yaml`
file needs to be edited. The inputs file comes with several configuration
options. Most of them, however, already have default values. All configuration
options come with detailed descriptions regarding their purpose.

The inputs file can be broken down into the following main sections:

1. Cloudify Manager Inputs: These are the inputs required for the AMQP
Middleware to be able to connect to Cloudify Manager's RabbitMQ server,
as well as query Cloudify Manager's REST API in order to retrieve information
on deployments and node instances.

2. User Inputs: This inputs section requires user information in order to
create a new Mist.io account and authenticate to the Mist.io API.

3. Cloud Credentials: Users may specify their cloud credentials and the AMQP
Middleware will take care of adding the user's infrastructure to Mist.io.

Once all required inputs have been provided, save the inputs file, initialize
the cloudify environment, and execute the `install` workflow:

    cfy local init -p local-blueprint.yaml -i inputs/local-blueprint-inputs.yaml
    cfy local execute -w install

By this time, the AMQP Middleware should have already started consuming data
from RabbitMQ and streaming it to the Mist.io SaaS.

Once the workflow's execution has finished successfully, execute:

    cfy local outputs

in order to retrieve useful information.

### Managing the service

The install workflow will create the `/opt/amqp-middleware/` directory.

Tail the AMQP Middleware's logs with:

    tail -f /opt/amqp-middleware/agent.log

The middleware is also controlled by `systemd`:

    # Verify the service is up and running
    systemctl status amqp-middleware

    # Restart the service
    systemctl restart amqp-middleware

## Additional workflows

The AMQP Middleware's blueprint comes with two additional workflows in order to
add/remove clouds outside the installation process.

### Adding more clouds

In order to add more clouds to an existing account, populate the `inputs/update-clouds.yaml` file.
Its structure is the same as the corresponding clouds section in `inputs/local-blueprint-inputs.yaml`.

Then, run:

    cfy local execute -w add_cloud -p inputs/update-clouds.yaml

### Removing existing clouds

Populate the `inputs/remove-clouds.yaml` in order to remove unwanted clouds.
Remember to refer to the clouds by their title.

Finally, execute:

    cfy local execute -w remove_cloud -p inputs/remove-clouds.yaml
