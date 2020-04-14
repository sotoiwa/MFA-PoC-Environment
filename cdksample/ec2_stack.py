from aws_cdk import (
    core,
    aws_ec2 as ec2,
    aws_iam as iam
)


class EC2Stack(core.Stack):

    def __init__(self, scope: core.Construct, id: str, props, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc = props['vpc']
        internal_sg = props['internal_sg']
        bastion_sg = props['bastion_sg']

        # Bastion用Linux
        bastion_linux = ec2.Instance(
            self, 'BastionLinux',
            instance_type=ec2.InstanceType('t3.micro'),
            machine_image=ec2.MachineImage.latest_amazon_linux(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            key_name=self.node.try_get_context('key_name'),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=internal_sg
        )
        bastion_linux.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSSMManagedInstanceCore'))
        bastion_linux.add_security_group(bastion_sg)

        # Bastion用Windows
        bastion_windows = ec2.Instance(
            self, 'BastionWindows',
            instance_type=ec2.InstanceType('t3.large'),
            machine_image=ec2.MachineImage.latest_windows(
                version=ec2.WindowsVersion.WINDOWS_SERVER_2016_JAPANESE_FULL_BASE),
            key_name=self.node.try_get_context('key_name'),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=internal_sg
        )
        bastion_windows.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSSMManagedInstanceCore'))
        bastion_windows.add_security_group(bastion_sg)

        # ドメインコントローラ用EC2
        domain_controller_windows = ec2.Instance(
            self, 'DomainController',
            instance_type=ec2.InstanceType('t3.large'),
            machine_image=ec2.MachineImage.latest_windows(
                version=ec2.WindowsVersion.WINDOWS_SERVER_2016_JAPANESE_FULL_BASE),
            key_name=self.node.try_get_context('key_name'),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE),
            security_group=internal_sg
        )
        domain_controller_windows.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSSMManagedInstanceCore'))

        # Radius用EC2ホスト
        radius_host = ec2.Instance(
            self, 'RadiusHost',
            instance_type=ec2.InstanceType('t3.small'),
            machine_image=ec2.MachineImage.latest_amazon_linux(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            key_name=self.node.try_get_context('key_name'),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE),
            security_group=internal_sg
        )
        radius_host.role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSSMManagedInstanceCore'))

        self.output_props = props.copy()

    @property
    def outputs(self):
        return self.output_props
