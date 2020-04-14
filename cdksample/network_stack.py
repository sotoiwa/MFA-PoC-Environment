from aws_cdk import (
    core,
    aws_ec2 as ec2
)


class NetworkStack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ################
        # VPCの作成
        ################

        # VPCの作成
        vpc = ec2.Vpc(
            self, 'VPC',
            cidr='10.1.0.0/16',
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name='Public',
                    subnet_type=ec2.SubnetType.PUBLIC
                ),
                ec2.SubnetConfiguration(
                    cidr_mask=24,
                    name='Private',
                    subnet_type=ec2.SubnetType.PRIVATE
                )
            ]
        )

        ################
        # セキュリティグループの作成
        ################

        # 内部用セキュリティグループ
        internal_sg = ec2.SecurityGroup(
            self, 'InternalSecurityGroup',
            vpc=vpc
        )
        # セキュリティグループ内の通信を全て許可
        internal_sg.connections.allow_internally(
            port_range=ec2.Port.all_traffic()
        )
        # 1812/UDPを許可
        internal_sg.connections.allow_from(
            other=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            port_range=ec2.Port.udp(1812)
        )

        # Bastion用セキュリティグループ
        bastion_sg = ec2.SecurityGroup(
            self, 'BastionSecurityGroup',
            vpc=vpc
        )
        # BastionへのRDPを許可
        bastion_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(3389)
        )
        # BastionへのSSHを許可
        bastion_sg.add_ingress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(22)
        )

        ################
        # VPCエンドポイントの作成
        ################

        # SSMのためのエンドポイントを作成
        vpc.add_interface_endpoint(
            id='SsmEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService.SSM,
            private_dns_enabled=True,
            security_groups=[internal_sg],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE)
        )
        vpc.add_interface_endpoint(
            id='SsmMessagesEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService.SSM_MESSAGES,
            private_dns_enabled=True,
            security_groups=[internal_sg],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE)
        )
        vpc.add_interface_endpoint(
            id='Ec2MessagesEndpoint',
            service=ec2.InterfaceVpcEndpointAwsService.E_C2_MESSAGES,
            private_dns_enabled=True,
            security_groups=[internal_sg],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE)
        )
        vpc.add_gateway_endpoint(
            id='S3Endpoint',
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE)]
        )

        self.output_props = props.copy()
        self.output_props['vpc'] = vpc
        self.output_props['internal_sg'] = internal_sg
        self.output_props['bastion_sg'] = bastion_sg

    @property
    def outputs(self):
        return self.output_props
