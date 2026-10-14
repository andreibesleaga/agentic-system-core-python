# Security policy

## Reporting a vulnerability

Report it privately, through this repository's **private vulnerability reporting**:
open the repository's **Security** tab and choose **Report a vulnerability**
(<https://github.com/andreibesleaga/agentic-system-core-python/security/advisories/new>).
The report goes to the maintainer and is not public while it is being handled. A
problem in the Node engine rather than in this package may go to the engine
repository's private reporting instead.

Please do not open a public issue for a security problem, and please do not post the
details anywhere public until a fix is released.

If private reporting is unavailable to you, use the contact page at
<https://andreibesleaga.com/contact/> and ask for a private channel; do not put the
details in the first message.

Useful in a report: what you did, what happened, what you expected, the package
version (`python -m pip show agentic-system-core`), the Python version and the exact
command.

## What this package touches

The package reads files and, only when `--allow-network` is on the command line,
fetches a published node's discovery document and its targets, with the protections
the [README](README.md) lists. The interesting reports are therefore usually about
input handling: a discovery document, a vector file or a published node that makes a
checker read or fetch something it should not, or report a pass it should not.

## Everything else

The engine's security policy applies to this package unchanged: what to expect, the
supported versions (this package follows the engine's version numbers, in the PEP 440
spelling), coordinated disclosure, and the honest limits of what the checks prove.
It is at
<https://github.com/andreibesleaga/agentic-system-core/blob/main/SECURITY.md>.
