"""Check if SSO profile works."""
import boto3

profiles = ["default", "poweruser"]
for p in profiles:
    print(f"Trying profile: {p}")
    try:
        session = boto3.Session(profile_name=p, region_name="us-east-1")
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        acct = identity["Account"]
        arn = identity["Arn"]
        print(f"  Account: {acct}")
        print(f"  ARN: {arn}")
        print(f"  STATUS: VALID")
    except Exception as e:
        err = str(e)[:150]
        print(f"  STATUS: FAILED - {err}")
    print()
