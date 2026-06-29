# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | ✅ Current stable release |
| 0.1.0a1 | ❌ Alpha — no longer supported |

Security fixes are backported to the current stable minor version only.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability privately:

1. Email **arsiemuha@gmail.com** with the subject line `[BridgeMCP Security] <brief description>`.
2. Include:
   - A description of the vulnerability
   - Steps to reproduce it
   - The version of BridgeMCP affected
   - Any suggested mitigations you are aware of

You will receive an acknowledgment within 72 hours. We aim to publish a fix within 14 days of confirmation, coordinated with the reporter.

If you prefer encrypted communication, request a PGP key in your initial email.

## Disclosure Policy

Once a fix is released, a security advisory will be published on the GitHub repository. Credit will be given to the reporter unless they prefer to remain anonymous.

We follow responsible disclosure: we will not publish details of a vulnerability until a fix is available, and we will notify downstream plugin authors if the vulnerability affects the plugin API.

## Scope

The following are considered in-scope for security reports:

- Vulnerabilities in the BridgeMCP Python package (`bridgemcp`)
- Vulnerabilities in the MCP adapter that could allow a malicious MCP client to affect the server process
- Dependency vulnerabilities in `pydantic` or `mcp` that affect BridgeMCP users

The following are out of scope:

- Vulnerabilities in user-written tool, resource, or prompt handlers
- Vulnerabilities in third-party plugins
- Vulnerabilities in AI clients (Claude Desktop, Cursor, etc.)
- Authentication weaknesses in the HTTP transport — BridgeMCP does not provide authentication; that is the responsibility of a plugin or a reverse proxy

## Security Considerations for Users

**HTTP transport**: `app.run_http()` binds to `127.0.0.1` by default and does not implement authentication. Do not expose it on `0.0.0.0` without a reverse proxy and authentication layer in front of it.

**Tool handler inputs**: BridgeMCP forwards arguments from MCP clients directly to your tool handlers. Validate all inputs inside your handlers if the tool is callable by untrusted clients.

**Dependency pinning**: BridgeMCP pins `pydantic>=2.0` and `mcp>=1.0`. Pin your own dependencies with exact versions in production deployments to avoid unexpected updates.
