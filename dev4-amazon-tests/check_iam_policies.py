"""Check IAM policies on the current role to find the explicit deny."""
import boto3
import json

session = boto3.Session(profile_name="poweruser", region_name="us-east-1")
sts = session.client("sts")
identity = sts.get_caller_identity()
arn = identity["Arn"]
print(f"Current identity: {arn}")

# Extract role name from assumed-role ARN
# Format: arn:aws:sts::ACCOUNT:assumed-role/ROLE_NAME/SESSION
parts = arn.split("/")
role_name = parts[1] if len(parts) > 1 else "unknown"
print(f"Role name: {role_name}")

iam = session.client("iam")

# List attached policies
print("\nAttached managed policies:")
try:
    attached = iam.list_attached_role_policies(RoleName=role_name)
    for p in attached.get("AttachedPolicies", []):
        print(f"  {p['PolicyName']} ({p['PolicyArn']})")
except Exception as e:
    print(f"  Cannot list (expected for SSO roles): {str(e)[:150]}")

# List inline policies
print("\nInline policies:")
try:
    inline = iam.list_role_policies(RoleName=role_name)
    for name in inline.get("PolicyNames", []):
        print(f"  {name}")
        try:
            doc = iam.get_role_policy(RoleName=role_name, PolicyName=name)
            policy = doc["PolicyDocument"]
            # Look for bedrock deny statements
            for stmt in policy.get("Statement", []):
                effect = stmt.get("Effect", "")
                actions = stmt.get("Action", [])
                if isinstance(actions, str):
                    actions = [actions]
                bedrock_actions = [a for a in actions if "bedrock" in a.lower()]
                if bedrock_actions:
                    print(f"    Effect: {effect}")
                    print(f"    Bedrock actions: {bedrock_actions}")
                    print(f"    Resource: {stmt.get('Resource', '*')}")
        except Exception as e2:
            print(f"    Cannot read policy: {str(e2)[:100]}")
except Exception as e:
    print(f"  Cannot list (expected for SSO roles): {str(e)[:150]}")

# Try to get the permission boundary if any
print("\nRole details:")
try:
    role = iam.get_role(RoleName=role_name)
    r = role["Role"]
    boundary = r.get("PermissionsBoundary", {}).get("PermissionsBoundaryArn", "none")
    print(f"  Permission boundary: {boundary}")
    print(f"  Max session duration: {r.get('MaxSessionDuration', '?')}s")
except Exception as e:
    print(f"  Cannot get role details: {str(e)[:150]}")

# Try a simulated policy evaluation
print("\nPolicy simulation (bedrock:InvokeModel):")
try:
    result = iam.simulate_principal_policy(
        PolicySourceArn=f"arn:aws:iam::{identity['Account']}:role/{role_name}",
        ActionNames=["bedrock:InvokeModel", "bedrock:ListFoundationModels"],
    )
    for r in result.get("EvaluationResults", []):
        print(f"  {r['EvalActionName']}: {r['EvalDecision']}")
        if r.get("MatchedStatements"):
            for s in r["MatchedStatements"]:
                print(f"    Matched: {s.get('SourcePolicyId', '?')} ({s.get('SourcePolicyType', '?')})")
except Exception as e:
    print(f"  Cannot simulate: {str(e)[:200]}")
