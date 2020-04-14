#!/usr/bin/env python3

from aws_cdk import core

from cdksample.network_stack import NetworkStack
from cdksample.ec2_stack import EC2Stack
from cdksample.managed_ad_stack import ManagedADStack

app = core.App()
prefix = app.node.try_get_context('stack_prefix')
env = core.Environment(
    account=app.node.try_get_context('account'),
    region='ap-northeast-1'
)
props = dict()

network_stack = NetworkStack(app, '{}-NetworkStack'.format(prefix), env=env, props=props)
props = network_stack.outputs

ec2_stack = EC2Stack(app, '{}-EC2Stack'.format(prefix), env=env, props=props)
props = ec2_stack.outputs

managed_ad_stack = ManagedADStack(app, '{}-ManagedADStack'.format(prefix), env=env, props=props)
props = managed_ad_stack.outputs

app.synth()
