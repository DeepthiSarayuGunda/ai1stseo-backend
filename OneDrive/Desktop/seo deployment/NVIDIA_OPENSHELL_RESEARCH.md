# NVIDIA OpenShell Research — Security for OpenClaw Agent

**Author:** Troy Sauriol | **Date:** April 2, 2026
**Context:** Gurbachan advised using NVIDIA OpenShell before deploying OpenClaw on seo-dev server.

---

## What OpenShell Is

NVIDIA OpenShell is an open-source sandbox runtime (Apache 2.0) for AI agents. It wraps agents like OpenClaw in containerized environments with kernel-level isolation. Released at GTC 2026, it's specifically designed for autonomous agents that execute code and access filesystems.

Key capabilities:
- Filesystem locked at creation — agent can only access declared paths
- Network blocked by default — must explicitly allow endpoints
- API keys never touch disk — injected via secure environment
- Declarative YAML policies control all permissions
- Full audit trail of every agent action
- Works with OpenClaw natively via NemoClaw plugin

## How It Works

OpenShell creates sandboxes (isolated execution environments) controlled by a gateway. Each sandbox runs with:
- Landlock (Linux kernel filesystem isolation)
- seccomp (system call filtering)
- Network namespace isolation
- Process privilege restrictions

Policies are defined in YAML:
```yaml
sandbox:
  filesystem:
    read: ["/opt/ai1stseo/openclaw-workspace"]
    write: ["/tmp"]
    deny: ["/root/.ssh", "/root/.aws"]
  network:
    allow:
      - "192.168.2.200:11434"  # Ollama accelerator
      - "127.0.0.1:8888"       # Site monitor API
    deny: ["*"]  # Block everything else
  process:
    allow_exec: false
    max_memory: "2G"
```

## NemoClaw — OpenClaw + OpenShell Integration

NVIDIA released NemoClaw, an orchestration plugin that runs OpenClaw agents inside OpenShell sandboxes. This is exactly what Gurbachan was referring to.

NemoClaw provides:
- Automatic sandbox creation for each OpenClaw agent session
- Policy enforcement around tool execution
- Network isolation (agent can only reach declared endpoints)
- Credential injection without disk exposure

## Relevance to Our Project

Our OpenClaw agent on seo-dev has access to:
- The local Ollama accelerator (192.168.2.200:11434)
- The site monitor API (127.0.0.1:8888)
- The filesystem (workspace at /opt/ai1stseo/openclaw-workspace)
- Root access on the server

Without OpenShell, a compromised agent (via prompt injection from scanned web content) could:
- Read SSH keys, AWS credentials, or other secrets
- Make network requests to arbitrary endpoints
- Modify system files or other services on the server

With OpenShell, the agent is locked to only what we declare in the policy.

## Implementation Plan

1. Install OpenShell on seo-dev: `pip install nvidia-openshell` (or from GitHub)
2. Create a sandbox policy YAML for our agent
3. Install NemoClaw plugin: `openclaw plugins install nemoclaw`
4. Configure OpenClaw to run inside the sandbox
5. Test that the agent can still reach Ollama and the monitor API
6. Verify that filesystem access is restricted to the workspace only

## Requirements

- Linux kernel 5.13+ (for Landlock) — seo-dev has 6.8.12 ✓
- Python 3.10+ — seo-dev has 3.12 ✓
- Container runtime (Podman or Docker) — not currently installed, may need setup
- 32GB RAM — seo-dev has 32GB ✓

## Recommendation

Implement OpenShell before connecting any customer-facing channels (WhatsApp, Telegram). For internal testing, the current setup is acceptable. OpenShell becomes critical when untrusted users can send messages that become agent prompts — that's when prompt injection risk is real.

Priority: Medium (implement before Phase 4 of OpenClaw integration plan).
