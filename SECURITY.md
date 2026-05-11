# Security Policy

## Supported Versions

Security updates are provided for the latest released version of `rarfile`.

If you are using an older version, please try to reproduce the issue with the latest release before reporting it. Reports affecting older versions may still be useful, but fixes will normally target the current codebase first.

## Reporting a Vulnerability

Please report security vulnerabilities privately instead of opening a public GitHub issue.

Preferred reporting method:

- Use GitHub's private vulnerability reporting / Security Advisory flow, if available for this repository.

If that is not available, contact the maintainer privately using the contact information listed on the maintainer's GitHub profile or package metadata.

Please include as much of the following information as possible:

- A clear description of the vulnerability.
- The affected `rarfile` version and commit, if known.
- The operating system and Python version used for testing.
- A minimal proof of concept or reproduction steps.
- The expected behavior and the actual behavior.
- Any known impact, such as arbitrary file write, path traversal, command execution, denial of service, or information disclosure.
- Suggested fixes or patches, if available.

Please do not publish exploit details, malicious archives, or proof-of-concept code publicly until the vulnerability has been reviewed and a fix or mitigation has been released.

## Scope

Security issues may include, but are not limited to:

- Archive extraction path traversal.
- Symlink or hardlink traversal during extraction.
- Arbitrary file overwrite outside the requested extraction directory.
- Unsafe handling of archive metadata.
- Unexpected command execution through external extractor tools.
- Denial of service caused by malformed or malicious archives.
- Information disclosure caused by unsafe file access.

General bugs, compatibility problems, feature requests, and documentation issues should be reported through regular GitHub issues instead.

## Response Process

After a private vulnerability report is received, the maintainer will try to:

1. Confirm receipt of the report.
2. Reproduce and assess the issue.
3. Determine the affected versions and severity.
4. Prepare a fix or mitigation.
5. Release an updated version when appropriate.
6. Publish a security advisory or public issue after users have had a reasonable opportunity to update.

Response times may vary depending on maintainer availability and the complexity of the issue.

## Disclosure Guidelines

Coordinated disclosure is appreciated.

Please allow reasonable time for investigation and remediation before publishing details. If you plan to disclose the issue publicly, please coordinate the timeline with the maintainer first.

## Safe Extraction Guidance

Applications using `rarfile` to process untrusted archives should extract files only into a dedicated temporary directory with limited permissions. Do not extract untrusted archives directly into sensitive directories, application source trees, user home directories, or system paths.

After extraction, applications should validate the resulting files before moving them to a final destination.
