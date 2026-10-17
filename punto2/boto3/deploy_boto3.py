#!/usr/bin/env python3
"""Despliegue / eliminacion con Boto3 de: S3 + red + EC2 + RDS PostgreSQL.

Autenticacion: cadena estandar de credenciales de boto3 (perfil user_cli).
    export AWS_PROFILE=user_cli
    python deploy_boto3.py create
    python deploy_boto3.py read-secret     # recupera el secreto en ejecucion (no lo imprime)
    python deploy_boto3.py destroy

La contrasena de RDS la genera y guarda RDS en Secrets Manager
(ManageMasterUserPassword=True). Este programa nunca contiene ni recibe una contrasena.
"""
import json
import sys
import time
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-2"
PREFIX = "lab-sdk"
STATE_FILE = Path(__file__).with_name("boto3_state.json")  # solo IDs, sin secretos (esta en .gitignore)
TAGS = [{"Key": "Project", "Value": "lab-punto2"}, {"Key": "Method", "Value": "boto3"}]

session = boto3.Session(region_name=REGION)
ec2 = session.client("ec2")
s3 = session.client("s3")
rds = session.client("rds")
sm = session.client("secretsmanager")
ssm = session.client("ssm")
sts = session.client("sts")


def tag(resource_type: str, name: str):
    return [{"ResourceType": resource_type, "Tags": TAGS + [{"Key": "Name", "Value": f"{PREFIX}-{name}"}]}]


def save(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load() -> dict:
    return json.loads(STATE_FILE.read_text())


def create():
    print("Identidad:", sts.get_caller_identity()["Arn"])  # debe terminar en user/user_cli
    st: dict = {}

    # ---- S3
    st["bucket"] = f"{PREFIX}-{uuid.uuid4().hex[:8]}"
    s3.create_bucket(Bucket=st["bucket"], CreateBucketConfiguration={"LocationConstraint": REGION})  # fuera de us-east-1 es obligatorio
    s3.put_public_access_block(
        Bucket=st["bucket"],
        PublicAccessBlockConfiguration={k: True for k in (
            "BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets")},
    )
    save(st)
    print("S3 creado:", st["bucket"])

    # ---- Red
    azs = [z["ZoneName"] for z in ec2.describe_availability_zones()["AvailabilityZones"]]
    vpc = ec2.create_vpc(CidrBlock="10.30.0.0/16", TagSpecifications=tag("vpc", "vpc"))["Vpc"]["VpcId"]
    st["vpc"] = vpc
    ec2.modify_vpc_attribute(VpcId=vpc, EnableDnsSupport={"Value": True})
    ec2.modify_vpc_attribute(VpcId=vpc, EnableDnsHostnames={"Value": True})

    igw = ec2.create_internet_gateway(TagSpecifications=tag("internet-gateway", "igw"))["InternetGateway"]["InternetGatewayId"]
    ec2.attach_internet_gateway(InternetGatewayId=igw, VpcId=vpc)
    st["igw"] = igw

    def subnet(cidr, az, name):
        return ec2.create_subnet(VpcId=vpc, CidrBlock=cidr, AvailabilityZone=az,
                                 TagSpecifications=tag("subnet", name))["Subnet"]["SubnetId"]

    st["subnet_public"] = subnet("10.30.1.0/24", azs[0], "public-a")
    st["subnet_priv_a"] = subnet("10.30.2.0/24", azs[0], "private-a")
    st["subnet_priv_b"] = subnet("10.30.3.0/24", azs[1], "private-b")

    rt = ec2.create_route_table(VpcId=vpc, TagSpecifications=tag("route-table", "rt"))["RouteTable"]["RouteTableId"]
    ec2.create_route(RouteTableId=rt, DestinationCidrBlock="0.0.0.0/0", GatewayId=igw)
    st["rt_assoc"] = ec2.associate_route_table(RouteTableId=rt, SubnetId=st["subnet_public"])["AssociationId"]
    st["rt"] = rt

    sg_ec2 = ec2.create_security_group(GroupName=f"{PREFIX}-ec2-sg", Description="EC2 sin ingreso",
                                       VpcId=vpc, TagSpecifications=tag("security-group", "ec2-sg"))["GroupId"]
    sg_rds = ec2.create_security_group(GroupName=f"{PREFIX}-rds-sg", Description="PostgreSQL desde EC2",
                                       VpcId=vpc, TagSpecifications=tag("security-group", "rds-sg"))["GroupId"]
    ec2.authorize_security_group_ingress(GroupId=sg_rds, IpPermissions=[{
        "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
        "UserIdGroupPairs": [{"GroupId": sg_ec2}]}])
    st["sg_ec2"], st["sg_rds"] = sg_ec2, sg_rds
    save(st)
    print("Red creada:", vpc)

    # ---- EC2
    ami = ssm.get_parameter(Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64")["Parameter"]["Value"]
    inst = ec2.run_instances(
        ImageId=ami, InstanceType="t3.micro", MinCount=1, MaxCount=1,
        NetworkInterfaces=[{"DeviceIndex": 0, "SubnetId": st["subnet_public"],
                            "Groups": [sg_ec2], "AssociatePublicIpAddress": False}],
        MetadataOptions={"HttpTokens": "required"},
        BlockDeviceMappings=[{"DeviceName": "/dev/xvda", "Ebs": {
            "VolumeSize": 8, "VolumeType": "gp3", "DeleteOnTermination": True, "Encrypted": True}}],
        TagSpecifications=tag("instance", "ec2"),
    )["Instances"][0]["InstanceId"]
    st["instance"] = inst
    save(st)
    ec2.get_waiter("instance_running").wait(InstanceIds=[inst])
    print("EC2 en ejecucion:", inst)

    # ---- RDS (contrasena administrada por Secrets Manager)
    st["dbsubnet"] = f"{PREFIX}-dbsubnets"
    rds.create_db_subnet_group(DBSubnetGroupName=st["dbsubnet"], DBSubnetGroupDescription="lab",
                               SubnetIds=[st["subnet_priv_a"], st["subnet_priv_b"]], Tags=TAGS)
    st["db"] = f"{PREFIX}-pg"
    rds.create_db_instance(
        DBInstanceIdentifier=st["db"], Engine="postgres", EngineVersion="16",
        DBInstanceClass="db.t4g.micro", AllocatedStorage=20, StorageType="gp3", StorageEncrypted=True,
        DBName="labdb", MasterUsername="labadmin",
        ManageMasterUserPassword=True,          # <-- sin MasterUserPassword
        DBSubnetGroupName=st["dbsubnet"], VpcSecurityGroupIds=[sg_rds],
        PubliclyAccessible=False, MultiAZ=False, BackupRetentionPeriod=0,
        DeletionProtection=False, Tags=TAGS,
    )
    save(st)
    print("Esperando RDS (5-10 min)...")
    rds.get_waiter("db_instance_available").wait(DBInstanceIdentifier=st["db"],
                                                 WaiterConfig={"Delay": 30, "MaxAttempts": 60})
    db = rds.describe_db_instances(DBInstanceIdentifier=st["db"])["DBInstances"][0]
    st["secret_arn"] = db["MasterUserSecret"]["SecretArn"]
    st["endpoint"] = db["Endpoint"]["Address"]
    save(st)
    print("RDS listo:", st["endpoint"], "| secreto:", st["secret_arn"])


def read_secret():
    """Demuestra la recuperacion en tiempo de ejecucion. user_cli ya esta autenticado via su perfil."""
    arn = load()["secret_arn"]
    value = json.loads(sm.get_secret_value(SecretId=arn)["SecretString"])
    print("Secreto leido OK. Claves:", sorted(value.keys()), "| usuario:", value["username"])
    # NUNCA imprimir value["password"]


def _try(fn, label, **kw):
    try:
        fn(**kw)
        print("eliminado:", label)
    except ClientError as e:
        print("aviso", label, "->", e.response["Error"]["Code"])


def destroy():
    st = load()
    if "db" in st:
        _try(rds.delete_db_instance, "rds", DBInstanceIdentifier=st["db"], SkipFinalSnapshot=True,
             DeleteAutomatedBackups=True)
        print("Esperando borrado de RDS...")
        rds.get_waiter("db_instance_deleted").wait(DBInstanceIdentifier=st["db"],
                                                   WaiterConfig={"Delay": 30, "MaxAttempts": 60})
        _try(rds.delete_db_subnet_group, "db subnet group", DBSubnetGroupName=st["dbsubnet"])
    if "instance" in st:
        _try(ec2.terminate_instances, "ec2", InstanceIds=[st["instance"]])
        ec2.get_waiter("instance_terminated").wait(InstanceIds=[st["instance"]])
    for sg in (st.get("sg_rds"), st.get("sg_ec2")):
        if sg:
            _try(ec2.delete_security_group, f"sg {sg}", GroupId=sg)
    if "rt_assoc" in st:
        _try(ec2.disassociate_route_table, "rt assoc", AssociationId=st["rt_assoc"])
    if "rt" in st:
        _try(ec2.delete_route_table, "route table", RouteTableId=st["rt"])
    for k in ("subnet_public", "subnet_priv_a", "subnet_priv_b"):
        if k in st:
            _try(ec2.delete_subnet, k, SubnetId=st[k])
    if "igw" in st:
        _try(ec2.detach_internet_gateway, "igw detach", InternetGatewayId=st["igw"], VpcId=st["vpc"])
        _try(ec2.delete_internet_gateway, "igw", InternetGatewayId=st["igw"])
    if "vpc" in st:
        _try(ec2.delete_vpc, "vpc", VpcId=st["vpc"])
    if "bucket" in st:
        b = boto3.resource("s3", region_name=REGION).Bucket(st["bucket"])
        b.objects.all().delete()
        _try(s3.delete_bucket, "s3", Bucket=st["bucket"])
    # El secreto rds!db-* lo elimina RDS automaticamente al borrar la instancia.
    STATE_FILE.unlink(missing_ok=True)
    print("Listo. Ejecute scripts/check_leftovers.sh para verificar.")


if __name__ == "__main__":
    actions = {"create": create, "destroy": destroy, "read-secret": read_secret}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        sys.exit(f"Uso: {sys.argv[0]} {{create|read-secret|destroy}}")
    actions[sys.argv[1]]()
