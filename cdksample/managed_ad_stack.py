from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_directoryservice as directoryservice
)


class ManagedADStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = props['vpc']
        internal_sg = props['internal_sg']

        # Managed AD
        managed_ad = directoryservice.CfnMicrosoftAD(
            self, 'ManagedAD',
            name=self.node.try_get_context('managed_ad')['domain_name'],
            password=self.node.try_get_context('managed_ad')['admin_password'],
            vpc_settings={
              "subnetIds": vpc.select_subnets(subnet_type=ec2.SubnetType.PRIVATE).subnet_ids,
              "vpcId": vpc.vpc_id
            },
            edition='Standard'
        )

        self.output_props = props.copy()
        self.output_props['managed_ad'] = managed_ad

    @property
    def outputs(self):
        return self.output_props
